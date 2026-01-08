#!/usr/bin/env bash

# DO NOT EXIT ON ERROR (important for debugging)
set +e

echo "==============================="
echo " Grocery Agent Setup (DEBUG)"
echo "==============================="

# -------- Detect HOME correctly --------
HOME_DIR="${HOME:-/c/Users/$(whoami)}"

UV_BIN_LOCAL="$HOME_DIR/.local/bin"
UV_BIN_CARGO="$HOME_DIR/.cargo/bin"

# -------- Fix PATH --------
export PATH="$UV_BIN_LOCAL:$UV_BIN_CARGO:$PATH"

echo "[INFO] HOME_DIR=$HOME_DIR"
echo "[INFO] PATH=$PATH"

# -------- Check uv --------
if command -v uv >/dev/null 2>&1; then
  echo "[OK] uv found: $(command -v uv)"
  uv --version
else
  echo "[WARN] uv not found, installing..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$UV_BIN_LOCAL:$UV_BIN_CARGO:$PATH"
fi

# -------- Verify uv again --------
echo "[CHECK] uv path:"
command -v uv
uv --version

# -------- Create venv --------
echo "[STEP] Creating virtual environment..."
uv venv .venv

# -------- Activate venv --------
echo "[STEP] Activating virtual environment..."
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
  source .venv/Scripts/activate
else
  echo "[ERROR] Could not find activate script"
fi

# -------- Install deps --------
echo "[STEP] Installing dependencies..."
uv pip install -e .

# -------- Done --------
echo "==============================="
echo " Setup finished (DEBUG MODE)"
echo "==============================="

echo
echo "Press ENTER to close this window..."
read
