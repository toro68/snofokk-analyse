# Fil: config.py
# Kategori: Configuration

import logging
import os

import streamlit as st

# Sett opp logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Frost API konfigurasjon
FROST_STATION_ID = "SN46220"

# Forbedret feilhåndtering og logging for FROST_CLIENT_ID
try:
    # Prøv å hente fra streamlit secrets først
    FROST_CLIENT_ID = st.secrets["general"]["FROST_CLIENT_ID"]
    logger.info("FROST_CLIENT_ID funnet i Streamlit secrets")

except KeyError:
    try:
        # Hvis ikke i secrets, prøv miljøvariabel
        FROST_CLIENT_ID = os.getenv("FROST_CLIENT_ID")
        if FROST_CLIENT_ID:
            logger.info("FROST_CLIENT_ID funnet i miljøvariabler")
        else:
            logger.warning("FROST_CLIENT_ID ble ikke funnet i miljøvariabler eller secrets")
            FROST_CLIENT_ID = None
    except Exception as e:
        logger.error(f"Feil ved henting av FROST_CLIENT_ID: {str(e)}")
        FROST_CLIENT_ID = None

# Standardparametre for snøfokk-analyse
DEFAULT_PARAMS = {
    "wind_strong": 10,
    "wind_moderate": 6,
    "wind_gust": 15,
    "wind_dir_change": 30,
    "wind_weight": 0.5,
    "temp_cold": -10,
    "temp_cool": -5,
    "temp_weight": 0.3,
    "snow_high": 5,
    "snow_moderate": 2,
    "snow_low": 0.5,
    "snow_weight": 0.3,
    "min_duration": 2,
    "wind_dir_primary": 270,
    "wind_dir_tolerance": 45,
    "wind_dir_weight": 1.5,
    "min_change": 0.5,  # Standard minimumsendring
    "max_gap": 2,  # Maksimal tidsavstand i timer for sammenslåing av perioder
}

# Grenser for parametervalidering
PARAMETER_BOUNDS = {
    # Vindparametre
    "wind_strong": (5, 30),  # m/s
    "wind_moderate": (3, 20),  # m/s
    "wind_gust": (10, 40),  # m/s
    "wind_dir_change": (0, 180),  # grader
    # Temperaturparametre
    "temp_cold": (-30, 0),  # celsius
    "temp_cool": (-20, 10),  # celsius
    # Snøparametre
    "snow_high": (0.5, 5),  # mm/t
    "snow_moderate": (0.2, 3),  # mm/t
    "snow_low": (0.1, 1),  # mm/t
    # Vekter
    "wind_weight": (0, 2),  # dimensjonsløs
    "temp_weight": (0, 2),  # dimensjonsløs
    "snow_weight": (0, 2),  # dimensjonsløs
    # Ny parameter for varighet
    "min_duration": (1, 12),  # timer
    # Oppdaterte grenser for vindretningsparametre
    "wind_dir_primary": (0, 360),  # Grader
    "wind_dir_tolerance": (15, 90),  # Grader (min 15, maks 90)
    "wind_dir_weight": (0, 2),  # Dimensjonsløs
    # Legg til denne nye parameteren
    "min_change": (0.1, 5.0),  # Minimum endring for å regne som signifikant
    "max_gap": (1, 6),  # Tillatte verdier for max_gap
}


# Valider parametergrenser
def validate_parameters():
    for param, value in DEFAULT_PARAMS.items():
        if param in PARAMETER_BOUNDS:
            min_val, max_val = PARAMETER_BOUNDS[param]
            if not min_val <= value <= max_val:
                logger.warning(
                    f"Parameter {param} = {value} er utenfor grensene [{min_val}, {max_val}]"
                )
# Kjør validering ved oppstart
validate_parameters()
