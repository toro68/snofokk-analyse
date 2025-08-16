# Fil: config.py
# Kategori: Configuration

import os

import streamlit as st
from dotenv import load_dotenv

# Last inn .env-filen
load_dotenv()

# Frost API konfigurasjon
FROST_STATION_ID = "SN46220"

# Prøv å hente FROST_CLIENT_ID fra ulike kilder
try:
    # Først prøv å hente fra miljøvariabel
    FROST_CLIENT_ID = os.getenv('FROST_CLIENT_ID')
    print(f"Prøver å hente fra miljøvariabel: {FROST_CLIENT_ID}")

    # Hvis ikke funnet, prøv streamlit secrets
    if not FROST_CLIENT_ID:
        FROST_CLIENT_ID = st.secrets.get("FROST_CLIENT_ID")
        print(f"Prøver å hente fra streamlit secrets: {FROST_CLIENT_ID}")

    # Logg resultatet
    if FROST_CLIENT_ID:
        print(f"FROST_CLIENT_ID funnet: {FROST_CLIENT_ID[:8]}...")
        print(f"API-nøkkel lengde: {len(FROST_CLIENT_ID)}")
        print(f"API-nøkkel bytes: {FROST_CLIENT_ID.encode()}")
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
    'wind_weight': 0.4,
    'temp_cold': -2.2,
    'temp_cool': 0,
    'temp_weight': 0.3,
    'snow_high': 1.61,
    'snow_moderate': 0.84,
    'snow_low': 0.31,
    'snow_weight': 0.3,
    'min_duration': 2
}

# Parameterområder for optimalisering
PARAM_RANGES = {
    'wind_strong': (8.0, 15.0),
    'wind_moderate': (5.0, 10.0),
    'wind_gust': (12.0, 20.0),
    'wind_dir_change': (20.0, 45.0),
    'wind_weight': (0.3, 0.5),
    'temp_cold': (-5.0, -1.0),
    'temp_cool': (-2.0, 2.0),
    'temp_weight': (0.2, 0.4),
    'snow_high': (1.0, 2.0),
    'snow_moderate': (0.5, 1.5),
    'snow_low': (0.2, 0.8),
    'snow_weight': (0.2, 0.4),
    'min_duration': (2, 4)
}

# Frost API elementer som skal hentes
FROST_ELEMENTS = [
    'air_temperature',
    'surface_snow_thickness',
    'wind_speed',
    'wind_from_direction',
    'relative_humidity',
    'max(wind_speed_of_gust PT1H)',
    'max(wind_speed PT1H)',
    'min(air_temperature PT1H)',
    'max(air_temperature PT1H)',
    'sum(duration_of_precipitation PT1H)',
    'sum(precipitation_amount PT1H)',
    'dew_point_temperature'
]
