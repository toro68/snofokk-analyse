#!/usr/bin/env python3
"""
Test data loader for syntetiske værdata.
Tillater testing uten API-avhengighet ved å bruke lokale historiske data.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import random

@dataclass
class WeatherTestData:
    """Test værdata struktur"""
    timestamp: datetime
    air_temperature: float
    surface_temperature: float
    surface_snow_thickness: float
    wind_speed: float
    wind_from_direction: float
    precipitation_amount_1h: float
    precipitation_amount_10m: float
    precipitation_duration_1h: float
    dew_point_temperature: float
    relative_humidity: float
    wind_gust_max_1h: float
    air_temp_max_1h: float
    air_temp_min_1h: float
    max_wind_speed_direction: float
    accumulated_precipitation: float

class SyntheticWeatherLoader:
    """Loader for syntetiske testdata"""
    
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / "data" / "historical"
        self._loaded_data = {}  # Cache
    
    def load_year_data(self, year: int) -> List[WeatherTestData]:
        """Last inn værdata for ett år"""
        if year in self._loaded_data:
            return self._loaded_data[year]
        
        data_file = self.data_dir / f"synthetic_weather_{year}.json"
        if not data_file.exists():
            raise FileNotFoundError(f"Ingen testdata for {year}: {data_file}")
        
        with open(data_file, 'r', encoding='utf-8') as f:
            file_data = json.load(f)
        
        weather_data = []
        for item in file_data["weather_data"]:
            weather_point = WeatherTestData(
                timestamp=datetime.fromisoformat(item["timestamp"].replace('Z', '+00:00')),
                air_temperature=item["air_temperature"],
                surface_temperature=item["surface_temperature"],
                surface_snow_thickness=item["surface_snow_thickness"],
                wind_speed=item["wind_speed"],
                wind_from_direction=item["wind_from_direction"],
                precipitation_amount_1h=item["precipitation_amount_1h"],
                precipitation_amount_10m=item["precipitation_amount_10m"],
                precipitation_duration_1h=item["precipitation_duration_1h"],
                dew_point_temperature=item["dew_point_temperature"],
                relative_humidity=item["relative_humidity"],
                wind_gust_max_1h=item["wind_gust_max_1h"],
                air_temp_max_1h=item["air_temp_max_1h"],
                air_temp_min_1h=item["air_temp_min_1h"],
                max_wind_speed_direction=item["max_wind_speed_direction"],
                accumulated_precipitation=item["accumulated_precipitation"]
            )
            weather_data.append(weather_point)
        
        self._loaded_data[year] = weather_data
        return weather_data
    
    def get_winter_scenarios(self, year: int) -> List[WeatherTestData]:
        """Hent kun vinter-scenarier (Nov-Mar)"""
        all_data = self.load_year_data(year)
        winter_months = [11, 12, 1, 2, 3]
        
        winter_data = [
            point for point in all_data 
            if point.timestamp.month in winter_months
        ]
        return winter_data
    
    def get_snow_scenarios(self, year: int, min_snow: float = 5.0) -> List[WeatherTestData]:
        """Hent scenarier med snø"""
        all_data = self.load_year_data(year)
        
        snow_data = [
            point for point in all_data 
            if point.surface_snow_thickness >= min_snow
        ]
        return snow_data
    
    def get_precipitation_scenarios(self, year: int, min_precip: float = 1.0) -> List[WeatherTestData]:
        """Hent scenarier med nedbør"""
        all_data = self.load_year_data(year)
        
        precip_data = [
            point for point in all_data 
            if point.precipitation_amount_1h >= min_precip
        ]
        return precip_data
    
    def get_high_wind_scenarios(self, year: int, min_wind: float = 10.0) -> List[WeatherTestData]:
        """Hent scenarier med høy vind"""
        all_data = self.load_year_data(year)
        
        wind_data = [
            point for point in all_data 
            if point.wind_speed >= min_wind
        ]
        return wind_data
    
    def get_critical_scenarios(self, year: int) -> Dict[str, List[WeatherTestData]]:
        """Hent kritiske operasjonelle scenarier"""
        all_data = self.load_year_data(year)
        
        scenarios = {
            "heavy_snowfall": [],
            "freezing_rain": [],
            "snowdrift_risk": [],
            "temperature_fluctuation": [],
            "slippery_conditions": []
        }
        
        for point in all_data:
            # Heavy snowfall
            if (point.precipitation_amount_1h >= 5.0 and 
                point.air_temperature <= -2.0 and 
                point.surface_snow_thickness >= 10.0):
                scenarios["heavy_snowfall"].append(point)
            
            # Freezing rain
            if (point.precipitation_amount_1h >= 2.0 and 
                point.air_temperature > 0.0 and 
                point.surface_temperature <= -1.0):
                scenarios["freezing_rain"].append(point)
            
            # Snowdrift risk
            if (point.wind_speed >= 12.0 and 
                point.surface_snow_thickness >= 8.0 and 
                point.air_temperature <= -5.0):
                scenarios["snowdrift_risk"].append(point)
            
            # Temperature fluctuation around freezing
            if (abs(point.air_temperature) <= 2.0 and 
                abs(point.surface_temperature) <= 2.0):
                scenarios["temperature_fluctuation"].append(point)
            
            # Slippery conditions
            if (point.relative_humidity >= 90.0 and 
                point.surface_temperature <= 0.0 and 
                point.air_temperature <= 2.0):
                scenarios["slippery_conditions"].append(point)
        
        return scenarios
    
    def get_random_scenario(self, year: int, scenario_type: str = "winter") -> WeatherTestData:
        """Hent tilfeldig scenario av gitt type"""
        if scenario_type == "winter":
            data = self.get_winter_scenarios(year)
        elif scenario_type == "snow":
            data = self.get_snow_scenarios(year)
        elif scenario_type == "precipitation":
            data = self.get_precipitation_scenarios(year)
        elif scenario_type == "wind":
            data = self.get_high_wind_scenarios(year)
        else:
            data = self.load_year_data(year)
        
        if not data:
            raise ValueError(f"Ingen data funnet for scenario_type: {scenario_type}")
        
        return random.choice(data)
    
    def get_time_series(self, year: int, start_month: int, duration_hours: int = 24) -> List[WeatherTestData]:
        """Hent tidsserie fra gitt måned"""
        all_data = self.load_year_data(year)
        
        # Find første datapoint i ønsket måned
        start_point = None
        for i, point in enumerate(all_data):
            if point.timestamp.month == start_month:
                start_point = i
                break
        
        if start_point is None:
            return []
        
        # Returner ønsket antall timer
        end_point = min(start_point + duration_hours, len(all_data))
        return all_data[start_point:end_point]
    
    def create_test_fixture(self, scenario_name: str, year: int = 2023) -> Dict:
        """Lag test-fixture for spesifikk scenario"""
        critical_scenarios = self.get_critical_scenarios(year)
        
        if scenario_name in critical_scenarios:
            data_points = critical_scenarios[scenario_name]
            if data_points:
                sample_point = random.choice(data_points)
                return {
                    "scenario": scenario_name,
                    "year": year,
                    "timestamp": sample_point.timestamp.isoformat(),
                    "weather_data": {
                        "air_temperature": sample_point.air_temperature,
                        "surface_temperature": sample_point.surface_temperature,
                        "surface_snow_thickness": sample_point.surface_snow_thickness,
                        "wind_speed": sample_point.wind_speed,
                        "wind_from_direction": sample_point.wind_from_direction,
                        "precipitation_amount_1h": sample_point.precipitation_amount_1h,
                        "precipitation_amount_10m": sample_point.precipitation_amount_10m,
                        "precipitation_duration_1h": sample_point.precipitation_duration_1h,
                        "dew_point_temperature": sample_point.dew_point_temperature,
                        "relative_humidity": sample_point.relative_humidity,
                        "wind_gust_max_1h": sample_point.wind_gust_max_1h,
                        "air_temp_max_1h": sample_point.air_temp_max_1h,
                        "air_temp_min_1h": sample_point.air_temp_min_1h,
                        "max_wind_speed_direction": sample_point.max_wind_speed_direction,
                        "accumulated_precipitation": sample_point.accumulated_precipitation
                    }
                }
        
        raise ValueError(f"Scenario ikke funnet: {scenario_name}")


# Global loader instance for testing
test_weather_loader = SyntheticWeatherLoader()


def get_test_weather_data(scenario_type: str = "winter", year: int = 2023) -> WeatherTestData:
    """Convenience function for å hente testdata"""
    return test_weather_loader.get_random_scenario(year, scenario_type)


def get_critical_test_scenarios(year: int = 2023) -> Dict[str, List[WeatherTestData]]:
    """Convenience function for kritiske scenarier"""
    return test_weather_loader.get_critical_scenarios(year)
