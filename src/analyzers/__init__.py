"""Væranalyse-moduler."""

from src.analyzers.base import AnalysisResult, BaseAnalyzer, RiskLevel
from src.analyzers.fresh_snow import FreshSnowAnalyzer
from src.analyzers.slaps import SlapsAnalyzer
from src.analyzers.slippery_road import SlipperyRoadAnalyzer
from src.analyzers.snowdrift import SnowdriftAnalyzer

__all__ = [
    'AnalysisResult',
    'RiskLevel',
    'BaseAnalyzer',
    'SnowdriftAnalyzer',
    'SlipperyRoadAnalyzer',
    'FreshSnowAnalyzer',
    'SlapsAnalyzer',
]
