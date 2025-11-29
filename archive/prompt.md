OPPGAVE: Redesign værvarslingssystem for Gullingen Skisenter

KONTEKST:
- Værstasjon: SN46220 (Gullingen, 639 moh)
- API: Frost API (Meteorologisk institutt)
- Formål: Varsle snøfokk og glattføre for skiløyper/veier

KRAV:
1. Hent historiske data (2018-2025) og lagre som JSON for analyse
2. Identifiser hvilke værelementer som faktisk er tilgjengelige
3. Bygg ML-modell basert på empiriske terskler
4. Lag ren, modulær Streamlit-app
5. Klargjør for Streamlit Cloud deployment

LEVERANSER:
1. scripts/fetch_historical_data.py - Hent og lagre historiske data
2. data/historical_weather.json - Strukturerte værdata
3. src/config.py - Sentralisert konfigurasjon
4. src/frost_client.py - Ren API-klient
5. src/analyzers/ - Modulære analysatorer
6. src/app.py - Enkel Streamlit-app
7. requirements.txt - Oppdaterte avhengigheter

KVALITETSKRAV:
- Ingen fil over 300 linjer
- Type hints på alle funksjoner
- Docstrings på alle klasser/funksjoner
- Error handling med informative meldinger
- Caching for API-kall