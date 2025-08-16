#!/usr/bin/env python3
"""
Snowdrift Parameter Optimizer - Optimaliserer snøfokk-parametere basert på historiske data
"""
import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

class SnowdriftParameterOptimizer:
    """Optimaliserer snøfokk-parametere basert på historiske data"""

    def __init__(self):
        self.analysis_file = Path(__file__).parent.parent.parent / 'data' / 'analyzed' / 'winter_snowdrift_analysis.json'

    def load_historical_analysis(self):
        """Last inn historisk analyse"""
        try:
            with open(self.analysis_file, encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print("❌ Kjør først winter_snowdrift_analysis.py for å generere data")
            return None

    def calculate_optimal_parameters(self, historical_data):
        """Beregn optimale parametere basert på historiske data"""

        # Siden vi ikke har rå hendelser, bruk aggregerte data
        total_events = sum(year['patterns']['total_events'] for year in historical_data)

        if total_events == 0:
            print("❌ Ingen historiske hendelser å analysere")
            return None

        # Samle aggregerte statistikker fra alle år
        wind_stats = []
        temp_stats = []
        snow_stats = []

        for year_data in historical_data:
            patterns = year_data['patterns']['patterns']
            if year_data['patterns']['total_events'] > 0:
                wind_stats.append(patterns['wind']['avg_max_wind'])
                temp_stats.append(patterns['temperature']['avg_min_temp'])
                snow_stats.append(patterns['snow']['avg_depth_at_start'])

        if not wind_stats:
            print("❌ Ingen gyldige statistikker å analysere")
            return None

        import numpy as np

        # Beregn optimale parametere basert på aggregerte data
        optimal_params = {
            'wind_thresholds': {
                'min_wind_speed': min(wind_stats) * 0.8,  # 20% under laveste observerte
                'optimal_wind_speed': np.mean(wind_stats),
                'max_effective_wind': max(wind_stats) * 1.1
            },
            'temperature_thresholds': {
                'max_temperature': max(temp_stats) * 0.8,  # Varmere enn kaldeste observerte
                'optimal_temperature': np.mean(temp_stats),
                'min_effective_temp': min(temp_stats) * 1.2  # Kaldere enn kaldeste
            },
            'snow_thresholds': {
                'min_snow_depth': min(snow_stats) * 0.5,  # Halvparten av laveste observerte
                'optimal_snow_depth': np.mean(snow_stats),
                'deep_snow_threshold': max(snow_stats)
            },
            'duration_thresholds': {
                'min_duration': 1,  # Basert på observasjoner
                'typical_duration': 2,  # Alle var 2 timer
                'long_duration': 3
            }
        }

        return optimal_params, total_events

    def generate_optimized_config(self, optimal_params):
        """Generer optimalisert konfigurasjon"""

        config = {
            "optimization_info": {
                "generated_date": datetime.now().isoformat(),
                "based_on": "Historical snowdrift analysis of 3 winters",
                "source": "Fjellbergsskardet (SN46220) weather station"
            },

            "snowdrift_detection": {
                "wind": {
                    "min_speed_ms": round(optimal_params['wind_thresholds']['min_wind_speed'], 1),
                    "optimal_speed_ms": round(optimal_params['wind_thresholds']['optimal_wind_speed'], 1),
                    "weight": 0.4,
                    "description": "Wind speed thresholds for snowdrift detection"
                },
                "temperature": {
                    "max_temp_c": round(optimal_params['temperature_thresholds']['max_temperature'], 1),
                    "optimal_temp_c": round(optimal_params['temperature_thresholds']['optimal_temperature'], 1),
                    "weight": 0.3,
                    "description": "Temperature thresholds (colder = higher risk)"
                },
                "snow": {
                    "min_depth_cm": round(optimal_params['snow_thresholds']['min_snow_depth'], 1),
                    "optimal_depth_cm": round(optimal_params['snow_thresholds']['optimal_snow_depth'], 1),
                    "weight": 0.2,
                    "description": "Snow depth requirements for drift formation"
                },
                "snow_change": {
                    "significant_change_cm": 2.0,
                    "weight": 0.1,
                    "description": "Snow depth change indicating active drifting"
                }
            },

            "detection_rules": {
                "min_duration_hours": round(optimal_params['duration_thresholds']['min_duration']),
                "risk_score_threshold": 0.6,
                "high_risk_score_threshold": 0.8,
                "description": "Rules for identifying snowdrift events"
            },

            "seasonal_adjustments": {
                "early_winter": {
                    "months": [12, 1],
                    "snow_depth_multiplier": 0.8,
                    "description": "Early winter - less established snow pack"
                },
                "peak_winter": {
                    "months": [2, 3],
                    "snow_depth_multiplier": 1.0,
                    "description": "Peak winter - full snow conditions"
                },
                "late_winter": {
                    "months": [4],
                    "snow_depth_multiplier": 1.2,
                    "description": "Late winter - snow becoming unstable"
                }
            }
        }

        return config

    def compare_with_current(self, optimized_config):
        """Sammenlign med nåværende parametere"""

        # Nåværende parametere fra analyzer
        current = {
            'min_wind_speed': 6.0,
            'optimal_wind_speed': 12.0,
            'max_temperature': -2.0,
            'optimal_temperature': -8.0,
            'min_snow_depth': 3.0,
            'duration_hours': 2
        }

        optimized = optimized_config['snowdrift_detection']

        print("📊 SAMMENLIGNING - NÅVÆRENDE VS OPTIMALISERT")
        print("=" * 60)

        print("💨 VIND:")
        print(f"   Nåværende min: {current['min_wind_speed']} m/s")
        print(f"   Optimalisert:  {optimized['wind']['min_speed_ms']} m/s")
        change = ((optimized['wind']['min_speed_ms'] - current['min_wind_speed']) / current['min_wind_speed']) * 100
        print(f"   Endring: {change:+.1f}%")

        print("\n🌡️ TEMPERATUR:")
        print(f"   Nåværende max: {current['max_temperature']}°C")
        print(f"   Optimalisert:  {optimized['temperature']['max_temp_c']}°C")

        print("\n❄️ SNØ:")
        print(f"   Nåværende min: {current['min_snow_depth']} cm")
        print(f"   Optimalisert:  {optimized['snow']['min_depth_cm']} cm")

        print("\n⏱️ VARIGHET:")
        print(f"   Nåværende: {current['duration_hours']} timer")
        print(f"   Optimalisert: {optimized_config['detection_rules']['min_duration_hours']} timer")

    def run_optimization(self):
        """Kjør fullstendig optimalisering"""

        print("🔧 SNØFOKK PARAMETER OPTIMALISERING")
        print("=" * 60)

        # Last inn historiske data
        historical_data = self.load_historical_analysis()
        if not historical_data:
            return

        print(f"📈 Analyserer {len(historical_data)} vintre med historiske data...")

        # Beregn optimale parametere
        optimal_params, event_count = self.calculate_optimal_parameters(historical_data)
        if not optimal_params:
            return

        print(f"✅ Basert på {event_count} historiske snøfokk-hendelser")

        # Generer konfigurasjon
        optimized_config = self.generate_optimized_config(optimal_params)

        # Sammenlign med nåværende
        self.compare_with_current(optimized_config)

        # Lagre optimalisert konfigurasjon
        output_file = Path(__file__).parent.parent.parent / 'config' / 'optimized_snowdrift_config.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(optimized_config, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Optimalisert konfigurasjon lagret i {output_file}")

        # Lag anbefaling for implementering
        print("\n🎯 IMPLEMENTERINGS-ANBEFALING:")
        print("1. Test den optimaliserte konfigurasjonen mot kjente hendelser")
        print("2. Gradvis juster grenseverdier i produksjon")
        print("3. Overvåk false positive/negative rate")
        print("4. Oppdater parametere årlig basert på ny data")

        return optimized_config

def main():
    optimizer = SnowdriftParameterOptimizer()
    optimizer.run_optimization()

if __name__ == '__main__':
    main()
