import time
import sys
import logging
import subprocess
import shutil
import hashlib
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict, field

# Configure custom logger to output format requested by user
logger = logging.getLogger("video_translator")
logger.setLevel(logging.INFO)

# Avoid adding multiple handlers if utils is imported multiple times
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

@dataclass
class SubtitleSegment:
    start: float  # Start time in seconds
    end: float    # End time in seconds
    text: str     # Original transcribed text
    translated_text: str = ""  # Translated text in Vietnamese

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubtitleSegment":
        return cls(
            start=data["start"],
            end=data["end"],
            text=data["text"],
            translated_text=data.get("translated_text", "")
        )

class StageTimer:
    """Helper class to track and display elapsed time for each stage."""
    def __init__(self, stage_name: str, percent: int) -> None:
        self.stage_name = stage_name
        self.percent = percent
        self.start_time: float = 0.0

    def __enter__(self) -> "StageTimer":
        logger.info(f"Step: {self.stage_name}... {self.percent}%")
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        elapsed = time.perf_counter() - self.start_time
        if exc_type is not None:
            logger.error(f"Failed {self.stage_name.lower()} after {elapsed:.2f}s: {exc_val}")
        else:
            logger.info(f"Finished {self.stage_name.lower()} in {elapsed:.2f}s.")


def check_ffmpeg_available() -> None:
    """Verify that FFmpeg is installed and accessible in the system PATH."""
    import os
    
    # Dynamically inject the Python executable parent directory (e.g. venv/Scripts)
    # and the file parent directory into the process PATH.
    python_parent = Path(sys.executable).parent
    file_parent = Path(__file__).parent
    
    extra_paths = [str(python_parent.resolve()), str(file_parent.resolve())]
    current_path = os.environ.get("PATH", "")
    
    for path_str in extra_paths:
        if path_str not in current_path:
            current_path = f"{path_str}{os.pathsep}{current_path}"
            
    os.environ["PATH"] = current_path

    try:
        # Run ffmpeg -version to check availability
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        raise RuntimeError(
            "FFmpeg is not installed or not found in system PATH. "
            "Please install FFmpeg and make sure it is added to your environment variables."
        ) from e


def get_file_metadata(filepath: Path) -> Dict[str, Any]:
    """Get metadata of source file to verify for checkpoint resuming."""
    if not filepath.exists():
        return {}
    stats = filepath.stat()
    return {
        "path": str(filepath.resolve()),
        "size": stats.st_size,
        "mtime": stats.st_mtime
    }

class CheckpointManager:
    """Manages the saving and loading of progress to support resumable processing."""
    def __init__(self, temp_dir: Path, src_video: Path, output_video: Path) -> None:
        self.temp_dir = temp_dir
        self.checkpoint_file = temp_dir / "checkpoint.json"
        self.src_metadata = get_file_metadata(src_video)
        self.output_path = str(output_video.resolve())

    def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Loads valid checkpoint if available and matches the current source file."""
        if not self.checkpoint_file.exists():
            return None
        
        try:
            with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Verify source metadata matches to ensure it's the same video
            saved_meta = data.get("source_metadata", {})
            saved_output = data.get("output_path", "")
            
            if (saved_meta.get("path") == self.src_metadata.get("path") and
                saved_meta.get("size") == self.src_metadata.get("size") and
                saved_meta.get("mtime") == self.src_metadata.get("mtime") and
                saved_output == self.output_path):
                return data
            
            logger.warning("Checkpoint found but it does not match the source video. Starting fresh.")
        except Exception as e:
            logger.warning(f"Failed to load checkpoint file: {e}. Starting fresh.")
            
        return None

    def save_checkpoint(self, stage: str, data: Dict[str, Any]) -> None:
        """Saves current state status including completed stages."""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_data = {
            "source_metadata": self.src_metadata,
            "output_path": self.output_path,
            "stage_completed": stage,
            "stage_data": data
        }
        try:
            with open(self.checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.warning(f"Could not save checkpoint: {e}")

    def clear(self) -> None:
        """Deletes checkpoint file."""
        if self.checkpoint_file.exists():
            try:
                self.checkpoint_file.unlink()
            except Exception as e:
                logger.debug(f"Failed to delete checkpoint file: {e}")
