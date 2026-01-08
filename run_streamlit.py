#!/usr/bin/env python
"""
Wrapper to run Streamlit app with proper path setup
"""
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Now run streamlit
import streamlit.cli as stcli

sys.argv = ["streamlit", "run", str(Path(__file__).parent / "src" / "ui" / "app.py")]
stcli.main()
