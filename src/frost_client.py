"""
Frost API-klient med caching og robust feilhåndtering.

Håndterer all kommunikasjon med Meteorologisk institutts Frost API.
"""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import pandas as pd
import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import settings

logger = logging.getLogger(__name__)


class FrostAPIError(Exception):
    """Custom exception for API-feil."""
    pass


class _FrostAPIRetryableError(Exception):
    """Internal exception used to trigger retries."""


@dataclass
class WeatherData:
    """Container for værdata med metadata."""
    df: pd.DataFrame
    station_id: str
    start_time: datetime
    end_time: datetime
    elements_fetched: list[str]

    @property
    def is_empty(self) -> bool:
        """Sjekk om data er tom."""
        return self.df is None or len(self.df) == 0

    @property
    def record_count(self) -> int:
        """Antall målinger."""
        return len(self.df) if self.df is not None else 0

    def to_json(self, filepath: str) -> None:
        """Lagre data til JSON-fil."""
        if self.is_empty:
            return

        data = {
            "metadata": {
                "station_id": self.station_id,
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat(),
                "record_count": self.record_count,
                "elements": self.elements_fetched,
                "exported_at": datetime.now(UTC).isoformat()
            },
            "observations": self.df.to_dict(orient='records')
        }

        # Konverter datetime til strings for JSON
        for obs in data["observations"]:
            if 'reference_time' in obs and isinstance(obs['reference_time'], pd.Timestamp):
                obs['reference_time'] = obs['reference_time'].isoformat()

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)


