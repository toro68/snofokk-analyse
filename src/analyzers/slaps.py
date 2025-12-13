"""
Slaps-deteksjon.

Slaps = tung blanding av snø og vann som gir dårlig fremkommelighet.
Oppstår når snø smelter (varmegrader) eller regn faller på snø.

VIKTIG: Slaps er IKKE is. Hvis slaps fryser, blir det is (→ glatte veier).
"""

from datetime import UTC, datetime, timedelta

import pandas as pd

from src.analyzers.base import AnalysisResult, BaseAnalyzer, RiskLevel
from src.config import settings


class SlapsAnalyzer(BaseAnalyzer):
    """
    Analyserer slaps-risiko.

    Hovedscenarier:
    1. Regn på snø ved temp 0-4°C
    2. Snøsmelting ved temp 0-4°C
    3. Overgang fra snø til regn

    Validert mot 42 bekreftet slaps-episoder:
    - Gjennomsnittstemperatur: 1.2°C
    - Gjennomsnittlig nedbør: 29.9mm
    """

    REQUIRED_COLUMNS = ['air_temperature']

    def analyze(self, df: pd.DataFrame) -> AnalysisResult:
        """
        Analyser slaps-risiko.

        Args:
            df: DataFrame med værdata

        Returns:
            AnalysisResult med risikovurdering
        """
        if not self._validate_data(df):
            return AnalysisResult(
                risk_level=RiskLevel.UNKNOWN,
                message="Mangler temperaturdata",
                scenario="Data mangler"
            )

        # Sommersesong = ingen slaps (ikke snø på bakken)
        if not self.is_winter_season():
            return self._summer_result()

        return self._winter_analysis(df)

    def _summer_result(self) -> AnalysisResult:
        """Returner lav risiko for sommersesong."""
        return AnalysisResult(
            risk_level=RiskLevel.LOW,
            message="Sommersesong - ingen slaps-risiko",
            scenario="Sommer",
            factors=["Utenfor vintersesong"]
        )

    def _winter_analysis(self, df: pd.DataFrame) -> AnalysisResult:
        """Full vinteranalyse for slaps."""
        thresholds = settings.slaps

        # Hent verdier
        latest = self._get_latest(df)
        temp = self._safe_get(latest, 'air_temperature')
        snow = self._safe_get(latest, 'surface_snow_thickness', 0)
        precip = self._safe_get(latest, 'precipitation_1h', 0)
        dew_point = self._safe_get(latest, 'dew_point_temperature')

        if temp is None:
            return AnalysisResult(
                risk_level=RiskLevel.UNKNOWN,
                message="Mangler temperaturdata",
                scenario="Data mangler"
            )

        # Beregn snøendring (synkende = smelting = slaps)
        snow_change = self._calculate_snow_change(df)

        precip_12h = self._calculate_precip_total(df, hours=12)

        # Sjekk om nedbør er regn (ikke snø)
        is_rain = self._is_precipitation_rain(temp, dew_point)

        factors = []
        details = {
            "temperature": round(temp, 1),
            "snow_depth_cm": round(snow, 1),
            "snow_change_6h": round(snow_change, 1),
            "precipitation_mm": round(precip, 2),
            "precipitation_12h_mm": round(precip_12h, 2),
            "dew_point": round(dew_point, 1) if dew_point else None,
            "is_rain": is_rain,
        }

        # Sjekk grunnleggende forutsetninger
        in_slaps_temp_range = thresholds.temp_min <= temp <= thresholds.temp_max
        has_snow = snow >= thresholds.snow_depth_min

        # Ingen snø = ingen slaps
        if not has_snow:
            return AnalysisResult(
                risk_level=RiskLevel.LOW,
                message=f"Lite snø ({snow:.0f} cm) - lav slaps-risiko",
                scenario="Lite snø",
                factors=[f"Snødybde: {snow:.0f} cm (krever ≥ {thresholds.snow_depth_min:.0f} cm)"],
                details=details
            )

        # Utenfor temperaturområde for slaps
        if not in_slaps_temp_range:
            if temp < thresholds.temp_min:
                return AnalysisResult(
                    risk_level=RiskLevel.LOW,
                    message=f"For kaldt for slaps ({temp:.1f}°C)",
                    scenario="Frost",
                    factors=[f"{temp:.1f}°C < {thresholds.temp_min}°C → snø, ikke slaps"],
                    details=details
                )
            else:  # temp > thresholds.temp_max
                # Ikke varsle på varmegrader alene – krever tegn på aktiv smelting.
                if snow_change < -2:
                    return AnalysisResult(
                        risk_level=RiskLevel.MEDIUM,
                        message=f"Varm ({temp:.1f}°C) - snøsmelting pågår",
                        scenario="Smelting",
                        factors=[f"{temp:.1f}°C > {thresholds.temp_max}°C → snø smelter"],
                        details=details
                    )
                return AnalysisResult(
                    risk_level=RiskLevel.LOW,
                    message=f"Varmt ({temp:.1f}°C) men ingen tydelig smelting",
                    scenario="Varmt",
                    factors=[f"{temp:.1f}°C > {thresholds.temp_max}°C"],
                    details=details
                )

        # SLAPS-scenario: Riktig temperatur + snø
        factors.append(f"Temperatur: {temp:.1f}°C (slaps-området)")
        factors.append(f"Snødybde: {snow:.0f} cm")

        # Sjekk tegn på aktiv slaps
        slaps_indicators = []

        # Bruk 12t akkumulert nedbør for å unngå varsling på små drypp.
        rain_on_snow = is_rain and precip_12h >= thresholds.precipitation_12h_min

        if rain_on_snow:
            slaps_indicators.append("rain_on_snow")
            factors.append(f"Regn på snø: {precip:.1f} mm/t")

        if snow_change < -2:
            slaps_indicators.append("melting")
            factors.append(f"Snø smelter: {abs(snow_change):.1f} cm siste 6t")

        if len(slaps_indicators) >= 2:
            return AnalysisResult(
                risk_level=RiskLevel.HIGH,
                message=f"Slaps! Regn ({precip:.1f} mm/t) på smeltende snø ved {temp:.1f}°C",
                scenario="Kraftig slaps",
                factors=factors,
                details=details
            )

        if "rain_on_snow" in slaps_indicators:
            if precip_12h >= thresholds.precipitation_12h_heavy:
                return AnalysisResult(
                    risk_level=RiskLevel.HIGH,
                    message=f"Kraftig regn på snø ({precip:.1f} mm/t) - vanskelig fremkommelighet",
                    scenario="Regn på snø",
                    factors=factors,
                    details=details
                )
            return AnalysisResult(
                risk_level=RiskLevel.MEDIUM,
                message=f"Regn på snø ved {temp:.1f}°C - slaps dannes",
                scenario="Regn på snø",
                factors=factors,
                details=details
            )

        if "melting" in slaps_indicators:
            return AnalysisResult(
                risk_level=RiskLevel.MEDIUM,
                message="Snøsmelting pågår - slaps på veien",
                scenario="Smelting",
                factors=factors,
                details=details
            )

        # Slaps-temperatur men ingen aktiv nedbør/smelting
        # Sjekk for frysefare (slaps som kan fryse)
        is_cooling = self._is_temperature_falling(df)

        if is_cooling and temp <= thresholds.temp_max:
            factors.append("Temperatur synker - frysefare")
            return AnalysisResult(
                risk_level=RiskLevel.MEDIUM,
                message=f"Slaps-forhold med frysefare ({temp:.1f}°C, synkende)",
                scenario="Frysefare",
                factors=factors,
                details=details
            )

        return AnalysisResult(
            risk_level=RiskLevel.LOW,
            message=f"Slaps-temperatur ({temp:.1f}°C) men ingen aktiv nedbør",
            scenario="Potensielt slaps",
            factors=factors + ["Krever både nedbør/smelting"],
            details=details
        )

    def _calculate_precip_total(self, df: pd.DataFrame, hours: int = 12) -> float:
        """Akkumuler nedbør siste N timer (mm)."""
        if 'reference_time' not in df.columns or 'precipitation_1h' not in df.columns or df.empty:
            return 0.0

        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=hours)
        recent = df[df['reference_time'] >= cutoff].copy()
        if recent.empty:
            return 0.0

        vals = pd.to_numeric(recent['precipitation_1h'], errors='coerce').fillna(0.0)
        return float(vals.sum())

    def _calculate_snow_change(self, df: pd.DataFrame, hours: int = 6) -> float:
        """Beregn snøendring over tid."""
        if 'surface_snow_thickness' not in df.columns:
            return 0.0

        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=hours)

        recent = df[df['reference_time'] >= cutoff].copy()
        if len(recent) < 2:
            return 0.0

        snow_values = recent['surface_snow_thickness'].dropna()
        if len(snow_values) < 2:
            return 0.0

        return snow_values.iloc[-1] - snow_values.iloc[0]

    def _is_precipitation_rain(
        self,
        temp: float | None,
        dew_point: float | None
    ) -> bool:
        """
        Klassifiser om nedbør er regn (ikke snø).

        Args:
            temp: Lufttemperatur
            dew_point: Duggpunkt

        Returns:
            True hvis nedbør sannsynligvis er regn
        """
        # Primær metode: duggpunkt
        if dew_point is not None:
            return dew_point >= 0.0  # Duggpunkt >= 0 = regn

        # Sekundær metode: lufttemperatur
        if temp is not None:
            return temp >= 1.0  # Temp >= 1°C = sannsynligvis regn

        return False

    def _is_temperature_falling(self, df: pd.DataFrame, hours: int = 3) -> bool:
        """Sjekk om temperatur synker."""
        if 'air_temperature' not in df.columns:
            return False

        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=hours)

        recent = df[df['reference_time'] >= cutoff].copy()
        if len(recent) < 2:
            return False

        temps = recent['air_temperature'].dropna()
        if len(temps) < 2:
            return False

        # Synkende hvis siste temp er lavere enn snitt
        return temps.iloc[-1] < temps.mean()
