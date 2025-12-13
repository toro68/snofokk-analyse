#!/bin/bash
# Script to always activate the virtual environment for this project

# Get the project directory (where this script is located)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if virtual environment exists
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "Virtual environment not found. Creating..."
    cd "$PROJECT_DIR"
    python3 -m venv venv
    echo "Virtual environment created."
fi

# Activate the virtual environment
echo "Activating virtual environment..."
source "$PROJECT_DIR/venv/bin/activate"

# Install/update requirements
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    echo "Installing/updating requirements..."
    pip install -r "$PROJECT_DIR/requirements.txt"
fi

echo "Virtual environment activated and ready!"
echo "You can now run: streamlit run app.py"
