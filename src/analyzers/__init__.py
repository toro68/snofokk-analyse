"""Væranalyse-moduler."""

from src.analyzers.base import AnalysisResult, RiskLevel, BaseAnalyzer
from src.analyzers.snowdrift import SnowdriftAnalyzer
from src.analyzers.slippery_road import SlipperyRoadAnalyzer
from src.analyzers.fresh_snow import FreshSnowAnalyzer
from src.analyzers.slaps import SlapsAnalyzer

__all__ = [
    'AnalysisResult',
    'RiskLevel',
    'BaseAnalyzer',
    'SnowdriftAnalyzer',
    'SlipperyRoadAnalyzer',
    'FreshSnowAnalyzer',
    'SlapsAnalyzer',
]
