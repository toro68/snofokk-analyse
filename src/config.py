"""
Sentralisert konfigurasjon for Alarm System.

All konfigurasjon samlet på ett sted for enkel vedlikehold.
Støtter både lokal utvikling (.env) og Streamlit Cloud (secrets).
"""

# pylint: disable=too-many-lines,too-many-instance-attributes

import os
from datetime import datetime
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

try:
    import streamlit as st
    from streamlit.errors import StreamlitAPIException, StreamlitSecretNotFoundError
except (ImportError, ModuleNotFoundError):
    st = None

    class StreamlitAPIException(Exception):
        """Fallback når streamlit ikke er installert."""

    class StreamlitSecretNotFoundError(Exception):
        """Fallback når streamlit ikke er installert."""


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
        secrets = getattr(st, "secrets", None)
        if secrets is not None:
            try:
                if key in secrets:
                    return str(secrets[key])
            except (StreamlitSecretNotFoundError, StreamlitAPIException):
                # Ingen secrets.toml konfigurert (typisk i test/lokal miljø)
                pass
    except (ImportError, ModuleNotFoundError, RuntimeError, AttributeError, TypeError):
        pass

    # Fallback til miljøvariabler
    return os.getenv(key, default)


@dataclass(frozen=True)
class APIConfig:
    """Frost API konfigurasjon."""
    base_url: str = "https://frost.met.no/observations/v0.jsonld"
    sources_url: str = "https://frost.met.no/sources/v0.jsonld"
    elements_url: str = "https://frost.met.no/elements/v0.jsonld"
    met_forecast_url: str = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
    timeout: int = 30
    streamlit_cache_ttl_seconds: int = 300
    forecast_timeout_seconds: int = 15
    forecast_hours: int = 24

    # Default tidsvindu for "siste N timer"-kall (brukes hvis ikke overstyrt i UI)
    default_hours_back: int = 24

    @property
    def client_id(self) -> str:
        """Hent API-nøkkel fra secrets."""
        return get_secret("FROST_CLIENT_ID", "")


@dataclass(frozen=True)
class StationConfig:
    """Værstasjon konfigurasjon."""
    station_id: str = "SN46220"
    name: str = "Gullingen"
    # Metadata fra Frost-kilde (se `data/gullingen_station_candidates.json`)
    altitude_m: int = 639
    lat: float = 59.4128
    lon: float = 6.4697

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
    # Kalibrert mot brøyte-/vær-kobling (`data/analyzed/broyting_weather_correlation_2025.csv`)
    # for å øke sensitivitet uten å øke falske treff i evalueringssettet.
    wind_chill_warning: float = -10.0   # Moderat risiko

    # Vindstyrke-terskler (snitt)
    wind_speed_critical: float = 10.0   # Høy risiko
    wind_speed_warning: float = 8.0     # Moderat risiko

    # Gate for vindkast-advarsel ("gust warning")
    # Justert svakt ned (2026) for å fange flere bekreftede SNØFOKK-perioder
    # uten å redusere gust-tersklene.
    wind_speed_gust_warning_gate: float = 8.5

    # Vindkast-terskler (NY - bedre trigger!)
    # Historisk snitt: 21.9 m/s - justert terskel til 20.0 for å fange typiske episoder
    wind_gust_critical: float = 20.0    # Kritisk risiko (tidligere 22.0)
    wind_gust_warning: float = 14.0     # Moderat risiko (redusert varslingsstøy)

    # Kritiske vindretninger (SE-S)
    critical_wind_dir_min: float = 135.0  # SE
    critical_wind_dir_max: float = 225.0  # S

    # Andre terskler
    # Hevet fra -1.0°C: snøfokk kan opptre ned mot 0°C (grensesnø).
    # Terskelen blokkerte vindkast- og ML-triggere ved -0.5°C til 0°C.
    temperature_max: float = -0.5       # Må være frost (nær frysepunkt)
    snow_depth_min_cm: float = 3.0      # Minimum snødekke (spesifikasjon ≥3 cm)
    fresh_snow_threshold: float = 0.3   # cm/h for nysnø
    wind_transport_snow_change_threshold_cm_per_h: float = (
        -0.2
    )  # cm/h (negativ endring indikerer vindtransport)
    # Snøfokk er et akutt fenomen; vi evaluerer maksimum risiko over et kortere vindu enn
    # f.eks. slaps/nysnø for å fange perioder som kan blokkere vei raskt.
    interval_hours: int = 6             # Evaluer maksimum risiko siste N timer

    # Sommersesong: terskel for å si "ingen snø" i enklere analyse
    summer_snow_depth_min_cm: float = 1.0

    # Løssnø-tilgjengelighet (heuristikk basert på temperatur siste 24t)
    loose_snow_lookback_hours: int = 24
    loose_snow_mild_temp_min_c: float = 0.0
    loose_snow_continuous_frost_temp_max_c: float = -1.0
    loose_snow_mild_hours_min: int = 6


