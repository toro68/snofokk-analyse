#!/usr/bin/env python3
"""
Weather Data Inspector - Inspiser faktiske værdata for å justere terskler
"""
import asyncio
import statistics
import sys
from datetime import date
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from enhanced_snowdrift_detector import EnhancedSnowdriftDetector


class WeatherDataInspector:
    """Inspiser værdata for å forstå verdier og justere terskler"""

    def __init__(self):
        self.detector = EnhancedSnowdriftDetector()

    async def inspect_weather_patterns(self, start_date, end_date):
        """Inspiser værdata-mønstre"""

        print(f"🔍 INSPISER VÆRDATA: {start_date} til {end_date}")
        print("=" * 60)

        # Hent data
        raw_data = await self.detector.get_comprehensive_weather_data(start_date, end_date)
        if not raw_data:
            print("❌ Ingen data mottatt")
            return

        weather_data = self.detector.organize_weather_data(raw_data)
        print(f"✅ {len(weather_data)} datapunkter analysert")

        # Analyser hver parameter
        parameters = {
            'wind_speed': [],
            'max(wind_speed_of_gust PT1H)': [],
            'wind_from_direction': [],
            'air_temperature': [],
            'surface_snow_thickness': [],
            'sum(precipitation_amount PT1H)': [],
            'relative_humidity': [],
            'surface_temperature': []
        }

        # Samle alle verdier
        for point in weather_data:
            for param in parameters.keys():
                value = point.get(param)
                if value is not None:
                    parameters[param].append(value)

        # Presenter statistikker
        print("\n📊 PARAMETER STATISTIKKER")
        print("=" * 60)

        for param, values in parameters.items():
            if values:
                print(f"\n🏷️ {param}:")
                print(f"   Datapunkter: {len(values)}")
                print(f"   Min: {min(values):.2f}")
                print(f"   Max: {max(values):.2f}")
                print(f"   Gjennomsnitt: {statistics.mean(values):.2f}")
                print(f"   Median: {statistics.median(values):.2f}")

                if len(values) > 1:
                    print(f"   Std.avvik: {statistics.stdev(values):.2f}")

                # Percentiler
                sorted_values = sorted(values)
                n = len(sorted_values)
                print(f"   10% percentil: {sorted_values[n//10]:.2f}")
                print(f"   90% percentil: {sorted_values[9*n//10]:.2f}")
            else:
                print(f"\n❌ {param}: Ingen data")

        # Analyser snøfokk-potensial
        await self.analyze_snowdrift_potential(weather_data)

        return weather_data

    async def analyze_snowdrift_potential(self, weather_data):
        """Analyser snøfokk-potensial med forskjellige terskler"""

        print("\n🎯 SNØFOKK-POTENSIAL ANALYSE")
        print("=" * 60)

        # Test forskjellige terskler
        threshold_tests = [
            {'name': 'Optimalisert (streng)', 'wind': 9.0, 'temp': -3.1, 'snow': 8.3},
            {'name': 'Moderat', 'wind': 7.0, 'temp': -2.0, 'snow': 5.0},
            {'name': 'Liberal', 'wind': 5.0, 'temp': -1.0, 'snow': 2.0},
            {'name': 'Veldig liberal', 'wind': 4.0, 'temp': 0.0, 'snow': 1.0}
        ]

        for test in threshold_tests:
            qualifying_points = 0
            wind_qualified = 0
            temp_qualified = 0
            snow_qualified = 0

            for point in weather_data:
                wind_speed = point.get('wind_speed', 0) or 0
                wind_gust = point.get('max(wind_speed_of_gust PT1H)', 0) or 0
                temperature = point.get('air_temperature', 0) or 0
                snow_depth = point.get('surface_snow_thickness', 0) or 0

                # Test betingelser
                wind_ok = wind_speed >= test['wind'] or wind_gust >= test['wind'] + 2
                temp_ok = temperature <= test['temp']
                snow_ok = snow_depth >= test['snow']

                if wind_ok:
                    wind_qualified += 1
                if temp_ok:
                    temp_qualified += 1
                if snow_ok:
                    snow_qualified += 1

                if wind_ok and temp_ok and snow_ok:
                    qualifying_points += 1

            total_points = len(weather_data)
            qualification_rate = (qualifying_points / total_points * 100) if total_points > 0 else 0

            print(f"\n📋 {test['name'].upper()}:")
            print(f"   Terskler: Vind ≥{test['wind']} m/s, Temp ≤{test['temp']}°C, Snø ≥{test['snow']} cm")
            print(f"   Kvalifiserende punkter: {qualifying_points}/{total_points} ({qualification_rate:.1f}%)")
            print(f"   Vind OK: {wind_qualified} ({wind_qualified/total_points*100:.1f}%)")
            print(f"   Temp OK: {temp_qualified} ({temp_qualified/total_points*100:.1f}%)")
            print(f"   Snø OK: {snow_qualified} ({snow_qualified/total_points*100:.1f}%)")

    async def suggest_optimal_thresholds(self, weather_data):
        """Foreslå optimale terskler basert på data"""

        print("\n💡 TERSKLER-FORSLAG")
        print("=" * 60)

        # Analyser vind-distribusjoner
        wind_speeds = [point.get('wind_speed', 0) or 0 for point in weather_data]
        wind_gusts = [point.get('max(wind_speed_of_gust PT1H)', 0) or 0 for point in weather_data]
        temperatures = [point.get('air_temperature', 0) or 0 for point in weather_data]
        snow_depths = [point.get('surface_snow_thickness', 0) or 0 for point in weather_data]

        # Filtrer bort nuller
        wind_speeds = [w for w in wind_speeds if w > 0]
        wind_gusts = [w for w in wind_gusts if w > 0]
        temperatures = [t for t in temperatures if t is not None]
        snow_depths = [s for s in snow_depths if s > 0]

        if wind_speeds:
            wind_75 = sorted(wind_speeds)[int(0.75 * len(wind_speeds))]
            wind_90 = sorted(wind_speeds)[int(0.90 * len(wind_speeds))]
            print("🌪️ Vind terskler:")
            print(f"   75% percentil: {wind_75:.1f} m/s (moderat)")
            print(f"   90% percentil: {wind_90:.1f} m/s (streng)")

        if temperatures:
            temp_25 = sorted(temperatures)[int(0.25 * len(temperatures))]
            temp_10 = sorted(temperatures)[int(0.10 * len(temperatures))]
            print("🌡️ Temperatur terskler:")
            print(f"   25% percentil: {temp_25:.1f}°C (liberal)")
            print(f"   10% percentil: {temp_10:.1f}°C (streng)")

        if snow_depths:
            snow_25 = sorted(snow_depths)[int(0.25 * len(snow_depths))]
            snow_50 = sorted(snow_depths)[int(0.50 * len(snow_depths))]
            print("❄️ Snødybde terskler:")
            print(f"   25% percentil: {snow_25:.1f} cm (liberal)")
            print(f"   50% percentil: {snow_50:.1f} cm (moderat)")

        # Forslag til nye terskler
        print("\n🎯 ANBEFALT JUSTERING:")
        if wind_speeds:
            suggested_wind = sorted(wind_speeds)[int(0.80 * len(wind_speeds))]
            print(f"   Vind: {suggested_wind:.1f} m/s (80% percentil)")

        if temperatures:
            suggested_temp = sorted(temperatures)[int(0.20 * len(temperatures))]
            print(f"   Temperatur: {suggested_temp:.1f}°C (20% percentil)")

        if snow_depths:
            suggested_snow = sorted(snow_depths)[int(0.30 * len(snow_depths))]
            print(f"   Snødybde: {suggested_snow:.1f} cm (30% percentil)")

async def main():
    inspector = WeatherDataInspector()

    # Test en vinterperiode
    start_date = date(2024, 2, 1)
    end_date = date(2024, 2, 29)

    weather_data = await inspector.inspect_weather_patterns(start_date, end_date)

    if weather_data:
        await inspector.suggest_optimal_thresholds(weather_data)

if __name__ == '__main__':
    asyncio.run(main())
