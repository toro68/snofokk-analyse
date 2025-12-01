"""
Glattføre-risikoanalyse.

Fokuserer på:
- Regn på snø (hovedscenario for glatte veier)
- Is-dannelse (overflatetemperatur under frysepunkt)
- Rimfrost (duggpunkt nær lufttemperatur)
"""

from datetime import UTC, datetime, timedelta

import pandas as pd

from src.analyzers.base import AnalysisResult, BaseAnalyzer, RiskLevel
from src.config import settings


class SlipperyRoadAnalyzer(BaseAnalyzer):
    """
    Analyserer risiko for glatte veier.

    Hovedscenarier:
    1. Regn på snø - mildvær + nedbør + snødekke
    2. Is-dannelse - bakketemperatur ≤ 0°C (PRIMÆR!)
    3. Rimfrost - duggpunkt nær lufttemperatur ved frost
    4. Temperaturovergang - stigning fra frost til mildvær

    NY INNSIKT (2025):
    - Bakketemperatur er i snitt 2.1°C kaldere enn luft
    - 28 av 166 brøyteepisoder: luft > 0°C men bakke < 0°C = FRYSEFARE
    - Bruk surface_temperature < 0 som primær is-indikator
    """

    REQUIRED_COLUMNS = ['air_temperature']

    def analyze(self, df: pd.DataFrame) -> AnalysisResult:
        """
        Analyser glattføre-risiko.

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

        latest = self._get_latest(df)

        # Hent alle relevante verdier
        temp = self._safe_get(latest, 'air_temperature')
        snow = self._safe_get(latest, 'surface_snow_thickness', 0)
        precip = self._safe_get(latest, 'precipitation_1h', 0)
        surface_temp = self._safe_get(latest, 'surface_temperature')
        dew_point = self._safe_get(latest, 'dew_point_temperature')
        humidity = self._safe_get(latest, 'relative_humidity')

        if temp is None:
            return AnalysisResult(
                risk_level=RiskLevel.UNKNOWN,
                message="Mangler temperaturdata",
                scenario="Data mangler"
            )

        # Sommersesong = enklere analyse
        if not self.is_winter_season():
            return self._summer_analysis(temp, precip, surface_temp, dew_point)

        # Vintersesong = full analyse
        return self._winter_analysis(
            df=df,
            temp=temp,
            snow=snow,
            precip=precip,
            surface_temp=surface_temp,
            dew_point=dew_point,
            humidity=humidity
        )

    def _summer_analysis(
        self,
        temp: float,
        precip: float,
        surface_temp: float | None,
        dew_point: float | None
    ) -> AnalysisResult:
        """Sommeranalyse - fokus på rimfrost og regn."""
        factors = []

        # Sjekk rimfrost (kan forekomme på kalde sommernetter)
        frost_risk = False
        if surface_temp is not None and dew_point is not None:
            frost_risk = surface_temp <= 0 and abs(temp - dew_point) < 2
            if frost_risk:
                factors.append(f"🧊 Rimfrost-risiko (bakketemperatur: {surface_temp:.1f}°C)")

        if frost_risk:
            return AnalysisResult(
                risk_level=RiskLevel.MEDIUM,
                message=f"Rimfrost-forhold mulig ({temp:.1f}°C)",
                scenario="Rimfrost",
                factors=factors,
                details={"surface_temp": surface_temp, "dew_point": dew_point}
            )

        if precip >= 0.5:
            return AnalysisResult(
                risk_level=RiskLevel.LOW,
                message=f"Sommerregn ({precip:.1f} mm/h) - normalt gode forhold",
                scenario="Sommerregn",
                factors=[f"🌧️ Nedbør: {precip:.1f} mm/h"]
            )

        return AnalysisResult(
            risk_level=RiskLevel.LOW,
            message=f"Normale sommerforhold ({temp:.1f}°C)",
            scenario="Sommer",
            factors=["✅ Sommersesong - lav glattføre-risiko"]
        )

    def _winter_analysis(
        self,
        df: pd.DataFrame,
        temp: float,
        snow: float,
        precip: float,
        surface_temp: float | None,
        dew_point: float | None,
        humidity: float | None
    ) -> AnalysisResult:
        """Full vinteranalyse."""
        thresholds = settings.slippery
        factors = []

        details = {
            "temperature": round(temp, 1),
            "snow_depth": round(snow, 1),
            "precipitation": round(precip, 2) if precip else 0,
            "surface_temp": round(surface_temp, 1) if surface_temp else None,
            "dew_point": round(dew_point, 1) if dew_point else None,
        }

        # SCENARIO 0: Nysnø = naturlig strøing (lav risiko) - men kun ved kaldt vær
        if self._check_recent_snow(df):
            return AnalysisResult(
                risk_level=RiskLevel.LOW,
                message="Fersk nysnø - naturlig strøing",
                scenario="Snøfall",
                factors=["🌨️ Økende snødybde - gir friksjon"],
                details=details
            )

        # Sjekk ulike risikoscenarier
        mild_weather = thresholds.mild_temp_min <= temp <= thresholds.mild_temp_max
        existing_snow = snow >= thresholds.snow_depth_min_cm
        rain_now = precip >= thresholds.rain_threshold_mm

        # Samle faktorer
        if mild_weather:
            factors.append(f"🌡️ Mildvær ({temp:.1f}°C)")
        if existing_snow:
            factors.append(f"❄️ Snødekke ({snow:.0f} cm)")
        if rain_now:
            factors.append(f"🌧️ Nedbør ({precip:.1f} mm/h)")

        # NY PRIMÆR LOGIKK: Bakketemperatur-basert is-risiko
        hidden_freeze = False
        ice_risk = False
        if surface_temp is not None:
            ice_risk = surface_temp <= thresholds.surface_temp_freeze
            # KRITISK: Luft > 0 men bakke < 0 = skjult frysefare!
            hidden_freeze = temp > 0 and surface_temp < 0
            if hidden_freeze:
                factors.insert(0, f"⚠️ SKJULT FRYSEFARE: Luft {temp:.1f}°C, bakke {surface_temp:.1f}°C")
            elif ice_risk:
                factors.append(f"🧊 Kald bakke ({surface_temp:.1f}°C)")

            # Vis temperaturforskjell
            temp_diff = temp - surface_temp
            if temp_diff > 2:
                factors.append(f"📉 Bakke {temp_diff:.1f}°C kaldere enn luft")

        # Rimfrost-risiko
        frost_risk = False
        if surface_temp is not None and dew_point is not None:
            frost_risk = surface_temp <= 0 and abs(temp - dew_point) < 2
            if frost_risk:
                factors.append(f"🌫️ Rimfrost-forhold (duggpunkt: {dew_point:.1f}°C)")

        # Temperaturovergang
        temp_rising = self._check_temp_rise(df)
        if temp_rising:
            factors.append("📈 Temperaturøkning siste 6t")

        # SCENARIO 0: Skjult frysefare (KRITISK - ofte oversett!)
        if hidden_freeze:
            return AnalysisResult(
                risk_level=RiskLevel.HIGH,
                message=f"FRYSEFARE! Plusgrader i luft ({temp:.1f}°C) men bakke under frysepunkt ({surface_temp:.1f}°C)",
                scenario="Skjult frysefare",
                factors=factors,
                details=details
            )

        # SCENARIO 1: Regn på snø (KRITISK)
        if mild_weather and existing_snow and rain_now:
            if not self._recent_snow_absent(df):
                return AnalysisResult(
                    risk_level=RiskLevel.MEDIUM,
                    message=f"Regn ({precip:.1f} mm/h) på fersk snø - slaps, ikke is",
                    scenario="Regn på snø",
                    factors=factors + ["❄️ Fersk snø modererer glattføre"],
                    details=details
                )
            return AnalysisResult(
                risk_level=RiskLevel.HIGH,
                message=f"Høy glattføre-risiko! Regn ({precip:.1f} mm/h) på {snow:.0f} cm snø ved {temp:.1f}°C",
                scenario="Regn på snø",
                factors=factors,
                details=details
            )

        # SCENARIO 2: Is-dannelse (KRITISK hvis kombinert med nedbør)
        if ice_risk and rain_now:
            return AnalysisResult(
                risk_level=RiskLevel.HIGH,
                message=f"Høy glattføre-risiko! Nedbør fryser på kald bakke ({surface_temp:.1f}°C)",
                scenario="Is-dannelse",
                factors=factors,
                details=details
            )

        if ice_risk and existing_snow:
            return AnalysisResult(
                risk_level=RiskLevel.MEDIUM,
                message=f"Moderat risiko: Kald bakke ({surface_temp:.1f}°C) under snødekke",
                scenario="Is under snø",
                factors=factors,
                details=details
            )

        # SCENARIO 3: Rimfrost
        if frost_risk:
            return AnalysisResult(
                risk_level=RiskLevel.MEDIUM,
                message=f"Moderat risiko: Rimfrost-forhold (duggpunkt {dew_point:.1f}°C)",
                scenario="Rimfrost",
                factors=factors,
                details=details
            )

        # SCENARIO 4: Temperaturovergang
        if mild_weather and existing_snow and temp_rising:
            return AnalysisResult(
                risk_level=RiskLevel.MEDIUM,
                message=f"Moderat risiko: Snøsmelting pga. temperaturøkning til {temp:.1f}°C",
                scenario="Temperaturovergang",
                factors=factors,
                details=details
            )

        # SCENARIO 5: Stabilt kaldt (LAV RISIKO)
        if temp < -5 and existing_snow:
            return AnalysisResult(
                risk_level=RiskLevel.LOW,
                message=f"Stabile vinterforhold: Kaldt ({temp:.1f}°C) og tørt",
                scenario="Stabilt kaldt",
                factors=factors + ["✅ Tørr snø ved god frost"],
                details=details
            )

        # Default: Lav risiko
        return AnalysisResult(
            risk_level=RiskLevel.LOW,
            message="Lav glattføre-risiko. Normale vinterforhold.",
            scenario="Normal",
            factors=factors if factors else ["✅ Ingen kritiske kombinasjoner"],
            details=details
        )

    def _check_recent_snow(self, df: pd.DataFrame) -> bool:
        """Sjekk om snødybden har økt nylig (naturlig strøing)."""
        if 'surface_snow_thickness' not in df.columns:
            return False

        now = datetime.now(UTC)
        window = settings.slippery.recent_snow_relief_hours
        sample = df[df['reference_time'] >= (now - timedelta(hours=window))]

        if len(sample) < 2:
            return False

        snow = sample['surface_snow_thickness'].dropna()
        if len(snow) < 2:
            return False

        return (snow.iloc[-1] - snow.iloc[0]) >= settings.slippery.recent_snow_relief_cm

    def _recent_snow_absent(self, df: pd.DataFrame) -> bool:
        """True hvis ingen fersk snø (øker sensitivitet for regn på snø)."""
        return not self._check_recent_snow(df)

    def _check_temp_rise(self, df: pd.DataFrame) -> bool:
        """Sjekk om temperaturen stiger markant."""
        if 'air_temperature' not in df.columns:
            return False

        now = datetime.now(UTC)
        last_6h = df[df['reference_time'] >= (now - timedelta(hours=6))]

        if len(last_6h) < 2:
            return False

        temps = last_6h['air_temperature'].dropna()
        if len(temps) < 2:
            return False

        # Økning på minst 1°C siste 6 timer
        return (temps.iloc[-1] - temps.iloc[0]) >= settings.slippery.temp_rise_threshold
