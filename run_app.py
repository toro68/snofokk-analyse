"""
Entry point for the Snøfokk application.
This file sets up the Python path and starts the Streamlit app.
"""
import sys
from pathlib import Path

# Legg til data/src i Python path
sys.path.append(str(Path(__file__).parent / "data" / "src"))

# Import og kjør appen

from snofokk.app import main

if __name__ == "__main__":
    main()
