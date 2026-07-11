import subprocess
import os
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from utils import logger, check_ffmpeg_available
from typing import Any

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

def draw_pill(draw, x0, y0, x1, y1, r, fill, outline=None, width=1):
    """Draw a capsule/pill shape."""
    draw.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=fill, outline=outline, width=width)

class SubtitleBurner:
    """Handles burning subtitles (SRT, ASS, or dynamic capsules) into video using FFmpeg subprocess."""
    def __init__(self, src_video: Path, subtitle_path: Path, output_video: Path, segments=None) -> None:
        self.src_video = Path(src_video)
        self.subtitle_path = Path(subtitle_path)
        self.output_video = Path(output_video)
        self.segments = segments

    def get_video_resolution(self) -> tuple[int, int]:
        """Fetch video stream width and height using ffprobe."""
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-select_streams", "v:0", str(self.src_video.resolve())
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            if result.stdout:
                data = json.loads(result.stdout)
                stream = data.get("streams", [{}])[0]
                w = int(stream.get("width", 1920))
                h = int(stream.get("height", 1080))
                return w, h
        except Exception as e:
            logger.warning(f"Failed to fetch resolution with ffprobe: {e}. Defaulting to 1920x1080.")
        return 1920, 1080

    def draw_dynamic_capsule(self, W: int, H: int, text: str, font_path: str, font_size: int) -> Image.Image:
        """
        Uses the provided subtitle_container.png from videos/ as the subtitle background container.
        Scales the background container to the video width W (maintaining aspect ratio),
        and renders the subtitle text over it in black.
        Falls back to mathematically rendering the capsule if the file is missing or errors out.
        """
        scale = H / 720.0  # Normalized scale factor
        
        try:
            font = ImageFont.truetype(font_path, int(font_size * scale * 0.95))
        except Exception:
            font = ImageFont.load_default()
            
        dummy = Image.new("RGBA", (1, 1))
        dummy_draw = ImageDraw.Draw(dummy)
        
        # Clean lines and wrap nicely (can allow up to 40 characters for wider template container)
        words = [word.strip() for word in text.split(" ") if word.strip()]
        wrapped_lines = []
        current_line = []
        current_length = 0
        for word in words:
            if current_length + len(word) > 40:
                if current_line:
                    wrapped_lines.append(" ".join(current_line))
                current_line = [word]
                current_length = len(word)
            else:
                current_line.append(word)
                current_length += len(word) + 1
        if current_line:
            wrapped_lines.append(" ".join(current_line))
            
        if not wrapped_lines:
            return Image.new("RGBA", (W, H), (0, 0, 0, 0))
            
        line_widths = [dummy_draw.textlength(line, font=font) for line in wrapped_lines]
        max_line_w = max(line_widths) if line_widths else 0
        
        line_height = int(font_size * scale * 1.3)
        total_text_h = len(wrapped_lines) * line_height
        
        # Load and scale subtitle_container.png
        container_path = Path(__file__).parent / "subtitle_container.png"
        if not container_path.exists():
            return self._draw_math_fallback(W, H, wrapped_lines, font, scale, line_height, total_text_h, max_line_w, font_size)
            
        try:
            with Image.open(container_path) as bg_img:
                # Aspect ratio is 3725 / 451
                bg_w = W
                bg_h = int(W * 451 / 3725)
                bg_img_scaled = bg_img.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
                
                # Create main frame
                canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                
                # Position container at the bottom center of the video
                bg_x = 0
                bg_y = H - bg_h
                canvas.paste(bg_img_scaled, (bg_x, bg_y), bg_img_scaled)
                
                # Center of the video is the text center
                text_area_cx = W // 2
                
                # Center text vertically inside the container
                container_cy = bg_y + bg_h // 2
                y_cursor = container_cy - total_text_h // 2
                
                draw = ImageDraw.Draw(canvas)
                for line in wrapped_lines:
                    line_w = draw.textlength(line, font=font)
                    x = text_area_cx - line_w // 2
                    
                    # Draw text in BLACK as requested
                    # Draw optional subtle white outline/highlight (1px) for readability
                    draw.text((x + 1, y_cursor + 1), line, font=font, fill=(255, 255, 255, 80)) # Subtle border shadow
                    draw.text((x, y_cursor), line, font=font, fill=(0, 0, 0, 255))
                    y_cursor += line_height
                
                return canvas
        except Exception as e:
            logger.error(f"Error rendering with subtitle_container.png: {e}. Falling back to default canvas.")
            return self._draw_math_fallback(W, H, wrapped_lines, font, scale, line_height, total_text_h, max_line_w, font_size)

    def _draw_math_fallback(
        self, W: int, H: int, wrapped_lines: list, font: Any, scale: float, 
        line_height: int, total_text_h: int, max_line_w: float, font_size: int
    ) -> Image.Image:
        """Original mathematical glassmorphic rendering fallback method."""
        # Determine capsule height dynamically
        box_h = int(total_text_h + 36 * scale)
        min_box_h = int(68 * scale)
        if box_h < min_box_h:
            box_h = min_box_h
            
        sub_r = box_h // 2
        
        # Space layout constraints
        logo_space = 1.0 * box_h
        pill_space = 1.1 * box_h
        text_padding_h = 30 * scale
        
        # Dynamic box width wrapping the content
        box_w = int(max_line_w + logo_space + pill_space + text_padding_h)
        
        # Position box near the bottom center
        box_x0 = (W - box_w) // 2
        box_y0 = int(H - box_h - H * 0.08) # 8% from screen bottom
        box_x1 = box_x0 + box_w
        box_y1 = box_y0 + box_h
        
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        
        # 1. Soft Drop Shadow
        shadow_offset_y = int(4 * scale)
        shadow_blur_radius = int(5 * scale)
        shadow_canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_canvas)
        shadow_draw.rounded_rectangle(
            [box_x0 - 2 * scale, box_y0 + shadow_offset_y - 2 * scale, 
             box_x1 + 2 * scale, box_y1 + shadow_offset_y + 2 * scale],
            radius=sub_r,
            fill=(0, 0, 0, 80)
        )
        shadow_blurred = shadow_canvas.filter(ImageFilter.GaussianBlur(shadow_blur_radius))
        canvas.alpha_composite(shadow_blurred)
        
        # 2. Transparent Frosted Glass Mask (Pill shape)
        mask = Image.new("L", (W, H), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([box_x0, box_y0, box_x1, box_y1], radius=sub_r, fill=255)
        
        # Cutout circle placeholder (logo area)
        circle_cx = box_x0 + 0.5 * box_h
        circle_cy = box_y0 + 0.5 * box_h
        circle_r = 0.28 * box_h
        mask_draw.ellipse(
            [circle_cx - circle_r, circle_cy - circle_r, circle_cx + circle_r, circle_cy + circle_r],
            fill=0
        )
        
        glass_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        glass_content = Image.new("RGBA", (W, H), (255, 255, 255, 45)) # 20% opacity white fill (around 45 alpha)
        glass_layer.paste(glass_content, (0, 0), mask=mask)
        
        # 3. Reflections / highlights
        glass_draw = ImageDraw.Draw(glass_layer)
        highlight_offset = int(2 * scale)
        glass_draw.rounded_rectangle(
            [box_x0 + highlight_offset, box_y0 + highlight_offset, 
             box_x1 - highlight_offset, box_y0 + highlight_offset + int(4 * scale)],
            radius=sub_r - highlight_offset,
            fill=(255, 255, 255, 80)
        )
        
        # Logo circular border outline
        glass_draw.ellipse(
            [circle_cx - circle_r, circle_cy - circle_r, circle_cx + circle_r, circle_cy + circle_r],
            outline=(255, 255, 255, 120),
            width=int(2 * scale)
        )
        
        # Light white container border outline (1px scaled)
        glass_draw.rounded_rectangle(
            [box_x0, box_y0, box_x1, box_y1],
            radius=sub_r,
            outline=(255, 255, 255, 100),
            width=int(1 * scale)
        )
        
        # Bottom-right category tag pill
        pill_w = int(0.75 * box_h)
        pill_h = int(0.18 * box_h)
        pill_x0 = box_x1 - pill_w - int(0.3 * box_h)
        pill_y0 = box_y1 - pill_h - int(0.15 * box_h)
        pill_x1 = pill_x0 + pill_w
        pill_y1 = pill_y0 + pill_h
        draw_pill_r = pill_h // 2
        
        glass_draw.rounded_rectangle(
            [pill_x0, pill_y0, pill_x1, pill_y1],
            radius=draw_pill_r,
            fill=(255, 255, 255, 230),
            outline=(255, 255, 255, 255),
            width=1
        )
        
        canvas.alpha_composite(glass_layer)
        
        # 4. Render Centered Text inside the middle text area
        text_area_cx = box_x0 + (logo_space + (box_w - pill_space)) // 2
        draw = ImageDraw.Draw(canvas)
        y_cursor = box_y0 + (box_h - total_text_h) // 2
        for line in wrapped_lines:
            w = draw.textlength(line, font=font)
            x = text_area_cx - w // 2
            # Text Drop Shadow for readability
            draw.text((x + 1, y_cursor + 1), line, font=font, fill=(0, 0, 0, 180))
            # Text White primary
            draw.text((x, y_cursor), line, font=font, fill=(255, 255, 255, 255))
            y_cursor += line_height
            
        return canvas

    def burn(self) -> Path:
        """Runs FFmpeg to burn subtitles using dynamic glassmorphism capsule overlays."""
        check_ffmpeg_available()

        if not self.src_video.exists():
            raise FileNotFoundError(f"Source video not found: {self.src_video}")

        temp_dir = Path("temp")
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Resolve Font Configuration
        font_name = os.getenv("SUB_FONT_NAME", "Arial")
        try:
            font_size = int(os.getenv("SUB_FONT_SIZE", "24"))
        except ValueError:
            font_size = 24
            
        font_path = "arial.ttf"
        font_name_lower = font_name.lower().strip()
        windir = os.environ.get("WINDIR", "C:\\Windows")
        fonts_dir = Path(windir) / "Fonts"
        if fonts_dir.exists():
            font_maps = {
                "arial": "arial.ttf",
                "arial bold": "arialbd.ttf",
                "times new roman": "times.ttf",
                "courier new": "cour.ttf",
                "consolas": "consola.ttf",
                "calibri": "calibri.ttf",
                "segoe ui": "segoeui.ttf",
                "tahoma": "tahoma.ttf",
                "verdana": "verdana.ttf"
            }
            mapped_file = font_maps.get(font_name_lower, f"{font_name_lower}.ttf")
            search_path = fonts_dir / mapped_file
            if search_path.exists():
                font_path = str(search_path.resolve())
            else:
                for p in fonts_dir.glob("*.ttf"):
                    if font_name_lower in p.name.lower():
                        font_path = str(p.resolve())
                        break

        # 2. Get Video Stream Resolution
        W, H = self.get_video_resolution()
        
        # 3. Generate dynamic subtitle overlay frames if segments exist
        active_overlays = []
        if self.segments:
            logger.info(f"Rendering {len(self.segments)} dynamic capsule subtitle overlays ({W}x{H})...")
            for idx, seg in enumerate(self.segments):
                text = seg.translated_text if seg.translated_text else seg.text
                if not text.strip():
                    continue
                    
                img_path = temp_dir / f"overlay_sub_{idx}.png"
                img = self.draw_dynamic_capsule(W, H, text, font_path, font_size)
                if img:
                    img.save(img_path, "PNG")
                    active_overlays.append({
                        "path": img_path,
                        "start": seg.start,
                        "end": seg.end
                    })

        # 4. If dynamic overlays are empty or not active, fall back to standard text rendering
        if not active_overlays:
            logger.info("No active segments to dynamically render. Falling back to standard subtitle filter...")
            fmt_sub_path = escape_path_for_ffmpeg(self.subtitle_path)
            ext = self.subtitle_path.suffix.lower()
            if ext == ".ass":
                vf_filter = f"ass={fmt_sub_path}"
            elif ext == ".srt":
                vf_filter = f"subtitles={fmt_sub_path}"
            else:
                raise ValueError(f"Unsupported subtitle format for burning: {ext}")
                
            cmd_copy_audio = [
                "ffmpeg", "-y",
                "-i", str(self.src_video.resolve()),
                "-vf", vf_filter,
                "-c:v", "libx264", "-c:a", "copy",
                str(self.output_video.resolve())
            ]
            filter_script_path = None
        else:
            # Create a FFmpeg filter complex string defining overlay segments inline
            filters = []
            last_label = "[0:v]"
            for idx, item in enumerate(active_overlays):
                next_label = f"[v{idx}]" if idx < len(active_overlays) - 1 else "[out]"
                start_val = f"{item['start']:.3f}"
                end_val = f"{item['end']:.3f}"
                filters.append(
                    f"{last_label}[{idx+1}:v]overlay=x=0:y=0:enable='between(t,{start_val},{end_val})'{next_label}"
                )
                last_label = next_label
                
            filter_complex_str = ";".join(filters)
                
            # Build FFmpeg command with -filter_complex instead of -filter_complex_script
            cmd_copy_audio = [
                "ffmpeg", "-y",
                "-i", str(self.src_video.resolve())
            ]
            for item in active_overlays:
                cmd_copy_audio.extend(["-i", str(item["path"].resolve())])
                
            cmd_copy_audio.extend([
                "-filter_complex", filter_complex_str,
                "-map", "[out]",
                "-map", "0:a?",
                "-c:v", "libx264", "-c:a", "copy",
                str(self.output_video.resolve())
            ])
            logger.info("Burning dynamic glassmorphism subtitle overlay sequence...")

        logger.debug(f"Running FFmpeg: {' '.join(cmd_copy_audio)}")

        try:
            result = subprocess.run(
                cmd_copy_audio,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            # Fallback to transcoding audio if copy fails
            if result.returncode != 0:
                logger.warning("Failed to burn video with stream copy audio. Trying with AAC transcode fallback...")
                
                if not active_overlays:
                    cmd_aac_audio = [
                        "ffmpeg", "-y",
                        "-i", str(self.src_video.resolve()),
                        "-vf", vf_filter,
                        "-c:v", "libx264", "-c:a", "aac",
                        str(self.output_video.resolve())
                    ]
                else:
                    cmd_aac_audio = [
                        "ffmpeg", "-y",
                        "-i", str(self.src_video.resolve())
                    ]
                    for item in active_overlays:
                        cmd_aac_audio.extend(["-i", str(item["path"].resolve())])
                    cmd_aac_audio.extend([
                        "-filter_complex", filter_complex_str,
                        "-map", "[out]",
                        "-map", "0:a?",
                        "-c:v", "libx264", "-c:a", "aac",
                        str(self.output_video.resolve())
                    ])
                
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
                    logger.error(f"FFmpeg burning failed: {err_msg}")
                    raise RuntimeError(f"FFmpeg burning failed with exit code {fallback_result.returncode}.")
            
            # Clean up generated overlay files
            if active_overlays:
                for item in active_overlays:
                    if item["path"].exists():
                        try:
                            item["path"].unlink()
                        except Exception:
                            pass
                        
            logger.info("Successfully burned subtitles into final video.")
            return self.output_video
            
        except Exception as e:
            if not isinstance(e, (RuntimeError, FileNotFoundError, ValueError)):
                raise RuntimeError(f"Unexpected error when burning subtitles: {str(e)}") from e
            raise
