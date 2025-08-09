#!/usr/bin/env python3
"""
Weather Pattern Configuration - Konfigurasjon og justering av parametere
"""
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SnowDriftConfig:
    """Konfigurasjon for snøfokk-deteksjon"""
    min_wind_speed: float = 8.0  # m/s
    max_temperature: float = -2.0  # °C
    min_duration_hours: int = 2
    min_snow_depth_variance: float = 5.0  # cm
    severity_weight_wind: float = 0.4
    severity_weight_temp: float = 0.3
    severity_weight_snow: float = 0.3
    alert_threshold: int = 70  # %

@dataclass
class SlipperyRoadConfig:
    """Konfigurasjon for glatt vei-deteksjon"""
    max_temperature: float = 2.0  # °C
    min_humidity: float = 80.0  # %
    min_precipitation: float = 0.1  # mm
    frost_temp_threshold: float = 0.0  # °C
    ice_temp_threshold: float = -1.0  # °C
    min_duration_hours: int = 1
    risk_weight_temp: float = 0.4
    risk_weight_humidity: float = 0.3
    risk_weight_precip: float = 0.3
    alert_threshold: int = 60  # %

@dataclass
class AlertConfig:
    """Konfigurasjon for varsling"""
    snow_drift_enabled: bool = True
    slippery_road_enabled: bool = True
    advance_warning_hours: int = 4
    monitoring_start_hour: int = 6
    monitoring_end_hour: int = 22
    email_alerts: bool = False
    sms_alerts: bool = False
    log_alerts: bool = True

@dataclass
class WeatherConfig:
    """Hovedkonfigurasjon for værmønster-system"""
    snow_drift: SnowDriftConfig
    slippery_road: SlipperyRoadConfig
    alerts: AlertConfig
    data_source: str = "frost_api"
    default_station: str = "SN46220"  # Stavanger Sola
    analysis_period_days: int = 7
    historical_years: int = 3

