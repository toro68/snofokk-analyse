"""
Snøfokk-risikoanalyse.

Bruker ML-baserte terskler validert mot 149 historiske episoder.
Vindkjøling har 73.1% viktighet i modellen.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from src.analyzers.base import AnalysisResult, BaseAnalyzer, RiskLevel
from src.config import settings


class SnowdriftAnalyzer(BaseAnalyzer):
    """
    Analyserer risiko for snøfokk.

    Bruker kombinasjon av:
    - Vindkast (primær trigger!) - bedre enn snittwind
    - ML-baserte vindkjøling-terskler
    - Tradisjonelle temperatur/vind-kriterier
    - Løssnø-tilgjengelighet

    Ny innsikt (2025):
    - Snøfokk-episoder: snittwind 10.3 m/s, vindkast 21.9 m/s
    - 73% fra SE-S vindretninger (135-225°)
    """

    REQUIRED_COLUMNS = ['air_temperature', 'wind_speed', 'surface_snow_thickness']

    def analyze(self, df: pd.DataFrame) -> AnalysisResult:
        """
        Analyser snøfokk-risiko.

        Args:
            df: DataFrame med værdata

        Returns:
            AnalysisResult med risikovurdering
        """
        if not self._validate_data(df):
            return AnalysisResult(
                risk_level=RiskLevel.UNKNOWN,
                message="Mangler nødvendige data for snøfokk-analyse",
                scenario="Data mangler"
            )

        # Sommersesong = begrenset analyse
        if not self.is_winter_season():
            return self._summer_analysis(df)

        return self._winter_analysis(df)

    def _summer_analysis(self, df: pd.DataFrame) -> AnalysisResult:
        """Begrenset analyse for sommersesong."""
        latest = self._get_latest(df)
        snow = self._safe_get(latest, 'surface_snow_thickness', 0)
        temp = self._safe_get(latest, 'air_temperature', 0)

        if snow < 1:
            return AnalysisResult(
                risk_level=RiskLevel.LOW,
                message=f"Sommersesong uten snø ({temp:.1f}°C)",
                scenario="Sommer",
                factors=["Ingen snø på bakken"]
            )

        return AnalysisResult(
            risk_level=RiskLevel.MEDIUM,
            message=f"Uvanlig snø i sommermånedene ({snow:.0f} cm)",
            scenario="Sommer-snø",
            factors=[f"Snødybde: {snow:.0f} cm", f"Temperatur: {temp:.1f}°C"]
        )

    def _winter_analysis(self, df: pd.DataFrame) -> AnalysisResult:
        """Full vinteranalyse med ML-terskler og vindkast."""
        thresholds = settings.snowdrift
        lookback_hours = thresholds.interval_hours
        window = self._select_recent_window(df, lookback_hours)
        loose_snow = self._check_loose_snow(window)
        snow_change = self._calculate_snow_change(window)

        best_result: AnalysisResult | None = None
        best_priority = -1

        for _, row in window.iterrows():
            snapshot = self._evaluate_snapshot(
                row=row,
                loose_snow=loose_snow,
                snow_change=snow_change,
                thresholds=thresholds,
                lookback_hours=lookback_hours
            )

            if snapshot is None:
                continue

            priority = self._risk_priority(snapshot.risk_level)
            if priority > best_priority:
                best_priority = priority
                best_result = snapshot
            elif priority == best_priority and best_result is not None:
                current_gust = snapshot.details.get('wind_gust') or 0
                best_gust = best_result.details.get('wind_gust') or 0
                if current_gust > best_gust:
                    best_result = snapshot

        if best_result is not None:
            return best_result

        return AnalysisResult(
            risk_level=RiskLevel.UNKNOWN,
            message="Mangler temperatur eller vinddata",
            scenario="Data mangler"
        )

    def _select_recent_window(self, df: pd.DataFrame, hours: int) -> pd.DataFrame:
        """Returner data for de siste N timene, eller hele datasettet hvis kortere."""
        if 'reference_time' not in df.columns or df.empty:
            return df
        times = pd.to_datetime(df['reference_time'])
        latest = times.iloc[-1]
        cutoff = latest - pd.Timedelta(hours=hours)
        recent = df.loc[times >= cutoff]
        return recent if not recent.empty else df

    def _is_critical_wind_direction(self, wind_dir: float | None) -> bool:
        """
        Sjekk om vinden kommer fra kritisk retning (SE-S).

        73% av snøfokk-episoder på Gullingen kom fra SE-S (135-225°).
        """
        if wind_dir is None:
            return False

        thresholds = settings.snowdrift
        return thresholds.critical_wind_dir_min <= wind_dir <= thresholds.critical_wind_dir_max

    def _check_loose_snow(self, df: pd.DataFrame) -> dict:
        """
        Sjekk om det er løssnø tilgjengelig.

        Løssnø kreves for snøfokk. Faktorer:
        - Nysnø gir frisk løssnø
        - Kontinuerlig frost bevarer løssnø
        - Mildvær (>0°C) smelter/kompakterer snøen
        """
        now = datetime.now(UTC)
        last_24h = df[df['reference_time'] >= (now - timedelta(hours=24))]

        if 'air_temperature' not in last_24h.columns or last_24h.empty:
            return {"available": True, "reason": "Usikker - mangler temperaturdata"}

        temps = last_24h['air_temperature'].dropna()
        if len(temps) == 0:
            return {"available": True, "reason": "Usikker - mangler temperaturdata"}

        # Sjekk for mildvær
        mild_hours = (temps > 0).sum()
        continuous_frost = (temps <= -1).all()

        if continuous_frost:
            return {"available": True, "reason": "Kontinuerlig frost bevarer løssnø"}
        elif mild_hours >= 6:
            return {"available": False, "reason": f"Mildvær siste 24t ({mild_hours} timer > 0°C)"}
        elif mild_hours > 0:
            return {"available": True, "reason": f"Delvis mildvær ({mild_hours} timer > 0°C)"}
        else:
            return {"available": True, "reason": "Frostforhold"}

    def _calculate_snow_change(self, df: pd.DataFrame) -> float:
        """Beregn snøendring over vinduet."""
        if 'surface_snow_thickness' not in df.columns or len(df) < 2:
            return 0.0

        snow = df['surface_snow_thickness'].dropna()
        if len(snow) < 2:
            return 0.0

        return snow.iloc[-1] - snow.iloc[0]

    def _evaluate_snapshot(
        self,
        row: pd.Series,
        loose_snow: dict,
        snow_change: float,
        thresholds,
        lookback_hours: int
    ) -> AnalysisResult | None:
        """Evaluer én observasjon og returner resultat."""
        temp = self._safe_get(row, 'air_temperature')
        wind = self._safe_get(row, 'wind_speed')
        if temp is None or wind is None:
            return None

        wind_gust = self._safe_get(row, 'max_wind_gust')
        wind_dir = self._safe_get(row, 'wind_from_direction')
        snow = self._safe_get(row, 'surface_snow_thickness', 0)
        wind_chill = self.calculate_wind_chill(temp, wind)
        is_critical_direction = self._is_critical_wind_direction(wind_dir)

        factors = self._collect_factors(
            temp=temp,
            wind=wind,
            wind_gust=wind_gust,
            wind_dir=wind_dir,
            snow=snow,
            wind_chill=wind_chill,
            snow_change=snow_change,
            is_critical_direction=is_critical_direction,
            thresholds=thresholds
        )

        result = self._classify_risk(
            temp=temp,
            wind=wind,
            wind_gust=wind_gust,
            snow=snow,
            wind_chill=wind_chill,
            loose_snow=loose_snow,
            snow_change=snow_change,
            is_critical_direction=is_critical_direction,
            factors=factors
        )

        reference_time = row.get('reference_time')
        try:
            reference_str = pd.to_datetime(reference_time).isoformat()
        except Exception:
            reference_str = str(reference_time) if reference_time is not None else None

        result.details = {
            **result.details,
            'reference_time': reference_str,
            'analysis_window_hours': lookback_hours
        }
        return result

    @staticmethod
    def _risk_priority(level: RiskLevel) -> int:
        order = {
            RiskLevel.UNKNOWN: -1,
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
        }
        return order.get(level, -1)

    def _collect_factors(
        self,
        temp: float,
        wind: float,
        wind_gust: float | None,
        wind_dir: float | None,
        snow: float,
        wind_chill: float,
        snow_change: float,
        is_critical_direction: bool,
        thresholds
    ) -> list[str]:
        """Samle risikofaktorer for visning."""
        factors = []

        # Vindkast (viktigste faktor!)
        if wind_gust is not None:
            if wind_gust >= thresholds.wind_gust_critical:
                factors.append(f"⚡ Kraftige vindkast ({wind_gust:.1f} m/s)!")
            elif wind_gust >= thresholds.wind_gust_warning:
                factors.append(f"🌬️ Vindkast ({wind_gust:.1f} m/s)")

        if wind >= thresholds.wind_speed_critical:
            factors.append(f"🌬️ Sterk vind ({wind:.1f} m/s)")
        elif wind >= thresholds.wind_speed_warning:
            factors.append(f"💨 Moderat vind ({wind:.1f} m/s)")

        if is_critical_direction:
            factors.append(f"⚠️ Kritisk vindretning ({wind_dir:.0f}° SE-S)")

        if temp <= thresholds.temperature_max:
            factors.append(f"🌡️ Frost ({temp:.1f}°C)")

        if snow >= thresholds.snow_depth_min_cm:
            factors.append(f"❄️ Snødekke ({snow:.0f} cm)")

        if wind_chill <= thresholds.wind_chill_critical:
            factors.append(f"🥶 Kritisk vindkjøling ({wind_chill:.1f}°C)")
        elif wind_chill <= thresholds.wind_chill_warning:
            factors.append(f"🌬️ Vindkjøling ({wind_chill:.1f}°C)")

        if snow_change >= thresholds.fresh_snow_threshold:
            factors.append(f"🌨️ Nysnø (+{snow_change:.1f} cm/h)")
        elif snow_change <= -0.2:
            factors.append(f"💨 Vindtransport ({snow_change:.1f} cm/h)")

        return factors

    def _classify_risk(
        self,
        temp: float,
        wind: float,
        wind_gust: float | None,
        snow: float,
        wind_chill: float,
        loose_snow: dict,
        snow_change: float,
        is_critical_direction: bool,
        factors: list[str]
    ) -> AnalysisResult:
        """Klassifiser risikonivå basert på alle faktorer."""
        thresholds = settings.snowdrift

        details = {
            "wind_chill": round(wind_chill, 1),
            "temperature": round(temp, 1),
            "wind_speed": round(wind, 1),
            "wind_gust": round(wind_gust, 1) if wind_gust else None,
            "snow_depth": round(snow, 1),
            "snow_change": round(snow_change, 2),
            "loose_snow_available": loose_snow["available"],
            "critical_direction": is_critical_direction
        }

        # Ingen løssnø = lav risiko
        if not loose_snow["available"]:
            return AnalysisResult(
                risk_level=RiskLevel.LOW,
                message=f"Stabile forhold: {loose_snow['reason']}",
                scenario="Ingen løssnø",
                factors=factors + [f"ℹ️ {loose_snow['reason']}"],
                details=details
            )

        # Minimum snødekke kreves
        if snow < thresholds.snow_depth_min_cm:
            return AnalysisResult(
                risk_level=RiskLevel.LOW,
                message=f"For lite snø for snøfokk ({snow:.0f} cm < {thresholds.snow_depth_min_cm} cm)",
                scenario="Lite snø",
                factors=factors,
                details=details
            )

        # NY: Vindkast-basert trigger (høyeste prioritet!)
        if wind_gust is not None:
            gust_gate_critical_ok = wind >= thresholds.wind_speed_warning
            gust_gate_warning_ok = wind >= thresholds.wind_speed_median

            if (
                gust_gate_critical_ok
                and wind_gust >= thresholds.wind_gust_critical
                and temp <= thresholds.temperature_max
            ):
                severity = "KRITISK" if is_critical_direction else "Høy"
                return AnalysisResult(
                    risk_level=RiskLevel.HIGH,
                    message=f"{severity} snøfokk-risiko! Vindkast {wind_gust:.1f} m/s ved {temp:.1f}°C",
                    scenario="Vindkast-kritisk",
                    factors=factors,
                    details={**details, "method": "Vindkast"}
                )

            if (
                gust_gate_warning_ok
                and wind_gust >= thresholds.wind_gust_warning
                and temp <= thresholds.temperature_max
            ):
                return AnalysisResult(
                    risk_level=RiskLevel.MEDIUM,
                    message=f"Snøfokk-fare. Vindkast {wind_gust:.1f} m/s ved {temp:.1f}°C",
                    scenario="Vindkast-advarsel",
                    factors=factors,
                    details={**details, "method": "Vindkast"}
                )

        # ML-kriterier (vindkjøling-basert)
        if (wind_chill <= thresholds.wind_chill_critical and
            wind >= thresholds.wind_speed_critical):
            return AnalysisResult(
                risk_level=RiskLevel.HIGH,
                message=f"Høy snøfokk-risiko! Vindkjøling {wind_chill:.1f}°C, vind {wind:.1f} m/s",
                scenario="ML-kritisk",
                factors=factors,
                details={**details, "method": "ML-basert"}
            )

        if (wind_chill <= thresholds.wind_chill_warning and
            wind >= thresholds.wind_speed_warning):
            return AnalysisResult(
                risk_level=RiskLevel.MEDIUM,
                message=f"Moderat snøfokk-risiko. Vindkjøling {wind_chill:.1f}°C, vind {wind:.1f} m/s",
                scenario="ML-advarsel",
                factors=factors,
                details={**details, "method": "ML-basert"}
            )

        # Tradisjonelle kriterier som fallback
        traditional_criteria = (
            wind >= thresholds.wind_speed_warning and
            temp <= thresholds.temperature_max
        )

        if traditional_criteria and wind >= thresholds.wind_speed_critical:
            return AnalysisResult(
                risk_level=RiskLevel.HIGH,
                message=f"Høy snøfokk-risiko. Sterk vind ({wind:.1f} m/s) ved frost ({temp:.1f}°C)",
                scenario="Tradisjonell-kritisk",
                factors=factors,
                details={**details, "method": "Tradisjonell"}
            )

        if traditional_criteria:
            return AnalysisResult(
                risk_level=RiskLevel.MEDIUM,
                message=f"Moderat snøfokk-risiko. Vind {wind:.1f} m/s, temp {temp:.1f}°C",
                scenario="Tradisjonell-moderat",
                factors=factors,
                details={**details, "method": "Tradisjonell"}
            )

        # Lav risiko
        return AnalysisResult(
            risk_level=RiskLevel.LOW,
            message="Lav snøfokk-risiko. Forhold innenfor normale grenser.",
            scenario="Normal",
            factors=factors if factors else ["✅ Alle kriterier under terskel"],
            details=details
        )