@dataclass(frozen=True)
class SlipperyRoadThresholds:
    """
    Terskler for glattføre-analyse.

    NY INNSIKT: Bakketemperatur er bedre indikator enn lufttemperatur!
    28 av 166 episoder hadde luft > 0°C men bakke < 0°C = FRYSEFARE
    """
    # Temperaturområde for regn-på-snø
    mild_temp_min: float = 0.0
    mild_temp_max: float = 5.0

    # Bakketemperatur (NY - kritisk for isdannelse)
    surface_temp_freeze: float = 0.0    # Is dannes når bakke < 0
    # Historisk observert snittdifferanse (luft - bakke).
    # NB: Ikke brukt direkte i logikken nå; beholdes som dokumentasjon/kalibreringskontekst.
    air_surface_diff_avg: float = 2.1
    surface_air_diff_notice_min_c: float = (
        2.0
    )  # Når vi viser "bakke kaldere enn luft" som egen faktor

    # Andre terskler
    snow_depth_min_cm: float = 5.0

    # Regn på snø → is på vei krever ofte at bakken er nær/under frysepunktet.
    # På vårføre kan det være bar vei selv om stasjonen måler snø i terrenget.
    rain_on_snow_surface_temp_max_c: float = 0.5

    # Kuldeperiode før mildvær/regn øker sannsynlighet for
    # snøkappe/kompakt underlag som kan bli glatt.
    # Brukes som fallback når `surface_temperature` er mild eller mangler.
    rain_on_snow_recent_cold_hours: int = 12
    rain_on_snow_recent_surface_temp_freeze_max_c: float = 0.0
    rain_on_snow_recent_air_temp_freeze_max_c: float = -1.0
    # Nedbørterskler
    # Hevet for å redusere falske positiver ("hysteriske" varsler) ved svært lett nedbør.
    rain_threshold_mm: float = 1.5
    # Underkjølt regn / frysing på kald bakke.
    # Skill mellom "warning" og "critical" for å unngå høy-alarm ved små drypp.
    freezing_precip_warning_mm: float = 0.1
    freezing_precip_critical_mm: float = 0.3

    # Skjult frysefare (luft > 0 men kald bakke) - strengere gating for å redusere støy.
    # Kalibrert mot brøyte-/vær-kobling (`data/analyzed/broyting_weather_correlation_2025.csv`)
    # for å øke treffrate uten å øke falske treff i evalueringssettet.
    hidden_freeze_surface_max: float = -1.0
    hidden_freeze_air_min: float = 0.0
    hidden_freeze_air_max: float = 1.0
    hidden_freeze_precip_12h_min: float = 1.0

    # Temperaturvindu for typiske "glatt føre"-situasjoner nær frysepunktet.
    near_freezing_temp_min: float = -1.0
    near_freezing_temp_max: float = 0.5

    # Rimfrost er vanligvis kun relevant ved høy fuktighet og lite vind.
    rimfrost_humidity_min: float = 90.0
    rimfrost_wind_max: float = 2.0
    rimfrost_dewpoint_delta_max: float = 2.0

    # Lett regn (mm/h) brukt i sommeranalyse.
    summer_rain_threshold_mm_per_h: float = 0.5

    # Smelting (negativ snøendring) som kan gi slaps/is ved etterfølgende kulde.
    melt_snow_change_6h_cm: float = -2.0
    temp_rise_threshold: float = 1.0    # °C stigning siste 6t
    recent_snow_relief_hours: int = 6   # Tidsrom for "fersk snø"-effekt
    recent_snow_relief_cm: float = 2.0  # Økning som gir naturlig strøing

    # Stabilt kaldt (lav risiko)
    stable_cold_air_temp_max: float = -5.0


@dataclass(frozen=True)
class FreshSnowThresholds:
    """
    Terskler for nysnø-deteksjon.

    Validert mot 166 brøyteepisoder.
    """
    # Snøøkning (cm over N timer)
    # 6 timer ble vurdert for kort (snø kan komme på natten).
    # Standard 12 timer (fanger natt, men gir mindre scenario-drift enn 18t).
    lookback_hours: int = 12
    # Merk: terskel for "hensikt å brøyte" avhenger av snøtype.
    # - Våt snø bygger mindre volum per mm nedbør, men påvirker vei tidligere.
    # - Tørr lett snø kan ofte ligge lengre før brøyting gir effekt.
    # Tolkning av nivåer:
    # - warning: kan nærme seg brøytebehov
    # - critical: brøyting sannsynligvis nyttig/nødvendig
    # Gap økt fra 1 cm (6/7) til 2 cm (5/7) for å redusere ustabil grenseklassifisering
    # ved støy i snødybdemåling. Terskelen 5 cm er praktisk brøyterelevant for våt snø.
    snow_increase_warning: float = 5.0    # våt snø
    snow_increase_critical: float = 7.0  # våt snø (typisk 6–7 cm)

    snow_increase_warning_dry: float = 8.0    # tørr lett snø (mindre sensitiv warning)
    snow_increase_critical_dry: float = 10.0 # tørr lett snø (typisk ~10 cm)

    # Temperatur for snø (ikke regn)
    dew_point_max: float = 0.0          # Primær: duggpunkt < 0 = snø
    air_temp_max: float = 1.0           # Sekundær: lufttemp < 1°C

    # Bakketemperatur: når overflaten er tydelig over 0°C er nedbør oftere regn/slaps på vei.
    # Brukes som gate for "snøfall pågår" og som støtte ved vindtransport.
    surface_temp_max: float = 0.5

    # Heuristikk: "våt snø" (tung snø) ved temperatur nær 0°C.
    wet_snow_air_temp_min: float = -0.5
    wet_snow_air_temp_max: float = 1.5
    wet_snow_dew_point_min: float = -0.5
    wet_snow_dew_point_max: float = 0.5

    # Nedbør
    precipitation_min: float = 0.5      # mm/t for å registrere

    # 6t akkumulert nedbør som fallback når snødybdemåler påvirkes av vindtransport.
    # Tommelfingerregel: 1 mm nedbør ~ 1 cm tørr snø (varierer), brukes som proxy.
    precipitation_6h_warning_mm: float = 5.0
    precipitation_6h_critical_mm: float = 7.0

    precipitation_6h_warning_mm_dry: float = 7.0
    precipitation_6h_critical_mm_dry: float = 10.0