class FrostClient:
    """
    Håndterer all kommunikasjon med Frost API.

    Eksempel:
        client = FrostClient()
        data = client.fetch_recent(hours_back=24)
        print(f"Hentet {data.record_count} målinger")
    """

    # Kolonnenavn-normalisering
    COLUMN_MAPPING = {
        'sum(precipitation_amount PT1H)': 'precipitation_1h',
        'sum(precipitation_amount PT10M)': 'precipitation_10m',
        'max(wind_speed_of_gust PT1H)': 'max_wind_gust',
        'min(air_temperature PT1H)': 'temp_min_1h',
        'max(air_temperature PT1H)': 'temp_max_1h',
        'dew_point_temperature': 'dew_point_temperature',
        'surface_temperature': 'surface_temperature',
    }

    def __init__(self, station_id: str | None = None):
        """
        Initialiser klient.

        Args:
            station_id: Overstyr standard stasjon
        """
        self.station_id = station_id or settings.station.station_id
        self._validate_config()

    def _validate_config(self) -> None:
        """Valider at nødvendig konfigurasjon er på plass."""
        if not settings.api.client_id:
            raise FrostAPIError(
                "FROST_CLIENT_ID mangler.\n"
                "Lokal utvikling: Legg til i .env fil\n"
                "Streamlit Cloud: Legg til i secrets"
            )

    def fetch_recent(self, hours_back: int | None = None) -> WeatherData:
        """
        Hent data for siste N timer.

        Args:
            hours_back: Antall timer tilbake i tid (default: `settings.api.default_hours_back`)

        Returns:
            WeatherData med målinger
        """
        end_time = datetime.now(UTC)
        hours = settings.api.default_hours_back if hours_back is None else hours_back
        start_time = end_time - timedelta(hours=hours)
        return self.fetch_period(start_time, end_time)

    def fetch_period(
        self,
        start_time: datetime,
        end_time: datetime,
        elements: list[str] | None = None
    ) -> WeatherData:
        """
        Hent data for spesifikk periode.

        Args:
            start_time: Start av periode
            end_time: Slutt av periode
            elements: Spesifikke elementer å hente (default: alle)

        Returns:
            WeatherData med målinger
        """
        # Sikre UTC timezone
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=UTC)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=UTC)

        elements = elements or settings.station.all_elements()

        df = self._fetch_observations(
            start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            tuple(elements)
        )

        return WeatherData(
            df=df,
            station_id=self.station_id,
            start_time=start_time,
            end_time=end_time,
            elements_fetched=elements
        )

    def fetch_available_elements(self) -> list[str]:
        """
        Hent liste over tilgjengelige elementer for stasjonen.

        Returns:
            Liste med element-IDer
        """
        try:
            response = self._request_with_retry(
                settings.api.sources_url, params={"ids": self.station_id}
            )

            if response.status_code == 401:
                raise FrostAPIError("Ugyldig API-nøkkel (401)")
            if response.status_code == 403:
                raise FrostAPIError("Ingen tilgang til API (403). Sjekk at IP er godkjent.")

            response.raise_for_status()

            data = response.json()
            if data.get('data'):
                return data['data'][0].get('validElements', [])
            return []

        except Exception as e:
            logger.warning(f"Kunne ikke hente elementer: {e}")
            return []

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=6),
        retry=retry_if_exception_type(_FrostAPIRetryableError),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _request_with_retry(self, url: str, *, params: dict[str, str]) -> requests.Response:
        try:
            response = requests.get(
                url,
                params=params,
                auth=(settings.api.client_id, ""),
                timeout=settings.api.timeout,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            raise _FrostAPIRetryableError(str(e)) from e

        if response.status_code in {429, 500, 502, 503, 504}:
            raise _FrostAPIRetryableError(f"Frost API svarte {response.status_code}")

        return response

    @lru_cache(maxsize=100)  # noqa: B019 - bevisst caching
    def _fetch_observations(
        self,
        start_iso: str,
        end_iso: str,
        elements: tuple[str, ...]
    ) -> pd.DataFrame:
        """
        Hent observasjoner fra API (cached).

        Args:
            start_iso: ISO-format start
            end_iso: ISO-format slutt
            elements: Tuple av elementer

        Returns:
            DataFrame med observasjoner
        """
        params = {
            'sources': self.station_id,
            'elements': ','.join(elements),
            'referencetime': f"{start_iso}/{end_iso}",
            'timeresolutions': 'PT1H'
        }

        logger.info(f"Henter data: {self.station_id}, {start_iso} til {end_iso}")

        try:
            try:
                response = self._request_with_retry(settings.api.base_url, params=params)
            except _FrostAPIRetryableError as e:
                raise FrostAPIError("Midlertidig feil mot Frost API. Prøv igjen om litt.") from e

            # Håndter spesifikke feilkoder
            if response.status_code == 401:
                raise FrostAPIError("Ugyldig API-nøkkel (401)")
            elif response.status_code == 403:
                raise FrostAPIError("Ingen tilgang til API (403). Sjekk at IP er godkjent.")
            elif response.status_code == 404:
                raise FrostAPIError(f"Stasjon {self.station_id} ikke funnet (404)")
            elif response.status_code == 412:
                # Ingen data for perioden - ikke en feil
                logger.warning(f"Ingen data for perioden {start_iso} til {end_iso}")
                return pd.DataFrame()

            response.raise_for_status()

        except requests.exceptions.HTTPError as e:
            raise FrostAPIError(f"HTTP-feil: {e}") from e

        return self._parse_response(response.json())

    def _parse_response(self, data: dict) -> pd.DataFrame:
        """
        Parse API-respons til DataFrame.

        Args:
            data: JSON-respons fra API

        Returns:
            DataFrame med normaliserte kolonnenavn
        """
        if not data.get('data'):
            logger.warning("Ingen data i API-respons")
            return pd.DataFrame()

        records = []
        for obs in data['data']:
            record = {'reference_time': pd.to_datetime(obs['referenceTime'])}

            for observation in obs['observations']:
                element_id = observation['elementId']
                value = observation['value']

                # Normaliser kolonnenavn
                col_name = self.COLUMN_MAPPING.get(element_id, element_id)
                record[col_name] = value

            records.append(record)

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = df.sort_values('reference_time')
        df = df.drop_duplicates('reference_time')
        df = df.reset_index(drop=True)

        logger.info(f"Parset {len(df)} observasjoner med {len(df.columns)} kolonner")

        return df

    def clear_cache(self) -> None:
        """Tøm API-cache."""
        self._fetch_observations.cache_clear()
        logger.info("Cache tømt")
