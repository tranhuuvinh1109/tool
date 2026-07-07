# Video Subtitle Translator & Burner (Vietnamese)

A production-ready Python tool that automatically transcribes audio from input videos, translates the transcriptions into natural, fluent Vietnamese using advanced translation providers, matches timestamps, formats subtitles, and burns them directly back into the output video.

---

## Architecture Overview

```
Input Video
      │
      ▼
Extract Audio (mono, 16kHz WAV via FFmpeg subprocess)
      │
      ▼
Speech-to-Text (Faster-Whisper on CPU/GPU with automated fallback)
      │
      ▼
Translate Transcript to Vietnamese (Gemini flash, OpenAI GPT, Google Translate, or DeepL with backoff retry)
      │
      ▼
Generate Subtitle (.srt / .ass with customizable fonts, colors, and shadows)
      │
      ▼
Burn Subtitle into Video (FFmpeg subprocess with fallback audio transcoding)
      │
      ▼
Output Video
```

---

## Features

- **Robust Speech-to-Text**: Powered by `faster-whisper` for outstanding precision. Automatically falls back to CPU (using float32/int8) if CUDA (GPU) libraries or compatible devices are absent.
- **Multiple Translation Frontends**: Supports:
  - **Google Gemini API** (Default: `gemini-1.5-flash`, features built-in JSON structured batch requests to handle context naturally and resource-effectively).
  - **Google Translate API** (Supports official Google Cloud Translation API credentials, alongside a built-in free web-crawler fallback for out-of-the-box usage).
- **Customizable Styling**: Generates custom SRT and ASS subtitles. Highly configurable ASS subtitle styling options (font name, font size, bold, italic, custom hexadecimal color codes, outline thickness, and shadow offset) editable inside the configuration file or workspace.
- **Batch Processing**: Point to a directory (e.g. `--src videos/`) or wildcard patterns (e.g. `--src "data/*.mp4"`), and the script will batch-process every file matching the description.
- **Resumable Execution**: Interrupted runs save step checkpoints (`temp/{video_name}_checkpoint.json`) saving generated metadata. Running with the `--resume` flag resumes from the exact failing step.
- **Progress Tracking & Metrics**: Displays a real-time progress bar for Whisper transcribing alongside structured elapsed processing metrics for extraction, translation, and rendering.
- **Wary Windows System Paths Handling**: Uses relative system pathing and advanced escapes to prevent FFmpeg filters from throwing errors due to Windows disk letter conventions (e.g., `C:\...`).

---

## Project Structure

```
videos/
├── index.py              # Application main workspace coordinator
├── audio.py              # Mono, 16kHz WAV audio extraction handler
├── whisper_engine.py      # Whisper Speech-to-Text loading and decoding engine
├── translator.py         # OpenAI / DeepL / Google translators collection
├── subtitle.py           # SRT + ASS writer & ASS color configuration helpers
├── burn.py               # Subtitle burning orchestrator (FFmpeg)
├── utils.py              # Logger, Stage Timers, and Checkpoints manager
├── requirements.txt      # Third-party dependency definitions
└── .env                  # Configuration file (API keys and styling attributes)
```

---

## Installation & Setup

### 1. System Requirements & FFmpeg

Make sure **FFmpeg** is installed on your system and registered to the system path environment variables:

- **Windows**: Install using [Chocolatey](https://chocolatey.org/) (`choco install ffmpeg-full`) or download executable packages from the official [FFmpeg Windows builds](https://www.gyan.dev/ffmpeg/builds/) and append `/bin` to your environment path.
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg`

Verify availability using:

```bash
ffmpeg -version
```

### 2. Python Environment Setting

This project requires **Python 3.11+**. Set up a clean virtual environment:

```bash
# Navigate to project page
cd videos

# Initialize python environment
python -m venv venv

# Activate workspace
# On Windows PowerShell:
venv\Scripts\Activate.ps1
# On macOS/Linux:
source venv/bin/activate
```

### 3. Dependencies Installation

```bash
pip install -r requirements.txt
```

---

## Configuration (`.env`)

Duplicate `.env.example` into a new `.env` file and set the credentials according to your chosen provider:

```bash
cp .env.example .env
```

Open `.env` and fill in:

- `GEMINI_API_KEY`: Required if using default Gemini translation model.
- `GOOGLE_USE_FREE_API`: Set to `true` to use Google Translate without any credentials hookup.
- **ASS font customization parameters**: Override values like `SUB_FONT_NAME`, `SUB_FONT_SIZE`, `SUB_PRIMARY_COLOR` (in hex `#FFFFFF`), etc.

---

## Usage Guide

Run a basic translation using default settings (Gemini translation engine processing an MP4 file):

```bash
python index.py --src sample.mp4 --output sample_vi.mp4
```

### Command Line Arguments Reference

| Arguments      | Short | Description                                                                                           |
| -------------- | ----- | ----------------------------------------------------------------------------------------------------- |
| `--src`        | `-s`  | Path to source video file, folder directory, or match wildcard (e.g. `'archive/*.mp4'`).              |
| `--output`     | `-o`  | Output file path or directory (under batch execution mode, it specifies the destination directory).   |
| `--model`      |       | Whisper model configuration size (Default: `large-v3`).                                               |
| `--device`     |       | Compute hardware interface: `cuda`, `cpu`, or `auto` (Default: `cuda`, falls back to `cpu` on error). |
| `--compute`    |       | Computing precision parameters: `float16` or `float32` (Default: `float16`).                          |
| `--language`   |       | Language designation for the source audio. Use `auto` for automated discovery.                        |
| `--sub-format` |       | Format encoding for generated subtitles: `srt` or `ass` (Default: `srt`).                             |
| `--translator` |       | Translation provider interface choice: `gemini`, `google` (Default: `gemini`).                        |
| `--overwrite`  |       | Force system to overwrite existing target outputs at matching paths.                                  |
| `--no-cleanup` |       | Instruct program to preserve temporary audio, transcripts and translation caches.                     |
| `--resume`     |       | Scan for existing progression checkpoints under workspace to skip completed stages.                   |

### Batch Processing Mode

Point to a directory or a pattern matching schema. Target outputs will be placed inside the `translated_videos/` directory by default, suffixing the names automatically with `_vi`:

```bash
# Bulk translates all AVI files using Google Translate engine:
python index.py --src "raw_clips/*.avi" --translator google

# Bulk process and output to custom folder using ASS styling configurations:
python index.py --src raw_clips/ --output project_exports/ --sub-format ass
```

### Resuming Interrupted Run

If the transcribing or rendering process is stopped midway, add the `--resume` flag to recover performance instantly from the last committed stage cached inside `temp/`:

```bash
python index.py --src source.mp4 --output output.mp4 --resume
```

---

## System Workflows & Diagnostics

### Substation Alpha (.ass) Styling

If choosing `--sub-format ass`, the program compiles fully styled subtitles overlay. The properties inside `.env` operate as follows:

- **Font & Size**: Specifying `Arial` at `24` renders relative size scaling inside 1280x720 project canvas bounds.
- **Hex Color Mapping**: Convert inputs recursively. Custom color tags like `#FF000080` (red with transparent alpha parameters) are handled automatically.
- **Alignment codes**: Default alignment `2` places text Bottom-Center.

### Temporary File Management

Workspace items generated under `temp/` folder (such as extracted audio clips, transcript data sheets representing original vs mapped Vietnamese translations, and raw styles tracks) are automatically deleted upon execution completion to preserve system disk space (unless running with the `--no-cleanup` parameter).
