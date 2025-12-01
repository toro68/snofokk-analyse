"""
Sentralisert konfigurasjon for Alarm System.

All konfigurasjon samlet på ett sted for enkel vedlikehold.
Støtter både lokal utvikling (.env) og Streamlit Cloud (secrets).
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

# Last .env-fil ved oppstart
try:
    from dotenv import load_dotenv
    # Finn .env relativt til prosjektrot
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # dotenv ikke installert


def get_secret(key: str, default: str = "") -> str:
    """
    Hent hemmelighet fra Streamlit secrets eller miljøvariabler.

    Prioritet:
    1. Streamlit secrets (for cloud deployment)
    2. Miljøvariabler (for lokal utvikling)
    3. Default verdi
    """
    # Prøv Streamlit secrets først
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass

    # Fallback til miljøvariabler
    return os.getenv(key, default)


@dataclass(frozen=True)
class APIConfig:
    """Frost API konfigurasjon."""
    base_url: str = "https://frost.met.no/observations/v0.jsonld"
    sources_url: str = "https://frost.met.no/sources/v0.jsonld"
    elements_url: str = "https://frost.met.no/elements/v0.jsonld"
    timeout: int = 30

    @property
    def client_id(self) -> str:
        """Hent API-nøkkel fra secrets."""
        return get_secret("FROST_CLIENT_ID", "")


@dataclass(frozen=True)
class StationConfig:
    """Værstasjon konfigurasjon."""
    station_id: str = "SN46220"
    name: str = "Gullingen"
    altitude_m: int = 637
    lat: float = 59.41172
    lon: float = 6.47204

    # Tilgjengelige elementer (verifisert mot API)
    CORE_ELEMENTS: ClassVar[tuple] = (
        'air_temperature',
        'surface_temperature',       # KRITISK: Bakketemperatur for isdannelse
        'wind_speed',
        'max(wind_speed_of_gust PT1H)',  # KRITISK: Vindkast for snøfokk
        'wind_from_direction',
        'surface_snow_thickness',
        'sum(precipitation_amount PT1H)',
        'relative_humidity',
        'dew_point_temperature',     # For snø vs regn-klassifisering
    )

    EXTENDED_ELEMENTS: ClassVar[tuple] = (
        'min(air_temperature PT1H)',
        'max(air_temperature PT1H)',
    )

    @classmethod
    def all_elements(cls) -> list[str]:
        """Returner alle elementer."""
        return list(cls.CORE_ELEMENTS + cls.EXTENDED_ELEMENTS)


@dataclass(frozen=True)
class SnowdriftThresholds:
    """
    ML-validerte terskler for snøfokk (2025).

    Basert på analyse av 166 episoder.
    Vindkast er bedre trigger enn snittwind!
    Historisk snitt vindkast ved snøfokk: 21.9 m/s
    """
    # Vindkjøling-baserte terskler
    wind_chill_critical: float = -15.0  # Høy risiko
    wind_chill_warning: float = -12.0   # Moderat risiko

    # Vindstyrke-terskler (snitt)
    wind_speed_critical: float = 10.0   # Høy risiko
    wind_speed_warning: float = 8.0     # Moderat risiko
    wind_speed_median: float = 12.2     # Empirisk median for snøtransport

    # Vindkast-terskler (NY - bedre trigger!)
    # Historisk snitt: 21.9 m/s - justert terskel til 20.0 for å fange typiske episoder
    wind_gust_critical: float = 20.0    # Kritisk risiko (tidligere 22.0)
    wind_gust_warning: float = 15.0     # Moderat risiko

    # Kritiske vindretninger (SE-S)
    critical_wind_dir_min: float = 135.0  # SE
    critical_wind_dir_max: float = 225.0  # S

    # Andre terskler
    temperature_max: float = -1.0       # Må være frost
    snow_depth_min_cm: float = 3.0      # Minimum snødekke (spesifikasjon ≥3 cm)
    fresh_snow_threshold: float = 0.3   # cm/h for nysnø
    interval_hours: int = 6             # Evaluer maksimum risiko siste N timer


@dataclass(frozen=True)
class SlipperyRoadThresholds:
    """
    Terskler for glattføre-analyse.

    NY INNSIKT: Bakketemperatur er bedre indikator enn lufttemperatur!
    28 av 166 episoder hadde luft > 0°C men bakke < 0°C = FRYSEFARE
    """
    # Temperaturområde for regn-på-snø
    mild_temp_min: float = 0.0
    mild_temp_max: float = 4.0

    # Bakketemperatur (NY - kritisk for isdannelse)
    surface_temp_freeze: float = 0.0    # Is dannes når bakke < 0
    air_surface_diff_avg: float = 2.1   # Bakke er typisk 2.1°C kaldere

    # Andre terskler
    snow_depth_min_cm: float = 5.0
    rain_threshold_mm: float = 0.3
    temp_rise_threshold: float = 1.0    # °C stigning siste 6t
    recent_snow_relief_hours: int = 6   # Tidsrom for "fersk snø"-effekt
    recent_snow_relief_cm: float = 2.0  # Økning som gir naturlig strøing


@dataclass(frozen=True)
class FreshSnowThresholds:
    """
    Terskler for nysnø-deteksjon.

    Validert mot 166 brøyteepisoder.
    """
    # Snøøkning
    snow_increase_warning: float = 5.0   # cm over 6 timer
    snow_increase_critical: float = 10.0 # cm over 6 timer

    # Temperatur for snø (ikke regn)
    dew_point_max: float = 0.0          # Primær: duggpunkt < 0 = snø
    air_temp_max: float = 1.0           # Sekundær: lufttemp < 1°C

    # Nedbør
    precipitation_min: float = 0.3      # mm/t for å registrere


@dataclass(frozen=True)
class SlapsThresholds:
    """
    Terskler for slaps-deteksjon.

    ML-validert mot 42 bekreftet slaps-episoder.
    Slaps = tung blanding av snø og vann.
    """
    # Temperatur (kritisk område for slaps)
    temp_min: float = -1.0              # Under dette: snø
    temp_max: float = 4.0               # Over dette: bare regn
    temp_optimal: float = 1.2           # Historisk snitt for slaps

    # Nedbør
    precipitation_min: float = 1.0      # mm/t for slaps
    precipitation_heavy: float = 5.0    # mm/t for kraftig slaps

    # Snødekke
    snow_depth_min: float = 5.0         # cm - må ha snø


@dataclass(frozen=True)
class VisualizationConfig:
    """Konfigurasjon for plotting."""
    max_datapoints: int = 10000
    max_bars: int = 1000
    sample_target: int = 5000
    figure_dpi: int = 100

    # Farger
    color_temp: str = "#1E88E5"
    color_wind: str = "#43A047"
    color_snow: str = "#8E24AA"
    color_precip: str = "#1565C0"
    color_warning: str = "#FF9800"
    color_critical: str = "#D32F2F"


@dataclass
class Settings:
    """Hovedkonfigurasjon som samler alt."""
    api: APIConfig = field(default_factory=APIConfig)
    station: StationConfig = field(default_factory=StationConfig)
    snowdrift: SnowdriftThresholds = field(default_factory=SnowdriftThresholds)
    slippery: SlipperyRoadThresholds = field(default_factory=SlipperyRoadThresholds)
    fresh_snow: FreshSnowThresholds = field(default_factory=FreshSnowThresholds)
    slaps: SlapsThresholds = field(default_factory=SlapsThresholds)
    viz: VisualizationConfig = field(default_factory=VisualizationConfig)

    # Sesongmåneder
    WINTER_MONTHS: ClassVar[tuple] = (10, 11, 12, 1, 2, 3, 4)

    def is_winter(self) -> bool:
        """Sjekk om det er vintersesong."""
        from datetime import datetime
        return datetime.now().month in self.WINTER_MONTHS

    def validate(self) -> tuple[bool, str]:
        """Valider at nødvendig konfigurasjon er på plass."""
        if not self.api.client_id:
            return False, "FROST_CLIENT_ID mangler. Legg til i .env eller Streamlit secrets."
        return True, "OK"


# Global singleton
settings = Settings()
