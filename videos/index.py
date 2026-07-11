import os
import sys
import warnings

# Suppress Hugging Face symlink warnings on Windows and general UserWarnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
warnings.filterwarnings("ignore", category=UserWarning)

import argparse
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Import our custom modules
from utils import logger, SubtitleSegment, StageTimer, CheckpointManager, check_ffmpeg_available
from audio import AudioExtractor
from whisper_engine import WhisperEngine
from translator import get_translator
from subtitle import generate_srt, generate_ass, generate_transcript_json
from burn import SubtitleBurner

# Load configuration from .env
load_dotenv()

def parse_args() -> argparse.Namespace:
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(
        description="Auto Video Translator - Translate audio into Vietnamese subtitles and burn them into the video."
    )
    # Source options (supports files, folders, and wildcards)
    parser.add_argument(
        "--src", "-s",
        type=str,
        required=True,
        help="Input video file path, folder path, or wildcard pattern (e.g., 'videos/*.mp4')"
    )
    # Output options
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output video file path or folder path. If batch processing, this is treated as an output folder."
    )
    # Whisper engine configurations
    parser.add_argument(
        "--model",
        type=str,
        default="large-v3",
        help="Whisper model size (default: large-v3)"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda",
        help="Compute device: 'cuda', 'cpu', or 'auto' (default: cuda with auto fallback to cpu)"
    )
    parser.add_argument(
        "--compute",
        type=str,
        default="float16",
        help="Compute type: 'float16', 'int8', 'float32' (default: float16)"
    )
    parser.add_argument(
        "--language",
        type=str,
        default="auto",
        help="Source audio language (default: auto language detection)"
    )
    
    # Subtitle styling configuration
    parser.add_argument(
        "--sub-format",
        type=str,
        choices=["srt", "ass"],
        default="srt",
        help="Subtitles format: 'srt' or 'ass' (default: srt)"
    )
    
    # Translation configurations
    parser.add_argument(
        "--translator",
        type=str,
        choices=["gemini", "google"],
        default="gemini",
        help="Translation agent to use (default: gemini)"
    )
    
    # Execution options
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Automatically overwrite existing output file"
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Do not delete intermediate temporary assets inside temp/ folder"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume processing if matching checkpoint in temp/ exists"
    )
    return parser.parse_args()

def glob_source_files(src_pattern: str) -> List[Path]:
    """Finds all input files matching the src folder, file, or wildcard pattern."""
    src_path = Path(src_pattern)
    
    # CASE 1: Exact directory match
    if src_path.is_dir():
        # Get all common video formats
        video_extensions = ["*.mp4", "*.mkv", "*.avi", "*.mov", "*.webm"]
        files = []
        for ext in video_extensions:
            files.extend(list(src_path.glob(ext)))
        return sorted(files)
        
    # CASE 2: Wildcard or glob pattern
    parent_dir = src_path.parent
    if not parent_dir.exists():
        parent_dir = Path(".")
    
    pattern = src_path.name
    files = list(parent_dir.glob(pattern))
    if files:
        return sorted(files)
        
    # CASE 3: Single file match
    if src_path.exists() and src_path.is_file():
        return [src_path]
        
    return []

def get_ass_styles_from_env() -> Dict[str, Any]:
    """Retrieves ASS subtitle configuration styles from environmental variables."""
    styles = {}
    mappings = {
        "SUB_FONT_NAME": "font_name",
        "SUB_FONT_SIZE": "font_size",
        "SUB_PRIMARY_COLOR": "primary_color",
        "SUB_SECONDARY_COLOR": "secondary_color",
        "SUB_OUTLINE_COLOR": "outline_color",
        "SUB_BACK_COLOR": "back_color",
        "SUB_BOLD": "bold",
        "SUB_ITALIC": "italic",
        "SUB_BORDER_STYLE": "border_style",
        "SUB_OUTLINE": "outline",
        "SUB_SHADOW": "shadow",
        "SUB_ALIGNMENT": "alignment",
        "SUB_MARGIN_V": "margin_v"
    }
    
    for env_var, key in mappings.items():
        val = os.getenv(env_var)
        if val is not None:
            if key in ["font_size", "bold", "italic", "border_style", "alignment", "margin_v"]:
                try:
                    styles[key] = int(val)
                except ValueError:
                    pass
            elif key in ["outline", "shadow"]:
                try:
                    styles[key] = float(val)
                except ValueError:
                    pass
            else:
                styles[key] = val
    return styles

