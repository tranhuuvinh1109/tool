from fastapi import APIRouter, HTTPException
from app.models.transcript import (
    AISummarizeRequest,
    AISummarizeResponse,
    AIExplainRequest,
    AIExplainResponse,
    AIChatRequest,
    AIChatResponse,
    AIFlashcardsRequest,
    AIFlashcardsResponse,
)
from app.services import gemini

router = APIRouter(prefix="/api/ai", tags=["AI Features"])


@router.post("/summarize", response_model=AISummarizeResponse)
def summarize_endpoint(req: AISummarizeRequest):
    """
    Summarize transcript using Gemini 2.5 Flash.
    """
    summary_text = gemini.summarize_transcript(req.transcript)
    return AISummarizeResponse(summary=summary_text)


@router.post("/explain", response_model=AIExplainResponse)
def explain_endpoint(req: AIExplainRequest):
    """
    Explain a specific transcript segment or phrase using Gemini 2.5 Flash.
    """
    explanation_text = gemini.explain_segment(req.segment_text, req.context or "")
    return AIExplainResponse(explanation=explanation_text)


@router.post("/chat", response_model=AIChatResponse)
def chat_endpoint(req: AIChatRequest):
    """
    Ask a question about the video transcript using Gemini 2.5 Flash.
    """
    answer_text = gemini.ask_question(req.transcript, req.question)
    return AIChatResponse(answer=answer_text)


@router.post("/flashcards", response_model=AIFlashcardsResponse)
def flashcards_endpoint(req: AIFlashcardsRequest):
    """
    Generate interactive flashcards from the transcript using Gemini 2.5 Flash.
    """
    cards = gemini.generate_flashcards(req.transcript)
    return AIFlashcardsResponse(flashcards=cards)
