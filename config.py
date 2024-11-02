# Fil: config.py
# Kategori: Configuration

import streamlit as st
import os

# Frost API konfigurasjon
FROST_STATION_ID = "SN44560"

# Prøv å hente FROST_CLIENT_ID fra ulike kilder
try:
    # Først prøv å hente fra miljøvariabel
    FROST_CLIENT_ID = os.getenv('FROST_CLIENT_ID')
    
    # Hvis ikke funnet, prøv streamlit secrets
    if not FROST_CLIENT_ID:
        FROST_CLIENT_ID = st.secrets.get("FROST_CLIENT_ID")
        
    # Logg resultatet
    if FROST_CLIENT_ID:
        print(f"FROST_CLIENT_ID funnet: {FROST_CLIENT_ID[:8]}...")
    else:
        print("ADVARSEL: FROST_CLIENT_ID ikke funnet")
        
except Exception as e:
    print(f"ADVARSEL: Kunne ikke hente FROST_CLIENT_ID: {str(e)}")
    FROST_CLIENT_ID = None

# Standardparametre for snøfokk-analyse
DEFAULT_PARAMS = {
    'wind_strong': 10.61,
    'wind_moderate': 7.77,
    'wind_gust': 16.96,
    'wind_dir_change': 37.83,
    'wind_weight': 1.65,
    'temp_cold': -2.2,
    'temp_cool': 0,
    'temp_weight': 1.2,
    'snow_high': 1.61,
    'snow_moderate': 0.84,
    'snow_low': 0.31,
    'snow_weight': 1.15,
    'min_duration': 2
}