@dataclass(frozen=True)
class MobileConfig:
    """Terskler for mobile UI-hjelpere."""
    nearby_distance_km: float = 10.0
    near_distance_km: float = 5.0
    medium_distance_km: float = 20.0
    refresh_interval_far_s: int = 1800
    refresh_interval_medium_s: int = 300
    refresh_interval_near_s: int = 60

    # Swipe-gestures (px)
    swipe_prevent_scroll_min_px: int = 20
    swipe_min_distance_px: int = 80

    # Mobil-layout defaults
    layout_columns_mobile: int = 2
    layout_columns_desktop: int = 4
    chart_height_mobile_px: int = 300
    chart_height_desktop_px: int = 400

    # Datakvalitet-indikator (UI)
    data_quality_success_min_pct: float = 80.0
    data_quality_warning_min_pct: float = 50.0


@dataclass(frozen=True)
class PerformanceCacheConfig:
    """Terskler for `src/components/performance_cache.py`."""
    ttl_fallback_multiplier: int = 2
    max_entries: int = 20
    keep_newest_entries: int = 15


@dataclass(frozen=True)
class TemperatureDisplayThresholds:
    """Temperaturgrenser brukt for klassifisering/visualisering."""
    very_cold_max: float = -10.0
    cold_max: float = -5.0
    chilly_max: float = -2.0
    freezing_max: float = 0.0
    mild_max: float = 2.0
    warm_max: float = 5.0


@dataclass(frozen=True)
class SnowLimitThresholds:
    """Terskler brukt i Netatmo-basert snøgrense-estimat i `src/gullingen_app.py`."""
    min_stations: int = 2
    min_alt_diff_m: float = 100.0

    # Høyde-bucketing for "høyfjell vs dal" i Netatmo-visningen
    high_station_min_altitude_m: float = 500.0
    low_station_max_altitude_m: float = 200.0

    snow_temp_c: float = 0.0
    slaps_temp_c: float = 1.0
    max_altitude_m: float = 1500.0

    confidence_high_alt_diff_m: float = 400.0
    confidence_high_station_count: int = 5
    confidence_medium_alt_diff_m: float = 200.0
    confidence_medium_station_count: int = 3

    inversion_delta_c: float = 1.0
    inversion_gradient_min: float = 0.0

    display_low_m: float = 300.0
    display_medium_m: float = 600.0

    gradient_weak_min: float = -0.4
    gradient_steep_max: float = -0.8


@dataclass(frozen=True)
class SlapsThresholds:
    """
    Terskler for slaps-deteksjon.

    ML-validert mot 42 bekreftet slaps-episoder.
    Slaps = tung blanding av snø og vann.
    """
    # Temperatur (kritisk område for slaps)
    temp_min: float = -1.0              # Under dette: snø
    # Hevet fra 2.0°C etter bekreftet episode 27. nov 2025 med snitt 3.8°C/topp 5.5°C.
    # Over 4.0°C klassifiseres som smelting/regn (ikke slaps) med eget scenario-kall.
    temp_max: float = 4.0
    temp_optimal: float = 1.2           # Historisk snitt for slaps

    # Nedbør
    precipitation_min: float = 1.0      # mm/t (øyeblikksindikator)
    precipitation_heavy: float = 5.0    # mm/t (øyeblikksindikator)
    # Akkumulert nedbør (historisk kalibrert som 12t-terskler;
    # vinduet styres av `precipitation_accum_hours`)
    precipitation_12h_min: float = 7.0
    precipitation_12h_heavy: float = 12.0

    # Snødekke
    snow_depth_min: float = 5.0         # cm - må ha snø

    # Smelteindikator: negativ snødybdeendring (over vinduet under)
    snow_change_hours: int = 12
    snow_melt_change_threshold_cm: float = -3.0

    # Nedbør-akkumulering for slaps (kan bygge seg opp over natten)
    precipitation_accum_hours: int = 12


