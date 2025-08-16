#!/usr/bin/env python3
"""
Generer syntetiske historiske værdata for testing uten API-avhengighet.
Basert på empirisk validerte værmønstre fra norske vinterforhold.
"""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
import numpy as np
import math

class SyntheticWeatherGenerator:
    """Generer realistiske syntetiske værdata for testing"""
    
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / "data" / "historical"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Seasonally realistic weather patterns for Norwegian winter
        self.winter_months = [11, 12, 1, 2, 3]  # Nov-Mar
        self.summer_months = [5, 6, 7, 8, 9]   # May-Sep
        
    def generate_realistic_weather_hour(self, timestamp: datetime, base_temp: float, season_factor: float) -> Dict:
        """Generer realistiske værdata for en time"""
        
        # Basic temperature with daily variation
        hour_variation = math.sin((timestamp.hour - 6) * math.pi / 12) * 3  # Peak at 18:00
        air_temp = base_temp + hour_variation + random.gauss(0, 1.5)
        
        # Surface temperature (usually slightly different from air)
        surface_temp = air_temp + random.gauss(-1.5, 1.0)
        
        # Seasonal precipitation probability
        is_winter = timestamp.month in self.winter_months
        precip_prob = 0.3 if is_winter else 0.2
        
        # Wind patterns (higher in winter)
        base_wind = 4.0 + season_factor * 2.0
        wind_speed = max(0, np.random.gamma(2, base_wind/2))
        wind_direction = random.uniform(0, 360)
        
        # Snow depth (only in winter, accumulates)
        snow_depth = 0.0
        if is_winter and air_temp < 2.0:
            snow_depth = max(0, np.random.gamma(1.5, 8) * season_factor)
        
        # Precipitation
        precipitation_1h = 0.0
        precipitation_10m = 0.0
        precip_duration = 0.0
        
        if random.random() < precip_prob:
            # Generate precipitation event
            intensity = np.random.exponential(2.0)  # mm/h
            duration = random.uniform(10, 60)  # minutes
            
            precipitation_1h = intensity
            precipitation_10m = intensity / 6.0  # Approximate
            precip_duration = duration
        
        # Humidity and dew point
        base_humidity = 70 if is_winter else 65
        humidity = max(30, min(100, random.gauss(base_humidity, 15)))
        
        # Simple dew point calculation
        dew_point = air_temp - ((100 - humidity) / 5.0)
        
        # Wind gusts (higher than base wind)
        wind_gust = wind_speed + np.random.exponential(2.0)
        
        # Daily temperature extremes (simplified)
        temp_max_1h = air_temp + random.uniform(0, 2)
        temp_min_1h = air_temp - random.uniform(0, 2)
        
        # Maximum wind from specific direction
        max_wind_direction = wind_speed + random.uniform(-1, 3)
        
        # Accumulated precipitation (daily running total)
        accumulated_precip = precipitation_1h * random.uniform(8, 24)  # Simulate daily accumulation
        
        return {
            "timestamp": timestamp.isoformat() + "Z",
            "air_temperature": round(air_temp, 1),
            "surface_temperature": round(surface_temp, 1),
            "surface_snow_thickness": round(snow_depth, 1),
            "wind_speed": round(wind_speed, 1),
            "wind_from_direction": round(wind_direction, 0),
            "precipitation_amount_1h": round(precipitation_1h, 1),
            "precipitation_amount_10m": round(precipitation_10m, 2),
            "precipitation_duration_1h": round(precip_duration, 0),
            "dew_point_temperature": round(dew_point, 1),
            "relative_humidity": round(humidity, 0),
            "wind_gust_max_1h": round(wind_gust, 1),
            "air_temp_max_1h": round(temp_max_1h, 1),
            "air_temp_min_1h": round(temp_min_1h, 1),
            "max_wind_speed_direction": round(max_wind_direction, 1),
            "accumulated_precipitation": round(accumulated_precip, 1)
        }
    
    def generate_year_scenarios(self, year: int) -> List[Dict]:
        """Generer realistiske værscenarier for et helt år"""
        
        scenarios = []
        start_date = datetime(year, 1, 1)
        end_date = datetime(year + 1, 1, 1)
        
        current_date = start_date
        
        # Seasonal base temperatures (Norway)
        seasonal_temps = {
            1: -8, 2: -7, 3: -3, 4: 3, 5: 10, 6: 15,
            7: 17, 8: 16, 9: 11, 10: 5, 11: 0, 12: -5
        }
        
        while current_date < end_date:
            month = current_date.month
            base_temp = seasonal_temps[month]
            
            # Winter season factor (for snow/wind calculations)
            season_factor = 1.0 if month in self.winter_months else 0.2
            
            # Add some weather system variation (3-7 day patterns)
            day_of_year = current_date.timetuple().tm_yday
            weather_cycle = math.sin(day_of_year * 2 * math.pi / 5.5) * 3  # 5.5-day cycle
            base_temp += weather_cycle
            
            # Generate hourly data
            for hour in range(24):
                timestamp = current_date.replace(hour=hour)
                weather_data = self.generate_realistic_weather_hour(timestamp, base_temp, season_factor)
                scenarios.append(weather_data)
            
            current_date += timedelta(days=1)
        
        return scenarios
    
    def add_operational_scenarios(self, year_data: List[Dict]) -> List[Dict]:
        """Legg til spesifikke operasjonelle testscenarier"""
        
        enhanced_data = year_data.copy()
        
        # Scenario 1: Heavy snowfall with wind (snowdrift risk)
        heavy_snow_start = len(enhanced_data) // 4  # 1/4 through year
        for i in range(heavy_snow_start, heavy_snow_start + 12):  # 12 hours
            if i < len(enhanced_data):
                enhanced_data[i].update({
                    "air_temperature": -8.0,
                    "surface_temperature": -10.0,
                    "precipitation_amount_1h": 8.0,  # Heavy snow
                    "wind_speed": 15.0,  # High wind
                    "wind_from_direction": 315.0,  # Critical NW direction
                    "surface_snow_thickness": 20.0 + (i - heavy_snow_start) * 2,  # Accumulating
                    "relative_humidity": 95.0
                })
        
        # Scenario 2: Freezing rain (slippery conditions)
        ice_start = len(enhanced_data) // 2  # Midway through year
        for i in range(ice_start, ice_start + 6):  # 6 hours
            if i < len(enhanced_data):
                enhanced_data[i].update({
                    "air_temperature": 1.0,  # Above freezing
                    "surface_temperature": -2.0,  # Below freezing
                    "precipitation_amount_1h": 4.0,  # Significant precipitation
                    "wind_speed": 3.0,  # Light wind
                    "relative_humidity": 98.0,  # Very humid
                    "dew_point_temperature": 0.5
                })
        
        # Scenario 3: Temperature fluctuation around freezing
        temp_change_start = len(enhanced_data) * 3 // 4  # 3/4 through year
        for i in range(temp_change_start, temp_change_start + 24):  # 24 hours
            if i < len(enhanced_data):
                hour_in_cycle = i - temp_change_start
                temp_variation = math.sin(hour_in_cycle * math.pi / 12) * 4  # ±4°C variation
                enhanced_data[i].update({
                    "air_temperature": -1.0 + temp_variation,
                    "surface_temperature": -3.0 + temp_variation,
                    "precipitation_amount_1h": 1.5 if hour_in_cycle % 3 == 0 else 0.0
                })
        
        return enhanced_data
    
    def generate_test_data_file(self, year: int) -> bool:
        """Generer testdata for ett år"""
        
        print(f"Genererer syntetiske værdata for {year}...")
        
        # Generate base year data
        year_scenarios = self.generate_year_scenarios(year)
        
        # Add specific operational test scenarios
        enhanced_scenarios = self.add_operational_scenarios(year_scenarios)
        
        # Create file structure
        file_data = {
            "metadata": {
                "year": year,
                "station": "SN46220",
                "station_name": "Gullingen (Syntetisk)",
                "type": "synthetic_test_data",
                "generated_timestamp": datetime.now().isoformat(),
                "description": "Realistiske syntetiske værdata for testing uten API-avhengighet",
                "scenario_count": len(enhanced_scenarios),
                "operational_scenarios": [
                    "Heavy snowfall with snowdrift risk",
                    "Freezing rain conditions",
                    "Temperature fluctuation around freezing point"
                ]
            },
            "weather_data": enhanced_scenarios
        }
        
        # Save to file
        output_file = self.data_dir / f"synthetic_weather_{year}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(file_data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Lagret {len(enhanced_scenarios)} værpunkter til {output_file}")
        return True
    
    def generate_all_test_years(self, start_year: int = 2018, end_year: int = 2025):
        """Generer syntetiske testdata for alle år"""
        
        print("SYNTETISK VÆRDATA GENERERING")
        print("="*50)
        print("Lager realistiske værdata for lokal testing")
        print(f"Periode: {start_year}-{end_year}")
        print("Formål: Testing uten API-avhengighet")
        print("="*50)
        
        for year in range(start_year, end_year + 1):
            self.generate_test_data_file(year)
        
        self.create_summary_file()
        print("\n✓ GENERERING FULLFØRT!")
    
    def create_summary_file(self):
        """Lag sammendrag av genererte testdata"""
        
        summary = {
            "summary": {
                "created": datetime.now().isoformat(),
                "type": "synthetic_test_data",
                "station": "SN46220",
                "station_name": "Gullingen (Syntetisk)",
                "purpose": "Local testing without API dependency",
                "description": "Realistic synthetic weather data based on Norwegian winter patterns"
            },
            "files": []
        }
        
        total_scenarios = 0
        for year_file in sorted(self.data_dir.glob("synthetic_weather_*.json")):
            try:
                with open(year_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                scenario_count = data["metadata"]["scenario_count"]
                total_scenarios += scenario_count
                
                file_info = {
                    "filename": year_file.name,
                    "year": data["metadata"]["year"],
                    "scenario_count": scenario_count,
                    "file_size_kb": round(year_file.stat().st_size / 1024, 1)
                }
                summary["files"].append(file_info)
                
            except Exception as e:
                print(f"Kunne ikke lese {year_file}: {e}")
        
        summary["summary"]["total_scenarios"] = total_scenarios
        summary["summary"]["file_count"] = len(summary["files"])
        
        summary_file = self.data_dir / "synthetic_weather_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Sammendrag lagret til {summary_file}")
        
        # Print summary
        print("\n" + "="*60)
        print("SYNTETISK VÆRDATA - SAMMENDRAG")
        print("="*60)
        print(f"Type: {summary['summary']['type']}")
        print(f"Stasjon: {summary['summary']['station_name']}")
        print(f"Filer: {len(summary['files'])} årsfiler")
        print(f"Total scenarier: {total_scenarios:,}")
        
        total_size = sum(f["file_size_kb"] for f in summary["files"])
        print(f"Total størrelse: {total_size:.1f} KB")
        
        print("\nÅrlige filer:")
        for file_info in summary["files"]:
            print(f"  {file_info['year']}: {file_info['scenario_count']:,} scenarier ({file_info['file_size_kb']} KB)")
        print("="*60)


def main():
    generator = SyntheticWeatherGenerator()
    generator.generate_all_test_years(2018, 2025)


if __name__ == "__main__":
    main()
