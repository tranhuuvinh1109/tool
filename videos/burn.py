import subprocess
from pathlib import Path
from utils import logger, check_ffmpeg_available

def escape_path_for_ffmpeg(p: Path) -> str:
    """
    Escapes a path string for use inside FFmpeg's vf filter arguments.
    Prefers relative paths to prevent colon/backslash issues on Windows, 
    and handles spaces by wrapping in single-quotes.
    """
    # 1. Resolve to get clean absolute slash-delimited paths
    abs_p = p.resolve().as_posix()
    abs_cwd = Path.cwd().resolve().as_posix()
    
    # Check if p is inside current working directory (case-insensitively for Windows drive letters)
    if abs_p.lower().startswith(abs_cwd.lower()):
        # Extract relative path portion
        rel_part = abs_p[len(abs_cwd):].lstrip("/")
        # Escape any single quotes inside the path for FFmpeg filter parameter string mapping
        escaped_rel = rel_part.replace("'", "'\\''")
        return f"'{escaped_rel}'"
        
    # 2. Fallback to absolute path with escaped colons and quotes
    escaped_abs = abs_p.replace(":", "\\:").replace("'", "'\\''")
    return f"'{escaped_abs}'"


class SubtitleBurner:
    """Handles burning subtitles (SRT or ASS) into video using FFmpeg subprocess."""
    def __init__(self, src_video: Path, subtitle_path: Path, output_video: Path) -> None:
        self.src_video = Path(src_video)
        self.subtitle_path = Path(subtitle_path)
        self.output_video = Path(output_video)

    def burn(self) -> Path:
        """
        Runs FFmpeg to burn subtitles into the destination video.
        Uses relative paths where possible to avoid Windows drive escaping issues.
        """
        # Step 0: Ensure FFmpeg is available
        check_ffmpeg_available()

        # Step 1: Validate file existence
        if not self.src_video.exists():
            raise FileNotFoundError(f"Source video not found: {self.src_video}")
        if not self.subtitle_path.exists():
            raise FileNotFoundError(f"Subtitle file not found: {self.subtitle_path}")

        # Step 2: Check for optional custom glassmorphic container overlay
        container_path = Path(__file__).parent / "subtitle_container.png"
        use_container = container_path.exists()
        
        fmt_sub_path = escape_path_for_ffmpeg(self.subtitle_path)
        ext = self.subtitle_path.suffix.lower()
        if ext not in [".ass", ".srt"]:
            raise ValueError(f"Unsupported subtitle format for burning: {ext}")
            
        if use_container:
            logger.info(f"Custom subtitle container found: {container_path.name}")
            sub_filter = f"ass={fmt_sub_path}" if ext == ".ass" else f"subtitles={fmt_sub_path}"
            # Scale background container relative to video width (88% width) and overlay bottom center
            filter_complex = (
                f"[1:v]scale=w='iw*0.88':h=-1[container];"
                f"[0:v][container]overlay=x='(main_w-overlay_w)/2':y='main_h-overlay_h-main_h*0.05'[bg];"
                f"[bg]{sub_filter}[out]"
            )
            cmd_copy_audio = [
                "ffmpeg",
                "-y",
                "-i", str(self.src_video.resolve()),
                "-i", str(container_path.resolve()),
                "-filter_complex", filter_complex,
                "-map", "[out]",
                "-map", "0:a?",
                "-c:v", "libx264",
                "-c:a", "copy",
                str(self.output_video.resolve())
            ]
        else:
            vf_filter = f"ass={fmt_sub_path}" if ext == ".ass" else f"subtitles={fmt_sub_path}"
            logger.info(f"Burning subtitles using filter: {vf_filter}")
            cmd_copy_audio = [
                "ffmpeg",
                "-y",
                "-i", str(self.src_video.resolve()),
                "-vf", vf_filter,
                "-c:v", "libx264",
                "-c:a", "copy",
                str(self.output_video.resolve())
            ]

        logger.debug(f"Running FFmpeg: {' '.join(cmd_copy_audio)}")

        try:
            # Try to copy audio stream (fastest & lossless)
            result = subprocess.run(
                cmd_copy_audio,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            # If copying audio fails (e.g. because input audio codec isn't supported in target container)
            if result.returncode != 0:
                logger.warning("Failed to burn video with stream copy audio. Trying with AAC transcode fallback...")
                
                if use_container:
                    cmd_aac_audio = [
                        "ffmpeg",
                        "-y",
                        "-i", str(self.src_video.resolve()),
                        "-i", str(container_path.resolve()),
                        "-filter_complex", filter_complex,
                        "-map", "[out]",
                        "-map", "0:a?",
                        "-c:v", "libx264",
                        "-c:a", "aac",
                        str(self.output_video.resolve())
                    ]
                else:
                    cmd_aac_audio = [
                        "ffmpeg",
                        "-y",
                        "-i", str(self.src_video.resolve()),
                        "-vf", vf_filter,
                        "-c:v", "libx264",
                        "-c:a", "aac",  # Transcode to AAC (safe/compatible)
                        str(self.output_video.resolve())
                    ]
                
                logger.debug(f"Running Fallback FFmpeg: {' '.join(cmd_aac_audio)}")
                fallback_result = subprocess.run(
                    cmd_aac_audio,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if fallback_result.returncode != 0:
                    err_msg = fallback_result.stderr or fallback_result.stdout
                    logger.error(f"FFmpeg burning failed (transcode fallback): {err_msg}")
                    raise RuntimeError(
                        f"FFmpeg burning failed with exit code {fallback_result.returncode}. "
                        f"Logs: {err_msg}"
                    )
            
            logger.info("Successfully burned subtitles into final video.")
            return self.output_video
            
        except Exception as e:
            if not isinstance(e, (RuntimeError, FileNotFoundError, ValueError)):
                raise RuntimeError(f"Unexpected error when burning subtitles: {str(e)}") from e
            raise
