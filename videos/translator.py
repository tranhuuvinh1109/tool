import os
import sys
import json
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import requests
from dotenv import load_dotenv

from utils import logger, SubtitleSegment

# Load environment variables
load_dotenv()

def retry_api_call(retries: int = 3, initial_delay: float = 2.0, backoff: float = 2.0):
    """Decorator to retry a function on exception with exponential backoff."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(
                        f"API invocation failed (attempt {attempt + 1}/{retries}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= backoff
            logger.error("All API retry attempts failed.")
            raise last_exception
        return wrapper
    return decorator


class BaseTranslator(ABC):
    """Abstract Base Class for translator implementations."""
    
    @abstractmethod
    def translate(self, segments: List[SubtitleSegment]) -> List[SubtitleSegment]:
        """Translates the list of SubtitleSegments, updates translated_text, and returns the list."""
        pass


class GeminiTranslator(BaseTranslator):
    """Translates subtitles using Google Gemini models in efficient batches."""

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not defined in system environment or .env file. "
                "Please add your key to proceed with Gemini translation."
            )

    @retry_api_call(retries=3, initial_delay=2.0)
    def _translate_batch_llm(self, model: Any, batch_texts: List[str]) -> List[str]:
        """Performs a single batch translation request using Gemini Generative API with JSON output constraint."""
        input_data = [{"id": idx, "text": txt} for idx, txt in enumerate(batch_texts)]
        
        prompt = (
            "You are a professional subtitle translator. Translate the text segments in the input JSON array "
            "into natural, fluent Vietnamese. Keep the exact index matching the input JSON block. "
            "Requirements:\n"
            "- Protect timestamps & timings (you are translating only the raw texts).\n"
            "- Translate to natural, spoken Vietnamese appropriate for subtitles.\n"
            "- Do not summarize or omit any information.\n"
            "- Return a JSON array of strings containing the translations, where output[idx] corresponds to input[idx].\n\n"
            f"Input JSON: {json.dumps(input_data, ensure_ascii=False)}"
        )

        # Enforce json response_mime_type to ensure valid JSON is produced
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )

        reply = response.text.strip()
        
        # Parse reply
        translated_list = json.loads(reply)
        if not isinstance(translated_list, list) or len(translated_list) != len(batch_texts):
            raise ValueError(
                f"Expected JSON array of size {len(batch_texts)} but got list of size {len(translated_list) if isinstance(translated_list, list) else 'non-list'}."
            )
        
        return [str(item) for item in translated_list]

    def translate(self, segments: List[SubtitleSegment]) -> List[SubtitleSegment]:
        import google.generativeai as genai
        
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model_name)
        
        logger.info(f"Translating {len(segments)} segments using Gemini ({self.model_name})...")
        
        # Batch size of 30 provides good balancing
        batch_size = 30
        
        for i in range(0, len(segments), batch_size):
            batch = segments[i : i + batch_size]
            batch_texts = [seg.text for seg in batch]
            
            try:
                translated_texts = self._translate_batch_llm(model, batch_texts)
                for idx, text in enumerate(translated_texts):
                    batch[idx].translated_text = text
            except Exception as e:
                logger.warning(f"Batch translation failed: {e}. Falling back to translating segment-by-segment for index {i} to {i+len(batch)}.")
                # Fallback to translating individual segments if batch fails
                for seg in batch:
                    seg.translated_text = self._translate_single_segment_fallback(model, seg.text)
                    
        return segments

    @retry_api_call(retries=3, initial_delay=1.0)
    def _translate_single_segment_fallback(self, model: Any, text: str) -> str:
        """Fallback method to translate a single segment if batch fails."""
        if not text.strip():
            return ""
        
        prompt = (
            "You are a subtitle translator. Translate the following single subtitle line from its original language "
            "into natural, fluent Vietnamese. Keep the original meaning. Do not include prefix/suffix/quotes. "
            "Return only the translated Vietnamese text.\n\n"
            f"Text: {text}"
        )
        response = model.generate_content(prompt)
        return response.text.strip().strip('"')





class GoogleTranslator(BaseTranslator):
    """
    Translates subtitles using Google Translate.
    Supports official Google Cloud Translation API standard library,
    with a free browser-mocking fallback for out-of-the-box usage.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("GOOGLE_TRANS_API_KEY")
        self.use_free_api = os.getenv("GOOGLE_USE_FREE_API", "true").lower() == "true"

    def translate(self, segments: List[SubtitleSegment]) -> List[SubtitleSegment]:
        logger.info(f"Translating {len(segments)} segments using Google Translate...")
        if not self.use_free_api and self.api_key:
            # Official Google Cloud Translation
            return self._translate_official(segments)
        else:
            # Free endpoint translation
            return self._translate_free(segments)

    @retry_api_call(retries=3, initial_delay=2.0)
    def _translate_official(self, segments: List[SubtitleSegment]) -> List[SubtitleSegment]:
        from google.cloud import translate_v2 as translate
        translate_client = translate.Client(api_key=self.api_key)
        
        texts = [seg.text for seg in segments]
        # Translate to Vietnamese (target_language='vi')
        results = translate_client.translate(texts, target_language="vi")
        
        for idx, result in enumerate(results):
            segments[idx].translated_text = result["translatedText"]
        return segments

    def _translate_free(self, segments: List[SubtitleSegment]) -> List[SubtitleSegment]:
        """Free Translate wrapper using Google's public translation endpoint in batches."""
        # Split into batches to prevent URL length issues
        batch_size = 50
        for i in range(0, len(segments), batch_size):
            batch = segments[i : i + batch_size]
            for seg in batch:
                if not seg.text.strip():
                    seg.translated_text = ""
                    continue
                seg.translated_text = self._free_translate_single(seg.text)
        return segments

    @retry_api_call(retries=3, initial_delay=1.0)
    def _free_translate_single(self, text: str) -> str:
        """Call Google's public translating endpoint."""
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": "vi",
            "dt": "t",
            "q": text
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        }
        res = requests.get(url, params=params, headers=headers, timeout=10)
        res.raise_for_status()
        
        data = res.json()
        translated_parts = []
        # Google returns an array of sentences under data[0]
        if data and data[0]:
            for sentence in data[0]:
                if sentence[0]:
                    translated_parts.append(sentence[0])
        return "".join(translated_parts).strip()




def get_translator(engine_name: str) -> BaseTranslator:
    """Factory function to instantiate the selected translator engine."""
    engine_name = engine_name.lower()
    if engine_name == "gemini":
        return GeminiTranslator()
    elif engine_name == "google":
        return GoogleTranslator()
    else:
        raise ValueError(
            f"Unsupported translation engine: '{engine_name}'. "
            "Supported options are: 'gemini', 'google'."
        )
