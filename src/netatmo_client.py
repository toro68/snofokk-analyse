"""
Netatmo Weather API-klient.

Henter offentlige værdata fra Netatmo-stasjoner i et område.
Brukes for å supplere Frost API med lokale temperaturer fra Fjellbergsskardet.

API-dokumentasjon: https://dev.netatmo.com/apidocumentation/weather
"""

import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime

import requests

logger = logging.getLogger(__name__)


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
    FJELLBERGSSKARDET = {
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
        self.client_id = client_id or os.getenv("NETATMO_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("NETATMO_CLIENT_SECRET")
        self.access_token = None

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
        if not self.access_token:
            logger.warning("Netatmo: Ingen access_token - kan ikke hente data")
            return []

        url = f"{self.BASE_URL}/getpublicdata"

        params = {
            "lat_ne": lat_ne,
            "lon_ne": lon_ne,
            "lat_sw": lat_sw,
            "lon_sw": lon_sw,
            "required_data": required_data,
            "filter": True
        }

        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            return self._parse_public_data(data)

        except requests.exceptions.RequestException as e:
            logger.error(f"Netatmo API-feil: {e}")
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
            lat_ne=loc["lat"] + delta,
            lon_ne=loc["lon"] + delta,
            lat_sw=loc["lat"] - delta,
            lon_sw=loc["lon"] - delta
        )

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
        if not self.client_id or not self.client_secret:
            logger.warning("Netatmo: Mangler client_id eller client_secret")
            return False

        refresh_token = refresh_token or os.getenv("NETATMO_REFRESH_TOKEN")

        if not refresh_token:
            logger.warning("Netatmo: Mangler NETATMO_REFRESH_TOKEN")
            logger.info("Generer token på https://dev.netatmo.com/apps -> din app -> Token generator")
            return False

        url = "https://api.netatmo.com/oauth2/token"

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data.get("access_token")

            # Lagre ny refresh_token for neste gang
            new_refresh = token_data.get("refresh_token")
            if new_refresh:
                logger.info("Netatmo: Ny refresh_token mottatt (lagre denne!)")

            logger.info("Netatmo: Autentisering vellykket")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Netatmo autentisering feilet: {e}")
            return False

    def _parse_public_data(self, data: dict) -> list[NetatmoStation]:
        """Parse API-respons til NetatmoStation-objekter."""
        stations = []

        body = data.get("body", [])

        for item in body:
            place = item.get("place", {})
            measures = item.get("measures", {})

            station = NetatmoStation(
                station_id=item.get("_id", ""),
                name=place.get("city", "Ukjent"),
                lat=place.get("location", [0, 0])[1],
                lon=place.get("location", [0, 0])[0],
                altitude=place.get("altitude", 0)
            )

            # Parse målinger fra ulike moduler
            for _module_id, module_data in measures.items():
                if isinstance(module_data, dict):
                    # Finn siste måling
                    res = module_data.get("res", {})
                    if res:
                        latest_time = max(res.keys())
                        values = res[latest_time]
                        types = module_data.get("type", [])

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

                    gust_strength = module_data.get("gust_strength")
                    if gust_strength is not None:
                        station.gust_strength = gust_strength

            stations.append(station)

        return stations


def test_netatmo():
    """Test Netatmo-klient."""
    client = NetatmoClient()

    print("Netatmo Weather API Test")
    print("=" * 40)

    # Sjekk om credentials er satt
    if not client.client_id:
        print("⚠️  NETATMO_CLIENT_ID ikke satt i .env")
        print("   Opprett en app på https://dev.netatmo.com/apps")
        return

    refresh_token = os.getenv("NETATMO_REFRESH_TOKEN")
    if not refresh_token:
        print("⚠️  NETATMO_REFRESH_TOKEN ikke satt i .env")
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
        print("✅ Autentisering OK")

        # Hent data fra Fjellbergsskardet
        stations = client.get_fjellbergsskardet_area()

        print(f"\n📍 Stasjoner i Fjellbergsskardet-området: {len(stations)}")

        for s in stations:
            print(f"\n  {s.name} ({s.altitude} moh)")
            if s.temperature is not None:
                print(f"    🌡️ Temperatur: {s.temperature:.1f}°C")
            if s.humidity is not None:
                print(f"    💧 Fuktighet: {s.humidity:.0f}%")
            if s.rain_1h is not None:
                print(f"    🌧️ Regn 1t: {s.rain_1h:.1f} mm")
    else:
        print("❌ Autentisering feilet")


if __name__ == "__main__":
    test_netatmo()
