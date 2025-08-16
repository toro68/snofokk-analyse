#!/bin/bash

# FAKTISK profesjonell app - ikke kosmetikk
# Med ekte funktionalitet og substans

set -e

echo "🏔️ Starter EKTE profesjonell væraapp"
echo "====================================="

# Activate virtual environment
if [ -d ".venv" ]; then
    echo "✅ Aktiverer virtual environment..."
    source .venv/bin/activate
else
    echo "❌ Virtual environment ikke funnet!"
    exit 1
fi

APP_FILE="src/actual_professional_app.py"
PORT=8501

echo ""
echo "📋 EKTE Konfigurasjon:"
echo "   • App: $APP_FILE"
echo "   • Port: $PORT"
echo "   • Substans: EKTE værdata og analyse"
echo "   • Ikke bare: CSS og fancy ord"
echo ""

# Check if app file exists
if [ ! -f "$APP_FILE" ]; then
    echo "❌ App file ikke funnet: $APP_FILE"
    exit 1
fi

echo "🚀 Starter FAKTISK profesjonell app..."
echo "   URL: http://localhost:$PORT"
echo "   Features: Ekte værdata, reelle analyser, faktisk substans"
echo ""

# Start med enkel konfigurasjon - focus på substans, ikke styling
streamlit run "$APP_FILE" \
    --server.port=$PORT \
    --server.headless=true
