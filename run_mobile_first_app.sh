#!/bin/bash
# Script for å kjøre den nye mobile-first værappen

echo "🚀 Starter Mobil-First Værapp for Gullingen..."
echo ""
echo "📱 PRIORITERING:"
echo "   1. 🆕 Nysnø"
echo "   2. 🧊 Glatte veier"
echo "   3. 🌪️ Snøfokk"
echo ""

# Aktiver python environment hvis det finnes
if [ -f "venv/bin/activate" ]; then
    echo "📦 Aktiverer virtual environment..."
    source venv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
    echo "📦 Aktiverer virtual environment..."
    source .venv/bin/activate
fi

# Sjekk om .env filen finnes
if [ ! -f ".env" ]; then
    echo "⚠️  .env fil mangler!"
    echo "   Opprett .env med: FROST_CLIENT_ID=din_api_nøkkel"
    echo "   Registrer deg på frost.met.no for å få API-nøkkel"
    echo ""
fi

# Sjekk dependencies
echo "🔍 Sjekker dependencies..."
python -c "import streamlit, pandas, requests" 2>/dev/null || {
    echo "❌ Mangler dependencies. Installer med:"
    echo "   pip install streamlit pandas requests python-dotenv"
    echo ""
    exit 1
}

echo "✅ Dependencies OK"
echo ""
echo "🌐 Starter Streamlit app..."
echo "   📱 Mobil-optimalisert design"
echo "   ⚡ Rask lasting med caching"
echo "   🔄 Auto-refresh"
echo ""

# Start streamlit app
streamlit run mobile_first_weather_app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false \
    --theme.base light \
    --theme.primaryColor "#ff4757" \
    --theme.backgroundColor "#ffffff" \
    --theme.secondaryBackgroundColor "#f8f9fa"
