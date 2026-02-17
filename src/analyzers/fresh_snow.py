"""
Nysnø-deteksjon.

Varsler brøytemannskaper og hytteeiere om nysnø som krever brøyting.
Bruker duggpunkt som primær indikator for snø vs regn.
"""

from datetime import timedelta

import pandas as pd

from src.analyzers.base import AnalysisResult, BaseAnalyzer, RiskLevel
from src.config import settings


class FreshSnowAnalyzer(BaseAnalyzer):
    """
    Analyserer nysnø-forhold.

    Kriterier:
    Vinduet styres av `settings.fresh_snow.lookback_hours` (default 12 timer).

    Tersklene er kalibrert mot historisk brøyting ("brøyting sannsynligvis nyttig"),
    ikke en garanti for når det blir ufremkommelig for alle. For noen kan dårlig
    fremkommelighet typisk oppleves først ved ~10+ cm, spesielt ved lett/tørr snø.

    - Våt snø: snødybde øker ≥ 6 cm over vinduet → MODERAT (kan nærme seg brøytebehov)
    - Våt snø: snødybde øker ≥ 7 cm over vinduet → HØY (brøyting ofte nyttig)
    - Tørr lett snø: snødybde øker ≥ 8 cm over vinduet → MODERAT
    - Tørr lett snø: snødybde øker ≥ 10 cm over vinduet → HØY

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
            factors=["Utenfor vintersesong"]
        )

    def _winter_analysis(self, df: pd.DataFrame) -> AnalysisResult:
        """Full vinteranalyse for nysnø."""
        thresholds = settings.fresh_snow

        window_hours = int(getattr(thresholds, "lookback_hours", 12))

        # Hent verdier
        latest = self._get_latest(df)
        snow_now = self._safe_get(latest, 'surface_snow_thickness', 0)
        temp = self._safe_get(latest, 'air_temperature')
        surface_temp = self._safe_get(latest, 'surface_temperature')
        dew_point = self._safe_get(latest, 'dew_point_temperature')
        precip = self._safe_get(latest, 'precipitation_1h', 0)
        wind = self._safe_get(latest, 'wind_speed')
        gust = self._safe_get(latest, 'max_wind_gust')

        # Beregn snøendring siste N timer.
        # Viktig: Ved vind kan snødybde synke selv når det snør (vindtransport til/fra måleren).
        snow_change = self._calculate_snow_change(df, hours=window_hours)
        precip_total = self._calculate_precip_total(df, hours=window_hours)

        # Fallback for vindpåvirket snøsensor bruker eksplisitt 6t-terskler.
        precip_fallback_hours = 6
        precip_fallback_total = self._calculate_precip_total(df, hours=precip_fallback_hours)

        # Sjekk om nedbør er snø (ikke regn)
        is_snow = self._is_precipitation_snow(temp, dew_point, precip)

        # Brukes for akkumulert nedbør selv om siste time er tørr.
        snow_favorable = (
            (dew_point is not None and dew_point < thresholds.dew_point_max)
            or (dew_point is None and temp is not None and temp < thresholds.air_temp_max)
        )

        surface_cold_enough = surface_temp is None or surface_temp <= thresholds.surface_temp_max

        wet_snow = self._is_wet_snow(temp=temp, dew_point=dew_point, surface_temp=surface_temp)
        snow_increase_warning = thresholds.snow_increase_warning if wet_snow else thresholds.snow_increase_warning_dry
        snow_increase_critical = thresholds.snow_increase_critical if wet_snow else thresholds.snow_increase_critical_dry
        precip_6h_warning = thresholds.precipitation_6h_warning_mm if wet_snow else thresholds.precipitation_6h_warning_mm_dry
        precip_6h_critical = thresholds.precipitation_6h_critical_mm if wet_snow else thresholds.precipitation_6h_critical_mm_dry

        windy = wind is not None and wind >= settings.snowdrift.wind_speed_gust_warning_gate
        snow_sensor_suspect = windy and snow_change < snow_increase_warning

        # Aktiv snøfall pågår?
        # OBS: selv om det snør i lufta, kan veien være våt/slaps hvis overflaten er for mild.
        active_snowfall = precip > thresholds.precipitation_min and is_snow and surface_cold_enough

        factors = []
        details = {
            "snow_depth_cm": round(snow_now, 1),
            "window_hours": window_hours,
            "snow_change_cm": round(snow_change, 1),
            "precip_total_mm": round(precip_total, 2),
            "precip_fallback_hours": precip_fallback_hours,
            "precip_fallback_total_mm": round(precip_fallback_total, 2),
            "temperature": round(temp, 1) if temp else None,
            "surface_temperature": round(surface_temp, 1) if surface_temp is not None else None,
            "dew_point": round(dew_point, 1) if dew_point else None,
            "precipitation_mm": round(precip, 2),
            "wind_speed": round(wind, 1) if wind is not None else None,
            "wind_gust": round(gust, 1) if gust is not None else None,
            "is_snow": is_snow,
            "wet_snow": wet_snow,
        }

        # Bygg faktor-liste
        factors.append(f"Snødybde: {snow_now:.0f} cm")
        if snow_change > 0:
            factors.append(f"Økt {snow_change:.1f} cm siste {window_hours}t")
        elif snow_change < settings.slaps.snow_melt_change_threshold_cm:
            factors.append(f"Redusert {abs(snow_change):.1f} cm siste {window_hours}t (smelting)")

        if precip_total > 0:
            factors.append(f"Nedbør {window_hours}t: {precip_total:.1f} mm")

        if wind is not None and wind >= settings.snowdrift.wind_speed_gust_warning_gate:
            factors.append(f"Vind {wind:.1f} m/s kan påvirke snødybde")

        if active_snowfall:
            factors.append(f"Aktivt snøfall: {precip:.1f} mm/t")

        if surface_temp is not None:
            factors.append(f"Bakketemp: {surface_temp:.1f}°C")

        if is_snow and dew_point is not None:
            factors.append(f"Duggpunkt {dew_point:.1f}°C < 0 → snø")

        # Klassifiser risiko
        if snow_change >= snow_increase_critical:
            return AnalysisResult(
                risk_level=RiskLevel.HIGH,
                message=f"Kraftig snøfall! {snow_change:.0f} cm siste {window_hours} timer",
                scenario="Kraftig nysnø",
                factors=factors,
                details=details
            )

        if snow_change >= snow_increase_warning:
            return AnalysisResult(
                risk_level=RiskLevel.MEDIUM,
                message=f"Nysnø: {snow_change:.0f} cm siste {window_hours} timer",
                scenario="Nysnø",
                factors=factors,
                details=details
            )

        # Fallback: Hvis snødybdemåler påvirkes av vind, bruk 6t akkumulert nedbør som proxy for nysnø.
        if snow_sensor_suspect and snow_favorable and surface_cold_enough and precip_fallback_total >= precip_6h_critical:
            return AnalysisResult(
                risk_level=RiskLevel.HIGH,
                message=f"Kraftig snøfall (nedbør {precip_fallback_total:.0f} mm siste {precip_fallback_hours}t)",
                scenario="Kraftig nysnø (nedbør)",
                factors=factors,
                details=details
            )

        if snow_sensor_suspect and snow_favorable and surface_cold_enough and precip_fallback_total >= precip_6h_warning:
            return AnalysisResult(
                risk_level=RiskLevel.MEDIUM,
                message=f"Nysnø sannsynlig (nedbør {precip_fallback_total:.0f} mm siste {precip_fallback_hours}t)",
                scenario="Nysnø (nedbør)",
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
        if is_snow and precip >= thresholds.precipitation_min and surface_cold_enough:
            return AnalysisResult(
                risk_level=RiskLevel.LOW,
                message=f"Lett snøvær ({precip:.1f} mm/t)",
                scenario="Lett snø",
                factors=factors,
                details=details
            )

        if is_snow and precip >= thresholds.precipitation_min and not surface_cold_enough:
            return AnalysisResult(
                risk_level=RiskLevel.LOW,
                message=f"Nedbør, men mild bakke ({precip:.1f} mm/t)",
                scenario="Mild bakke",
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

        if df.empty or 'reference_time' not in df.columns:
            return 0.0

        now = pd.to_datetime(df['reference_time']).max()
        if pd.isna(now):
            return 0.0

        cutoff = now - timedelta(hours=hours)

        # Filtrer til tidsperiode
        recent = df[pd.to_datetime(df['reference_time']) >= cutoff].copy()
        if len(recent) < 2:
            return 0.0

        snow_values = recent['surface_snow_thickness'].dropna()
        if len(snow_values) < 2:
            return 0.0

        # Beregn endring fra start til slutt av perioden
        start_snow = snow_values.iloc[0]
        end_snow = snow_values.iloc[-1]

        return end_snow - start_snow

    def _calculate_precip_total(self, df: pd.DataFrame, hours: int = 6) -> float:
        """Akkumulert nedbør siste N timer (mm), basert på `precipitation_1h`."""
        if df.empty or 'reference_time' not in df.columns or 'precipitation_1h' not in df.columns:
            return 0.0

        now = pd.to_datetime(df['reference_time']).max()
        if pd.isna(now):
            return 0.0

        cutoff = now - timedelta(hours=hours)

        # Bruk "siste N timer" (ekskluderer punktet akkurat på cutoff) for å unngå å telle 7 timer ved timeoppløsning.
        recent = df[pd.to_datetime(df['reference_time']) > cutoff].copy()
        if recent.empty:
            return 0.0

        precip = pd.to_numeric(recent['precipitation_1h'], errors='coerce').fillna(0)
        return float(precip.sum())

    def _is_wet_snow(
        self,
        *,
        temp: float | None,
        dew_point: float | None,
        surface_temp: float | None,
    ) -> bool:
        """Heuristikk: klassifiser om snø sannsynligvis er "våt" (tung) vs "tørr".

        Bruker bare parametre vi har fra Frost-stasjonen: lufttemp, duggpunkt, bakketemp.
        """
        th = settings.fresh_snow

        if temp is not None and th.wet_snow_air_temp_min <= temp <= th.wet_snow_air_temp_max:
            return True
        if dew_point is not None and th.wet_snow_dew_point_min <= dew_point <= th.wet_snow_dew_point_max:
            return True
        # Overflaten nær 0°C er ofte en indikator på våt/tung snø eller blanding.
        if surface_temp is not None and -0.5 <= surface_temp <= 0.5:
            return True

        return False

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