@dataclass(frozen=True)
class VisualizationConfig:
    """Konfigurasjon for plotting."""
    max_datapoints: int = 10000
    max_bars: int = 1000
    sample_target: int = 5000
    figure_dpi: int = 100

    # Vindkjøling-formel (gyldighetsområde; brukes i plotting/markering)
    wind_chill_valid_temp_max_c: float = 10.0
    wind_chill_valid_wind_min_ms: float = 1.34

    # Farger
    color_temp: str = "#1E88E5"
    color_wind: str = "#43A047"
    color_snow: str = "#8E24AA"
    color_precip: str = "#1565C0"
    color_warning: str = "#FF9800"
    color_critical: str = "#D32F2F"
    color_invalid: str = "#B0BEC5"


@dataclass(frozen=True)
class DashboardConfig:
    """UI-terskler og guardrails for Streamlit-dashboard."""

    # Default valgt periode når appen åpnes
    default_period_hours: int = 24

    # Maks periode brukeren kan velge i UI (ytelse/lesbarhet)
    max_period_days: int = 7

    # Varsel-stabilisering (anti-støy)
    alert_downgrade_hold_minutes: int = 30

    # Datakvalitet-gating i UI
    data_stale_warning_minutes: int = 90
    data_stale_unknown_minutes: int = 240
    data_coverage_warning_pct: float = 70.0
    data_coverage_unknown_pct: float = 40.0


@dataclass(frozen=True)
class NetatmoConfig:
    """Konfigurasjon for Netatmo-integrasjon og kartvisning i `src/gullingen_app.py`."""

    # Streamlit caching for henting av stasjoner
    cache_ttl_seconds: int = 300

    # HTTP
    http_timeout_seconds: int = 10

    # Søk etter stasjoner rundt Fjellbergsskardet
    search_radius_km: int = 10

    # Referansepunkt (Fjellbergsskardet) for å sentrere kart (midt mellom Gullingen og Fjellberg)
    fjellberg_lat: float = 59.39205
    fjellberg_lon: float = 6.42667

    # Pydeck/ScatterplotLayer
    map_point_radius_m: int = 300
    map_point_radius_min_px: int = 10
    map_point_radius_max_px: int = 30
    map_zoom: int = 10


@dataclass(frozen=True)
class PlowmanConfig:
    """Konfigurasjon for Plowman/vedlikeholds-API-klienter."""

    http_timeout_seconds: int = 10


@dataclass(frozen=True)
class PlowingServiceConfig:
    """Terskler og kapasiteter for `src/plowing_service.py`."""
    recent_plowing_hours: float = 24.0
    cache_max_entries: int = 20
    default_max_cache_age_hours: int = 1

    # Streamlit caching
    streamlit_cache_ttl_seconds: int = 900

    # Formatteringsgrenser i `PlowingInfo.formatted_time`
    formatted_recent_seconds: int = 3600
    formatted_week_days: int = 7


@dataclass(frozen=True)
class LegacySnofokkParams:
    """
    Legacy terskler/parametre for `src/snofokk`.

    Dette delsystemet er ikke i aktiv bruk i appen, men har tester og kan være nyttig
    for historisk referanse. For å unngå hardkodede verdier i flere filer, samles
    parameterne her.
    """
    # Analyse-terskler
    snow_change_threshold: float = 0.5
    temperature_snow_threshold: float = 2.0
    wind_impact_threshold: float = 8.0
    rolling_window: int = 3

    # Snødybde-normalisering
    snow_invalid_sentinel: float = -1.0
    snow_depth_outlier_max: float = 1000.0
    snow_interpolation_limit_hours: int = 24

    # "Høy"-terskler brukt i risikoscore
    wind_speed_high_threshold: float = 15.0
    temperature_cold_threshold: float = -10.0
    snow_change_high_threshold: float = 5.0
    risk_score_high_threshold: float = 0.6

    # Risikoverdier per komponent
    wind_risk_high: float = 1.0
    wind_risk_medium: float = 0.6
    temp_risk_high: float = 0.8
    temp_risk_medium: float = 0.4
    snow_risk_high: float = 0.8
    snow_risk_medium: float = 0.4

    # Vekting av komponenter i samlet score
    wind_weight: float = 0.4
    temp_weight: float = 0.3
    snow_weight: float = 0.3

    # Confidence-heuristikk
    confidence_base: float = 0.8
    confidence_extreme_depth_threshold: float = 200.0
    confidence_extreme_depth_penalty: float = 0.2
    confidence_extreme_change_threshold: float = 20.0
    confidence_extreme_change_penalty: float = 0.3
    confidence_min: float = 0.1


