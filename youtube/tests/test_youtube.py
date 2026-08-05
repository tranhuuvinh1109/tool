import pytest
import sys
import os

# Make sure youtube root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.youtube import extract_video_id


def test_extract_video_id_standard_url():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert extract_video_id(url) == "dQw4w9WgXcQ"


def test_extract_video_id_short_link():
    url = "https://youtu.be/dQw4w9WgXcQ"
    assert extract_video_id(url) == "dQw4w9WgXcQ"


def test_extract_video_id_embed_url():
    url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
    assert extract_video_id(url) == "dQw4w9WgXcQ"


def test_extract_video_id_shorts_url():
    url = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
    assert extract_video_id(url) == "dQw4w9WgXcQ"


def test_extract_video_id_raw_id():
    raw_id = "dQw4w9WgXcQ"
    assert extract_video_id(raw_id) == "dQw4w9WgXcQ"


def test_extract_video_id_url_with_query_params():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120s&feature=shared"
    assert extract_video_id(url) == "dQw4w9WgXcQ"


def test_extract_video_id_invalid_domain():
    with pytest.raises(ValueError, match="is not a recognized YouTube domain"):
        extract_video_id("https://vimeo.com/123456789")


def test_extract_video_id_invalid_url():
    with pytest.raises(ValueError):
        extract_video_id("https://www.youtube.com/watch?v=invalid_short_id")
