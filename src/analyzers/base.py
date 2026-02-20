"""
Baseklasser for væranalyse.

Definerer felles interface og hjelpefunksjoner for alle analysatorer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

import pandas as pd


class RiskLevel(Enum):
    """
    Standardiserte risikonivåer.

    Brukes konsistent på tvers av alle analysatorer.
    """
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def emoji(self) -> str:
        """Emoji-representasjon for UI.

        Appen bruker ikke emojis i UI.
        """
        return ""

    @property
    def color(self) -> str:
        """Fargekode for visualisering."""
        return {
            RiskLevel.UNKNOWN: "#9E9E9E",  # Gray
            RiskLevel.LOW: "#4CAF50",       # Green
            RiskLevel.MEDIUM: "#FF9800",    # Orange
            RiskLevel.HIGH: "#F44336"       # Red
        }[self]

    @property
    def norwegian(self) -> str:
        """Norsk beskrivelse."""
        return {
            RiskLevel.UNKNOWN: "Ukjent",
            RiskLevel.LOW: "Lav",
            RiskLevel.MEDIUM: "Moderat",
            RiskLevel.HIGH: "Høy"
        }[self]


@dataclass
class AnalysisResult:
    """
    Standardisert resultat fra analyse.

    Attributes:
        risk_level: Risikonivå (UNKNOWN, LOW, MEDIUM, HIGH)
        message: Hovedmelding til bruker
        scenario: Kort beskrivelse av scenario (f.eks. "Regn på snø")
        factors: Liste med faktorer som bidrar til vurderingen
        details: Ekstra detaljer som dict
        timestamp: Tidspunkt for analyse
    """
    risk_level: RiskLevel
    message: str
    scenario: str | None = None
    factors: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Konverter til dictionary for JSON/API.

        Standardfelter (risk_level, message, …) overskriver alltid
        eventuelle nøkler med samme navn i `details`.
        """
        return {
            **self.details,
            "risk_level": self.risk_level.value,
            "risk_level_norwegian": self.risk_level.norwegian,
            "message": self.message,
            "scenario": self.scenario,
            "factors": self.factors,
            "timestamp": self.timestamp.isoformat(),
        }

    @property
    def is_warning(self) -> bool:
        """Sjekk om dette er et varsel (medium eller høy)."""
        return self.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)

    @property
    def is_critical(self) -> bool:
        """Sjekk om dette er kritisk (høy)."""
        return self.risk_level == RiskLevel.HIGH


class BaseAnalyzer(ABC):
    """
    Abstrakt baseklasse for alle analysatorer.

    Definerer felles interface og hjelpefunksjoner.
    """

    # Overstyr i subklasser
    REQUIRED_COLUMNS: list[str] = []

    @abstractmethod
    def analyze(self, df: pd.DataFrame) -> AnalysisResult:
        """
        Utfør analyse på værdata.

        Args:
            df: DataFrame med værdata

        Returns:
            AnalysisResult med risikovurdering
        """
        ...

    def _get_latest(self, df: pd.DataFrame) -> pd.Series:
        """Hent siste måling."""
        return df.iloc[-1]

    def _validate_data(self, df: pd.DataFrame, required: list[str] | None = None) -> bool:
        """
        Valider at nødvendige kolonner finnes.

        Args:
            df: DataFrame å validere
            required: Påkrevde kolonner (default: self.REQUIRED_COLUMNS)

        Returns:
            True hvis alle kolonner finnes
        """
        if df is None or df.empty:
            return False

        required = required or self.REQUIRED_COLUMNS
        return all(col in df.columns for col in required)

    def _safe_get(self, series: pd.Series, key: str, default=None):
        """
        Hent verdi fra Series med fallback.

        Håndterer NaN og manglende nøkler.
        """
        try:
            value = series.get(key)
            if pd.isna(value):
                return default
            return value
        except (TypeError, ValueError, KeyError, AttributeError):
            return default

    @staticmethod
    def calculate_wind_chill(temp: float, wind: float) -> float:
        """
        Beregn vindkjøling (NWS-formel).

        Gyldig for:
        - Temperatur < 10°C
        - Vindstyrke > 4.8 km/h (1.34 m/s)

        Args:
            temp: Lufttemperatur i °C
            wind: Vindstyrke i m/s

        Returns:
            Vindkjølingsindeks i °C
        """
        if temp is None or wind is None:
            return temp if temp is not None else 0.0

        from src.config import settings

        if temp >= settings.viz.wind_chill_valid_temp_max_c or wind < settings.viz.wind_chill_valid_wind_min_ms:
            return temp

        wind_kmh = wind * 3.6
        return (
            13.12 + 0.6215 * temp
            - 11.37 * (wind_kmh ** 0.16)
            + 0.3965 * temp * (wind_kmh ** 0.16)
        )

    @staticmethod
    def _analysis_now(df: pd.DataFrame) -> datetime:
        """
        Bruk siste reference_time i datasettet som «nå».

        Returnerer alltid en UTC-aware datetime slik at sammenligninger
        med timezone-aware og timezone-naive data ikke kaster TypeError.
        """
        try:
            if 'reference_time' in df.columns and not df.empty:
                ts = pd.to_datetime(df['reference_time']).iloc[-1]
                if not pd.isna(ts):
                    if ts.tzinfo is None:
                        ts = ts.tz_localize('UTC')
                    return ts.to_pydatetime()
        except (TypeError, ValueError, IndexError, KeyError):
            pass
        return datetime.now(UTC)

    def _calculate_snow_change(self, df: pd.DataFrame, hours: int = 6) -> float:
        """
        Beregn snøendring siste N timer (basert på dataens tidsakse).

        Positiv verdi = økning (nysnø), negativ = smelting/blåst vekk.
        Returnerer 0.0 hvis data mangler.
        """
        if 'surface_snow_thickness' not in df.columns or 'reference_time' not in df.columns:
            return 0.0
        if df.empty:
            return 0.0

        now = self._analysis_now(df)
        cutoff = now - timedelta(hours=hours)
        recent = df[pd.to_datetime(df['reference_time']) > cutoff].copy()
        if len(recent) < 2:
            return 0.0

        snow = recent['surface_snow_thickness'].dropna()
        if len(snow) < 2:
            return 0.0

        return float(snow.iloc[-1] - snow.iloc[0])

    def _precip_total(self, df: pd.DataFrame, hours: int = 12) -> float:
        """
        Akkumuler nedbør siste N timer (mm) basert på precipitation_1h.

        Bruker eksklusiv cutoff (>) for å unngå dobbel-telling ved
        timeoppløste data.
        """
        if 'precipitation_1h' not in df.columns or 'reference_time' not in df.columns:
            return 0.0
        if df.empty:
            return 0.0

        now = self._analysis_now(df)
        cutoff = now - timedelta(hours=hours)
        recent = df[pd.to_datetime(df['reference_time']) > cutoff].copy()
        if recent.empty:
            return 0.0

        vals = pd.to_numeric(recent['precipitation_1h'], errors='coerce').fillna(0.0)
        return float(vals.sum())

    @staticmethod
    def is_winter_season() -> bool:
        """Sjekk om det er vintersesong (okt-apr)."""
        from src.config import settings
        return settings.is_winter()
