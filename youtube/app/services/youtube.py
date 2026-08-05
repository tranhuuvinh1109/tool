import re
from urllib.parse import parse_qs, urlparse


YOUTUBE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{11}$")


def extract_video_id(url_or_id: str) -> str:
    """
    Extract YouTube 11-character video ID from various YouTube URL formats or raw ID.

    Supported patterns:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://www.youtube.com/v/VIDEO_ID
    - https://www.youtube.com/live/VIDEO_ID
    - https://m.youtube.com/watch?v=VIDEO_ID
    - Raw VIDEO_ID string (e.g., 'dQw4w9WgXcQ')

    Raises:
        ValueError: If video ID cannot be found or is invalid.
    """
    if not url_or_id or not isinstance(url_or_id, str):
        raise ValueError("Invalid YouTube URL or Video ID provided.")

    cleaned_input = url_or_id.strip()

    # Check if raw 11-char ID
    if YOUTUBE_ID_PATTERN.match(cleaned_input):
        return cleaned_input

    # Parse URL
    if not cleaned_input.startswith(("http://", "https://")):
        cleaned_input = "https://" + cleaned_input

    try:
        parsed = urlparse(cleaned_input)
    except Exception as e:
        raise ValueError(f"Could not parse YouTube URL: {e}")

    hostname = parsed.hostname or ""
    hostname = hostname.lower()

    if not any(domain in hostname for domain in ["youtube.com", "youtu.be", "youtube-nocookie.com"]):
        raise ValueError(f"Domain '{hostname}' is not a recognized YouTube domain.")

    # Format 1: short link (youtu.be/VIDEO_ID)
    if "youtu.be" in hostname:
        path_parts = [p for p in parsed.path.split("/") if p]
        if path_parts:
            candidate_id = path_parts[0]
            if YOUTUBE_ID_PATTERN.match(candidate_id):
                return candidate_id

    # Format 2: standard watch link (youtube.com/watch?v=VIDEO_ID)
    query_params = parse_qs(parsed.query)
    if "v" in query_params and query_params["v"]:
        candidate_id = query_params["v"][0]
        if YOUTUBE_ID_PATTERN.match(candidate_id):
            return candidate_id

    # Format 3: embed, v, live, or shorts paths (youtube.com/embed/VIDEO_ID or youtube.com/shorts/VIDEO_ID)
    path_parts = [p for p in parsed.path.split("/") if p]
    if len(path_parts) >= 2 and path_parts[0] in ["embed", "v", "live", "shorts"]:
        candidate_id = path_parts[1]
        if YOUTUBE_ID_PATTERN.match(candidate_id):
            return candidate_id

    raise ValueError("Could not extract a valid YouTube video ID from the provided URL.")