@dataclass(frozen=True)
class HistoricalServiceThresholds:
    """Terskler brukt i `src/components/historical_service.py` (historisk analyse)."""
    # UI/validering
    date_range_max_days: int = 14
    date_range_min_hours: int = 1

    # HTTP
    http_timeout_seconds: int = 60

    # LRU-cache
    fetch_cache_maxsize: int = 20

    new_snow_change_min_cm: float = 0.5
    new_snow_air_temp_max: float = 2.0
    new_snow_hourly_cap_cm: float = 20.0

    # Konverteringsheuristikk (Frost kan levere snødybde i m eller cm avhengig av kilde)
    snow_depth_conversion_cutoff_cm: float = 10.0

    # Klassifisering av nysnø-type basert på lufttemperatur
    snow_type_powder_air_temp_max: float = -5.0
    snow_type_dry_air_temp_max: float = -1.0
    snow_type_wet_air_temp_max: float = 1.0

    plowing_threshold_wet_cm: float = 6.0
    plowing_threshold_dry_cm: float = 12.0
    plowing_threshold_total_cm: float = 15.0

    # February sample data (create_february_sample_data)
    feb_sample_seed: int = 42
    feb_sample_start_snow_depth_cm: float = 45.0
    feb_sample_wind_cap_ms: float = 25.0
    feb_sample_snow_min_depth_cm: float = 5.0

    feb_sample_base_temp_start_c: float = -8.0
    feb_sample_base_temp_daily_increase_c: float = 0.5
    feb_sample_base_temp_diurnal_amp_c: float = 4.0
    feb_sample_temp_noise_sigma_c: float = 2.0

    feb_sample_storm_main_day_start: int = 3
    feb_sample_storm_main_day_end: int = 5
    feb_sample_storm_main_wind_base_ms: float = 12.0
    feb_sample_storm_main_wind_exp_scale: float = 3.0

    feb_sample_storm_minor_day_start: int = 9
    feb_sample_storm_minor_day_end: int = 10
    feb_sample_storm_minor_wind_base_ms: float = 8.0
    feb_sample_storm_minor_wind_exp_scale: float = 2.0

    feb_sample_wind_base_ms: float = 3.0
    feb_sample_wind_exp_scale: float = 2.0

    feb_sample_precip_ep1_day_start: int = 2
    feb_sample_precip_ep1_day_end: int = 3
    feb_sample_precip_ep1_temp_max_c: float = 0.0
    feb_sample_precip_ep1_exp_scale: float = 0.8
    feb_sample_precip_ep1_prob: float = 0.4

    feb_sample_precip_ep2_day_start: int = 7
    feb_sample_precip_ep2_day_end: int = 8
    feb_sample_precip_ep2_temp_max_c: float = 1.0
    feb_sample_precip_ep2_exp_scale: float = 1.2
    feb_sample_precip_ep2_prob: float = 0.3

    feb_sample_precip_ep3_day_start: int = 12
    feb_sample_precip_ep3_day_end: int = 13
    feb_sample_precip_ep3_temp_max_c: float = 2.0
    feb_sample_precip_ep3_exp_scale: float = 0.5
    feb_sample_precip_ep3_prob: float = 0.2

    feb_sample_snow_accum_temp_max_c: float = 1.0
    feb_sample_snow_accum_cm_per_mm: float = 2.0

    feb_sample_blowing_wind_min_ms: float = 10.0
    feb_sample_blowing_temp_max_c: float = -2.0
    feb_sample_blowing_snow_depth_reduction_coef: float = 0.05

    feb_sample_melt_temp_min_c: float = 3.0
    feb_sample_melt_offset_c: float = 2.0
    feb_sample_melt_coef: float = 0.2

    feb_sample_surface_temp_drop_min_c: float = 0.5
    feb_sample_surface_temp_drop_max_c: float = 2.0

    feb_sample_wind_dir_base_deg: float = 225.0
    feb_sample_wind_dir_sigma_deg: float = 30.0

    feb_sample_humidity_base_pct: float = 60.0
    feb_sample_humidity_sigma_pct: float = 15.0
    feb_sample_dew_point_offset_c: float = -5.0
    feb_sample_dew_point_sigma_c: float = 2.0

    feb_sample_gust_multiplier: float = 1.4
    feb_sample_weather_symbol_precip: int = 1
    feb_sample_weather_symbol_wind: int = 2
    feb_sample_weather_symbol_clear: int = 3
    feb_sample_weather_symbol_wind_min_ms: float = 8.0


