#!/usr/bin/env python3
"""
Analyse av samsvar mellom faktiske brøytingsrapporter og værdata.
Validerer hvor godt våre værbaserte algoritmer matcher real-world operasjoner.
"""
import pandas as pd
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np
from dataclasses import dataclass

@dataclass
class SnowPlowingRecord:
    """Faktisk brøytingsrecord fra operasjonell data"""
    date: datetime
    start_time: datetime
    end_time: datetime
    route: str
    unit: str
    duration_hours: float
    distance_km: float
    
@dataclass
class WeatherCorrelation:
    """Korrelasjon mellom vær og brøyting"""
    plowing_record: SnowPlowingRecord
    weather_conditions: Dict
    correlation_score: float
    predicted_needed: bool
    actual_needed: bool
    match: bool

class WeatherPlowingCorrelationAnalyzer:
    """Analyserer samsvar mellom værdata og faktiske brøytinger"""
    
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / "data"
        self.plowing_data = []
        self.weather_data = {}
        
    def load_plowing_data(self, csv_file: str) -> List[SnowPlowingRecord]:
        """Last inn faktiske brøytingsdata"""
        csv_path = self.data_dir / "analyzed" / csv_file
        
        # Read CSV with semicolon separator and Norwegian date format
        df = pd.read_csv(csv_path, sep=';', encoding='utf-8')
        
        records = []
        
        for _, row in df.iterrows():
            if row['Dato'] == 'Totalt':  # Skip summary row
                continue
                
            try:
                # Parse Norwegian date format
                date_str = row['Dato']
                start_time_str = row['Starttid']
                end_time_str = row['Sluttid']
                
                # Convert Norwegian date format to datetime
                date_parts = date_str.replace('.', '').split()
                day = int(date_parts[0])
                
                month_mapping = {
                    'jan': 1, 'feb': 2, 'mars': 3, 'apr': 4, 'mai': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'okt': 10, 'nov': 11, 'des': 12
                }
                month = month_mapping[date_parts[1]]
                year = int(date_parts[2])
                
                base_date = datetime(year, month, day)
                
                # Parse time strings
                start_hours, start_minutes, start_seconds = map(int, start_time_str.split(':'))
                end_hours, end_minutes, end_seconds = map(int, end_time_str.split(':'))
                
                start_datetime = base_date.replace(
                    hour=start_hours, minute=start_minutes, second=start_seconds
                )
                end_datetime = base_date.replace(
                    hour=end_hours, minute=end_minutes, second=end_seconds
                )
                
                # Handle overnight operations
                if end_datetime < start_datetime:
                    end_datetime += timedelta(days=1)
                
                # Parse duration
                duration_str = row['Varighet']
                if ':' in duration_str:
                    time_parts = duration_str.split(':')
                    duration_hours = int(time_parts[0]) + int(time_parts[1])/60
                    if len(time_parts) > 2:
                        duration_hours += int(time_parts[2])/3600
                else:
                    duration_hours = 0
                
                record = SnowPlowingRecord(
                    date=base_date,
                    start_time=start_datetime,
                    end_time=end_datetime,
                    route=row['Rode'],
                    unit=str(row['Enhet']),
                    duration_hours=duration_hours,
                    distance_km=float(str(row['Distanse (km)']).replace(',', '.'))
                )
                
                records.append(record)
                
            except Exception as e:
                print(f"Kunne ikke parse rad: {row} - Feil: {e}")
                continue
        
        self.plowing_data = records
        return records
    
    def load_synthetic_weather_data(self, year: int) -> Dict:
        """Last inn syntetiske værdata for gitt år"""
        weather_file = self.data_dir / "historical" / f"synthetic_weather_{year}.json"
        
        if not weather_file.exists():
            return {}
        
        with open(weather_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Convert to datetime-indexed dict for easy lookup
        weather_dict = {}
        for item in data["weather_data"]:
            timestamp = datetime.fromisoformat(item["timestamp"].replace('Z', '+00:00'))
            weather_dict[timestamp.replace(tzinfo=None)] = item
        
        return weather_dict
    
    def get_weather_conditions_for_plowing(self, plowing_record: SnowPlowingRecord) -> Dict:
        """Hent værforhold for en brøytingsperiode"""
        year = plowing_record.date.year
        
        if year not in self.weather_data:
            self.weather_data[year] = self.load_synthetic_weather_data(year)
        
        weather_year_data = self.weather_data[year]
        
        if not weather_year_data:
            return {}
        
        # Find weather data in a 24-hour window around plowing
        start_window = plowing_record.start_time - timedelta(hours=12)
        end_window = plowing_record.end_time + timedelta(hours=12)
        
        relevant_weather = []
        
        for timestamp, weather in weather_year_data.items():
            if start_window <= timestamp <= end_window:
                relevant_weather.append(weather)
        
        if not relevant_weather:
            return {}
        
        # Calculate aggregated conditions
        conditions = {
            "avg_air_temperature": np.mean([w["air_temperature"] for w in relevant_weather]),
            "min_surface_temperature": min([w["surface_temperature"] for w in relevant_weather]),
            "max_precipitation_1h": max([w["precipitation_amount_1h"] for w in relevant_weather]),
            "total_precipitation": sum([w["precipitation_amount_1h"] for w in relevant_weather]),
            "max_wind_speed": max([w["wind_speed"] for w in relevant_weather]),
            "max_snow_depth": max([w["surface_snow_thickness"] for w in relevant_weather]),
            "avg_humidity": np.mean([w["relative_humidity"] for w in relevant_weather]),
            "weather_data_points": len(relevant_weather),
            "period_start": start_window,
            "period_end": end_window
        }
        
        return conditions
    
    def predict_plowing_needed(self, weather_conditions: Dict) -> Tuple[bool, float]:
        """Prediker om brøyting er nødvendig basert på værforhold"""
        if not weather_conditions:
            return False, 0.0
        
        score = 0.0
        
        # Snow accumulation factor
        snow_depth = weather_conditions.get("max_snow_depth", 0)
        if snow_depth > 15:
            score += 0.4
        elif snow_depth > 8:
            score += 0.3
        elif snow_depth > 3:
            score += 0.1
        
        # Precipitation factor
        total_precip = weather_conditions.get("total_precipitation", 0)
        max_precip_1h = weather_conditions.get("max_precipitation_1h", 0)
        
        if total_precip > 10:
            score += 0.3
        elif total_precip > 5:
            score += 0.2
        
        if max_precip_1h > 5:
            score += 0.2
        
        # Temperature factor (freezing conditions)
        avg_temp = weather_conditions.get("avg_air_temperature", 10)
        min_surface_temp = weather_conditions.get("min_surface_temperature", 10)
        
        if avg_temp < -5 and min_surface_temp < -2:
            score += 0.2
        elif avg_temp < 0:
            score += 0.1
        
        # Wind factor (drifting snow)
        max_wind = weather_conditions.get("max_wind_speed", 0)
        if max_wind > 12 and snow_depth > 5:
            score += 0.15
        elif max_wind > 8 and snow_depth > 3:
            score += 0.1
        
        # Threshold for predicting plowing needed
        needed = score > 0.4
        
        return needed, score
    
    def analyze_correlations(self) -> List[WeatherCorrelation]:
        """Analyser korrelasjon mellom vær og brøyting"""
        correlations = []
        
        for plowing_record in self.plowing_data:
            weather_conditions = self.get_weather_conditions_for_plowing(plowing_record)
            
            if weather_conditions:
                predicted_needed, score = self.predict_plowing_needed(weather_conditions)
                
                correlation = WeatherCorrelation(
                    plowing_record=plowing_record,
                    weather_conditions=weather_conditions,
                    correlation_score=score,
                    predicted_needed=predicted_needed,
                    actual_needed=True,  # All records in CSV are actual plowing
                    match=predicted_needed  # True if we correctly predicted need
                )
                
                correlations.append(correlation)
        
        return correlations
    
    def generate_correlation_report(self, correlations: List[WeatherCorrelation]) -> Dict:
        """Generer rapport om korrelasjon"""
        if not correlations:
            return {"error": "Ingen korrelasjonsdata tilgjengelig"}
        
        total_operations = len(correlations)
        correct_predictions = sum(1 for c in correlations if c.match)
        
        # Statistics
        correlation_scores = [c.correlation_score for c in correlations]
        weather_conditions = [c.weather_conditions for c in correlations if c.weather_conditions]
        
        report = {
            "summary": {
                "total_plowing_operations": total_operations,
                "correct_predictions": correct_predictions,
                "prediction_accuracy": (correct_predictions / total_operations * 100) if total_operations > 0 else 0,
                "avg_correlation_score": np.mean(correlation_scores) if correlation_scores else 0,
                "analysis_period": {
                    "start": min(c.plowing_record.date for c in correlations).isoformat(),
                    "end": max(c.plowing_record.date for c in correlations).isoformat()
                }
            },
            "weather_statistics": {
                "avg_snow_depth": np.mean([w["max_snow_depth"] for w in weather_conditions]) if weather_conditions else 0,
                "avg_precipitation": np.mean([w["total_precipitation"] for w in weather_conditions]) if weather_conditions else 0,
                "avg_temperature": np.mean([w["avg_air_temperature"] for w in weather_conditions]) if weather_conditions else 0,
                "avg_wind_speed": np.mean([w["max_wind_speed"] for w in weather_conditions]) if weather_conditions else 0
            },
            "operational_patterns": self._analyze_operational_patterns(correlations),
            "missed_predictions": [
                {
                    "date": c.plowing_record.date.isoformat(),
                    "score": c.correlation_score,
                    "weather": {
                        "snow_depth": c.weather_conditions.get("max_snow_depth", 0),
                        "precipitation": c.weather_conditions.get("total_precipitation", 0),
                        "temperature": c.weather_conditions.get("avg_air_temperature", 0)
                    }
                }
                for c in correlations if not c.match
            ][:10]  # Top 10 missed predictions
        }
        
        return report
    
    def _analyze_operational_patterns(self, correlations: List[WeatherCorrelation]) -> Dict:
        """Analyser operasjonelle mønstre"""
        monthly_ops = {}
        hourly_ops = {}
        unit_ops = {}
        
        for c in correlations:
            # Monthly pattern
            month = c.plowing_record.date.month
            monthly_ops[month] = monthly_ops.get(month, 0) + 1
            
            # Hourly pattern
            hour = c.plowing_record.start_time.hour
            hourly_ops[hour] = hourly_ops.get(hour, 0) + 1
            
            # Unit pattern
            unit = c.plowing_record.unit
            unit_ops[unit] = unit_ops.get(unit, 0) + 1
        
        return {
            "busiest_month": max(monthly_ops, key=monthly_ops.get) if monthly_ops else None,
            "busiest_hour": max(hourly_ops, key=hourly_ops.get) if hourly_ops else None,
            "most_active_unit": max(unit_ops, key=unit_ops.get) if unit_ops else None,
            "monthly_distribution": monthly_ops,
            "hourly_distribution": hourly_ops,
            "unit_distribution": unit_ops
        }
    
    def save_correlation_analysis(self, report: Dict, filename: str = "weather_plowing_correlation_analysis.json"):
        """Lagre korrelasjonsanalyse til fil"""
        output_file = self.data_dir / "analyzed" / filename
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"Korrelasjonsanalyse lagret til: {output_file}")


