"""
Configuration management for Snøfokk application
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytz
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config import settings as core_settings


@dataclass
class WeatherConfig:
    """Legacy weather configuration dataclass for backward compatibility"""
    frost_client_id: str
    weather_station: str
    email_from: str
    email_to: str
    smtp_server: str
    smtp_username: str
    smtp_password: str


class Settings(BaseSettings):
    """Modern settings using Pydantic with environment variable support"""

    # API Configuration
    frost_client_id: str = "default-frost-client-id"
    weather_station: str = "SN46220"

    # Email Configuration
    email_from: str = ""
    email_to: str = ""
    smtp_server: str = ""
    smtp_username: str = ""
    smtp_password: str = ""

    # Paths
    data_dir: str = "data"
    logs_dir: str = "logs"
    config_dir: str = "config"

    # Analysis Parameters (legacy) - defaults fra sentral config
    snow_change_threshold: float = core_settings.legacy_snofokk.snow_change_threshold
    temperature_snow_threshold: float = core_settings.legacy_snofokk.temperature_snow_threshold
    wind_impact_threshold: float = core_settings.legacy_snofokk.wind_impact_threshold
    rolling_window: int = core_settings.legacy_snofokk.rolling_window

    wind_speed_high_threshold: float = core_settings.legacy_snofokk.wind_speed_high_threshold
    temperature_cold_threshold: float = core_settings.legacy_snofokk.temperature_cold_threshold
    snow_change_high_threshold: float = core_settings.legacy_snofokk.snow_change_high_threshold
    risk_score_high_threshold: float = core_settings.legacy_snofokk.risk_score_high_threshold

    wind_risk_high: float = core_settings.legacy_snofokk.wind_risk_high
    wind_risk_medium: float = core_settings.legacy_snofokk.wind_risk_medium
    temp_risk_high: float = core_settings.legacy_snofokk.temp_risk_high
    temp_risk_medium: float = core_settings.legacy_snofokk.temp_risk_medium
    snow_risk_high: float = core_settings.legacy_snofokk.snow_risk_high
    snow_risk_medium: float = core_settings.legacy_snofokk.snow_risk_medium

    wind_weight: float = core_settings.legacy_snofokk.wind_weight
    temp_weight: float = core_settings.legacy_snofokk.temp_weight
    snow_weight: float = core_settings.legacy_snofokk.snow_weight

    confidence_base: float = core_settings.legacy_snofokk.confidence_base
    confidence_extreme_depth_threshold: float = (
        core_settings.legacy_snofokk.confidence_extreme_depth_threshold
    )
    confidence_extreme_depth_penalty: float = (
        core_settings.legacy_snofokk.confidence_extreme_depth_penalty
    )
    confidence_extreme_change_threshold: float = (
        core_settings.legacy_snofokk.confidence_extreme_change_threshold
    )
    confidence_extreme_change_penalty: float = (
        core_settings.legacy_snofokk.confidence_extreme_change_penalty
    )
    confidence_min: float = core_settings.legacy_snofokk.confidence_min

    # Enhanced weather heuristics (defaults fra sentral config)
    blowing_wind_high_ms: float = core_settings.enhanced_weather.blowing_wind_high_ms
    blowing_wind_medium_ms: float = core_settings.enhanced_weather.blowing_wind_medium_ms
    blowing_wind_high_add: float = core_settings.enhanced_weather.blowing_wind_high_add
    blowing_wind_medium_add: float = core_settings.enhanced_weather.blowing_wind_medium_add

    blowing_gust_min_ms: float = core_settings.enhanced_weather.blowing_gust_min_ms
    blowing_gust_add: float = core_settings.enhanced_weather.blowing_gust_add

    blowing_snow_depth_high_cm: float = core_settings.enhanced_weather.blowing_snow_depth_high_cm
    blowing_snow_depth_medium_cm: float = (
        core_settings.enhanced_weather.blowing_snow_depth_medium_cm
    )
    blowing_snow_depth_high_add: float = core_settings.enhanced_weather.blowing_snow_depth_high_add
    blowing_snow_depth_medium_add: float = (
        core_settings.enhanced_weather.blowing_snow_depth_medium_add
    )

    blowing_temp_very_cold_c: float = core_settings.enhanced_weather.blowing_temp_very_cold_c
    blowing_temp_wet_snow_min_c: float = core_settings.enhanced_weather.blowing_temp_wet_snow_min_c
    blowing_temp_very_cold_add: float = core_settings.enhanced_weather.blowing_temp_very_cold_add
    blowing_temp_wet_snow_penalty: float = (
        core_settings.enhanced_weather.blowing_temp_wet_snow_penalty
    )

    ice_air_temp_max_c: float = core_settings.enhanced_weather.ice_air_temp_max_c
    ice_air_temp_min_c: float = core_settings.enhanced_weather.ice_air_temp_min_c
    ice_air_temp_add: float = core_settings.enhanced_weather.ice_air_temp_add
    ice_surface_below_air_add: float = core_settings.enhanced_weather.ice_surface_below_air_add
    ice_humidity_high_pct: float = core_settings.enhanced_weather.ice_humidity_high_pct
    ice_humidity_add: float = core_settings.enhanced_weather.ice_humidity_add
    ice_risk_max: float = core_settings.enhanced_weather.ice_risk_max

    visibility_base_km: float = core_settings.enhanced_weather.visibility_base_km
    visibility_blowing_risk_min: float = core_settings.enhanced_weather.visibility_blowing_risk_min
    visibility_precip_min_mmph: float = core_settings.enhanced_weather.visibility_precip_min_mmph
    visibility_precip_multiplier: float = (
        core_settings.enhanced_weather.visibility_precip_multiplier
    )
    visibility_min_km: float = core_settings.enhanced_weather.visibility_min_km

    combined_blowing_risk_weight: float = (
        core_settings.enhanced_weather.combined_blowing_risk_weight
    )
    combined_wind_threshold_ms: float = core_settings.enhanced_weather.combined_wind_threshold_ms
    combined_wind_weight: float = core_settings.enhanced_weather.combined_wind_weight

    visibility_impact_high_risk_min: float = (
        core_settings.enhanced_weather.visibility_impact_high_risk_min
    )
    visibility_impact_medium_risk_min: float = (
        core_settings.enhanced_weather.visibility_impact_medium_risk_min
    )

    road_critical_wind_min_ms: float = core_settings.enhanced_weather.road_critical_wind_min_ms
    road_challenging_wind_min_ms: float = (
        core_settings.enhanced_weather.road_challenging_wind_min_ms
    )
    road_freezing_max_c: float = core_settings.enhanced_weather.road_freezing_max_c

    trend_window_points: int = core_settings.enhanced_weather.trend_window_points
    trend_adjustment_coef: float = core_settings.enhanced_weather.trend_adjustment_coef

    analysis_wind_hours_above_ms: float = (
        core_settings.enhanced_weather.analysis_wind_hours_above_ms
    )
    analysis_snow_available_min_cm: float = (
        core_settings.enhanced_weather.analysis_snow_available_min_cm
    )
    analysis_precip_any_min_mmph: float = (
        core_settings.enhanced_weather.analysis_precip_any_min_mmph
    )
    analysis_blowing_snow_hours_risk_min: float = (
        core_settings.enhanced_weather.analysis_blowing_snow_hours_risk_min
    )

    deterioration_trend_tail_points: int = (
        core_settings.enhanced_weather.deterioration_trend_tail_points
    )
    deterioration_wind_trend_high: float = (
        core_settings.enhanced_weather.deterioration_wind_trend_high
    )
    deterioration_risk_trend_high: float = (
        core_settings.enhanced_weather.deterioration_risk_trend_high
    )
    deterioration_wind_trend_low: float = (
        core_settings.enhanced_weather.deterioration_wind_trend_low
    )
    deterioration_risk_trend_low: float = (
        core_settings.enhanced_weather.deterioration_risk_trend_low
    )

    action_high_risk_min: float = core_settings.enhanced_weather.action_high_risk_min
    action_high_wind_max_min_ms: float = core_settings.enhanced_weather.action_high_wind_max_min_ms
    action_medium_risk_min: float = core_settings.enhanced_weather.action_medium_risk_min
    action_medium_wind_max_min_ms: float = (
        core_settings.enhanced_weather.action_medium_wind_max_min_ms
    )

    demo_hours_back: int = core_settings.enhanced_weather.demo_hours_back

    # Timezone
    timezone: str = "Europe/Oslo"

    # Development
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="SNOFOKK_",
        extra="ignore"  # Ignorer ekstra felter fra .env (f.eks. netatmo_*)
    )

    @property
    def tz(self) -> Any:
        """Returner tidssone for konfigurert region."""
        return pytz.timezone(self.timezone)

    @property
    def base_dir(self) -> Path:
        """Returner prosjektrot for snofokk-pakken."""
        return Path(__file__).parent.parent.parent

    @property
    def data_path(self) -> Path:
        """Returner og opprett datakatalog ved behov."""
        path = self.base_dir / self.data_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def logs_path(self) -> Path:
        """Returner og opprett loggkatalog ved behov."""
        path = self.base_dir / self.logs_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def config_path(self) -> Path:
        """Returner konfigurasjonskatalog."""
        return self.base_dir / self.config_dir

# Global settings instance
settings = Settings()

# Legacy configuration loader for backward compatibility
def load_config() -> WeatherConfig:
    """Load configuration from JSON file (legacy support)"""
    # NB: Ikke les inn en versjonert "test_config.json" her.
    # Hvis man vil bruke JSON lokalt, legg det i en ikke-versjonert fil.
    config_file = settings.config_path / 'local_config.json'

    try:
        with open(config_file, encoding='utf-8') as f:
            config_data = json.load(f)

        # Filter out fields that aren't in WeatherConfig
        weather_config_fields = {
            'frost_client_id', 'weather_station', 'email_from', 'email_to',
            'smtp_server', 'smtp_username', 'smtp_password'
        }
        filtered_config = {k: v for k, v in config_data.items() if k in weather_config_fields}

        return WeatherConfig(**filtered_config)
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        # Fallback to environment-based settings
        return WeatherConfig(
            frost_client_id=settings.frost_client_id,
            weather_station=settings.weather_station,
            email_from=settings.email_from,
            email_to=settings.email_to,
            smtp_server=settings.smtp_server,
            smtp_username=settings.smtp_username,
            smtp_password=settings.smtp_password
        )
