"""
Data models for Snøfokk application
"""
from dataclasses import dataclass
from typing import Dict, Union
from datetime import datetime
import pandas as pd

# Type aliases
WeatherData = pd.DataFrame
WeatherAnalysis = Dict[str, Union[datetime, Dict[str, float]]]

@dataclass
class SnowAnalysis:
    """Dataklasse for snøanalyse."""
    raw_depth: float
    normalized_depth: float
    confidence: float
    is_valid: bool
    change_type: str  # 'steady', 'increase', 'decrease'

@dataclass
class RiskPeriod:
    """Dataklasse for risikoperioder."""
    start_time: datetime
    end_time: datetime
    duration: float  # timer
    max_risk_score: float
    avg_risk_score: float
    conditions: Dict[str, float]  # {'wind_speed': 12.0, 'temperature': -5.0, etc}

@dataclass 
class WeatherSummary:
    """Sammendrag av værdata for en periode."""
    period_start: datetime
    period_end: datetime
    avg_temperature: float
    min_temperature: float
    max_temperature: float
    avg_wind_speed: float
    max_wind_speed: float
    total_precipitation: float
    snow_depth_change: float
    risk_periods: int
