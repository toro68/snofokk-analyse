"""
Baseklasser for væranalyse.

Definerer felles interface og hjelpefunksjoner for alle analysatorer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
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
        """Emoji-representasjon for UI."""
        return {
            RiskLevel.UNKNOWN: "❓",
            RiskLevel.LOW: "🟢",
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.HIGH: "🔴"
        }[self]

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
        """Konverter til dictionary for JSON/API."""
        return {
            "risk_level": self.risk_level.value,
            "risk_level_norwegian": self.risk_level.norwegian,
            "message": self.message,
            "scenario": self.scenario,
            "factors": self.factors,
            "timestamp": self.timestamp.isoformat(),
            **self.details
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
        pass

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
        except Exception:
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

        if temp >= 10 or wind < 1.34:
            return temp

        wind_kmh = wind * 3.6
        return (
            13.12 + 0.6215 * temp
            - 11.37 * (wind_kmh ** 0.16)
            + 0.3965 * temp * (wind_kmh ** 0.16)
        )

    @staticmethod
    def is_winter_season() -> bool:
        """Sjekk om det er vintersesong (okt-apr)."""
        from src.config import settings
        return settings.is_winter()
