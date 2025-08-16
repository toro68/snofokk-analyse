#!/bin/bash
# Forbedret kjøreskript for Streamlit Admin/Analysis UI
# Port 8501 for admin/desktop bruk

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🏔️ Starter Streamlit Admin/Analysis UI for Føreforhold"
echo "=================================================="

# Activate virtual environment
if [ -d "$PROJECT_DIR/.venv" ]; then
    echo "✅ Aktiverer virtual environment (.venv)..."
    source "$PROJECT_DIR/.venv/bin/activate"
elif [ -d "$PROJECT_DIR/venv" ]; then
    echo "✅ Aktiverer virtual environment (venv)..."
    source "$PROJECT_DIR/venv/bin/activate"
else
    echo "⚠️  Ingen virtual environment funnet, bruker system Python"
fi

# Sjekk om Streamlit er installert
if ! command -v streamlit &> /dev/null; then
    echo "❌ Streamlit ikke funnet. Installer med: pip install streamlit"
    exit 1
fi

# Sett miljøvariabler for optimal ytelse
export STREAMLIT_SERVER_PORT=8501
export STREAMLIT_SERVER_HEADLESS=true
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
export STREAMLIT_SERVER_ENABLE_STATIC_SERVING=true

# Sjekk om .env fil eksisterer
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "⚠️  .env fil ikke funnet. Noen funksjoner kan være begrenset."
fi

# Vis konfigurasjon
echo ""
echo "📋 Konfigurasjon:"
echo "   • Port: 8501 (Admin/Desktop)"
echo "   • App: enhanced_streamlit_app.py"
echo "   • Cache: Aktivert med TTL"
echo "   • PWA: Desktop-optimalisert"
echo ""

# Kjør appen
echo "🚀 Starter applikasjon..."
echo "   Tilgjengelig på: http://localhost:8501"
echo "   Stopp med: Ctrl+C"
echo ""

cd "$PROJECT_DIR"

# Kjør Streamlit med optimale innstillinger
streamlit run src/enhanced_streamlit_app.py \
    --server.port 8501 \
    --server.headless false \
    --browser.gatherUsageStats false \
    --runner.magicEnabled true
