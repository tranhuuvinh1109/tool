# Screen Scroll Automation

A simple Python script for detecting screen positions and automatically scrolling at a specific screen location until a configured end time.

## Requirements

- Python 3.9 or higher
- `pip`
- A desktop environment with mouse access

## Installation

### 1. Create a Virtual Environment

#### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

#### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

## Usage

### Step 1: Get Screen Position

Run:

```bash
python GetPostion/index.py
```

The program will wait for you to click somewhere on the screen.

**Click anywhere on the screen** where you want to get the position.

The coordinates will be printed in the terminal, for example:

```text
Position: x=850, y=450
```

Copy the `x` and `y` values from the terminal.

### Step 2: Configure the Scroll Position

Open:

```text
Scroll/index.py
```

Find the `x` and `y` variables and replace them with the coordinates obtained from `GetPostion/index.py`.

Example:

```python
x = 850
y = 450
```

### Step 3: Set the End Time

Open:

```text
Scroll/index.py
```

Set the time when the script should stop running.

For example:

```python
END_TIME = "18:00"
```

The script will continue scrolling until the configured end time.

> Make sure the time format matches the format expected by the script.

### Step 4: Start the Scroll Script

Run:

```bash
python Scroll/index.py
```

The script will start scrolling at the configured screen position and automatically stop when the end time is reached.

## Typical Workflow

```text
1. Create virtual environment
        ↓
2. Activate virtual environment
        ↓
3. Install dependencies
        ↓
4. Run GetPostion/index.py
        ↓
5. Click on the desired screen position
        ↓
6. Copy x and y from the terminal
        ↓
7. Update x and y in Scroll/index.py
        ↓
8. Set the end time
        ↓
9. Run Scroll/index.py
```

## Deactivate Virtual Environment

When you are finished, you can deactivate the virtual environment:

```bash
deactivate
```

## Troubleshooting

### `python` command not found

On Linux/macOS, try:

```bash
python3 --version
```

If `python3` is available, use:

```bash
python3 GetPostion/index.py
python3 Scroll/index.py
```

### Permission Issues on Linux/macOS

If the script cannot control the mouse or read the screen, check your operating system's accessibility and screen-control permissions.

On macOS, you may need to allow your terminal application under:

```text
System Settings → Privacy & Security → Accessibility
```

## Project Structure

```text
.
├── GetPostion/
│   └── index.py
├── Scroll/
│   └── index.py
├── requirements.txt
├── README.md
└── venv/
```

> The `venv/` directory is a local virtual environment and should normally be excluded from Git using `.gitignore`.
