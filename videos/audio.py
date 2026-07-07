import subprocess
from pathlib import Path
from utils import logger, check_ffmpeg_available

class AudioExtractor:
    """Handles professional extraction of audio from source video using FFmpeg."""
    def __init__(self, src_path: Path, temp_dir: Path) -> None:
        self.src_path = Path(src_path)
        self.temp_dir = Path(temp_dir)
        self.output_wav = self.temp_dir / "audio.wav"

    def extract(self) -> Path:
        """
        Extracts mono channel, 16kHz WAV audio from the video file.
        Returns the path to the extracted WAV file.
        """
        # Step 0: Ensure FFmpeg is available
        check_ffmpeg_available()

        # Step 1: Validate input video path
        if not self.src_path.exists():
            raise FileNotFoundError(f"Source video file not found: {self.src_path}")
        if not self.src_path.is_file():
            raise ValueError(f"Source path is not a file: {self.src_path}")

        # Step 2: Ensure temp directory exists
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Step 3: Define ffmpeg arguments
        # -y: overwrite output
        # -i: input file
        # -vn: skip video extraction
        # -ac 1: mono channel
        # -ar 16000: 16kHz sampling rate
        # -acodec pcm_s16le: 16-bit PCM WAV
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(self.src_path.resolve()),
            "-vn",
            "-ac", "1",
            "-ar", "16000",
            "-acodec", "pcm_s16le",
            str(self.output_wav.resolve())
        ]

        logger.debug(f"Executing FFmpeg command: {' '.join(cmd)}")

        # Step 4: Execute command and capture exceptions
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            if result.returncode != 0:
                # Log the ffmpeg error and raise Exception
                error_msg = result.stderr or result.stdout
                logger.error(f"FFmpeg audio extraction failed: {error_msg}")
                raise RuntimeError(
                    f"FFmpeg failed with exit code {result.returncode}. "
                    "Make sure the input file is a valid video format and is not corrupted."
                )
        except Exception as e:
            if not isinstance(e, (RuntimeError, FileNotFoundError, ValueError)):
                raise RuntimeError(f"Unexpected error while extracting audio: {str(e)}") from e
            raise

        logger.debug(f"Successfully extracted audio to: {self.output_wav}")
        return self.output_wav
