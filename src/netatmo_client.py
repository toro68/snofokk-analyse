"""
Netatmo Weather API-klient.

Henter offentlige værdata fra Netatmo-stasjoner i et område.
Brukes for å supplere Frost API med lokale temperaturer fra Fjellbergsskardet.

API-dokumentasjon: https://dev.netatmo.com/apidocumentation/weather
"""

import logging
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from src.config import get_secret, settings

logger = logging.getLogger(__name__)


def _persist_refresh_token(new_token: str) -> None:
    """Lagre rotert NETATMO_REFRESH_TOKEN tilbake til .env-filen.

    Netatmo roterer refresh_token ved hvert OAuth2-kall. Uten auto-lagring
    vil neste restart av appen feile fordi den gamle token er ugyldig.
    """
    # Finn .env fra prosjektrot (to nivåer opp fra denne filen: src/ → root)
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        logger.warning("Netatmo: Ny refresh_token mottatt, men fant ikke .env (%s)", env_path)
        return

    try:
        content = env_path.read_text(encoding="utf-8")
        if "NETATMO_REFRESH_TOKEN=" in content:
            updated = re.sub(
                r"(?m)^NETATMO_REFRESH_TOKEN=.*$",
                f"NETATMO_REFRESH_TOKEN={new_token}",
                content,
            )
        else:
            updated = content.rstrip("\n") + f"\nNETATMO_REFRESH_TOKEN={new_token}\n"
        env_path.write_text(updated, encoding="utf-8")
        logger.info("Netatmo: Ny refresh_token lagret automatisk til .env")
    except OSError as exc:
        logger.warning("Netatmo: Klarte ikke lagre ny refresh_token til .env: %s", exc)


@dataclass
class NetatmoStation:
    """Data fra en Netatmo-stasjon."""
    station_id: str
    name: str
    lat: float
    lon: float
    altitude: int
    temperature: float | None = None
    humidity: float | None = None
    pressure: float | None = None
    rain_1h: float | None = None
    rain_24h: float | None = None
    wind_strength: float | None = None
    wind_angle: int | None = None
    gust_strength: float | None = None
    timestamp: datetime | None = None


