import os
import json
import re
import google.generativeai as genai
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "gemini-2.5-flash"


def _get_configured_model():
    """Initializes and returns the GenerativeModel instance using GEMINI_API_KEY."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise ValueError(
            "GEMINI_API_KEY environment variable is not configured. "
            "Please add your Gemini API key to the .env file."
        )
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(MODEL_NAME)


def summarize_transcript(text: str) -> str:
    """Summarizes a video transcript into key takeaways and bullet points."""
    try:
        model = _get_configured_model()
        prompt = f"""
You are an expert video content summarizer.
Analyze the following YouTube video transcript and provide a clear, well-structured summary.

Requirements:
- Executive Summary (2-3 sentences overview)
- Key Takeaways & Highlights (4-6 bullet points)
- Main Topics Covered

Transcript:
\"\"\"
{text[:15000]}
\"\"\"
"""
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Gemini AI Error: {str(e)}"


def explain_segment(segment_text: str, context: str = "") -> str:
    """Explains difficult phrases, vocabulary, or concepts in a transcript segment."""
    try:
        model = _get_configured_model()
        prompt = f"""
You are an AI language & technical tutor.
Explain the following segment from a YouTube video transcript clearly.

Segment to Explain:
"{segment_text}"

Context surrounding segment:
"{context[:2000]}"

Instructions:
1. Explain the core meaning in simple terms.
2. Highlight key vocabulary, idioms, or technical jargon if present.
3. Provide a practical real-world example sentence.
"""
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Gemini AI Error: {str(e)}"


def ask_question(transcript: str, question: str) -> str:
    """Answers user questions strictly based on the provided video transcript."""
    try:
        model = _get_configured_model()
        prompt = f"""
You are an assistant that answers questions based ONLY on the provided video transcript.

Question: {question}

Transcript:
\"\"\"
{transcript[:15000]}
\"\"\"

Provide a concise, direct answer. If the answer is not mentioned in the transcript, state that clearly.
"""
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Gemini AI Error: {str(e)}"


def generate_flashcards(transcript: str) -> List[Dict[str, str]]:
    """Generates key term/concept flashcards from the transcript."""
    try:
        model = _get_configured_model()
        prompt = f"""
Extract 4 to 6 key terms, concepts, or important vocabulary words from this YouTube transcript.
Return ONLY valid JSON array of objects with keys: "term", "definition", "context".

JSON Example:
[
  {{"term": "FastAPI", "definition": "A modern, fast web framework for building APIs with Python.", "context": "Used to create backends"}}
]

Transcript:
\"\"\"
{transcript[:15000]}
\"\"\"
"""
        response = model.generate_content(prompt)
        raw_text = response.text
        # Clean markdown codeblocks if present
        clean_json = re.sub(r"```json\s*", "", raw_text)
        clean_json = re.sub(r"```\s*$", "", clean_json).strip()
        data = json.loads(clean_json)
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        return [
            {
                "term": "Notice",
                "definition": f"Could not generate flashcards: {str(e)}",
                "context": "AI Error",
            }
        ]