def process_video(
    src_video: Path,
    output_video: Path,
    args: argparse.Namespace,
    temp_dir: Path
) -> None:
    """Processes a single video: extracts, transcribes, translates, generates, and burns subtitles."""
    prefix = src_video.stem
    
    # Define file names/paths for intermediate outputs to prevent collisions during batch
    audio_path = temp_dir / f"{prefix}_audio.wav"
    orig_transcript_path = temp_dir / f"{prefix}_transcript_original.json"
    translated_transcript_path = temp_dir / f"{prefix}_transcript.json"
    sub_path = temp_dir / f"{prefix}_subtitle.{args.sub_format}"
    
    # Initialize checkpoint manager
    checkpoint_mgr = CheckpointManager(temp_dir, src_video, output_video)
    checkpoint = checkpoint_mgr.load_checkpoint() if args.resume else None
    
    segments: List[SubtitleSegment] = []
    
    logger.info("=" * 60)
    logger.info(f"Processing Video: {src_video.name}")
    logger.info(f"Output Target: {output_video.resolve()}")
    logger.info("=" * 60)

    # ----------------- Step 1: Extract Audio -----------------
    if checkpoint and checkpoint.get("stage_completed") in ["audio", "transcribe", "translate", "burn"]:
        logger.info("[RESUME] Skipping audio extraction, using cached media...")
    else:
        with StageTimer("Extracting audio", 0):
            extractor = AudioExtractor(src_video, temp_dir)
            # Override generated output path name mapping
            extractor.output_wav = audio_path
            extractor.extract()
        checkpoint_mgr.save_checkpoint("audio", {"audio_path": str(audio_path.resolve())})

    # ----------------- Step 2: Speech Recognition -----------------
    if checkpoint and checkpoint.get("stage_completed") in ["transcribe", "translate", "burn"]:
        logger.info("[RESUME] Skipping Speech-to-Text transcription, loading cached JSON transcript...")
        try:
            with open(orig_transcript_path, "r", encoding="utf-8") as f:
                raw_segments = json.load(f)
            segments = [SubtitleSegment.from_dict(item) for item in raw_segments]
        except Exception as e:
            logger.error(f"Failed to load cached original transcript: {e}. Re-transcribing...")
            checkpoint = None  # Invalidate checkpoint

    if not segments:
        with StageTimer("Loading Whisper & Transcribing", 16):
            engine = WhisperEngine(
                model_size=args.model,
                device=args.device,
                compute_type=args.compute,
                language=args.language
            )
            segments = engine.transcribe(audio_path, temp_dir)
            # Rename the default generated original transcript to our prefixed name
            default_orig = temp_dir / "transcript_original.json"
            if default_orig.exists():
                if orig_transcript_path.exists():
                    orig_transcript_path.unlink()
                default_orig.rename(orig_transcript_path)
                
        checkpoint_mgr.save_checkpoint("transcribe", {"orig_transcript_path": str(orig_transcript_path.resolve())})

    if not segments:
        logger.warning(f"No speech detected in '{src_video.name}'. Subtitles will be empty.")
        # Proceed with empty segments or abort
        
    # ----------------- Step 3: Translate -----------------
    # Check if translation is already cached
    has_translation = False
    if checkpoint and checkpoint.get("stage_completed") in ["translate", "burn"]:
        logger.info("[RESUME] Skipping Translation, loading cached translations...")
        try:
            with open(translated_transcript_path, "r", encoding="utf-8") as f:
                raw_segments = json.load(f)
            segments = [SubtitleSegment.from_dict(item) for item in raw_segments]
            has_translation = True
        except Exception as e:
            logger.error(f"Failed to load cached translation: {e}. Re-translating...")
            
    if not has_translation and segments:
        with StageTimer("Translating", 33):
            translator = get_translator(args.translator)
            segments = translator.translate(segments)
            
            # Save translated transcript JSON
            generate_transcript_json(segments, translated_transcript_path)
            
        checkpoint_mgr.save_checkpoint("translate", {"translated_transcript_path": str(translated_transcript_path.resolve())})

    # ----------------- Step 4: Generate Subtitle -----------------
    with StageTimer("Generating subtitles", 50):
        if args.sub_format == "srt":
            generate_srt(segments, sub_path, use_translation=True)
        else:
            style_settings = get_ass_styles_from_env()
            generate_ass(segments, sub_path, use_translation=True, style_conf=style_settings)

    # ----------------- Step 5: Burn Subtitles -----------------
    with StageTimer("Burning subtitles", 66):
        burner = SubtitleBurner(src_video, sub_path, output_video, segments=segments)
        burner.burn()
        
    checkpoint_mgr.save_checkpoint("burn", {"output_video": str(output_video.resolve())})
    
    # ----------------- Step 6: Clean up -----------------
    logger.info("Step: Cleaning up... 83%")
    if not args.no_cleanup:
        for temp_file in [audio_path, orig_transcript_path, translated_transcript_path, sub_path]:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception as e:
                    logger.debug(f"Failed to delete temp file '{temp_file}': {e}")
        checkpoint_mgr.clear()
        
    logger.info("Step: Done... 100%")


