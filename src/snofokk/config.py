"""
Configuration management for Snøfokk application
"""
from dataclasses import dataclass
from pathlib import Path

import pytz
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    frost_client_id: str
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

    # Analysis Parameters
    snow_change_threshold: float = 0.5  # cm
    temperature_snow_threshold: float = 2.0  # °C
    wind_impact_threshold: float = 8.0  # m/s
    rolling_window: int = 3  # Timer for rullende gjennomsnitt

    # Timezone
    timezone: str = "Europe/Oslo"

    # Development
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    @property
    def tz(self):
        return pytz.timezone(self.timezone)

    @property
    def base_dir(self) -> Path:
        return Path(__file__).parent.parent.parent

    @property
    def data_path(self) -> Path:
        path = self.base_dir / self.data_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def logs_path(self) -> Path:
        path = self.base_dir / self.logs_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def config_path(self) -> Path:
        return self.base_dir / self.config_dir

# Global settings instance
settings = Settings()

# Legacy configuration loader for backward compatibility
def load_config() -> WeatherConfig:
    """Load configuration from JSON file (legacy support)"""
    import json

    config_file = settings.config_path / 'test_config.json'

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