@dataclass(frozen=True)
class FallbackAnalysisThresholds:
    """Terskler for enkle fallback-analyser i UI (uten ML).

    Brukes av `src/components/weather_utils.py`.
    """

    # simple_snowdrift_analysis
    snowdrift_confidence_base: float = 0.5
    snowdrift_confidence_high: float = 0.8
    snowdrift_confidence_medium: float = 0.7
    snowdrift_confidence_low: float = 0.6
    snowdrift_confidence_very_low: float = 0.4

    snowdrift_temp_very_cold_max_c: float = -10.0
    snowdrift_temp_cold_max_c: float = -5.0
    snowdrift_temp_freezing_max_c: float = -1.0

    snowdrift_wind_strong_min_ms: float = 15.0
    snowdrift_wind_moderate_min_ms: float = 10.0
    snowdrift_wind_light_min_ms: float = 6.0

    snowdrift_snow_cm_high_min: float = 20.0
    snowdrift_snow_cm_medium_min: float = 5.0

    snowdrift_high_total_score_min: int = 6
    snowdrift_high_temp_max_c: float = -3.0
    snowdrift_high_wind_min_ms: float = 12.0

    snowdrift_medium_total_score_min: int = 4
    snowdrift_medium_temp_max_c: float = -1.0
    snowdrift_medium_wind_min_ms: float = 8.0

    snowdrift_low_total_score_min: int = 2

    # simple_slippery_analysis
    slippery_temp_band_min_c: float = -3.0
    slippery_temp_band_max_c: float = 3.0

    slippery_humidity_high_pct: float = 90.0
    slippery_humidity_medium_pct: float = 80.0

    slippery_temp_near_freezing_min_c: float = -1.0
    slippery_temp_near_freezing_max_c: float = 1.0

    slippery_stable_cold_max_c: float = -10.0
    slippery_too_warm_min_c: float = 8.0

    slippery_confidence_unknown: float = 0.0
    slippery_confidence_high: float = 0.9
    slippery_confidence_medium: float = 0.7
    slippery_confidence_low: float = 0.6
    slippery_confidence_low_no_humidity: float = 0.5
    slippery_confidence_medium_no_humidity: float = 0.6
    slippery_confidence_stable_cold: float = 0.8
    slippery_confidence_too_warm: float = 0.8

    # validate_weather_data
    data_quality_score_start: int = 100
    data_quality_missing_col_penalty: int = 30
    data_quality_missing_pct_high: float = 50.0
    data_quality_missing_pct_medium: float = 20.0
    data_quality_missing_pct_high_penalty: int = 20
    data_quality_missing_pct_medium_penalty: int = 10

    data_quality_hours_old_critical: float = 6.0
    data_quality_hours_old_warning: float = 3.0
    data_quality_hours_old_critical_penalty: int = 15
    data_quality_hours_old_warning_penalty: int = 5

    data_quality_min_rows: int = 10
    data_quality_min_rows_penalty: int = 10

    data_quality_reco_backup_below_score: int = 70
    data_quality_reco_basic_only_below_score: int = 50
    data_quality_reco_wait_below_score: int = 30

    data_quality_valid_min_score: int = 30


@dataclass(frozen=True)
class ChartRiskTimelineThresholds:
    """Terskler for enkel risiko-tidslinje i UI.

    Brukes av `src/components/advanced_charts.py`.
    """

    # Snøfokk score (per timepunkt)
    snowdrift_wind_low_ms: float = 8.0
    snowdrift_wind_high_ms: float = 12.0
    snowdrift_temp_cold_c: float = -1.0
    snowdrift_temp_very_cold_c: float = -5.0

    # Glattføre score (per timepunkt)
    slippery_temp_min_c: float = -2.0
    slippery_temp_max_c: float = 2.0
    slippery_humidity_high_pct: float = 85.0

    # Sammendrag (kort)
    precip_any_min_mmph: float = 0.0

    # Fargekoding basert på samlet score
    risk_red_min: int = 4
    risk_orange_min: int = 3
    risk_yellow_min: int = 2

    # Skala/bånd i plott (0-6)
    band_green_max: int = 1
    band_yellow_max: int = 3
    band_orange_max: int = 5
    band_red_max: int = 6

    chart_height_px: int = 300
    yaxis_max: int = 6