def main() -> None:
    args = parse_args()
    
    start_all = time.perf_counter()
    
    # Verify FFmpeg is setup
    try:
        check_ffmpeg_available()
    except RuntimeError as e:
        logger.error(f"FFmpeg system validation failed: {e}")
        sys.exit(1)
        
    # Resolve source files
    src_files = glob_source_files(args.src)
    if not src_files:
        logger.error(
            f"Error: Invalid video path or no matching files found for input pattern: '{args.src}'. "
            "Please check if the filepath or pattern is correct."
        )
        sys.exit(1)
        
    logger.info(f"Targeting {len(src_files)} video file(s) for processing.")

    # Prepare temp directory
    temp_dir = Path("temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Prepare output path
    out_arg = args.output
    
    # Default output directory is the root 'output' folder
    root_output_dir = Path(__file__).parent.parent / "output"
    root_output_dir.mkdir(parents=True, exist_ok=True)
    
    # If processing multiple files, output argument MUST be a folder
    is_batch = len(src_files) > 1
    out_dir: Optional[Path] = None
    
    if is_batch:
        if out_arg:
            out_dir = Path(out_arg)
            out_dir.mkdir(parents=True, exist_ok=True)
        else:
            out_dir = root_output_dir
            logger.info(f"No output location provided. Saving translates inside: '{out_dir}/'")
    else:
        # Single file processing
        single_src = src_files[0]
        if out_arg:
            single_out = Path(out_arg)
            if single_out.is_dir():
                # If output is a directory, place output file inside it
                output_file = single_out / f"{single_src.stem}_vi{single_src.suffix}"
            else:
                output_file = single_out
        else:
            # Default output: save in the root output folder
            output_file = root_output_dir / f"{single_src.stem}_vi{single_src.suffix}"

    processed_count = 0
    failed_count = 0
    
    for idx, video in enumerate(src_files, 1):
        if is_batch:
            # Treat out_dir as output directory
            current_output = out_dir / f"{video.stem}_vi{video.suffix}"
        else:
            current_output = output_file
            
        # Error handling: Check if output already exists (and not overwriting)
        if current_output.exists() and not args.overwrite and not args.resume:
            logger.error(
                f"Error: Output file already exists: '{current_output}'. "
                "Use the '--overwrite' flag to permit replacement, or specify a new output name/path."
            )
            failed_count += 1
            continue

        try:
            process_video(video, current_output, args, temp_dir)
            processed_count += 1
        except Exception as e:
            logger.exception(f"Critical error processing video '{video.name}': {e}")
            failed_count += 1
            
    # Final cleanup of temp directory if empty and requested
    if not args.no_cleanup and temp_dir.exists():
        try:
            # Check if temp directory is empty
            if not any(temp_dir.iterdir()):
                temp_dir.rmdir()
                logger.debug("Cleaned up empty temp directory.")
        except Exception as e:
            logger.debug(f"Failed to delete temp dir: {e}")

    total_time = time.perf_counter() - start_all
    logger.info("=" * 60)
    logger.info(f"Execution complete. Total elapsed time: {total_time:.2f}s")
    logger.info(f"Processed: {processed_count} | Failed: {failed_count}")
    logger.info("=" * 60)
    
    if failed_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
