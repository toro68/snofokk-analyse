"""Alarm System - Værvarsling for Gullingen Skisenter."""

__version__ = "2.0.0"
__author__ = "Alarm System"

from .config import settings, get_secret
from .frost_client import FrostClient, FrostAPIError, WeatherData

__all__ = [
    'settings',
    'get_secret', 
    'FrostClient',
    'FrostAPIError',
    'WeatherData',
]
