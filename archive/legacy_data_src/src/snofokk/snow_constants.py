"""
LÅST KONFIGURASJON FOR SNØDYBDEHÅNDTERING
"""

import logging
from functools import wraps
from typing import Any

import numpy as np
import pandas as pd

# Sett opp logging med mer detaljert konfigurasjon
logger = logging.getLogger("data.src.snofokk.snow_constants")
logger.setLevel(logging.INFO)

# Fjern alle eksisterende handlers
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Opprett en formatter for loggmeldinger
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# Legg til console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Legg til file handler for å lagre logger til fil
file_handler = logging.FileHandler("snow_processing.log")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Unngå propagering til root logger
logger.propagate = False


def enforce_snow_processing(func):
    """Dekoratør for å sikre korrekt snødatabehandling"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            logger.debug(f"Starter snødatabehandling med {func.__name__}")
            result = func(*args, **kwargs)
            if result is None:
                raise ValueError("Funksjonen returnerte None")
            return result
        except Exception as e:
            logger.error(f"Feil i snødatabehandling: {str(e)}", exc_info=True)
            raise

    return wrapper


def get_risk_level(risk_score: float) -> str:
    """
    Konverterer en numerisk risikoscore til et tekstbasert risikonivå.

    Args:
        risk_score (float): Risikoscore mellom 0 og 1

    Returns:
        str: Risikonivå som tekst ('Lav', 'Moderat', 'Høy', eller 'Kritisk')
    """
    try:
        # Valider input
        if not isinstance(risk_score, int | float):
            logger.error(f"Ugyldig risikoscore type: {type(risk_score)}")
            return "Ukjent"

        # Normaliser score til 0-1 intervall
        score = max(0, min(1, float(risk_score)))

        # Definer grenser for ulike risikonivåer
        if score < 0.3:
            return "Lav"
        elif score < 0.5:
            return "Moderat"
        elif score < 0.7:
            return "Høy"
        else:
            return "Kritisk"

    except Exception as e:
        logger.error(f"Feil i get_risk_level: {str(e)}")
        return "Ukjent"


class SnowDepthConfig:
    # Grunnleggende konfigurasjon
    MIN_VALID_DEPTH: float = -1.0
    MAX_VALID_DEPTH: float = 1000.0
    INTERPOLATION_LIMIT: int = 24
    FFILL_LIMIT: int = 48
    BFILL_LIMIT: int = 48
    WINDOW_SIZE: int = 3
    MIN_PERIODS: int = 1
    MIN_CHANGE: float = -10.0
    MAX_CHANGE: float = 10.0

    @classmethod
    def get_processing_config(cls) -> dict[str, Any]:
        """Henter prosesseringskonfigurasjon"""
        return {
            "min_valid": cls.MIN_VALID_DEPTH,
            "max_valid": cls.MAX_VALID_DEPTH,
            "interpolation_limit": cls.INTERPOLATION_LIMIT,
            "ffill_limit": cls.FFILL_LIMIT,
            "bfill_limit": cls.BFILL_LIMIT,
            "window": cls.WINDOW_SIZE,
            "min_periods": cls.MIN_PERIODS,
            "method": "linear",
            "min_change": cls.MIN_CHANGE,
            "max_change": cls.MAX_CHANGE,
        }

    @classmethod
    def process_snow_depth(cls, snow_df: pd.Series) -> pd.Series:
        """Prosesserer snødybdedata."""
        try:
            snow_depth = pd.to_numeric(snow_df, errors="coerce")
            snow_depth = snow_depth.replace(-1.0, 0.0)
            snow_depth = snow_depth.mask(
                (snow_depth < cls.MIN_VALID_DEPTH) | (snow_depth > cls.MAX_VALID_DEPTH)
            )

            logger.info("=== Snødybdeprosessering ===")
            logger.info(f"Prosessert {len(snow_depth)} målinger")
            logger.info(
                f"Filtrert: {len(snow_depth) - snow_depth.count()} målinger fjernet"
            )

            return snow_depth

        except Exception as e:
            logger.error(f"Feil i snødatabehandling: {str(e)}", exc_info=True)
            raise

    @classmethod
    def validate_snow_depth(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Validerer snødybdedata
        """
        if not isinstance(df, pd.DataFrame):
            logger.error("Inndata må være pandas DataFrame")
            raise TypeError("Inndata må være pandas DataFrame")

        if df.empty:
            logger.error("Tom dataserie mottatt")
            raise ValueError("Kan ikke prosessere tom dataserie")

        logger.info("=== Start snødybdevalidering ===")
        logger.info(f"Inndata: {len(df)} målinger")
        logger.debug(f"Konfigurasjon: {cls.get_processing_config()}")

        data = df.copy()
        invalid_mask = (data < cls.MIN_VALID_DEPTH) | (data > cls.MAX_VALID_DEPTH)
        invalid_count = invalid_mask.sum().sum()

        if invalid_count.any() > 0:
            logger.warning(
                f"Fant {invalid_count.any()} ugyldige målinger "
                f"({(invalid_count.any()/len(df))*100:.1f}% av datasettet)"
            )

        data[invalid_mask] = np.nan

        validated_data = (
            data.interpolate(method="linear", limit=cls.INTERPOLATION_LIMIT)
            .ffill(limit=cls.FFILL_LIMIT)
            .bfill(limit=cls.BFILL_LIMIT)
            .fillna(0)
        )

        logger.info(f"Validering fullført. Utdata: {len(validated_data)} målinger")
        logger.info("=== Slutt snødybdevalidering ===")
        return validated_data


# Eksporter både klassen og dekoratøren
__all__ = ["SnowDepthConfig", "enforce_snow_processing", "get_risk_level"]
