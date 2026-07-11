import json
from pathlib import Path
from typing import List, Dict, Any
from utils import logger, SubtitleSegment

def format_time_srt(seconds: float) -> str:
    """Format seconds into SRT timestamp format: HH:MM:SS,mmm"""
    if seconds < 0:
        seconds = 0.0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msecs = int(round((seconds - int(seconds)) * 1000))
    # Handle rounding overflows
    if msecs >= 1000:
        msecs -= 1000
        secs += 1
    if secs >= 60:
        secs -= 60
        minutes += 1
    if minutes >= 60:
        minutes -= 60
        hours += 1
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{msecs:03d}"

def format_time_ass(seconds: float) -> str:
    """Format seconds into ASS timestamp format: H:MM:SS.cs"""
    if seconds < 0:
        seconds = 0.0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    csecs = int(round((seconds - int(seconds)) * 100))
    # Handle rounding overflows
    if csecs >= 100:
        csecs -= 100
        secs += 1
    if secs >= 60:
        secs -= 60
        minutes += 1
    if minutes >= 60:
        minutes -= 60
        hours += 1
    return f"{hours:01d}:{minutes:02d}:{secs:02d}.{csecs:02d}"

def convert_hex_to_ass_color(hex_str: str) -> str:
    """
    Converts standard RGB/RGBA Hex color to ASS format: &HAABBGGRR.
    Handles inputs like: '#FFFFFF', '#FF000080', 'FFFFFF', '&H00FFFFFF'
    """
    hex_str = hex_str.strip()
    if hex_str.startswith("&H"):
        return hex_str  # Already in ASS format
    
    if hex_str.startswith("#"):
        hex_str = hex_str[1:]
        
    alpha = "00"
    if len(hex_str) == 8:
        # RGBA
        r, g, b, a = hex_str[0:2], hex_str[2:4], hex_str[4:6], hex_str[6:8]
        # ASS Alpha is opacity inverted (00 is opaque, FF is transparent)
        # So we can calculate alpha_val = 255 - hex(a) or simply map it. 
        # For simplicity, we invert user's alpha, or just copy it
        # Opacity inversion mapping for ASS format
        try:
            a_val = 255 - int(a, 16)
            alpha = f"{a_val:02X}"
        except ValueError:
            alpha = "00"
    elif len(hex_str) == 6:
        # RGB
        r, g, b = hex_str[0:2], hex_str[2:4], hex_str[4:6]
    else:
        # Fallback default (white)
        logger.warning(f"Unrecognized color string format: {hex_str}. Using solid white.")
        return "&H00FFFFFF"

    # ASS represents colors in Blue-Green-Red order
    return f"&H{alpha}{b}{g}{r}"

def generate_srt(segments: List[SubtitleSegment], output_path: Path, use_translation: bool = True) -> None:
    """Generates a standard UTF-8 encoded SRT file."""
    logger.info(f"Generating SRT subtitle: {output_path}")
    lines = []
    for idx, seg in enumerate(segments, 1):
        text = seg.translated_text if use_translation else seg.text
        # Fallback to original text if translation is empty
        if not text.strip():
            text = seg.text
            
        start_t = format_time_srt(seg.start)
        end_t = format_time_srt(seg.end)
        
        lines.append(f"{idx}")
        lines.append(f"{start_t} --> {end_t}")
        lines.append(f"{text}\n")
        
    # Join with newlines
    content = "\n".join(lines)
    
    # Save file with UTF-8
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.debug("SRT file written successfully.")

def generate_ass(
    segments: List[SubtitleSegment],
    output_path: Path,
    use_translation: bool = True,
    style_conf: Dict[str, Any] = None
) -> None:
    """
    Generates a stylized ASS (Advanced SubStation Alpha) subtitle file.
    Standard resolution 1920x1080, custom font, sizing, border styling.
    """
    logger.info(f"Generating ASS subtitle: {output_path}")
    
    # Default styling options (override with environment settings if specified)
    default_styles = {
        "font_name": "Arial",
        "font_size": 24,
        "primary_color": "#000000",      # Visible solid target color (black)
        "secondary_color": "#00FFFF",    # Karaoke/secondary color (cyan)
        "outline_color": "#FFFFFF",      # Outline (white)
        "back_color": "#00000080",       # Back shadow (translucent black)
        "bold": 1,                       # 1 standard bold, 0 normal
        "italic": 0,                     # 1 italic, 0 normal
        "border_style": 1,               # 1: Outline + shadow, 3: Opaque box
        "outline": 2.0,                  # Outline thickness
        "shadow": 1.0,                   # Shadow depth
        "alignment": 2                   # 2 = Bottom Center
    }
    
    if style_conf:
        for k, v in style_conf.items():
            if v is not None and v != "":
                default_styles[k] = v

    primary = convert_hex_to_ass_color(str(default_styles["primary_color"]))
    secondary = convert_hex_to_ass_color(str(default_styles["secondary_color"]))
    outline_c = convert_hex_to_ass_color(str(default_styles["outline_color"]))
    back_c = convert_hex_to_ass_color(str(default_styles["back_color"]))
    
    # Configure dynamic margins to fit inside glassmorphic subtitle container
    margin_l = default_styles.get("margin_l", 10)
    margin_r = default_styles.get("margin_r", 10)
    margin_v = default_styles.get("margin_v", 12)
    
    container_path = Path(__file__).parent / "subtitle_container.png"
    if container_path.exists():
        # Adjust margins to center inside capsule safely: 
        # MarginL=160 to avoid left logo placeholder
        # MarginR=160 to avoid right category pill
        # MarginV=65 to center text vertically inside the glass box
        if "margin_l" not in default_styles:
            margin_l = 160
        if "margin_r" not in default_styles:
            margin_r = 160
        if "margin_v" not in default_styles:
            margin_v = 65
    
    # Create the ASS file content
    ass_template = f"""[Script Info]
Title: Translated Video Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{default_styles['font_name']},{default_styles['font_size']},{primary},{secondary},{outline_c},{back_c},{default_styles['bold']},{default_styles['italic']},0,0,100,100,0,0,{default_styles['border_style']},{default_styles['outline']},{default_styles['shadow']},{default_styles['alignment']},{margin_l},{margin_r},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    dialogue_lines = []
    for seg in segments:
        text = seg.translated_text if use_translation else seg.text
        if not text.strip():
            text = seg.text
            
        # Strip potential manual newlines and clean up
        clean_text = text.replace("\n", " ").strip()
        
        start_t = format_time_ass(seg.start)
        end_t = format_time_ass(seg.end)
        
        dialogue_lines.append(
            f"Dialogue: 0,{start_t},{end_t},Default,,0,0,0,,{clean_text}"
        )
        
    full_content = ass_template + "\n".join(dialogue_lines) + "\n"
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_content)
    logger.debug("ASS file written successfully.")

def generate_transcript_json(segments: List[SubtitleSegment], output_path: Path) -> None:
    """Generates a transcript.json file containing both original and translated text side-by-side."""
    logger.info(f"Generating transcript JSON file: {output_path}")
    data = [seg.to_dict() for seg in segments]
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logger.debug("Transcript JSON file written successfully.")
    except Exception as e:
        logger.warning(f"Could not generate transcript JSON file: {e}")
