"""src.plowman_client

Klient for å hente «siste brøyting/vedlikehold»-tidspunkt.

Tidligere ble dette hentet ved å scrape Plowman share-siden. Det er nå byttet ut
med Vintervakt vedlikeholds-API:

- GET {MAINTENANCE_API_BASE_URL}/v1/maintenance/latest
- Auth: Authorization: Bearer {MAINTENANCE_API_TOKEN}

Dette modulen beholder hjelpefunksjonen `get_last_plowing_time()` for å være en
drop-in erstatning for resten av appen.
"""

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import requests

from src.config import get_secret

logger = logging.getLogger(__name__)


@dataclass
class PlowingEvent:
    """Representerer en brøytehendelse."""
    timestamp: datetime
    vehicle_id: str | None = None
    vehicle_name: str | None = None
    sector_name: str | None = None
    distance_km: float | None = None
    # Vedlikeholds-API metadata (valgfritt)
    event_id: str | None = None
    event_type: str | None = None
    status: str | None = None
    work_types: list[str] | None = None
    operator_id: str | None = None

    def hours_since(self) -> float:
        """Beregn timer siden brøyting."""
        now = datetime.now(UTC)
        if self.timestamp.tzinfo is None:
            # Anta UTC hvis ingen tidssone
            ts = self.timestamp.replace(tzinfo=UTC)
        else:
            ts = self.timestamp
        return (now - ts).total_seconds() / 3600


class MaintenanceApiClient:
    """Klient for Vintervakt vedlikeholds-API."""

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        session: requests.Session | None = None,
    ):
        self.base_url = (base_url or get_secret("MAINTENANCE_API_BASE_URL", "")).rstrip("/")
        self.token = token or get_secret("MAINTENANCE_API_TOKEN", "")
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "gullingen-eu/maintenance-client",
                "Accept": "application/json",
            }
        )

    def get_latest(self) -> dict | None:
        """Returner rå JSON fra `/v1/maintenance/latest`, eller None hvis ikke funnet."""
        if not self.base_url:
            logger.info("MAINTENANCE_API_BASE_URL er ikke satt")
            return None

        url = f"{self.base_url}/v1/maintenance/latest"

        headers: dict[str, str] = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            r = self.session.get(url, headers=headers, timeout=10)
        except requests.RequestException as e:
            logger.warning("Vedlikeholds-API utilgjengelig: %s", e)
            return None

        if r.status_code == 404:
            return None

        if r.status_code in (401, 403):
            logger.warning("Vedlikeholds-API auth-feil (%s)", r.status_code)
            return None

        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            logger.warning("Vedlikeholds-API HTTP-feil: %s", e)
            return None

        try:
            return r.json()
        except ValueError as e:
            logger.warning("Vedlikeholds-API returnerte ikke gyldig JSON: %s", e)
            return None

    def get_last_maintenance_time(self) -> PlowingEvent | None:
        """Hent siste vedlikeholdstidspunkt som PlowingEvent."""
        payload = self.get_latest()
        if not payload:
            # Lokal dev / fallback: hvis vedlikeholds-API ikke er konfigurert,
            # prøv å hente tidspunkt fra Plowman share-siden.
            if not self.base_url:
                return self._get_last_from_plowman_share()
            return None

        ts_str = payload.get("timestamp_utc")
        ts = _parse_iso_utc(ts_str)
        if not ts:
            return None

        work_types = payload.get("work_types")
        if not isinstance(work_types, list):
            work_types = None

        return PlowingEvent(
            timestamp=ts,
            vehicle_id=str(payload.get("session_id") or payload.get("event_id") or "") or None,
            vehicle_name=payload.get("operator_id"),
            sector_name=payload.get("event_type"),
            distance_km=None,
            event_id=str(payload.get("event_id") or payload.get("session_id") or "") or None,
            event_type=payload.get("event_type"),
            status=payload.get("status"),
            work_types=work_types,
            operator_id=payload.get("operator_id"),
        )

    def _get_last_from_plowman_share(self) -> PlowingEvent | None:
        """Fallback: Hent siste brøytingstidspunkt ved å lese share-siden.

        Merk: Dette er en best-effort fallback for utvikling / drift hvis
        vedlikeholds-API ikke er konfigurert. For full funksjonalitet
        (type/arbeid) må vedlikeholds-API brukes.
        """
        share_url = _get_plowman_share_url()
        if not share_url:
            return None

        try:
            r = self.session.get(share_url, timeout=10)
        except requests.RequestException as e:
            logger.warning("Plowman share utilgjengelig: %s", e)
            return None

        if not r.ok:
            logger.warning("Plowman share HTTP-feil (%s)", r.status_code)
            return None

        latest_ts = _extract_latest_timestamp_from_share_html(r.text)
        if not latest_ts:
            return None

        return PlowingEvent(
            timestamp=latest_ts,
            vehicle_id=None,
            vehicle_name=None,
            sector_name=None,
            distance_km=None,
            event_id=None,
            event_type=None,
            status=None,
            work_types=None,
            operator_id=None,
        )


def _parse_iso_utc(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return None


def _get_plowman_share_url() -> str:
    """URL til Plowman share-side (fallback).

    Kan overstyres via secrets/env: PLOWMAN_SHARE_URL
    """
    default_url = "https://plowman-new.xn--snbryting-m8ac.net/nb/share/Y3VzdG9tZXItMTM="
    return (get_secret("PLOWMAN_SHARE_URL", default_url) or "").strip()


def _extract_latest_timestamp_from_share_html(html: str) -> datetime | None:
    """Ekstraher siste relevante `$D...Z` timestamp fra Plowman share HTML.

    Share-siden inneholder typisk timestamps i formen `$D2025-11-27T10:55:38.911Z`.
    Vi plukker siste tidsstempel som ikke ligger urimelig i fremtiden.
    """
    if not html:
        return None

    # Match $D-prefiks som brukes i Next.js-serialisering, også hvis det er escaped.
    matches = re.findall(
        r"\$D(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)",
        html,
    )

    timestamps: list[datetime] = []
    for ts in matches:
        dt = _parse_iso_utc(ts)
        if dt:
            timestamps.append(dt)

    if not timestamps:
        return None

    now = datetime.now(UTC)
    future_tolerance = timedelta(minutes=5)

    valid = [t for t in timestamps if t <= now + future_tolerance]
    if not valid:
        return None

    return max(valid)


def get_last_plowing_time(sector_name: str = None) -> PlowingEvent | None:
    """
    Hjelpefunksjon for å hente siste brøytetidspunkt.

    Args:
        sector_name: Filtrer på spesifikk rode (optional)

    Returns:
        PlowingEvent eller None
    """
    if sector_name:
        logger.info("sector_name er ignorert for vedlikeholds-API (%s)", sector_name)

    client = MaintenanceApiClient()
    return client.get_last_maintenance_time()


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.DEBUG)

    print("Tester vedlikeholds-API...")
    event = get_last_plowing_time()
    if event:
        print("\nSiste brøyting:")
        print(f"  Tidspunkt: {event.timestamp}")
        print(f"  Timer siden: {event.hours_since():.1f}")
        print(f"  Operatør: {event.vehicle_name or 'Ukjent'}")
        print(f"  Type: {event.sector_name or 'Ukjent'}")
    else:
        print("\nKunne ikke hente brøytedata")
