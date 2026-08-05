import pytest
import sys
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.services import gemini

client = TestClient(app)


@patch("app.services.gemini._get_configured_model")
def test_summarize_transcript_service(mock_get_model):
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = "This is a video summary."
    mock_get_model.return_value = mock_model

    result = gemini.summarize_transcript("Sample transcript text.")
    assert "This is a video summary." in result


@patch("app.services.gemini._get_configured_model")
def test_explain_segment_service(mock_get_model):
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = "This phrase means..."
    mock_get_model.return_value = mock_model

    result = gemini.explain_segment("complex jargon", "context text")
    assert "This phrase means..." in result


@patch("app.services.gemini._get_configured_model")
def test_generate_flashcards_service(mock_get_model):
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = '[{"term": "FastAPI", "definition": "Web framework", "context": "Backend"}]'
    mock_get_model.return_value = mock_model

    cards = gemini.generate_flashcards("FastAPI is a web framework.")
    assert len(cards) == 1
    assert cards[0]["term"] == "FastAPI"


@patch("app.services.gemini.summarize_transcript")
def test_ai_summarize_endpoint(mock_summarize):
    mock_summarize.return_value = "Mocked AI Summary."

    response = client.post(
        "/api/ai/summarize",
        json={"video_id": "dQw4w9WgXcQ", "transcript": "Hello world transcript."}
    )
    assert response.status_code == 200
    assert response.json()["summary"] == "Mocked AI Summary."
