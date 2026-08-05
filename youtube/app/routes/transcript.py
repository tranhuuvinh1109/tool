from fastapi import APIRouter, Query, HTTPException
from app.models.transcript import TranscriptResponse
from app.services.youtube import extract_video_id
from app.services.transcript import fetch_youtube_transcript

router = APIRouter(prefix="/api", tags=["Transcript"])


@router.get("/transcript", response_model=TranscriptResponse)
def get_transcript_endpoint(url: str = Query(..., description="YouTube video URL or video ID")):
    """
    Get transcript segments for a given YouTube URL or Video ID.
    """
    try:
        video_id = extract_video_id(url)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))

    try:
        response_data = fetch_youtube_transcript(video_id)
        return response_data
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(err)}")
