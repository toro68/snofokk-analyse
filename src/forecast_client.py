"""MET Locationforecast-klient for korttidsprognose."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import logging

import requests

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ForecastPoint:
    """Én prognose-observasjon."""

    reference_time: datetime
    air_temperature: float | None = None
    wind_speed: float | None = None
    wind_gust: float | None = None
    precipitation_1h: float | None = None


class ForecastClientError(Exception):
    """Feil ved henting/parsing av prognose."""


class ForecastClient:
    """Klient for MET locationforecast."""

    USER_AGENT = "snofokk-analyse/1.0 (github.com/toro68/snofokk-analyse)"

    def fetch_hourly_forecast(self, *, lat: float, lon: float, hours: int | None = None) -> list[ForecastPoint]:
        """Hent timeprognose for koordinat."""
        url = settings.api.met_forecast_url
        timeout = settings.api.forecast_timeout_seconds
        horizon_hours = settings.api.forecast_hours if hours is None else max(1, int(hours))

        params = {
            "lat": f"{lat:.5f}",
            "lon": f"{lon:.5f}",
        }
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json",
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ForecastClientError(f"Kunne ikke hente prognose: {exc}") from exc

        timeseries = payload.get("properties", {}).get("timeseries", [])
        if not isinstance(timeseries, list) or not timeseries:
            raise ForecastClientError("Prognose inneholder ingen timeseries-data")

        now_utc = datetime.now(UTC)
        points: list[ForecastPoint] = []

        for item in timeseries:
            if len(points) >= horizon_hours:
                break

            time_raw = item.get("time")
            if not time_raw:
                continue

            try:
                ts = datetime.fromisoformat(str(time_raw).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                else:
                    ts = ts.astimezone(UTC)
            except ValueError:
                continue

            if ts < now_utc:
                continue

            data = item.get("data", {})
            instant = data.get("instant", {}).get("details", {})
            next_1h = data.get("next_1_hours", {}).get("details", {})

            points.append(
                ForecastPoint(
                    reference_time=ts,
                    air_temperature=_safe_float(instant.get("air_temperature")),
                    wind_speed=_safe_float(instant.get("wind_speed")),
                    wind_gust=_safe_float(instant.get("wind_speed_of_gust")),
                    precipitation_1h=_safe_float(next_1h.get("precipitation_amount")),
                )
            )

        if not points:
            raise ForecastClientError("Fant ingen fremtidige prognosepunkter")

        return points


def _safe_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
