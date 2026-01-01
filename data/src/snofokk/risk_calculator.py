import pandas as pd
import numpy as np
import logging
from typing import Tuple, Dict, Any

logger = logging.getLogger(__name__)

def calculate_snow_drift_risk(df: pd.DataFrame, params: Dict[str, Any]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Beregner snøfokk-risiko"""
    df = df.copy()
    
    required_features = [
        # Temperatur
        'air_temperature',
        'min(air_temperature PT1H)',
        'max(air_temperature PT1H)',
        
        # Vind
        'wind_speed',
        'wind_from_direction',
        'max(wind_speed_of_gust PT1H)',
        'max(wind_speed PT1H)',
        
        # Snø og fuktighet
        'surface_snow_thickness',
        'relative_humidity'
    ]
    
    # Sjekk at alle nødvendige features finnes
    missing_features = [f for f in required_features if f not in df.columns]
    if missing_features:
        logger.warning(f"Manglende features: {missing_features}")
        for feature in missing_features:
            df[feature] = 0  # Sett standardverdi
    
    # Beregn deriverte features
    df['snow_depth_change'] = df['surface_snow_thickness'].diff()
    df['sustained_wind'] = df['wind_speed'].rolling(window=2).mean()
    df['wind_dir_change'] = df['wind_from_direction'].diff().abs()
    df['wind_stability'] = df['wind_speed'].rolling(window=6).std()
    
    # Beregn risikoscore og legg til i dataframe
    df['risk_score'] = df.apply(lambda row: calculate_risk_score(row, params), axis=1)
    
    # Legg til risk_level basert på systemanalysen
    df['risk_level'] = df['risk_score'].apply(lambda score: 
        'Kritisk' if score >= 0.8 else
        'Høy' if score >= 0.6 else
        'Moderat' if score >= 0.4 else
        'Lav'
    )
    
    # Identifiser risikoperioder med terskel fra params
    risk_periods = identify_risk_periods(df, params.get('risk_threshold', 0.7))
    
    return df, risk_periods

def calculate_risk_score(row: pd.Series, params: Dict[str, Any]) -> float:
    """Beregner risikoscore for én observasjon"""
    try:
        score = 0.0
        
        # Vindrisiko med stabilitetsvurdering
        if row["wind_speed"] >= params["wind_strong"]:
            wind_factor = 40
            # Øk risiko ved ustabil vind
            if "wind_stability" in row and row["wind_stability"] > 3:
                wind_factor *= 1.2
            score += wind_factor * params.get("wind_weight", 1.0)
        elif row["wind_speed"] >= params["wind_moderate"]:
            score += 20 * params.get("wind_weight", 1.0)

        # Vindkast-risiko
        if ("max(wind_speed_of_gust PT1H)" in row 
            and row["max(wind_speed_of_gust PT1H)"] >= params["wind_gust"]):
            score += 10 * params.get("wind_weight", 1.0)

        # Vindretningsrisiko
        if "wind_dir_change" in row and row["wind_dir_change"] >= params["wind_dir_change"]:
            dir_factor = min(20, row["wind_dir_change"] / 9)
            score += dir_factor * params.get("wind_weight", 1.0)

        # Temperaturrisiko
        if row["air_temperature"] <= params.get("temp_cold", -10):
            score += 20 * params.get("temp_weight", 1.0)
        elif row["air_temperature"] <= params.get("temp_cool", -5):
            temp_factor = (params["temp_cool"] - row["air_temperature"]) / (
                params["temp_cool"] - params["temp_cold"]
            )
            score += 10 * temp_factor * params.get("temp_weight", 1.0)

        return min(100, max(0, score)) / 100  # Normaliser til 0-1

    except Exception as e:
        logger.error(f"Feil i calculate_risk_score: {str(e)}")
        return 0.0

def identify_risk_periods(df: pd.DataFrame, threshold: float = 50) -> pd.DataFrame:
    """Identifiserer sammenhengende perioder med høy risiko"""
    risk_periods = pd.DataFrame()
    high_risk = df['risk_score'] >= threshold
    
    if high_risk.any():
        risk_periods['start_time'] = df.index[high_risk & ~high_risk.shift(1).fillna(False)]
        risk_periods['end_time'] = df.index[high_risk & ~high_risk.shift(-1).fillna(False)]
        risk_periods['max_risk'] = [df.loc[s:e, 'risk_score'].max() 
                                  for s, e in zip(risk_periods['start_time'], 
                                                risk_periods['end_time'])]
    
    return risk_periods 