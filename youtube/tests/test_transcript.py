import pytest
import sys
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.models.transcript import TranscriptSegment, TranscriptResponse
from app.services.transcript import fetch_youtube_transcript

client = TestClient(app)


def test_transcript_segment_model():
    segment = TranscriptSegment(
        id=0,
        start=1.5,
        duration=3.2,
        end=4.7,
        text="Hello world"
    )
    assert segment.id == 0
    assert segment.start == 1.5
    assert segment.duration == 3.2
    assert segment.end == 4.7
    assert segment.text == "Hello world"


@patch("app.services.transcript.YouTubeTranscriptApi")
def test_fetch_youtube_transcript_success(mock_transcript_api_class):
    mock_api_instance = MagicMock()
    mock_transcript_api_class.return_value = mock_api_instance

    mock_transcript_obj = MagicMock()
    mock_transcript_obj.language_code = "en"
    mock_transcript_obj.fetch.return_value = [
        {"text": "Hello everyone.", "start": 0.0, "duration": 3.2},
        {"text": "Today we will learn Python.", "start": 3.2, "duration": 4.5},
    ]

    mock_transcript_list = MagicMock()
    mock_transcript_list.find_transcript.return_value = mock_transcript_obj
    mock_api_instance.list.return_value = mock_transcript_list

    res = fetch_youtube_transcript("dQw4w9WgXcQ")

    assert res.video_id == "dQw4w9WgXcQ"
    assert res.language == "en"
    assert len(res.segments) == 2
    assert res.segments[0].text == "Hello everyone."
    assert res.segments[0].end == 3.2
    assert res.segments[1].start == 3.2
    assert res.segments[1].end == 7.7


@patch("app.routes.transcript.fetch_youtube_transcript")
def test_get_transcript_endpoint_success(mock_fetch):
    mock_fetch.return_value = TranscriptResponse(
        video_id="dQw4w9WgXcQ",
        language="en",
        title="Test Title",
        segments=[
            TranscriptSegment(id=0, start=0.0, duration=3.2, end=3.2, text="Hello everyone.")
        ]
    )

    response = client.get("/api/transcript?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert response.status_code == 200
    data = response.json()
    assert data["video_id"] == "dQw4w9WgXcQ"
    assert len(data["segments"]) == 1
    assert data["segments"][0]["text"] == "Hello everyone."


def test_get_transcript_endpoint_invalid_url():
    response = client.get("/api/transcript?url=https://invalid-website.com")
    assert response.status_code == 400
    assert "not a recognized YouTube domain" in response.json()["detail"]