class NetatmoClient:
    """
    Klient for Netatmo Weather API.

    Kan hente offentlige værdata uten autentisering via getpublicdata-endepunktet.
    For private stasjoner kreves OAuth2-autentisering.
    """

    BASE_URL = "https://api.netatmo.com/api"

    # Fjellbergsskardet Hyttegrend område (ca 5km radius)
    FJELLBERGSSKARDET: dict[str, Any] = {
        "lat": 59.39205,
        "lon": 6.42667,
        "name": "Fjellbergsskardet",
        "altitude": 607
    }

    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        """
        Initialiser klient.

        Args:
            client_id: Netatmo app client ID (fra .env eller secrets)
            client_secret: Netatmo app client secret
        """
        raw_client_id = client_id if client_id is not None else get_secret("NETATMO_CLIENT_ID", "")
        raw_client_secret = client_secret if client_secret is not None else get_secret("NETATMO_CLIENT_SECRET", "")
        self.client_id = str(raw_client_id).strip().strip('"').strip("'")
        self.client_secret = str(raw_client_secret).strip().strip('"').strip("'")
        self.access_token: str | None = (get_secret("NETATMO_ACCESS_TOKEN", "") or "").strip().strip('"').strip("'") or None
        self.refresh_token: str | None = (get_secret("NETATMO_REFRESH_TOKEN", "") or "").strip().strip('"').strip("'") or None
        self.access_token_expires_at: datetime | None = None
        self.last_error: str | None = None
        self._session = requests.Session()

    def get_public_data(
        self,
        lat_ne: float,
        lon_ne: float,
        lat_sw: float,
        lon_sw: float,
        required_data: str = "temperature"
    ) -> list[NetatmoStation]:
        """
        Hent offentlige værdata fra et område.

        Merk: Krever autentisering (access_token).

        Args:
            lat_ne: Nordøstlig breddegrad
            lon_ne: Nordøstlig lengdegrad
            lat_sw: Sørvest breddegrad
            lon_sw: Sørvest lengdegrad
            required_data: Påkrevd data (temperature, humidity, pressure, rain, wind)

        Returns:
            Liste med NetatmoStation-objekter
        """
        if not self.authenticate():
            logger.warning("Netatmo: Ingen gyldig access_token - kan ikke hente data")
            return []

        url = f"{self.BASE_URL}/getpublicdata"

        params: dict[str, str | float | int] = {
            "lat_ne": lat_ne,
            "lon_ne": lon_ne,
            "lat_sw": lat_sw,
            "lon_sw": lon_sw,
            "required_data": required_data,
            "filter": "true",
        }

        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        try:
            response = self._session.get(
                url,
                params=params,
                headers=headers,
                timeout=settings.netatmo.http_timeout_seconds,
            )
            if response.status_code == 401:
                # Token kan være utløpt/revokert før lokal expiry-check.
                logger.info("Netatmo: 401 fra getpublicdata - forsøker token-fornyelse")
                if not self.authenticate():
                    return []
                headers["Authorization"] = f"Bearer {self.access_token}"
                response = self._session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=settings.netatmo.http_timeout_seconds,
                )

            response.raise_for_status()
            data = response.json()

            return self._parse_public_data(data)

        except requests.exceptions.RequestException as e:
            logger.error("Netatmo API-feil: %s", e)
            self.last_error = f"Netatmo API-feil: {e}"
            return []

    def get_fjellbergsskardet_area(self, radius_km: float = 5.0) -> list[NetatmoStation]:
        """
        Hent værdata fra Fjellbergsskardet-området.

        Args:
            radius_km: Søkeradius i km

        Returns:
            Liste med stasjoner i området
        """
        # Konverter km til grader (ca. 0.009 grader per km på denne breddegraden)
        delta = radius_km * 0.009

        loc = self.FJELLBERGSSKARDET

        return self.get_public_data(
            lat_ne=float(loc["lat"]) + delta,
            lon_ne=float(loc["lon"]) + delta,
            lat_sw=float(loc["lat"]) - delta,
            lon_sw=float(loc["lon"]) - delta
        )

    def get_private_stations(self) -> list[NetatmoStation]:
        """Hent private stasjoner (konto-eide) via getstationsdata."""
        if not self.authenticate():
            logger.warning("Netatmo: Ingen gyldig access_token - kan ikke hente private stasjoner")
            return []

        url = f"{self.BASE_URL}/getstationsdata"
        headers = {"Authorization": f"Bearer {self.access_token}"}

        try:
            response = self._session.get(
                url,
                headers=headers,
                timeout=settings.netatmo.http_timeout_seconds,
            )
            if response.status_code == 401:
                logger.info("Netatmo: 401 fra getstationsdata - forsøker token-fornyelse")
                if not self.authenticate():
                    return []
                headers["Authorization"] = f"Bearer {self.access_token}"
                response = self._session.get(
                    url,
                    headers=headers,
                    timeout=settings.netatmo.http_timeout_seconds,
                )

            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                api_error = data.get("error")
                if api_error:
                    self.last_error = f"Netatmo getstationsdata-feil: {api_error}"
                    logger.warning(self.last_error)
                    return []

                body = data.get("body")
                if isinstance(body, dict):
                    devices = body.get("devices")
                    user = body.get("user", {})
                    user_mail = ""
                    if isinstance(user, dict):
                        user_mail = str(user.get("mail", "")).strip()
                    if isinstance(devices, list) and not devices:
                        if user_mail:
                            self.last_error = f"Ingen private Netatmo-enheter for konto: {user_mail}"
                        else:
                            self.last_error = "Ingen private Netatmo-enheter på kontoen"
                        logger.info(self.last_error)
                        return []

            self.last_error = None
            return self._parse_public_data(data)
        except requests.exceptions.RequestException as e:
            logger.error("Netatmo private stasjoner feilet: %s", e)
            self.last_error = f"Netatmo private stasjoner feilet: {e}"
            return []

    def get_fjellbergsskardet_private(self, radius_km: float = 35.0) -> list[NetatmoStation]:
        """Hent private stasjoner filtrert til området rundt Fjellbergsskardet."""
        loc = self.FJELLBERGSSKARDET
        stations = self.get_private_stations()
        center_lat = float(loc["lat"])
        center_lon = float(loc["lon"])

        return [
            station for station in stations
            if self._distance_km(center_lat, center_lon, station.lat, station.lon) <= radius_km
        ]

    def authenticate(self, refresh_token: str | None = None) -> bool:
        """
        Autentiser med Netatmo API.

        Netatmo krever OAuth2 med brukerautentisering.
        Bruk refresh_token fra .env for å fornye access_token.

        For å få refresh_token første gang:
        1. Gå til https://dev.netatmo.com/apps
        2. Velg din app og klikk "Token generator"
        3. Velg scope "read_station" og generer token
        4. Kopier refresh_token til .env

        Args:
            refresh_token: Refresh token fra Netatmo

        Returns:
            True hvis autentisering lyktes
        """
        # Hvis vi allerede har en gyldig token, ikke forny unødig.
        if self.access_token and self.access_token_expires_at:
            now = datetime.now(tz=UTC)
            # Litt buffer for å unngå race rundt utløp
            if now < (self.access_token_expires_at - timedelta(seconds=60)):
                self.last_error = None
                return True

        # Tillat statisk access token uten expiry metadata
        # (nyttig i miljøer der refresh-token ikke brukes).
        if self.access_token and self.access_token_expires_at is None:
            self.last_error = None
            return True

        if not self.client_id or not self.client_secret:
            logger.warning("Netatmo: Mangler client_id eller client_secret")
            self.last_error = "Mangler NETATMO_CLIENT_ID/NETATMO_CLIENT_SECRET"
            return False

        refresh_token = (
            refresh_token
            or self.refresh_token
            or get_secret("NETATMO_REFRESH_TOKEN", "")
            or ""
        ).strip().strip('"').strip("'")

        if not refresh_token:
            logger.warning("Netatmo: Mangler NETATMO_REFRESH_TOKEN")
            logger.info("Generer token på https://dev.netatmo.com/apps -> din app -> Token generator")
            self.last_error = "Mangler NETATMO_REFRESH_TOKEN"
            return False

        url = "https://api.netatmo.com/oauth2/token"

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            response = self._session.post(
                url,
                data=data,
                timeout=settings.netatmo.http_timeout_seconds,
            )
            response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data.get("access_token")

            expires_in = token_data.get("expires_in")
            try:
                if expires_in is not None:
                    self.access_token_expires_at = datetime.now(tz=UTC) + timedelta(seconds=int(expires_in))
                else:
                    self.access_token_expires_at = None
            except (TypeError, ValueError):
                self.access_token_expires_at = None

            # Lagre ny refresh_token for neste gang (Netatmo roterer token ved hvert kall)
            new_refresh = token_data.get("refresh_token")
            if new_refresh:
                self.refresh_token = str(new_refresh).strip()
                persist_local = str(get_secret("NETATMO_PERSIST_REFRESH_TO_DOTENV", "")).strip().lower() in {
                    "1", "true", "yes", "on"
                }
                if persist_local:
                    _persist_refresh_token(self.refresh_token)

            logger.info("Netatmo: Autentisering vellykket")
            self.last_error = None
            return True

        except requests.exceptions.RequestException as e:
            details = ""
            if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
                try:
                    payload = e.response.json()
                    if isinstance(payload, dict):
                        err = str(payload.get("error", "")).strip()
                        desc = str(payload.get("error_description", "")).strip()
                        if err and desc:
                            details = f"{err}: {desc}"
                        else:
                            details = err or desc
                except (ValueError, TypeError):
                    details = (e.response.text or "").strip()[:200]

            if details:
                logger.error("Netatmo autentisering feilet: %s (%s)", e, details)
                self.last_error = f"Netatmo autentisering feilet: {details}"
            else:
                logger.error("Netatmo autentisering feilet: %s", e)
                self.last_error = f"Netatmo autentisering feilet: {e}"
            return False

    def _parse_public_data(self, data: dict) -> list[NetatmoStation]:
        """Parse API-respons til NetatmoStation-objekter."""
        stations = []

        body_raw = data.get("body", [])
        if isinstance(body_raw, dict):
            # Netatmo kan returnere body som objekt med device-liste.
            body = body_raw.get("devices") or body_raw.get("data") or []
        elif isinstance(body_raw, list):
            body = body_raw
        else:
            body = []

        for item in body:
            place = item.get("place", {})
            measures = item.get("measures", {})
            location = place.get("location", [0, 0])
            lon = 0.0
            lat = 0.0
            if isinstance(location, list) and len(location) >= 2:
                try:
                    lon = float(location[0])
                    lat = float(location[1])
                except (TypeError, ValueError):
                    lon, lat = 0.0, 0.0

            station = NetatmoStation(
                station_id=item.get("_id", ""),
                name=place.get("city", "Ukjent"),
                lat=lat,
                lon=lon,
                altitude=int(place.get("altitude", 0) or 0),
            )

            dashboard_data = item.get("dashboard_data", {})
            if isinstance(dashboard_data, dict):
                temp = dashboard_data.get("Temperature")
                if temp is not None:
                    station.temperature = temp
                hum = dashboard_data.get("Humidity")
                if hum is not None:
                    station.humidity = hum
                pressure = dashboard_data.get("Pressure")
                if pressure is not None:
                    station.pressure = pressure
                time_utc = dashboard_data.get("time_utc")
                if time_utc is not None:
                    try:
                        station.timestamp = datetime.fromtimestamp(int(time_utc), tz=UTC)
                    except (TypeError, ValueError, OSError):
                        station.timestamp = station.timestamp

            # Parse målinger fra ulike moduler
            for _module_id, module_data in measures.items():
                if isinstance(module_data, dict):
                    # Finn siste måling
                    res = module_data.get("res", {})
                    if res:
                        latest_time = max(res.keys())
                        values = res[latest_time]
                        if not isinstance(values, list):
                            values = [values]
                        types = module_data.get("type", [])
                        if not isinstance(types, list):
                            types = []

                        for i, data_type in enumerate(types):
                            if i < len(values):
                                if data_type == "temperature":
                                    station.temperature = values[i]
                                elif data_type == "humidity":
                                    station.humidity = values[i]
                                elif data_type == "pressure":
                                    station.pressure = values[i]

                        station.timestamp = datetime.fromtimestamp(
                            int(latest_time),
                            tz=UTC
                        )

                    # Regndata
                    rain_60min = module_data.get("rain_60min")
                    if rain_60min is not None:
                        station.rain_1h = rain_60min

                    rain_24h = module_data.get("rain_24h")
                    if rain_24h is not None:
                        station.rain_24h = rain_24h

                    # Vinddata
                    wind_strength = module_data.get("wind_strength")
                    if wind_strength is not None:
                        station.wind_strength = wind_strength

                    wind_angle = module_data.get("wind_angle")
                    if wind_angle is not None:
                        try:
                            station.wind_angle = int(wind_angle)
                        except (TypeError, ValueError):
                            station.wind_angle = None

                    gust_strength = module_data.get("gust_strength")
                    if gust_strength is not None:
                        station.gust_strength = gust_strength

            modules = item.get("modules", [])
            if isinstance(modules, list):
                for module in modules:
                    if not isinstance(module, dict):
                        continue
                    module_dashboard = module.get("dashboard_data", {})
                    if not isinstance(module_dashboard, dict):
                        continue

                    if station.temperature is None:
                        module_temp = module_dashboard.get("Temperature")
                        if module_temp is not None:
                            station.temperature = module_temp
                    if station.humidity is None:
                        module_hum = module_dashboard.get("Humidity")
                        if module_hum is not None:
                            station.humidity = module_hum
                    if station.pressure is None:
                        module_pressure = module_dashboard.get("Pressure")
                        if module_pressure is not None:
                            station.pressure = module_pressure

                    module_time = module_dashboard.get("time_utc")
                    if module_time is not None:
                        try:
                            module_ts = datetime.fromtimestamp(int(module_time), tz=UTC)
                            if station.timestamp is None or module_ts > station.timestamp:
                                station.timestamp = module_ts
                        except (TypeError, ValueError, OSError):
                            pass

            stations.append(station)

        return stations

    @staticmethod
    def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Grov avstandsestimat i km uten tunge trig-funksjoner."""
        lat_scale = 111.0
        lon_scale = 57.0  # ~cos(59.4) * 111
        dx = (lon2 - lon1) * lon_scale
        dy = (lat2 - lat1) * lat_scale
        return (dx * dx + dy * dy) ** 0.5


def test_netatmo() -> None:
    """Test Netatmo-klient."""
    client = NetatmoClient()

    print("Netatmo Weather API Test")
    print("=" * 40)

    # Sjekk om credentials er satt
    if not client.client_id:
        print("NETATMO_CLIENT_ID ikke satt i .env")
        print("   Opprett en app på https://dev.netatmo.com/apps")
        return

    refresh_token = os.getenv("NETATMO_REFRESH_TOKEN")
    if not refresh_token:
        print("NETATMO_REFRESH_TOKEN ikke satt i .env")
        print("")
        print("   Slik får du refresh_token:")
        print("   1. Gå til https://dev.netatmo.com/apps")
        print("   2. Klikk på din app")
        print("   3. Klikk 'Token generator' i menyen")
        print("   4. Velg scope 'read_station'")
        print("   5. Klikk 'Generate Token'")
        print("   6. Kopier 'Refresh Token' og legg i .env:")
        print("      NETATMO_REFRESH_TOKEN=din-refresh-token")
        return

    # Autentiser
    if client.authenticate():
        print("Autentisering OK")

        # Hent data fra Fjellbergsskardet
        stations = client.get_fjellbergsskardet_area()

        print(f"\nStasjoner i Fjellbergsskardet-området: {len(stations)}")

        for s in stations:
            print(f"\n  {s.name} ({s.altitude} moh)")
            if s.temperature is not None:
                print(f"    Temperatur: {s.temperature:.1f}°C")
            if s.humidity is not None:
                print(f"    Fuktighet: {s.humidity:.0f}%")
            if s.rain_1h is not None:
                print(f"    Regn 1t: {s.rain_1h:.1f} mm")
    else:
        print("Autentisering feilet")


if __name__ == "__main__":
    test_netatmo()
