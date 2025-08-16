#!/bin/bash
# Forbedret script for å kjøre weather app med mobil-støtte

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Farger for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Sjekk om vi har argumenter
MOBILE_MODE=false
DESKTOP_MODE=false
ADVANCED_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --mobile|-m)
            MOBILE_MODE=true
            shift
            ;;
        --desktop|-d)
            DESKTOP_MODE=true
            shift
            ;;
        --advanced|-a)
            ADVANCED_MODE=true
            shift
            ;;
        --help|-h)
            echo "Bruk: $0 [OPSJONER]"
            echo ""
            echo "OPSJONER:"
            echo "  --mobile, -m     Kjør mobil-optimalisert versjon"
            echo "  --advanced, -a   Kjør avansert versjon med historisk analyse"
            echo "  --desktop, -d    Kjør desktop versjon (original)"
            echo "  --help, -h       Vis denne hjelpeteksten"
            echo ""
            echo "Hvis ingen opsjon er gitt, velges avansert som standard"
            exit 0
            ;;
        *)
            echo -e "${RED}Ukjent opsjon: $1${NC}"
            echo "Bruk --help for hjelp"
            exit 1
            ;;
    esac
done

# Standard til avansert hvis ingenting er spesifisert
if [[ "$MOBILE_MODE" == false && "$DESKTOP_MODE" == false && "$ADVANCED_MODE" == false ]]; then
    ADVANCED_MODE=true
fi

echo -e "${BLUE}🌨️  Gullingen Snøfokk & Glattføre Varsling${NC}"
echo "================================================"

# Sjekk virtual environment
if [[ ! -d "$PROJECT_DIR/venv" ]]; then
    echo -e "${RED}❌ Virtual environment ikke funnet!${NC}"
    echo "Kjør først: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Aktiver virtual environment
echo -e "${YELLOW}🔧 Aktiverer virtual environment...${NC}"
source "$PROJECT_DIR/venv/bin/activate"

# Sjekk .env fil
if [[ ! -f "$PROJECT_DIR/.env" ]]; then
    echo -e "${YELLOW}⚠️  .env fil ikke funnet - oppretter eksempel...${NC}"
    if [[ -f "$PROJECT_DIR/.env.example" ]]; then
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        echo -e "${GREEN}✅ .env fil opprettet fra .env.example${NC}"
        echo -e "${YELLOW}📝 Husk å legge til din FROST_CLIENT_ID i .env${NC}"
    else
        echo -e "${RED}❌ Verken .env eller .env.example funnet!${NC}"
        echo "Opprett .env med: FROST_CLIENT_ID=din_api_nøkkel"
    fi
fi

# Sjekk dependencies
echo -e "${YELLOW}📦 Sjekker dependencies...${NC}"
if ! python -c "import streamlit" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Installerer manglende dependencies...${NC}"
    pip install -r "$PROJECT_DIR/requirements.txt"
fi

# Velg og kjør riktig versjon
if [[ "$ADVANCED_MODE" == true ]]; then
    echo -e "${GREEN}🚀 Starter avansert versjon med historisk analyse...${NC}"
    echo -e "${BLUE}💡 Nysnø-tracking • Brøyting-optimalisering • PWA-klar${NC}"
    
    # Sjekk om avansert app eksisterer
    if [[ ! -f "$PROJECT_DIR/src/advanced_mobile_app.py" ]]; then
        echo -e "${RED}❌ Avansert app ikke funnet! Kjører mobil-versjon i stedet...${NC}"
        streamlit run "$PROJECT_DIR/src/mobile_weather_app.py" --server.port 8501
    else
        # Kjør avansert versjon
        streamlit run "$PROJECT_DIR/src/advanced_mobile_app.py" \
            --server.port 8501 \
            --server.address localhost \
            --browser.gatherUsageStats false \
            --browser.serverAddress localhost \
            --server.enableCORS false \
            --server.enableXsrfProtection false \
            --logger.level warning
    fi

elif [[ "$MOBILE_MODE" == true ]]; then
    echo -e "${GREEN}📱 Starter mobil-optimalisert versjon...${NC}"
    echo -e "${BLUE}💡 Optimalisert for telefon og nettbrett${NC}"
    
    # Sjekk om mobil-komponenter eksisterer
    if [[ ! -f "$PROJECT_DIR/src/mobile_weather_app.py" ]]; then
        echo -e "${RED}❌ Mobil-app ikke funnet! Kjører desktop-versjon i stedet...${NC}"
        streamlit run "$PROJECT_DIR/src/live_conditions_app.py" --server.port 8501
    else
        # Kjør mobil-versjon med mobil-optimaliserte innstillinger
        streamlit run "$PROJECT_DIR/src/mobile_weather_app.py" \
            --server.port 8501 \
            --server.address localhost \
            --browser.gatherUsageStats false \
            --browser.serverAddress localhost \
            --server.enableCORS false \
            --server.enableXsrfProtection false \
            --logger.level warning
    fi
    
elif [[ "$DESKTOP_MODE" == true ]]; then
    echo -e "${GREEN}🖥️  Starter desktop versjon...${NC}"
    echo -e "${BLUE}💡 Full funksjonalitet for store skjermer${NC}"
    
    streamlit run "$PROJECT_DIR/src/live_conditions_app.py" \
        --server.port 8501
fi

echo ""
echo -e "${GREEN}🚀 Appen starter på: ${BLUE}http://localhost:8501${NC}"
echo -e "${YELLOW}💡 Tips: Legg til som favoritt på mobil for app-lignende opplevelse${NC}"
echo ""
echo -e "${BLUE}📱 For beste mobil-opplevelse:${NC}"
echo "   • Åpne i Safari/Chrome på mobil"
echo "   • Trykk 'Del' -> 'Legg til på hjemskjerm'"
echo "   • Bruk som native app!"
echo ""
echo -e "${GREEN}🆕 NYE FUNKSJONER I AVANSERT VERSJON:${NC}"
echo "   📊 Historisk væranalyse (opptil 14 dager)"
echo "   ❄️  Nysnø-beregning og -klassifisering"
echo "   🚜 Brøyting-tracking med anbefalinger"
echo "   📈 Interaktive Plotly-charts"
echo "   💾 Eksport til CSV/JSON/Rapport"
echo "   🎯 Risiko-tidslinjer"
