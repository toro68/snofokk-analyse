#!/bin/bash

# Professional Streamlit App Runner
# Weather Analysis Pro - Enterprise Grade

set -e

echo "🏢 Starting Weather Analysis Pro"
echo "======================================"

# Activate virtual environment
if [ -d ".venv" ]; then
    echo "✅ Activating virtual environment (.venv)..."
    source .venv/bin/activate
else
    echo "❌ Virtual environment not found!"
    echo "Please create one with: python -m venv .venv"
    exit 1
fi

# Configuration
PORT=8501
APP_FILE="src/professional_streamlit_app.py"

echo ""
echo "📋 Configuration:"
echo "   • Port: $PORT (Professional UI)"
echo "   • App: $APP_FILE"
echo "   • Mode: Production Ready"
echo "   • UI: Enterprise Grade"
echo ""

# Check if app file exists
if [ ! -f "$APP_FILE" ]; then
    echo "❌ App file not found: $APP_FILE"
    exit 1
fi

echo "🚀 Starting Professional UI..."
echo "   Available at: http://localhost:$PORT"
echo "   Stop with: Ctrl+C"
echo ""

# Start Streamlit with professional configuration
streamlit run "$APP_FILE" \
    --server.port=$PORT \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --theme.base="light" \
    --theme.primaryColor="#2c3e50" \
    --theme.backgroundColor="#ffffff" \
    --theme.secondaryBackgroundColor="#ecf0f1" \
    --theme.textColor="#2c3e50"
