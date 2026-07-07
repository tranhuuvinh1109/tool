import json
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from tqdm import tqdm
from utils import logger, SubtitleSegment

class WhisperEngine:
    """Uses Faster-Whisper to transcribe audio files with progress tracking and CPU fallback."""
    
    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "cuda",
        compute_type: str = "float16",
        language: str = "auto"
    ) -> None:
        self.model_size = model_size
        self.requested_device = device
        self.requested_compute = compute_type
        self.language = None if language == "auto" else language
        self.model = None

    def _initialize_model(self) -> None:
        """Initializes the Faster-Whisper model with GPU support and automatic CPU fallback."""
        from faster_whisper import WhisperModel

        device = self.requested_device
        compute_type = self.requested_compute

        # Auto fallback checklist
        if device == "cuda":
            try:
                logger.info(f"Initializing Whisper model '{self.model_size}' on GPU (CUDA) with compute_type '{compute_type}'...")
                self.model = WhisperModel(self.model_size, device="cuda", compute_type=compute_type)
                logger.info("Successfully loaded Whisper model on GPU.")
                return
            except Exception as e:
                logger.warning(
                    f"Failed to initialize Faster-Whisper on CUDA (Error: {e}). "
                    "Automatically falling back to CPU."
                )
                device = "cpu"
                compute_type = "float32"

        logger.info(f"Initializing Whisper model '{self.model_size}' on CPU with compute_type '{compute_type}'...")
        try:
            self.model = WhisperModel(self.model_size, device="cpu", compute_type=compute_type)
            logger.info("Successfully loaded Whisper model on CPU.")
        except Exception as e:
            # Fallback to int8 if float32 fails for some resource constraints, or raise
            logger.warning(f"Failed to load Whisper with compute type {compute_type} on CPU. Triangulating int8 float fallback...")
            try:
                self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
                logger.info("Successfully loaded Whisper model on CPU in INT8 mode.")
            except Exception as inner_e:
                raise RuntimeError(
                    f"Crucial failure loading Faster-Whisper model: {inner_e}. "
                    "Ensure you have downloaded the weights or have internet access."
                ) from inner_e

    def transcribe(self, audio_path: Path, temp_dir: Path) -> List[SubtitleSegment]:
        """
        Transcribes the audio file and saves the original transcript.
        Returns a list of SubtitleSegment instances.
        """
        if self.model is None:
            self._initialize_model()

        assert self.model is not None, "Whisper model was not initialized."

        audio_str = str(audio_path.resolve())
        logger.info("Transcribing audio...")

        # Transcribe returns generator of Segment and WhisperInfo metadata
        # beam_size default is 5. Using temperature fallback by default
        segments_gen, info = self.model.transcribe(
            audio_str,
            language=self.language,
            beam_size=5
        )

        detected_lang = info.language
        lang_prob = info.language_probability
        duration = info.duration

        logger.info(f"Detected language: '{detected_lang}' (probability: {lang_prob:.2f})")
        logger.info(f"Audio duration: {duration:.2f} seconds")

        # Set up progress bar based on audio duration
        segments: List[SubtitleSegment] = []
        
        with tqdm(total=round(duration, 2), unit="s", desc="Transcription Progress", leave=True) as pbar:
            last_end = 0.0
            for segment in segments_gen:
                # Add segment details
                segments.append(
                    SubtitleSegment(
                        start=round(segment.start, 3),
                        end=round(segment.end, 3),
                        text=segment.text.strip()
                    )
                )
                
                # Update progress bar using time elapsed in processed segment
                delta = segment.end - last_end
                if delta > 0:
                    pbar.update(round(delta, 2))
                last_end = segment.end
            
            # Ensure the bar finishes at 100%
            if last_end < duration:
                pbar.update(round(duration - last_end, 2))

        # Save original transcript
        temp_dir.mkdir(parents=True, exist_ok=True)
        orig_transcript_path = temp_dir / "transcript_original.json"
        
        serializable_segments = [seg.to_dict() for seg in segments]
        try:
            with open(orig_transcript_path, "w", encoding="utf-8") as f:
                json.dump(serializable_segments, f, ensure_ascii=False, indent=4)
            logger.info(f"Saved original transcript to {orig_transcript_path}")
        except Exception as e:
            logger.warning(f"Could not save original transcript to JSON: {e}")

        return segments
