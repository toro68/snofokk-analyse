"""Alarm System - Værvarsling for Gullingen Skisenter."""

__version__ = "2.0.0"
__author__ = "Alarm System"

from .config import get_secret, settings
from .frost_client import FrostAPIError, FrostClient, WeatherData

__all__ = [
    'settings',
    'get_secret',
    'FrostClient',
    'FrostAPIError',
    'WeatherData',
]
