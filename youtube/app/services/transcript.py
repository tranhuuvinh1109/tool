import html
import urllib.parse
import urllib.request
import json
from typing import List, Dict, Any
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    InvalidVideoId,
)
from app.models.transcript import TranscriptResponse, TranscriptSegment


def merge_raw_segments_into_sentences(
    raw_segments: List[Any],
    max_gap: float = 1.2,
    max_duration: float = 12.0,
    max_words: int = 25,
) -> List[Dict[str, Any]]:
    """
    Merge raw auto-caption fragments into clean, natural sentences.
    """
    if not raw_segments:
        return []

    merged_chunks: List[Dict[str, Any]] = []
    current_chunk: List[Dict[str, Any]] = []

    for idx, item in enumerate(raw_segments):
        if isinstance(item, dict):
            start = float(item.get("start", 0.0))
            duration = float(item.get("duration", 0.0))
            text = str(item.get("text", ""))
        else:
            start = float(getattr(item, "start", 0.0))
            duration = float(getattr(item, "duration", 0.0))
            text = str(getattr(item, "text", ""))

        clean_text = html.unescape(text).replace("\n", " ").strip()
        if not clean_text:
            continue

        end = round(start + duration, 2)
        current_chunk.append({
            "start": start,
            "duration": duration,
            "end": end,
            "text": clean_text,
        })

        has_next = idx < len(raw_segments) - 1
        next_item = raw_segments[idx + 1] if has_next else None
        if next_item:
            next_start = float(next_item.get("start", 0.0)) if isinstance(next_item, dict) else float(getattr(next_item, "start", 0.0))
        else:
            next_start = 0.0

        full_text = " ".join(c["text"] for c in current_chunk)
        chunk_duration = current_chunk[-1]["end"] - current_chunk[0]["start"]
        word_count = len(full_text.split())
        gap_to_next = (next_start - current_chunk[-1]["end"]) if has_next else 0.0

        # Capitalize sentence start
        if full_text and full_text[0].islower():
            full_text = full_text[0].upper() + full_text[1:]

        ends_with_sentence_punct = any(full_text.endswith(p) for p in [".", "!", "?", ";", ":"])

        should_flush = (
            not has_next or
            ends_with_sentence_punct or
            gap_to_next > max_gap or
            chunk_duration >= max_duration or
            word_count >= max_words
        )

        if should_flush:
            if not ends_with_sentence_punct:
                full_text += "."

            merged_chunks.append({
                "id": len(merged_chunks),
                "start": round(current_chunk[0]["start"], 2),
                "end": round(current_chunk[-1]["end"], 2),
                "duration": round(chunk_duration, 2),
                "text": full_text,
            })
            current_chunk = []

    return merged_chunks


def translate_text_to_vietnamese_batch(texts: List[str]) -> List[str]:
    """
    Translate a list of English sentences into Vietnamese using batch translation.
    """
    if not texts:
        return []

    translations: List[str] = []
    batch_size = 15

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        combined = "\n__SEG__\n".join(batch)

        try:
            url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=vi&dt=t&q=" + urllib.parse.quote(combined)
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=5) as res:
                data = json.loads(res.read().decode("utf-8"))
                translated_combined = "".join([item[0] for item in data[0] if item[0]])
                
            translated_split = [t.strip() for t in translated_combined.split("__SEG__")]
            if len(translated_split) == len(batch):
                translations.extend(translated_split)
            else:
                for single in batch:
                    try:
                        u = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=vi&dt=t&q=" + urllib.parse.quote(single)
                        r = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(r, timeout=3) as resp:
                            d = json.loads(resp.read().decode("utf-8"))
                            translations.append("".join([item[0] for item in d[0] if item[0]]).strip())
                    except Exception:
                        translations.append("")
        except Exception:
            for single in batch:
                translations.append("")

    return translations


def fetch_youtube_transcript(video_id: str) -> TranscriptResponse:
    """
    Fetch transcript for a given YouTube video ID, merge into clean sentences,
    and provide Vietnamese translation for each segment.

    Raises:
        ValueError: On transcript unavailable or invalid video ID.
    """
    try:
        api = YouTubeTranscriptApi()
        try:
            transcript_list = api.list(video_id)
            try:
                transcript_obj = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
            except Exception:
                try:
                    transcript_obj = next(iter(transcript_list))
                except StopIteration:
                    raise ValueError("No transcript items found for this video.")

            language_code = getattr(transcript_obj, 'language_code', 'unknown')
            raw_segments = transcript_obj.fetch()
        except (AttributeError, Exception):
            raw_segments = api.fetch(video_id, languages=('en', 'en-US', 'vi', 'auto'))
            language_code = 'en'

    except TranscriptsDisabled:
        raise ValueError("Subtitles/Transcripts are disabled for this YouTube video.")
    except NoTranscriptFound:
        raise ValueError("No transcript was found for this YouTube video in any available language.")
    except VideoUnavailable:
        raise ValueError("The requested YouTube video is unavailable or private.")
    except InvalidVideoId:
        raise ValueError("The provided YouTube video ID is invalid.")
    except Exception as e:
        raise ValueError(f"Failed to retrieve transcript: {str(e)}")

    if not raw_segments:
        raise ValueError("Transcript dataset returned empty.")

    # Step 1: Merge raw fragments into clean natural sentences
    merged_sentences = merge_raw_segments_into_sentences(raw_segments)

    # Step 2: Batch translate sentences into Vietnamese
    english_texts = [s["text"] for s in merged_sentences]
    vietnamese_translations = translate_text_to_vietnamese_batch(english_texts)

    formatted_segments: List[TranscriptSegment] = []
    for idx, item in enumerate(merged_sentences):
        vi_text = vietnamese_translations[idx] if idx < len(vietnamese_translations) else ""

        formatted_segments.append(
            TranscriptSegment(
                id=idx,
                start=item["start"],
                duration=item["duration"],
                end=item["end"],
                text=item["text"],
                text_vi=vi_text,
            )
        )

    return TranscriptResponse(
        video_id=video_id,
        language=language_code,
        title=f"YouTube Video ({video_id})",
        segments=formatted_segments,
    )
