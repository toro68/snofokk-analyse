# API konfigurasjon
import streamlit as st

# Frost API konfigurasjon
FROST_STATION_ID = "SN44560"

# Standardparametre for snøfokk-analyse
DEFAULT_PARAMS = {'wind_strong': 10.61,
'wind_moderate': 7.77,
'wind_gust': 16.96,
'wind_dir_change': 37.83,
'wind_weight': 1.65,
'temp_cold': -2.20,
'temp_cool': 0.0,
'temp_weight': 1.20,
'snow_high': 1.61,
'snow_moderate': 0.84,
'snow_low': 0.31,
'snow_weight': 1.15,
'min_duration': 2}

# Hent FROST_CLIENT_ID fra Streamlit secrets
try:
    FROST_CLIENT_ID = st.secrets["FROST_CLIENT_ID"]
except Exception as e:
    print(f"ADVARSEL: Kunne ikke hente FROST_CLIENT_ID fra secrets: {str(e)}")
    print("Sørg for at FROST_CLIENT_ID er satt i .streamlit/secrets.toml")
    FROST_CLIENT_ID = None
    