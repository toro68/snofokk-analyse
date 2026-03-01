"""
Frost API-klient med caching og robust feilhåndtering.

Håndterer all kommunikasjon med Meteorologisk institutts Frost API.
"""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import pandas as pd
import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import get_secret, settings

logger = logging.getLogger(__name__)

CACHE_FILE = Path(__file__).parent.parent / "data" / "cache" / "frost_weather_cache.json"
def _get_cache_max_age_hours() -> float:
    try:
        return float(get_secret("FROST_CACHE_MAX_AGE_HOURS", "12"))
    except ValueError:
        return 12.0


CACHE_MAX_AGE_HOURS = _get_cache_max_age_hours()


class FrostAPIError(Exception):
    """Custom exception for API-feil."""


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
    source: str = "live"
    cache_age_hours: float | None = None

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

        observations = self.df.to_dict(orient='records')
        data = {
            "metadata": {
                "station_id": self.station_id,
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat(),
                "record_count": self.record_count,
                "elements": self.elements_fetched,
                "source": self.source,
                "exported_at": datetime.now(UTC).isoformat()
            },
            "observations": observations
        }

        # Konverter datetime til strings for JSON
        for obs in observations:
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
        # dew_point_temperature and surface_temperature need no remapping
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

        pt10m_elements = [e for e in elements if "PT10M" in e]
        hourly_elements = [e for e in elements if e not in pt10m_elements]

        try:
            df_hourly = pd.DataFrame()
            if hourly_elements:
                df_hourly = self._fetch_observations(
                    start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    tuple(hourly_elements),
                    timeresolutions="PT1H"
                )

            df_10m = pd.DataFrame()
            if pt10m_elements:
                df_10m = self._fetch_observations(
                    start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    tuple(pt10m_elements),
                    timeresolutions="PT10M"
                )

            if not df_10m.empty:
                df_10m = df_10m.copy()
                df_10m["reference_time"] = pd.to_datetime(df_10m["reference_time"], utc=True, errors="coerce")
                df_10m = df_10m.dropna(subset=["reference_time"])
                df_10m["reference_hour"] = df_10m["reference_time"].dt.floor("H")

                agg_cols = [c for c in df_10m.columns if c not in ("reference_time", "reference_hour")]
                df_10m_hourly = (
                    df_10m.sort_values("reference_time")
                    .groupby("reference_hour")[agg_cols]
                    .last()
                    .reset_index()
                    .rename(columns={"reference_hour": "reference_time"})
                )

                if df_hourly.empty:
                    df = df_10m_hourly
                else:
                    df_hourly = df_hourly.copy()
                    df_hourly["reference_time"] = pd.to_datetime(df_hourly["reference_time"], utc=True, errors="coerce")
                    df = pd.merge(df_hourly, df_10m_hourly, on="reference_time", how="outer")
                    df = df.sort_values("reference_time").drop_duplicates("reference_time").reset_index(drop=True)
            else:
                df = df_hourly
        except FrostAPIError as exc:
            cached = self._load_cache()
            if cached and not cached.is_empty:
                logger.warning("Frost API-feil (%s). Bruker cache %s", exc, CACHE_FILE)
                return cached
            raise
        except (ValueError, TypeError, KeyError) as exc:
            cached = self._load_cache()
            if cached and not cached.is_empty:
                logger.warning("Uventet feil (%s). Bruker cache %s", exc, CACHE_FILE)
                return cached
            raise

        weather_data = WeatherData(
            df=df,
            station_id=self.station_id,
            start_time=start_time,
            end_time=end_time,
            elements_fetched=elements,
            source="live"
        )

        if not weather_data.is_empty:
            self._save_cache(weather_data)

        return weather_data

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
                elements = data['data'][0].get('validElements', [])
                if isinstance(elements, list):
                    return [str(e) for e in elements]
            return []

        except (FrostAPIError, requests.exceptions.RequestException, ValueError, KeyError) as e:
            logger.warning("Kunne ikke hente elementer: %s", e)
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
        elements: tuple[str, ...],
        timeresolutions: str = "PT1H"
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
            'timeresolutions': timeresolutions
        }

        logger.info("Henter data: %s, %s til %s", self.station_id, start_iso, end_iso)

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
                logger.warning("Ingen data for perioden %s til %s", start_iso, end_iso)
                return pd.DataFrame()
            elif response.status_code == 429:
                raise FrostAPIError("Rate limit fra Frost API (429)")
            elif 500 <= response.status_code <= 599:
                raise FrostAPIError(f"Serverfeil fra Frost API ({response.status_code})")

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
            # utc=True ensures timezone-aware timestamps; avoids TypeError in
            # downstream comparisons against UTC-aware datetimes.
            record = {'reference_time': pd.to_datetime(obs['referenceTime'], utc=True)}

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

        logger.info("Parset %d observasjoner med %d kolonner", len(df), len(df.columns))

        return df

    def clear_cache(self) -> None:
        """Tøm API-cache."""
        self._fetch_observations.cache_clear()
        logger.info("Cache tømt")

    def _save_cache(self, weather_data: WeatherData) -> None:
        """Lagre siste vellykkede værdata til disk."""
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            weather_data.to_json(str(CACHE_FILE))
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("Kunne ikke lagre cache: %s", exc)

    def _load_cache(self, max_age_hours: float | None = None) -> WeatherData | None:
        """Last cached værdata fra disk."""
        try:
            if not CACHE_FILE.exists():
                return None

            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            observations = data.get("observations", [])
            if not observations:
                return None

            df = pd.DataFrame(observations)
            if "reference_time" in df.columns:
                df["reference_time"] = pd.to_datetime(df["reference_time"], utc=True, errors="coerce")
                df = df.dropna(subset=["reference_time"])
                df = df.sort_values("reference_time").drop_duplicates("reference_time").reset_index(drop=True)

            if df.empty:
                return None

            metadata = data.get("metadata", {})
            exported_at_raw = metadata.get("exported_at")
            exported_at = pd.to_datetime(exported_at_raw, utc=True, errors="coerce")
            if max_age_hours is None:
                max_age_hours = CACHE_MAX_AGE_HOURS
            cache_age_hours = None
            if not pd.isna(exported_at):
                cache_age_hours = (datetime.now(UTC) - exported_at.to_pydatetime()).total_seconds() / 3600
                if cache_age_hours > max_age_hours:
                    return None
            start_ts = pd.to_datetime(metadata.get("start_time"), utc=True, errors="coerce")
            end_ts = pd.to_datetime(metadata.get("end_time"), utc=True, errors="coerce")

            start_time = start_ts.to_pydatetime() if not pd.isna(start_ts) else df["reference_time"].iloc[0].to_pydatetime()
            end_time = end_ts.to_pydatetime() if not pd.isna(end_ts) else df["reference_time"].iloc[-1].to_pydatetime()

            elements_fetched = metadata.get("elements") or [c for c in df.columns if c != "reference_time"]

            return WeatherData(
                df=df,
                station_id=metadata.get("station_id", self.station_id),
                start_time=start_time,
                end_time=end_time,
                elements_fetched=elements_fetched,
                source="cache",
                cache_age_hours=cache_age_hours,
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("Kunne ikke lese cache: %s", exc)
            return None