def main():
    """Kjør korrelasjonsanalyse"""
    print("ANALYSE AV SAMSVAR: VÆRDATA ↔ BRØYTINGSRAPPORTER")
    print("="*60)
    
    analyzer = WeatherPlowingCorrelationAnalyzer()
    
    # Load plowing data
    print("Laster brøytingsdata...")
    plowing_records = analyzer.load_plowing_data("Rapport 2022-2025.csv")
    print(f"✓ Lastet {len(plowing_records)} brøytingsoperasjoner")
    
    # Analyze correlations
    print("Analyserer korrelasjoner...")
    correlations = analyzer.analyze_correlations()
    print(f"✓ Analyserte {len(correlations)} korrelasjoner")
    
    # Generate report
    print("Genererer rapport...")
    report = analyzer.generate_correlation_report(correlations)
    
    # Save analysis
    analyzer.save_correlation_analysis(report)
    
    # Print summary
    print("\n" + "="*60)
    print("KORRELASJONSANALYSE - SAMMENDRAG")
    print("="*60)
    print(f"Totale brøytingsoperasjoner: {report['summary']['total_plowing_operations']}")
    print(f"Korrekte prediksjoner: {report['summary']['correct_predictions']}")
    print(f"Prediksjonsaccuracy: {report['summary']['prediction_accuracy']:.1f}%")
    print(f"Gjennomsnittlig korrelasjonsscore: {report['summary']['avg_correlation_score']:.3f}")
    
    weather_stats = report['weather_statistics']
    print(f"\nVærstatistikk (gjennomsnitt):")
    print(f"  Snødybde: {weather_stats['avg_snow_depth']:.1f} cm")
    print(f"  Nedbør: {weather_stats['avg_precipitation']:.1f} mm")
    print(f"  Temperatur: {weather_stats['avg_temperature']:.1f}°C")
    print(f"  Vindstyrke: {weather_stats['avg_wind_speed']:.1f} m/s")
    
    patterns = report['operational_patterns']
    print(f"\nOperasjonelle mønstre:")
    print(f"  Travleste måned: {patterns['busiest_month']}")
    print(f"  Travleste time: {patterns['busiest_hour']:02d}:00")
    print(f"  Mest aktive enhet: {patterns['most_active_unit']}")
    
    print("="*60)
    

if __name__ == "__main__":
    main()
