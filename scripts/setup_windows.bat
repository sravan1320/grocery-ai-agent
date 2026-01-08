@echo off
REM Windows Setup Script for Autonomous Grocery Shopping Super-Agent
REM Uses 'uv' for fast, modern Python dependency management
REM
REM Prerequisites:
REM   - Python 3.10+ installed and in PATH
REM   - Ollama installed (https://ollama.ai)
REM   - uv installed (https://github.com/astral-sh/uv) - auto-installed if missing

setlocal enabledelayedexpansion

echo.
echo ===============================================
echo  AUTONOMOUS GROCERY SHOPPING SUPER-AGENT
echo  Windows Setup Script
echo ===============================================
echo.

REM Get project root directory (parent of scripts folder)
set SCRIPT_DIR=%~dp0..
cd /d "%SCRIPT_DIR%"

REM Check Python
echo [1/5] Checking Python installation...
python --version > nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.10+ is required but not found in PATH
    echo Download from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Check/Install uv
echo [3/5] Ensuring uv is installed...
uv --version > nul 2>&1
if errorlevel 1 (
    echo Installing uv (fast Python package manager)...
    pip install uv > nul 2>&1
    if errorlevel 1 (
        echo ERROR: Failed to install uv
        pause
        exit /b 1
    )
)

REM Create virtual environment with uv
echo [4/5] Setting up Python environment...
uv venv --python 3.12 .venv > nul 2>&1
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install dependencies with uv
echo [5/5] Installing dependencies (using uv)...
uv pip install -e . > nul 2>&1
if errorlevel 1 (
    echo WARNING: Some dependencies may not have installed correctly
    echo Attempting alternative installation...
    pip install -e . > nul 2>&1
)

REM Initialize database
echo.
echo Initializing database...
python -c "from src.core import init_database; init_database()" > nul 2>&1

echo.
echo ===============================================
echo  SETUP COMPLETE!
echo ===============================================
echo.
echo Next steps - Run these commands in separate terminals:
echo.
echo TERMINAL 1 - Start API Server:
echo   cd "%SCRIPT_DIR%"
echo   .venv\Scripts\activate.bat
echo   python -m uvicorn src.api.vendor_api:app --host 127.0.0.1 --port 8000 --reload
echo.
echo TERMINAL 2 - Start Streamlit UI:
echo   cd "%SCRIPT_DIR%"
echo   .venv\Scripts\activate.bat
echo   streamlit run src/ui/app.py
echo.
echo TERMINAL 3 - Start Ollama (if not running):
echo   ollama serve
echo.
echo Then open: http://localhost:8501
echo.
echo Documentation:
echo   - Quick Start: QUICK_START_NEW_STRUCTURE.md
echo   - Project Structure: PROJECT_STRUCTURE.md
echo   - Module Reference: MODULE_REFERENCE.md
echo.
pause
