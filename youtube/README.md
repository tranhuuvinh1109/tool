# YouTube Transcript Sync Web Application 🎬⚡

A fast, interactive web application built with **Python (FastAPI)**, **Vanilla JS**, **YouTube IFrame Player API**, and **Gemini 2.5 Flash AI**.

The application extracts transcript/subtitle data from any YouTube video URL, displays an interactive player alongside synchronized transcript segments, highlights speaking segments in real-time using an **O(log N) Binary Search engine**, auto-scrolls smoothly, supports click-to-seek, and provides optional AI utilities (Summarization, Segment Explanation, Q&A Chat, Flashcards).

---

## 🚀 Features

- 📹 **YouTube URL Validation**: Supports `youtube.com/watch?v=`, `youtu.be/`, `embed/`, `shorts/`, and raw video IDs.
- 📜 **Automatic Subtitle Fetching**: Prefers English transcripts, with automatic fallback to any available language.
- ⚡ **Real-time Synchronization**: O(log N) Binary Search algorithm highlights the current speaking line at 60 FPS.
- 🎯 **Click-to-Seek**: Click any transcript segment to instantly jump video playback to that exact timestamp.
- 🔍 **Live Search & Highlight**: Instantly filter lines with live text highlighting.
- 📥 **Transcript Export**: Export transcripts to `.txt` or `.srt` formats with single-click downloads.
- 🤖 **Gemini 2.5 Flash AI Workspace**:
  - **Summarize Video**: Executive overview & key takeaways.
  - **Ask Video (Q&A)**: Ask questions directly against the video transcript content.
  - **Explain Segment**: Deep-dive explanation of vocabulary and concepts.
  - **Create Flashcards**: Automatic vocabulary & concept flashcard generator.

---

## 📂 Project Structure

```text
youtube/
│
├── app/
│   ├── main.py                # FastAPI app initialization & route mounting
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── transcript.py      # Transcript API routes (/api/transcript)
│   │   └── ai.py              # Gemini AI routes (/api/ai/*)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── youtube.py         # URL parsing & video ID extraction
│   │   ├── transcript.py      # youtube-transcript-api integration
│   │   └── gemini.py          # Gemini 2.5 Flash AI service layer
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── transcript.py      # Pydantic data schemas
│   │
│   ├── templates/
│   │   └── index.html         # Main UI layout
│   │
│   └── static/
│       ├── css/
│       │   └── style.css      # Dark glassmorphism stylesheet
│       └── js/
│           └── app.js         # Frontend IFrame player & sync engine
│
├── tests/
│   ├── __init__.py
│   ├── test_youtube.py        # URL parser unit tests
│   ├── test_transcript.py     # Transcript service unit tests
│   └── test_gemini.py         # Gemini AI mock unit tests
│
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── run.py                     # Entry point server script
```

---

## 🛠️ Setup & Execution

### 1. Install Dependencies
Run from project root or inside `youtube/`:
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables (Optional for AI)
Copy `.env.example` to `.env` and insert your Gemini API Key:
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
```
*(Note: Core transcript sync works without an API key. AI features require `GEMINI_API_KEY`.)*

### 3. Run Application
```bash
python youtube/run.py
```
Open your browser and navigate to:
```
http://localhost:8000
```

---

## 🧪 Running Unit Tests

Run the full pytest suite:
```bash
pytest youtube/tests
```

---

## 📡 API Reference

### 1. Get Transcript
`GET /api/transcript?url={youtube_url}`
- **Response**:
```json
{
  "video_id": "dQw4w9WgXcQ",
  "language": "en",
  "title": "YouTube Video (dQw4w9WgXcQ)",
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "duration": 3.2,
      "end": 3.2,
      "text": "Hello everyone."
    }
  ]
}
```

### 2. Summarize Video (Gemini 2.5 Flash)
`POST /api/ai/summarize`
- **Body**: `{ "video_id": "...", "transcript": "..." }`
- **Response**: `{ "summary": "..." }`

### 3. Explain Segment
`POST /api/ai/explain`
- **Body**: `{ "segment_text": "...", "context": "..." }`
- **Response**: `{ "explanation": "..." }`

### 4. Q&A over Video
`POST /api/ai/chat`
- **Body**: `{ "transcript": "...", "question": "..." }`
- **Response**: `{ "answer": "..." }`

### 5. Generate Flashcards
`POST /api/ai/flashcards`
- **Body**: `{ "transcript": "..." }`
- **Response**: `{ "flashcards": [ { "term": "...", "definition": "..." } ] }`