@dataclass(frozen=True)
class EnhancedWeatherHeuristics:
    """Heuristiske terskler/vekter for `src/snofokk/services/enhanced_weather.py`.

    Dette er et "utvidet"/eksperimentelt datasett, men tersklene holdes likevel
    sentralisert for å unngå hardkoding.
    """

    # _calculate_blowing_snow_risk
    blowing_wind_high_ms: float = 8.0
    blowing_wind_medium_ms: float = 5.0
    blowing_wind_high_add: float = 0.4
    blowing_wind_medium_add: float = 0.2

    blowing_gust_min_ms: float = 12.0
    blowing_gust_add: float = 0.2

    blowing_snow_depth_high_cm: float = 10.0
    blowing_snow_depth_medium_cm: float = 5.0
    blowing_snow_depth_high_add: float = 0.3
    blowing_snow_depth_medium_add: float = 0.15

    blowing_temp_very_cold_c: float = -5.0
    blowing_temp_wet_snow_min_c: float = 2.0
    blowing_temp_very_cold_add: float = 0.1
    blowing_temp_wet_snow_penalty: float = 0.2

    # _calculate_ice_formation_risk
    ice_air_temp_max_c: float = 0.0
    ice_air_temp_min_c: float = -3.0
    ice_air_temp_add: float = 0.4
    ice_surface_below_air_add: float = 0.3
    ice_humidity_high_pct: float = 85.0
    ice_humidity_add: float = 0.3
    ice_risk_max: float = 1.0

    # _estimate_visibility
    visibility_base_km: float = 10.0
    visibility_blowing_risk_min: float = 0.3
    visibility_precip_min_mmph: float = 2.0
    visibility_precip_multiplier: float = 0.7
    visibility_min_km: float = 0.1

    # _estimate_visibility_impact (tekst-bucketer)
    visibility_impact_high_max_m: int = 500
    visibility_impact_medium_max_m: int = 2000

    # _calculate_combined_risk
    combined_blowing_risk_weight: float = 0.6
    combined_wind_threshold_ms: float = 10.0
    combined_wind_weight: float = 0.4

    # _estimate_visibility_impact
    visibility_impact_high_risk_min: float = 0.7
    visibility_impact_medium_risk_min: float = 0.4

    # _assess_road_conditions
    road_critical_wind_min_ms: float = 10.0
    road_challenging_wind_min_ms: float = 8.0
    road_freezing_max_c: float = 0.0

    # _predict_next_hour_risk
    trend_window_points: int = 3
    trend_adjustment_coef: float = 0.1

    # analyze_snowdrift_conditions (summary stats)
    analysis_wind_hours_above_ms: float = 8.0
    analysis_snow_available_min_cm: float = 5.0
    analysis_precip_any_min_mmph: float = 0.0
    analysis_blowing_snow_hours_risk_min: float = 0.5

    # _calculate_deterioration_trend
    deterioration_trend_tail_points: int = 5
    deterioration_wind_trend_high: float = 1.0
    deterioration_risk_trend_high: float = 0.1
    deterioration_wind_trend_low: float = -1.0
    deterioration_risk_trend_low: float = -0.1

    # _recommend_action
    action_high_risk_min: float = 0.7
    action_high_wind_max_min_ms: float = 15.0
    action_medium_risk_min: float = 0.4
    action_medium_wind_max_min_ms: float = 10.0

    # test_enhanced_service
    demo_hours_back: int = 6


