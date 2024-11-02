"""
LÅST KONFIGURASJON FOR SNØDYBDEHÅNDTERING
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
from functools import wraps
import logging

# Sett opp logging med mer detaljert konfigurasjon
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Opprett en formatter for loggmeldinger
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Legg til console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Legg til file handler for å lagre logger til fil
file_handler = logging.FileHandler('snow_processing.log')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

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
    def get_processing_config(cls) -> Dict[str, Any]:
        """Henter prosesseringskonfigurasjon"""
        return {
            'min_valid': cls.MIN_VALID_DEPTH,
            'max_valid': cls.MAX_VALID_DEPTH,
            'interpolation_limit': cls.INTERPOLATION_LIMIT,
            'ffill_limit': cls.FFILL_LIMIT,
            'bfill_limit': cls.BFILL_LIMIT,
            'window': cls.WINDOW_SIZE,
            'min_periods': cls.MIN_PERIODS,
            'method': 'linear',
            'min_change': cls.MIN_CHANGE,
            'max_change': cls.MAX_CHANGE
        }
    
    @classmethod
    def process_snow_depth(cls, snow_data: pd.Series) -> pd.Series:
        """Prosesserer snødybdedata med standardiserte metoder"""
        if not isinstance(snow_data, pd.Series):
            logger.error("Inndata må være pandas Series")
            raise TypeError("Inndata må være pandas Series")
        
        if snow_data.empty:
            logger.error("Tom dataserie mottatt")
            raise ValueError("Kan ikke prosessere tom dataserie")
        
        logger.info("=== Start snødybdeprosessering ===")
        logger.info(f"Inndata: {len(snow_data)} målinger")
        logger.debug(f"Konfigurasjon: {cls.get_processing_config()}")
        
        data = snow_data.copy()
        invalid_mask = (data < cls.MIN_VALID_DEPTH) | (data > cls.MAX_VALID_DEPTH)
        invalid_count = invalid_mask.sum()
        
        if invalid_count > 0:
            logger.warning(
                f"Fant {invalid_count} ugyldige målinger "
                f"({(invalid_count/len(snow_data))*100:.1f}% av datasettet)"
            )
        
        data[invalid_mask] = np.nan
        
        processed_data = (
            data
            .interpolate(method='linear', limit=cls.INTERPOLATION_LIMIT)
            .ffill(limit=cls.FFILL_LIMIT)
            .bfill(limit=cls.BFILL_LIMIT)
            .fillna(0)
        )
        
        logger.info(f"Prosessering fullført. Utdata: {len(processed_data)} målinger")
        logger.info("=== Slutt snødybdeprosessering ===")
        return processed_data

# Eksporter både klassen og dekoratøren
__all__ = ['SnowDepthConfig', 'enforce_snow_processing'] 