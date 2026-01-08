# Setup Guide

This project uses modern Python tooling with **uv** for fast, reliable dependency management.

## Prerequisites

- **Python 3.10+** - [Download](https://www.python.org/downloads/)
- **Ollama** - [Download](https://ollama.ai)
- **uv** (optional, auto-installed) - [Info](https://github.com/astral-sh/uv)

## Quick Start

### Windows
From project root:
```bash
scripts\setup_windows.bat
```

### Linux/Mac
From project root:
```bash
chmod +x scripts/setup_linux.sh
scripts/setup_linux.sh
```

## What the Setup Does

1. ✅ Checks Python installation (3.10+)
2. ✅ Checks Ollama installation
3. ✅ Installs uv (if not present)
4. ✅ Creates Python virtual environment (.venv)
5. ✅ Installs all dependencies from pyproject.toml
6. ✅ Initializes the database

## Manual Setup (if scripts don't work)

```bash
# 1. Create virtual environment
uv venv --python 3.12 .venv

# 2. Activate environment
# On Windows:
.venv\Scripts\activate.bat
# On Linux/Mac:
source .venv/bin/activate

# 3. Install dependencies
uv pip install -e .

# 4. Initialize database
python -c "from src.core import init_database; init_database()"
```

## Running the Application

After setup, run these in **separate terminals**:

### Terminal 1: Start API Server
```bash
# Activate environment
.venv\Scripts\activate.bat  # Windows
source .venv/bin/activate  # Linux/Mac

# Start API
python -m uvicorn src.api.vendor_api:app --host 127.0.0.1 --port 8000 --reload
```

### Terminal 2: Start Streamlit UI
```bash
# Activate environment
.venv\Scripts\activate.bat  # Windows
source .venv/bin/activate  # Linux/Mac

# Start UI
streamlit run src/ui/app.py
```

### Terminal 3: Start Ollama (if not running)
```bash
ollama serve
```

Then open: **http://localhost:8501**

## Project Structure

```
project/
├── scripts/                # Setup scripts
│   ├── setup_windows.bat   # Windows setup
│   ├── setup_linux.sh      # Linux/Mac setup
│   └── SETUP.md            # This file
├── src/                    # Source code (23 Python files)
│   ├── agents/            # AI agents (planner, executor, observer)
│   ├── api/               # REST API endpoints
│   ├── models/            # Data validation schemas
│   ├── core/              # LLM engine, retry logic, database
│   ├── ui/                # Streamlit user interface
│   └── utils/             # Testing utilities
├── data/                  # CSV data files
├── pyproject.toml         # Project configuration (modern approach)
└── requirements.txt       # Legacy requirements (kept for compatibility)
```

## Using uv Commands

```bash
# Add new package
uv pip install package-name

# Install dev dependencies
uv pip install -e ".[dev]"

# Sync environment to pyproject.toml
uv sync

# Run Python in environment
uv run python script.py

# Run tests
uv run pytest
```

## Troubleshooting

### "Python not found"
- Make sure Python 3.10+ is installed and in PATH
- Check: `python --version` or `python3 --version`

### "Ollama not found"
- Install from https://ollama.ai
- Pull the model: `ollama pull qwen2.5:7b`
- It will auto-detect, just continue setup

### "pip install fails"
- Delete `.venv` directory and run setup again
- Make sure you're not in a conda environment

### "ModuleNotFoundError"
- Activate virtual environment: `.venv\Scripts\activate.bat` (Windows) or `source .venv/bin/activate` (Linux/Mac)
- Reinstall: `uv pip install -e .`

### "Port 8000/8501 already in use"
- Find and kill the process using the port
- Or specify different ports when starting:
  ```bash
  python -m uvicorn src.api.vendor_api:app --port 8001
  streamlit run src/ui/app.py --server.port 8502
  ```

## Development

### Install dev dependencies
```bash
uv pip install -e ".[dev]"
```

### Run tests
```bash
uv run pytest
```

### Code formatting
```bash
uv run black src/
uv run isort src/
```

### Type checking
```bash
uv run mypy src/
```

## Documentation

- [QUICK_START_NEW_STRUCTURE.md](../QUICK_START_NEW_STRUCTURE.md) - Quick start guide
- [PROJECT_STRUCTURE.md](../PROJECT_STRUCTURE.md) - Folder structure
- [MODULE_REFERENCE.md](../MODULE_REFERENCE.md) - Module details
- [README.md](../README.md) - Main documentation

## Version Info

- Python: 3.10+
- uv: Latest
- FastAPI: 0.104.1
- LangGraph: 0.0.20
- Streamlit: 1.28.1
- Ollama: Local (Qwen 2.5 7B recommended)


chmod +x scripts/setup.sh
. scripts/setup.sh