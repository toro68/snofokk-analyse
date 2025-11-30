"""
Nysnø-deteksjon.

Varsler brøytemannskaper og hytteeiere om nysnø som krever brøyting.
Bruker duggpunkt som primær indikator for snø vs regn.
"""

from datetime import UTC, datetime, timedelta

import pandas as pd

from src.analyzers.base import AnalysisResult, BaseAnalyzer, RiskLevel
from src.config import settings


class FreshSnowAnalyzer(BaseAnalyzer):
    """
    Analyserer nysnø-forhold.

    Kriterier:
    - Snødybde øker ≥ 5 cm over 6 timer → MODERAT
    - Snødybde øker ≥ 10 cm over 6 timer → HØY

    Snø vs regn-klassifisering:
    - Primær: Duggpunkt < 0°C → nedbør er snø
    - Sekundær: Lufttemp < 1°C (hvis duggpunkt mangler)
    """

    REQUIRED_COLUMNS = ['surface_snow_thickness']

    def analyze(self, df: pd.DataFrame) -> AnalysisResult:
        """
        Analyser nysnø-forhold.

        Args:
            df: DataFrame med værdata

        Returns:
            AnalysisResult med risikovurdering
        """
        if not self._validate_data(df):
            return AnalysisResult(
                risk_level=RiskLevel.UNKNOWN,
                message="Mangler snødybde-data",
                scenario="Data mangler"
            )

        # Sommersesong = ingen nysnø-varsling
        if not self.is_winter_season():
            return self._summer_result()

        return self._winter_analysis(df)

    def _summer_result(self) -> AnalysisResult:
        """Returner lav risiko for sommersesong."""
        return AnalysisResult(
            risk_level=RiskLevel.LOW,
            message="Sommersesong - ingen nysnø-varsling",
            scenario="Sommer",
            factors=["☀️ Utenfor vintersesong"]
        )

    def _winter_analysis(self, df: pd.DataFrame) -> AnalysisResult:
        """Full vinteranalyse for nysnø."""
        thresholds = settings.fresh_snow

        # Hent verdier
        latest = self._get_latest(df)
        snow_now = self._safe_get(latest, 'surface_snow_thickness', 0)
        temp = self._safe_get(latest, 'air_temperature')
        dew_point = self._safe_get(latest, 'dew_point_temperature')
        precip = self._safe_get(latest, 'precipitation_1h', 0)

        # Beregn snøendring siste 6 timer
        snow_change = self._calculate_snow_change(df, hours=6)

        # Sjekk om nedbør er snø (ikke regn)
        is_snow = self._is_precipitation_snow(temp, dew_point, precip)

        # Aktiv snøfall pågår?
        active_snowfall = precip > thresholds.precipitation_min and is_snow

        factors = []
        details = {
            "snow_depth_cm": round(snow_now, 1),
            "snow_change_6h": round(snow_change, 1),
            "temperature": round(temp, 1) if temp else None,
            "dew_point": round(dew_point, 1) if dew_point else None,
            "precipitation_mm": round(precip, 2),
            "is_snow": is_snow,
        }

        # Bygg faktor-liste
        factors.append(f"❄️ Snødybde: {snow_now:.0f} cm")
        if snow_change > 0:
            factors.append(f"📈 Økt {snow_change:.1f} cm siste 6t")
        elif snow_change < -2:
            factors.append(f"📉 Redusert {abs(snow_change):.1f} cm siste 6t (smelting)")

        if active_snowfall:
            factors.append(f"🌨️ Aktivt snøfall: {precip:.1f} mm/t")

        if is_snow and dew_point is not None:
            factors.append(f"🌡️ Duggpunkt {dew_point:.1f}°C < 0 → snø")

        # Klassifiser risiko
        if snow_change >= thresholds.snow_increase_critical:
            return AnalysisResult(
                risk_level=RiskLevel.HIGH,
                message=f"Kraftig snøfall! {snow_change:.0f} cm siste 6 timer",
                scenario="Kraftig nysnø",
                factors=factors,
                details=details
            )

        if snow_change >= thresholds.snow_increase_warning:
            return AnalysisResult(
                risk_level=RiskLevel.MEDIUM,
                message=f"Nysnø: {snow_change:.0f} cm siste 6 timer",
                scenario="Nysnø",
                factors=factors,
                details=details
            )

        if active_snowfall:
            return AnalysisResult(
                risk_level=RiskLevel.MEDIUM,
                message=f"Snøfall pågår ({precip:.1f} mm/t)",
                scenario="Snøfall pågår",
                factors=factors,
                details=details
            )

        # Sjekk forventet snøfall basert på forhold
        if is_snow and precip > 0:
            return AnalysisResult(
                risk_level=RiskLevel.LOW,
                message=f"Lett snøvær ({precip:.1f} mm/t)",
                scenario="Lett snø",
                factors=factors,
                details=details
            )

        return AnalysisResult(
            risk_level=RiskLevel.LOW,
            message=f"Stabil snødybde: {snow_now:.0f} cm",
            scenario="Stabilt",
            factors=factors,
            details=details
        )

    def _calculate_snow_change(self, df: pd.DataFrame, hours: int = 6) -> float:
        """
        Beregn snøendring over tid.

        Args:
            df: DataFrame med værdata
            hours: Antall timer tilbake

        Returns:
            Snøendring i cm (positiv = økning)
        """
        if 'surface_snow_thickness' not in df.columns:
            return 0.0

        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=hours)

        # Filtrer til tidsperiode
        recent = df[df['reference_time'] >= cutoff].copy()
        if len(recent) < 2:
            return 0.0

        snow_values = recent['surface_snow_thickness'].dropna()
        if len(snow_values) < 2:
            return 0.0

        # Beregn endring fra start til slutt av perioden
        start_snow = snow_values.iloc[0]
        end_snow = snow_values.iloc[-1]

        return end_snow - start_snow

    def _is_precipitation_snow(
        self,
        temp: float | None,
        dew_point: float | None,
        precipitation: float | None
    ) -> bool:
        """
        Klassifiser om nedbør er snø.

        Primær: Duggpunkt < 0°C → snø
        Sekundær: Lufttemp < 1°C → snø

        Args:
            temp: Lufttemperatur
            dew_point: Duggpunkt

        Returns:
            True hvis nedbør sannsynligvis er snø
        """
        thresholds = settings.fresh_snow

        if precipitation is None or precipitation <= 0:
            return False

        # Primær metode: duggpunkt
        if dew_point is not None:
            return dew_point < thresholds.dew_point_max

        # Sekundær metode: lufttemperatur bare hvis nedbør faktisk måles
        if temp is not None:
            return temp < thresholds.air_temp_max

        return False
