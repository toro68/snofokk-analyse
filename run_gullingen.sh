#!/bin/bash
# Start Gullingen Føreforhold-appen

cd "$(dirname "$0")"
source venv/bin/activate

echo "🚀 Starter Føreforhold Gullingen..."
echo "   URL: http://localhost:8501"
echo ""

streamlit run src/gullingen_app.py --server.headless true