@dataclass(frozen=True)
class ScriptAnalysisThresholds:
    """Terskler brukt av analyse-scripts i `scripts/`.

    Scripts er ikke del av live app-logikk, men bør likevel unngå hardkodede terskler
    for å holde systemet konsistent og testbart.
    """

    # Brøyting/inspeksjon-proxy
    short_run_45m_max_minutes: float = 45.0
    short_run_30m_max_minutes: float = 30.0
    inspection_duration_max_minutes: float = 30.0
    inspection_distance_max_km: float = 6.0

    # "Trigger"-flagg for å skille korte sjekkturer fra vær-drevet behov
    trigger_fresh_snow_min_cm: float = 5.0
    trigger_slaps_air_temp_min_c: float = 0.0
    trigger_slaps_precip_total_min_mm: float = 5.0
    trigger_freezing_air_temp_min_c: float = 0.0
    trigger_snowdrift_gust_min_ms: float = 15.0
    trigger_snowdrift_wind_min_ms: float = 8.0
    trigger_snowdrift_air_temp_max_c: float = -1.0

    # Enkel scenario-heuristikk
    scenario_slaps_precip_total_min_mm: float = 5.0
    scenario_snow_precip_total_min_mm: float = 2.0
    scenario_snowdrift_wind_min_ms: float = 6.0
    scenario_snowdrift_air_temp_max_c: float = -1.0

    # Felles tidsvinduer brukt i flere scripts
    snow_change_window_hours: int = 6
    slaps_precip_accumulation_hours: int = 12

    # scripts/analyze_weather_plowing_correlation.py
    plowing_weather_window_before_hours: int = 12
    plowing_weather_window_after_hours: int = 12

    correlation_snow_depth_high_cm: float = 15.0
    correlation_snow_depth_medium_cm: float = 8.0
    correlation_snow_depth_low_cm: float = 3.0
    correlation_score_snow_high: float = 0.4
    correlation_score_snow_medium: float = 0.3
    correlation_score_snow_low: float = 0.1

    correlation_total_precip_high_mm: float = 10.0
    correlation_total_precip_medium_mm: float = 5.0
    correlation_score_precip_high: float = 0.3
    correlation_score_precip_medium: float = 0.2
    correlation_max_precip_1h_mm: float = 5.0
    correlation_score_precip_1h: float = 0.2

    correlation_avg_temp_very_cold_c: float = -5.0
    correlation_min_surface_temp_cold_c: float = -2.0
    correlation_score_temp_very_cold: float = 0.2
    correlation_avg_temp_freezing_c: float = 0.0
    correlation_score_temp_freezing: float = 0.1

    correlation_wind_high_ms: float = 12.0
    correlation_wind_medium_ms: float = 8.0
    correlation_wind_high_requires_snow_cm: float = 5.0
    correlation_wind_medium_requires_snow_cm: float = 3.0
    correlation_score_wind_high: float = 0.15
    correlation_score_wind_medium: float = 0.1

    correlation_needed_score_min: float = 0.4

    # scripts/reports/daily_report.py
    daily_report_snow_smooth_window_size: int = 3
    daily_report_snow_change_classification_threshold_cm: float = 0.2
    daily_report_discrepancy_snow_change_threshold_cm: float = 1.0
    daily_report_discrepancy_wind_threshold_ms: float = 5.0
    daily_report_discrepancy_precip_min_mm: float = 0.5
    daily_report_hourly_precip_any_min_mm: float = 0.0
    daily_report_total_precip_any_min_mm: float = 0.0

    # Plowman share parsing (used by multiple scripts)
    plowman_share_scripts_min_count: int = 29
    plowman_share_script_index: int = 28

    # scripts/reports/compare_broyting_windows.py
    compare_morning_start_hour: int = 6
    compare_morning_end_hour: int = 11

    # scripts/utils/precipitation_type.py
    precip_type_temp_snow_c: float = -1.0
    precip_type_temp_mix_low_c: float = -1.0
    precip_type_temp_mix_high_c: float = 2.0
    precip_intensity_light_mmph: float = 0.4
    precip_intensity_moderate_mmph: float = 2.5
    precip_intensity_heavy_mmph: float = 6.0
    precip_probability_temp_coef: float = 0.5
    precip_probability_snow_temp_offset_c: float = 1.0
    precip_probability_rain_temp_offset_c: float = 2.0
    precip_transition_near_threshold_delta_c: float = 0.5
    precip_transition_near_threshold_base_risk: float = 0.5
    precip_transition_temp_change_weight: float = 0.2

    # scripts/reports/calibrate_event_thresholds.py
    calibrate_need_duration_min_default_minutes: float = 45.0
    calibrate_need_distance_default_km: float = 8.0

    calibrate_weight_false_negative: float = 3.0
    calibrate_weight_false_positive: float = 1.0
    calibrate_weight_false_positive_no_need: float = 4.0
    calibrate_target_alert_rate_default_pct: float = 30.0
    calibrate_weight_alert_rate: float = 6.0
    calibrate_top_default: int = 25

    calibrate_slaps_temp_min_c: float = -1.0
    calibrate_drift_temp_max_c: float = -1.0
    calibrate_freeze_air_min_c: float = 0.0

    calibrate_grid_snow_change_cm: tuple[float, ...] = (3.0, 4.0, 5.0, 6.0, 7.0)
    calibrate_grid_slaps_precip_mm: tuple[float, ...] = (3.0, 4.0, 5.0, 6.0, 7.0, 8.0)
    calibrate_grid_slaps_temp_max_c: tuple[float, ...] = (2.0, 3.0, 4.0, 5.0)
    calibrate_grid_gust_mps: tuple[float, ...] = (13.0, 15.0, 17.0, 19.0, 21.0)
    calibrate_grid_wind_mps: tuple[float, ...] = (6.0, 8.0, 10.0, 12.0)
    calibrate_grid_freeze_surface_max_c: tuple[float, ...] = (-0.5, -1.0, -1.5, -2.0)
    calibrate_grid_freeze_air_max_c: tuple[float, ...] = (1.0, 2.0, 3.0)
    calibrate_grid_freeze_precip_mm: tuple[float, ...] = (0.0, 0.5, 1.0, 2.0)


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

    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    netatmo: NetatmoConfig = field(default_factory=NetatmoConfig)
    plowman: PlowmanConfig = field(default_factory=PlowmanConfig)

    plowing_service: PlowingServiceConfig = field(default_factory=PlowingServiceConfig)
    performance_cache: PerformanceCacheConfig = field(default_factory=PerformanceCacheConfig)
    mobile: MobileConfig = field(default_factory=MobileConfig)
    display: TemperatureDisplayThresholds = field(default_factory=TemperatureDisplayThresholds)
    snow_limit: SnowLimitThresholds = field(default_factory=SnowLimitThresholds)
    legacy_snofokk: LegacySnofokkParams = field(default_factory=LegacySnofokkParams)
    historical: HistoricalServiceThresholds = field(default_factory=HistoricalServiceThresholds)
    scripts: ScriptAnalysisThresholds = field(default_factory=ScriptAnalysisThresholds)

    fallback: FallbackAnalysisThresholds = field(default_factory=FallbackAnalysisThresholds)
    chart_risk_timeline: ChartRiskTimelineThresholds = field(
        default_factory=ChartRiskTimelineThresholds
    )
    enhanced_weather: EnhancedWeatherHeuristics = field(default_factory=EnhancedWeatherHeuristics)

    # Sesongmåneder
    WINTER_MONTHS: ClassVar[tuple] = (10, 11, 12, 1, 2, 3, 4)

    def is_winter(self) -> bool:
        """Sjekk om det er vintersesong."""
        return datetime.now().month in self.WINTER_MONTHS

    def validate(self) -> tuple[bool, str]:
        """Valider at nødvendig konfigurasjon er på plass."""
        if not self.api.client_id:
            return False, "FROST_CLIENT_ID mangler. Legg til i .env eller Streamlit secrets."
        return True, "OK"


# Global singleton
settings = Settings()
