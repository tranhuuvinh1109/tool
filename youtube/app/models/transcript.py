from typing import List, Optional
from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    id: int
    start: float
    duration: float
    end: float
    text: str
    text_vi: Optional[str] = ""


class TranscriptResponse(BaseModel):
    video_id: str
    language: str
    title: Optional[str] = None
    segments: List[TranscriptSegment]


class AISummarizeRequest(BaseModel):
    video_id: Optional[str] = None
    transcript: str = Field(..., min_length=1)


class AISummarizeResponse(BaseModel):
    summary: str


class AIExplainRequest(BaseModel):
    segment_text: str = Field(..., min_length=1)
    context: Optional[str] = ""


class AIExplainResponse(BaseModel):
    explanation: str


class AIChatRequest(BaseModel):
    transcript: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)


class AIChatResponse(BaseModel):
    answer: str


class AIFlashcardItem(BaseModel):
    term: str
    definition: str
    context: Optional[str] = ""


class AIFlashcardsRequest(BaseModel):
    transcript: str = Field(..., min_length=1)


class AIFlashcardsResponse(BaseModel):
    flashcards: List[AIFlashcardItem]