class ConfigManager:
    """Håndtering av konfigurasjonsfiler"""
    
    def __init__(self, config_file: str = "weather_config.json"):
        self.config_file = Path(config_file)
        self.config: Optional[WeatherConfig] = None
        self.load_config()
    
    def load_config(self) -> WeatherConfig:
        """Last konfigurasjon fra fil eller opprett standard"""
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Konverter fra dict til dataclass
                self.config = WeatherConfig(
                    snow_drift=SnowDriftConfig(**data.get('snow_drift', {})),
                    slippery_road=SlipperyRoadConfig(**data.get('slippery_road', {})),
                    alerts=AlertConfig(**data.get('alerts', {})),
                    data_source=data.get('data_source', 'frost_api'),
                    default_station=data.get('default_station', 'SN46220'),
                    analysis_period_days=data.get('analysis_period_days', 7),
                    historical_years=data.get('historical_years', 3)
                )
                
                logger.info(f"Konfigurasjon lastet fra {self.config_file}")
                
            except Exception as e:
                logger.error(f"Feil ved lasting av konfigurasjon: {e}")
                self.config = self._create_default_config()
        else:
            logger.info("Oppretter standard konfigurasjon")
            self.config = self._create_default_config()
            self.save_config()
        
        return self.config
    
    def _create_default_config(self) -> WeatherConfig:
        """Opprett standard konfigurasjon"""
        return WeatherConfig(
            snow_drift=SnowDriftConfig(),
            slippery_road=SlipperyRoadConfig(),
            alerts=AlertConfig()
        )
    
    def save_config(self) -> None:
        """Lagre konfigurasjon til fil"""
        
        if not self.config:
            logger.error("Ingen konfigurasjon å lagre")
            return
        
        # Konverter til dict
        config_dict = asdict(self.config)
        
        # Opprett mappe hvis nødvendig
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Konfigurasjon lagret til {self.config_file}")
    
    def update_snow_drift_params(self, **kwargs) -> None:
        """Oppdater snøfokk-parametere"""
        
        if not self.config:
            return
        
        for key, value in kwargs.items():
            if hasattr(self.config.snow_drift, key):
                setattr(self.config.snow_drift, key, value)
                logger.info(f"Oppdatert snøfokk parameter: {key} = {value}")
        
        self.save_config()
    
    def update_slippery_road_params(self, **kwargs) -> None:
        """Oppdater glatt vei-parametere"""
        
        if not self.config:
            return
        
        for key, value in kwargs.items():
            if hasattr(self.config.slippery_road, key):
                setattr(self.config.slippery_road, key, value)
                logger.info(f"Oppdatert glatt vei parameter: {key} = {value}")
        
        self.save_config()
    
    def update_alert_params(self, **kwargs) -> None:
        """Oppdater varslingsparametere"""
        
        if not self.config:
            return
        
        for key, value in kwargs.items():
            if hasattr(self.config.alerts, key):
                setattr(self.config.alerts, key, value)
                logger.info(f"Oppdatert varsling parameter: {key} = {value}")
        
        self.save_config()
    
    def get_optimal_params_from_analysis(self, analysis_file: str) -> None:
        """Hent optimale parametere fra analyseresultater"""
        
        analysis_path = Path(analysis_file)
        if not analysis_path.exists():
            logger.error(f"Analysefil ikke funnet: {analysis_file}")
            return
        
        try:
            with open(analysis_path, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
            
            # Hent optimaliserte parametere
            optimization = analysis_data.get('optimization_results', {})
            
            if 'snow_drift_params' in optimization:
                snow_params = optimization['snow_drift_params']
                self.update_snow_drift_params(
                    min_wind_speed=snow_params.get('optimal_wind_threshold', 8.0),
                    max_temperature=snow_params.get('optimal_temp_threshold', -2.0),
                    min_duration_hours=snow_params.get('recommended_min_duration', 2),
                    alert_threshold=snow_params.get('confidence_threshold', 70)
                )
            
            if 'slippery_road_params' in optimization:
                slip_params = optimization['slippery_road_params']
                self.update_slippery_road_params(
                    max_temperature=slip_params.get('optimal_temp_threshold', 2.0),
                    min_humidity=slip_params.get('optimal_humidity_threshold', 80.0),
                    min_duration_hours=slip_params.get('recommended_min_duration', 1),
                    alert_threshold=slip_params.get('confidence_threshold', 60)
                )
            
            logger.info("Parametere oppdatert basert på analyseresultater")
            
        except Exception as e:
            logger.error(f"Feil ved lesing av analysefil: {e}")
    
    def print_current_config(self) -> None:
        """Skriv ut gjeldende konfigurasjon"""
        
        if not self.config:
            logger.error("Ingen konfigurasjon lastet")
            return
        
        print("\n=== GJELDENDE KONFIGURASJON ===")
        
        print("\nSnøfokk-parametere:")
        print(f"  Min vindstyrke: {self.config.snow_drift.min_wind_speed} m/s")
        print(f"  Maks temperatur: {self.config.snow_drift.max_temperature} °C")
        print(f"  Min varighet: {self.config.snow_drift.min_duration_hours} timer")
        print(f"  Min snødybde-variasjon: {self.config.snow_drift.min_snow_depth_variance} cm")
        print(f"  Varslingsterskel: {self.config.snow_drift.alert_threshold}%")
        
        print("\nGlatt vei-parametere:")
        print(f"  Maks temperatur: {self.config.slippery_road.max_temperature} °C")
        print(f"  Min luftfuktighet: {self.config.slippery_road.min_humidity}%")
        print(f"  Min nedbør: {self.config.slippery_road.min_precipitation} mm")
        print(f"  Frost-terskel: {self.config.slippery_road.frost_temp_threshold} °C")
        print(f"  Is-terskel: {self.config.slippery_road.ice_temp_threshold} °C")
        print(f"  Varslingsterskel: {self.config.slippery_road.alert_threshold}%")
        
        print("\nVarsling:")
        print(f"  Snøfokk aktivert: {self.config.alerts.snow_drift_enabled}")
        print(f"  Glatt vei aktivert: {self.config.alerts.slippery_road_enabled}")
        print(f"  Forhåndsvarsel: {self.config.alerts.advance_warning_hours} timer")
        print(f"  Overvåkingsperiode: {self.config.alerts.monitoring_start_hour}-{self.config.alerts.monitoring_end_hour}")
        
        print("\nData:")
        print(f"  Datakilde: {self.config.data_source}")
        print(f"  Standard stasjon: {self.config.default_station}")
        print(f"  Analyseperiode: {self.config.analysis_period_days} dager")
        print(f"  Historiske år: {self.config.historical_years}")

def interactive_config_setup():
    """Interaktiv konfigurasjon"""
    
    print("=== INTERAKTIV KONFIGURASJON ===")
    print("Trykk Enter for å beholde standardverdier")
    
    # Snøfokk-parametere
    print("\n--- SNØFOKK-PARAMETERE ---")
    wind_speed = input("Min vindstyrke (m/s) [8.0]: ").strip()
    max_temp = input("Maks temperatur (°C) [-2.0]: ").strip()
    duration = input("Min varighet (timer) [2]: ").strip()
    
    # Glatt vei-parametere
    print("\n--- GLATT VEI-PARAMETERE ---")
    slip_temp = input("Maks temperatur (°C) [2.0]: ").strip()
    humidity = input("Min luftfuktighet (%) [80.0]: ").strip()
    precipitation = input("Min nedbør (mm) [0.1]: ").strip()
    
    # Varsling
    print("\n--- VARSLING ---")
    advance_hours = input("Forhåndsvarsel (timer) [4]: ").strip()
    enable_email = input("Aktiver e-postvarsling (y/n) [n]: ").strip().lower()
    
    # Opprett konfigurasjon
    config_manager = ConfigManager("config/weather_config.json")
    
    # Oppdater med brukervalg
    if wind_speed:
        config_manager.update_snow_drift_params(min_wind_speed=float(wind_speed))
    if max_temp:
        config_manager.update_snow_drift_params(max_temperature=float(max_temp))
    if duration:
        config_manager.update_snow_drift_params(min_duration_hours=int(duration))
    
    if slip_temp:
        config_manager.update_slippery_road_params(max_temperature=float(slip_temp))
    if humidity:
        config_manager.update_slippery_road_params(min_humidity=float(humidity))
    if precipitation:
        config_manager.update_slippery_road_params(min_precipitation=float(precipitation))
    
    if advance_hours:
        config_manager.update_alert_params(advance_warning_hours=int(advance_hours))
    if enable_email == 'y':
        config_manager.update_alert_params(email_alerts=True)
    
    print("\nKonfigurasjon oppdatert!")
    config_manager.print_current_config()

def main():
    """Test av konfigurasjonsystem"""
    
    # Opprett konfigurasjon
    config_manager = ConfigManager("config/weather_config.json")
    
    # Vis gjeldende konfigurasjon
    config_manager.print_current_config()
    
    # Test oppdatering
    print("\n=== TESTER OPPDATERING ===")
    config_manager.update_snow_drift_params(
        min_wind_speed=10.0,
        alert_threshold=75
    )
    
    config_manager.update_alert_params(
        advance_warning_hours=6,
        email_alerts=True
    )
    
    print("\nOppdatert konfigurasjon:")
    config_manager.print_current_config()

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        interactive_config_setup()
    else:
        main()
