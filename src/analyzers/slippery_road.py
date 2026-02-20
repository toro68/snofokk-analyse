"""
Glattføre-risikoanalyse.

Fokuserer på:
- Regn på snø (hovedscenario for glatte veier)
- Is-dannelse (overflatetemperatur under frysepunkt)
- Rimfrost (duggpunkt nær lufttemperatur)
"""

from datetime import timedelta

import pandas as pd

from src.analyzers.base import AnalysisResult, BaseAnalyzer, RiskLevel
from src.config import settings

# Forbehold som vises ved alle MEDIUM/HIGH varsler fra SlipperyRoadAnalyzer.
# Koden kan ikke vite om veibanen faktisk har en snø-/issåle eller tele.
# Tidlig vinter og om våren kan det regne på bar bakke – da er varslet irrelevant.
_SAALE_CAVEAT = (
    "Forutsetter etablert snø-/issåle eller tele i veibanen. "
    "Tidlig vinter og om våren – hvis regnet faller på bar asfalt – er varslet ikke relevant."
)


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
        wind = self._safe_get(latest, 'wind_speed')

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
            humidity=humidity,
            wind=wind
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
        thresholds = settings.slippery

        # Sjekk rimfrost (kan forekomme på kalde sommernetter)
        frost_risk = False
        if surface_temp is not None and dew_point is not None:
            frost_risk = (
                surface_temp <= thresholds.surface_temp_freeze
                and abs(temp - dew_point) < thresholds.rimfrost_dewpoint_delta_max
            )
            if frost_risk:
                factors.append(f"Rimfrost-risiko (bakketemperatur: {surface_temp:.1f}°C)")

        if frost_risk:
            return AnalysisResult(
                risk_level=RiskLevel.MEDIUM,
                message=f"Rimfrost-forhold mulig ({temp:.1f}°C)",
                scenario="Rimfrost",
                factors=factors,
                caveat=_SAALE_CAVEAT,
                details={"surface_temp": surface_temp, "dew_point": dew_point}
            )

        if precip >= thresholds.summer_rain_threshold_mm_per_h:
            return AnalysisResult(
                risk_level=RiskLevel.LOW,
                message=f"Sommerregn ({precip:.1f} mm/h) - normalt gode forhold",
                scenario="Sommerregn",
                factors=[f"Nedbør: {precip:.1f} mm/h"]
            )

        return AnalysisResult(
            risk_level=RiskLevel.LOW,
            message=f"Normale sommerforhold ({temp:.1f}°C)",
            scenario="Sommer",
            factors=["Sommersesong - lav glattføre-risiko"]
        )

    def _winter_analysis(
        self,
        df: pd.DataFrame,
        temp: float,
        snow: float,
        precip: float,
        surface_temp: float | None,
        dew_point: float | None,
        humidity: float | None,
        wind: float | None
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
            "wind_speed": round(wind, 1) if wind else None,
        }

        # SCENARIO 0: Nysnø = naturlig strøing (lav risiko) - men kun ved kaldt vær
        # OBS: Hopp over hvis det pågår regn (ikke snø) - regn på snø overstyrer!
        # Regn identifiseres ved duggpunkt ≥ 0°C, eller lufttemp ≥ 1°C hvis duggpunkt mangler.
        rain_falling_now = precip >= thresholds.rain_threshold_mm and (
            (dew_point is not None and dew_point >= settings.fresh_snow.dew_point_max)
            or (dew_point is None and temp >= settings.fresh_snow.air_temp_max)
        )
        if self._check_recent_snow(df) and not rain_falling_now:
            return AnalysisResult(
                risk_level=RiskLevel.LOW,
                message="Fersk nysnø - naturlig strøing",
                scenario="Snøfall",
                factors=["Økende snødybde - gir friksjon"],
                details=details
            )

        # Sjekk ulike risikoscenarier
        mild_weather = thresholds.mild_temp_min <= temp <= thresholds.mild_temp_max
        existing_snow = snow >= thresholds.snow_depth_min_cm
        near_freezing = thresholds.near_freezing_temp_min <= temp <= thresholds.near_freezing_temp_max

        snow_change_6h = self._calculate_snow_change(df, hours=6)

        precip_12h = self._precip_total(df, hours=12)
        details["precipitation_12h"] = round(precip_12h, 2)

        # KJERNEPREMISS: Glatte veier (is-fare) oppstår ved FLYTENDE nedbør (regn/sludd) på
        # kald/frossen bakke. Snøfall gir ikke is på veien – det er FreshSnowAnalyzer sitt domene.
        # Duggpunkt >= 0°C indikerer regn; < 0°C indikerer snø.
        # Konservativ fallback: hvis duggpunkt mangler, anta at nedbøren KAN være flytende.
        precip_is_liquid = dew_point is None or dew_point >= settings.fresh_snow.dew_point_max
        rain_now = precip >= thresholds.rain_threshold_mm and precip_is_liquid
        freezing_precip_warning = precip >= thresholds.freezing_precip_warning_mm and precip_is_liquid
        freezing_precip_critical = precip >= thresholds.freezing_precip_critical_mm and precip_is_liquid
        # Flytende nedbør siste 12t (regnfall som nå fryser = is-fare).
        liquid_precip_12h = precip_12h >= thresholds.hidden_freeze_precip_12h_min and precip_is_liquid

        # Samle faktorer
        if mild_weather:
            factors.append(f"Mildvær ({temp:.1f}°C)")
        if existing_snow:
            factors.append(f"Snødekke ({snow:.0f} cm)")
        if rain_now:
            factors.append(f"Nedbør ({precip:.1f} mm/h)")

        # NY PRIMÆR LOGIKK: Bakketemperatur-basert is-risiko
        hidden_freeze = False
        ice_risk = False
        if surface_temp is not None:
            ice_risk = surface_temp <= thresholds.surface_temp_freeze
            # KRITISK: Luft > 0 men bakke < 0 = skjult frysefare!
            hidden_freeze = (
                thresholds.hidden_freeze_air_min <= temp <= thresholds.hidden_freeze_air_max
                and surface_temp <= thresholds.hidden_freeze_surface_max
            )
            if hidden_freeze:
                factors.insert(0, f"SKJULT FRYSEFARE: Luft {temp:.1f}°C, bakke {surface_temp:.1f}°C")
            elif ice_risk:
                factors.append(f"Kald bakke ({surface_temp:.1f}°C)")

            # Vis temperaturforskjell
            temp_diff = temp - surface_temp
            if temp_diff > thresholds.surface_air_diff_notice_min_c:
                factors.append(f"Bakke {temp_diff:.1f}°C kaldere enn luft")

        # Rimfrost-risiko
        frost_risk = False
        if surface_temp is not None and dew_point is not None:
            frost_risk = (
                surface_temp <= thresholds.surface_temp_freeze
                    and abs(temp - dew_point) < thresholds.rimfrost_dewpoint_delta_max
                and (humidity is None or humidity >= thresholds.rimfrost_humidity_min)
                and (wind is None or wind <= thresholds.rimfrost_wind_max)
            )
            if frost_risk:
                factors.append(f"Rimfrost-forhold (duggpunkt: {dew_point:.1f}°C)")

        # Temperaturovergang
        temp_rising = self._check_temp_rise(df)
        if temp_rising:
            factors.append("Temperaturøkning siste 6t")

        # SCENARIO 0: Skjult frysefare – luft > 0°C men bakke < 0°C.
        # Farlig KUN hvis det er flytende nedbør (regn) nå eller nylig.
        # Kun kald bakke uten regn = ikke is-fare (normalt vintervær).
        if hidden_freeze:
            if rain_now or liquid_precip_12h:
                return AnalysisResult(
                    risk_level=RiskLevel.HIGH if rain_now else RiskLevel.MEDIUM,
                    message=(
                        f"FRYSEFARE! Regn ({precip:.1f} mm/h) på frossen bakke ({surface_temp:.1f}°C)"
                        if rain_now
                        else f"Isfare: Regnvær nylig på frossen bakke ({surface_temp:.1f}°C, luft {temp:.1f}°C)"
                    ),
                    scenario="Skjult frysefare",
                    factors=factors,
                    caveat=_SAALE_CAVEAT,
                    details={**details, "snow_change_6h": snow_change_6h}
                )
            # Ingen regn = ikke is-fare nå
            return AnalysisResult(
                risk_level=RiskLevel.LOW,
                message=f"Kald bakke ({surface_temp:.1f}°C) men ingen regn – lav is-risiko",
                scenario="Kald bakke uten regn",
                factors=factors,
                details={**details, "snow_change_6h": snow_change_6h}
            )

        # SCENARIO 1: Regn på snø (KRITISK)
        if mild_weather and existing_snow and rain_now:
            # Viktig: Snødybde måles i terreng og er ikke det samme som "snøkappe på vei".
            # For å redusere falske positiver på vårføre, bruker vi bakketemperatur når mulig.
            # Samtidig: etter en kuldeperiode kan mildvær + regn gi is/glatt føre selv om
            # bakketemperaturen akkurat nå er mild (snøkappe/kompakt underlag + refrysing senere).
            recent_hours = thresholds.rain_on_snow_recent_cold_hours
            recent_cold_surface = self._recent_min_leq(
                df,
                column='surface_temperature',
                hours=recent_hours,
                max_value=thresholds.rain_on_snow_recent_surface_temp_freeze_max_c,
            )
            recent_cold_air = self._recent_min_leq(
                df,
                column='air_temperature',
                hours=recent_hours,
                max_value=thresholds.rain_on_snow_recent_air_temp_freeze_max_c,
            )

            surface_near_freeze_now = (
                surface_temp is not None and surface_temp <= thresholds.rain_on_snow_surface_temp_max_c
            )
            cold_context = surface_near_freeze_now or recent_cold_surface or recent_cold_air

            if recent_cold_surface:
                factors.append(f"Kald bakke nylig (min siste {recent_hours}t ≤ {thresholds.rain_on_snow_recent_surface_temp_freeze_max_c:.0f}°C)")
            elif recent_cold_air:
                factors.append(f"Kuldeperiode nylig (min luft siste {recent_hours}t ≤ {thresholds.rain_on_snow_recent_air_temp_freeze_max_c:.0f}°C)")

            # Ingen kald kontekst → sannsynlig vårføre/bar vei: varsle moderat (vått/slaps) heller enn høy isfare.
            if not cold_context:
                surface_label = f"{surface_temp:.1f}°C" if surface_temp is not None else "ukjent"
                return AnalysisResult(
                    risk_level=RiskLevel.MEDIUM,
                    message=f"Regn ({precip:.1f} mm/h) på snø, men ingen nylig kulde (bakketemp {surface_label}) - vått/slaps",
                    scenario="Regn på snø (uten kald kontekst)",
                    factors=factors + ["Mild bakke uten nylig kulde reduserer is-risiko"],
                    caveat=_SAALE_CAVEAT,
                    details=details
                )
            if not self._recent_snow_absent(df):
                return AnalysisResult(
                    risk_level=RiskLevel.MEDIUM,
                    message=f"Regn ({precip:.1f} mm/h) på fersk snø - slaps, ikke is",
                    scenario="Regn på snø",
                    factors=factors + ["Fersk snø modererer glattføre"],
                    caveat=_SAALE_CAVEAT,
                    details=details
                )
            return AnalysisResult(
                risk_level=RiskLevel.HIGH,
                message=f"Høy glattføre-risiko! Regn ({precip:.1f} mm/h) på {snow:.0f} cm snø ved {temp:.1f}°C",
                scenario="Regn på snø",
                factors=factors,
                caveat=_SAALE_CAVEAT,
                details=details
            )

        # SCENARIO 2: Underkjølt regn / nedbør som fryser på kald bakke.
        # precip_is_liquid er allerede bakt inn i freezing_precip_* over.
        if ice_risk and freezing_precip_critical and near_freezing:
            return AnalysisResult(
                risk_level=RiskLevel.HIGH,
                message=f"Høy glattføre-risiko! Nedbør fryser på kald bakke ({surface_temp:.1f}°C)",
                scenario="Underkjølt regn / frysing",
                factors=factors,
                caveat=_SAALE_CAVEAT,
                details=details
            )

        if ice_risk and freezing_precip_warning and near_freezing:
            return AnalysisResult(
                risk_level=RiskLevel.MEDIUM,
                message=f"Mulig glatt føre: Lett regn på kald bakke ({surface_temp:.1f}°C)",
                scenario="Lett frysing",
                factors=factors,
                caveat=_SAALE_CAVEAT,
                details=details
            )

        # SCENARIO 2b, 3, 4: Kald bakke / rimfrost / temperaturovergang UTEN regn.
        # Ingen flytende nedbør = ingen is-fare. LAV risiko.
        if ice_risk and existing_snow:
            return AnalysisResult(
                risk_level=RiskLevel.LOW,
                message="Lav risiko: Tørr vinterføre (ingen regn)",
                scenario="Tørr vinterføre",
                factors=factors if factors else ["Ingen regn – is-risiko lav"],
                details=details
            )

        if frost_risk:
            return AnalysisResult(
                risk_level=RiskLevel.LOW,
                message=f"Rimfrost-forhold mulig, men ingen regn – lav is-risiko",
                scenario="Rimfrost",
                factors=factors,
                details=details
            )

        if mild_weather and existing_snow and temp_rising:
            return AnalysisResult(
                risk_level=RiskLevel.LOW,
                message=f"Snøsmelting pågår ({temp:.1f}°C) men ingen regn – ikke is-fare",
                scenario="Snøsmelting",
                factors=factors,
                details=details
            )

        # SCENARIO 5: Stabilt kaldt (LAV RISIKO)
        if temp < thresholds.stable_cold_air_temp_max and existing_snow:
            return AnalysisResult(
                risk_level=RiskLevel.LOW,
                message=f"Stabile vinterforhold: Kaldt ({temp:.1f}°C) og tørt",
                scenario="Stabilt kaldt",
                factors=factors + ["Tørr snø ved god frost"],
                details=details
            )

        # Default: Lav risiko
        return AnalysisResult(
            risk_level=RiskLevel.LOW,
            message="Lav glattføre-risiko. Normale vinterforhold.",
            scenario="Normal",
            factors=factors if factors else ["Ingen kritiske kombinasjoner"],
            details=details
        )

    def _recent_min_leq(self, df: pd.DataFrame, *, column: str, hours: int, max_value: float) -> bool:
        """True hvis minimum i `column` siste `hours` er <= `max_value` (basert på dataens tidsakse)."""
        if df.empty or 'reference_time' not in df.columns or column not in df.columns:
            return False

        now = self._analysis_now(df)
        cutoff = now - timedelta(hours=hours)
        recent = df[df['reference_time'] >= cutoff].copy()
        if recent.empty:
            return False

        vals = pd.to_numeric(recent[column], errors='coerce').dropna()
        if vals.empty:
            return False

        return float(vals.min()) <= float(max_value)

    def _check_recent_snow(self, df: pd.DataFrame) -> bool:
        """Sjekk om snødybden har økt nylig (naturlig strøing)."""
        if 'surface_snow_thickness' not in df.columns:
            return False

        now = self._analysis_now(df)
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

        now = self._analysis_now(df)
        last_6h = df[df['reference_time'] >= (now - timedelta(hours=6))]

        if len(last_6h) < 2:
            return False

        temps = last_6h['air_temperature'].dropna()
        if len(temps) < 2:
            return False

        # Økning på minst 1°C siste 6 timer
        return (temps.iloc[-1] - temps.iloc[0]) >= settings.slippery.temp_rise_threshold

    # _analysis_now, _calculate_snow_change og _precip_total er arvet fra BaseAnalyzer
