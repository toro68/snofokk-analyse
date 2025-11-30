"""
Weather data service for fetching and processing data from Frost API
"""
import logging
from functools import lru_cache

import numpy as np
import pandas as pd
import requests

from ..config import settings
from ..models import WeatherData

logger = logging.getLogger(__name__)

class WeatherService:
    """Service for fetching and caching weather data from Frost API"""

    def __init__(self):
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Snofokk-Analyse/2.0.0'
        })
        return session

    @lru_cache(maxsize=32)  # noqa: B019 - bevisst caching
    def fetch_weather_data(
        self,
        station: str,
        from_time: str,
        to_time: str,
        client_id: str
    ) -> WeatherData | None:
        """Fetch weather data from Frost API with caching"""

        elements = [
            'air_temperature',
            'relative_humidity',
            'wind_speed',
            'wind_from_direction',
            'surface_snow_thickness',
            'sum(precipitation_amount PT1H)',
            'surface_temperature',
            'dew_point_temperature',
            'max(wind_speed PT1H)',
            'min(air_temperature PT1H)',
            'max(air_temperature PT1H)'
        ]

        params = {
            'sources': station,
            'elements': ','.join(elements),
            'referencetime': f"{from_time}/{to_time}"
        }

        try:
            response = self.session.get(
                'https://frost.met.no/observations/v0.jsonld',
                params=params,
                auth=(client_id, ''),
                timeout=30
            )

            response.raise_for_status()
            data = response.json()

            if not data.get('data'):
                logger.warning("No data received from Frost API")
                return None

            # Convert to DataFrame
            df = pd.json_normalize(
                data['data'],
                ['observations'],
                ['referenceTime']
            )

            df = df.pivot_table(
                index='referenceTime',
                columns='elementId',
                values='value',
                aggfunc='first'
            ).reset_index()

            # Convert to Oslo timezone
            df['referenceTime'] = pd.to_datetime(df['referenceTime'])
            df['referenceTime'] = df['referenceTime'].dt.tz_convert(settings.tz)

            return df

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing weather data: {e}")
            return None

    def normalize_snow_data(self, df: WeatherData) -> WeatherData:
        """Normalize and clean snow depth data"""
        if 'surface_snow_thickness' not in df.columns:
            return df

        df = df.copy()

        # Replace invalid values
        df['surface_snow_thickness'] = df['surface_snow_thickness'].replace(-1, np.nan)

        # Remove outliers (negative values except -1, extremely high values)
        mask = (df['surface_snow_thickness'] < 0) | (df['surface_snow_thickness'] > 1000)
        df.loc[mask, 'surface_snow_thickness'] = np.nan

        # Interpolate missing values
        df['surface_snow_thickness'] = df['surface_snow_thickness'].interpolate(
            method='linear',
            limit=24  # Max 24 timer interpolering
        )

        # Apply rolling average to smooth data
        df['surface_snow_thickness'] = df['surface_snow_thickness'].rolling(
            window=settings.rolling_window,
            min_periods=1,
            center=True
        ).mean()

        return df

# Global weather service instance
weather_service = WeatherService()
