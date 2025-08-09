#!/bin/bash
# Simple script to run the live conditions app with venv activated

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate virtual environment
source "$PROJECT_DIR/venv/bin/activate"

# Run the app
echo "Starting Gullingen Live Conditions App..."
streamlit run "$PROJECT_DIR/src/live_conditions_app.py"
