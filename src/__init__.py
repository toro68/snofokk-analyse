"""Alarm System - Værvarsling for Gullingen Skisenter."""

__version__ = "2.0.0"
__author__ = "Alarm System"

from src.config import settings, get_secret
from src.frost_client import FrostClient, FrostAPIError, WeatherData

__all__ = [
    'settings',
    'get_secret', 
    'FrostClient',
    'FrostAPIError',
    'WeatherData',
]
