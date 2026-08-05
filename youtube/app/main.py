from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.routes import transcript, ai

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="YouTube Transcript Sync Web App",
    description="Sync YouTube video playback with interactive transcript segments & Gemini 2.5 Flash AI features.",
    version="1.0.0",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static & Templates setup
static_dir = BASE_DIR / "static"
templates_dir = BASE_DIR / "templates"

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

# Include Routers
app.include_router(transcript.router)
app.include_router(ai.router)


@app.get("/")
def read_root(request: Request):
    """
    Render main application UI page.
    """
    return templates.TemplateResponse(request=request, name="index.html")

