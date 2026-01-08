#!/bin/bash
# Linux/Mac Setup Script for Autonomous Grocery Shopping Super-Agent
# Uses 'uv' for fast, modern Python dependency management
#
# Prerequisites:
#   - Python 3.10+ installed
#   - Ollama installed (https://ollama.ai)
#   - uv installed (https://github.com/astral-sh/uv) - auto-installed if missing

set -e

echo ""
echo "==============================================="
echo "  AUTONOMOUS GROCERY SHOPPING SUPER-AGENT"
echo "  Linux/Mac Setup Script"
echo "==============================================="
echo ""

# Get project root directory (parent of scripts folder)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$SCRIPT_DIR"

# Check Python
echo "[1/5] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3.10+ is required but not found"
    echo "Install with: sudo apt install python3.10 (Ubuntu/Debian)"
    echo "            : brew install python@3.12 (macOS)"
    exit 1
fi

python3 --version

# Check Ollama
echo "[2/5] Checking Ollama installation..."
if ! command -v ollama &> /dev/null; then
    echo "WARNING: Ollama not found"
    echo "Download from: https://ollama.ai"
    echo "After installing, run: ollama pull qwen2.5:7b"
    echo ""
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check/Install uv
echo "[3/5] Ensuring uv is installed..."
if ! command -v uv &> /dev/null; then
    echo "Installing uv (fast Python package manager)..."
    pip3 install uv
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install uv"
        exit 1
    fi
fi

# Create virtual environment with uv
echo "[4/5] Setting up Python environment..."
if [ ! -d ".venv" ]; then
    uv venv --python 3.12 .venv
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment"
        exit 1
    fi
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies with uv
echo "[5/5] Installing dependencies (using uv)..."
uv pip install -e .
if [ $? -ne 0 ]; then
    echo "WARNING: Some dependencies may not have installed correctly"
    echo "Attempting alternative installation..."
    pip install -e .
fi

# Initialize database
echo ""
echo "Initializing database..."
python -c "from src.core import init_database; init_database()" 2>/dev/null || true

echo ""
echo "==============================================="
echo "  SETUP COMPLETE!"
echo "==============================================="
echo ""
echo "Next steps - Run these commands in separate terminals:"
echo ""
echo "TERMINAL 1 - Start API Server:"
echo "  cd \"$SCRIPT_DIR\""
echo "  source .venv/bin/activate"
echo "  python -m uvicorn src.api.vendor_api:app --host 127.0.0.1 --port 8000 --reload"
echo ""
echo "TERMINAL 2 - Start Streamlit UI:"
echo "  cd \"$SCRIPT_DIR\""
echo "  source .venv/bin/activate"
echo "  streamlit run src/ui/app.py"
echo ""
echo "TERMINAL 3 - Start Ollama (if not running):"
echo "  ollama serve"
echo ""
echo "Then open: http://localhost:8501"
echo ""
echo "Documentation:"
echo "  - Quick Start: QUICK_START_NEW_STRUCTURE.md"
echo "  - Project Structure: PROJECT_STRUCTURE.md"
echo "  - Module Reference: MODULE_REFERENCE.md"
echo ""
