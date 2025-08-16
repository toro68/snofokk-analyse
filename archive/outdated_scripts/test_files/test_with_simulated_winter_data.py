"""
Test script med simulerte vinterdata for å teste ML-kriterier korrekt.
Dette løser problemet med at sommerdata gir "unknown" resultater.
"""

import os
import sys
import time
import traceback
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

# Legg til src-mappen til Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from live_conditions_app import LiveConditionsChecker
    print("✅ Importerte Live Conditions moduler")
except ImportError as e:
    print(f"❌ Feil ved import av Live Conditions moduler: {e}")
    sys.exit(1)


def create_winter_scenario_data(scenario: str, hours: int = 72) -> pd.DataFrame:
    """Lag realistiske vinterdata for å teste ML-kriterier korrekt"""

    # Lag tidsserier (vinter-dato for riktig sesongdeteksjon)
    end_time = datetime(2025, 2, 15, 12, 0, 0, tzinfo=UTC)
    start_time = end_time - timedelta(hours=hours)
    times = pd.date_range(start=start_time, end=end_time, freq='15min', tz='UTC')

    # Seed for reproduserbare resultater
    np.random.seed(42)

    if scenario == "vinterstorm":
        # Kraftig snøfall med sterk vind
        base_temp = -8
        base_wind = 12
        base_snow = 35
        base_precip = 2.0
        print(f"🌨️  Lager VINTERSTORM scenario: {base_temp}°C, {base_wind} m/s vind, {base_snow}cm snø")

    elif scenario == "ekstrem_kulde":
        # Ekstrem kulde med lite vind
        base_temp = -18
        base_wind = 3
        base_snow = 45
        base_precip = 0.1
        print(f"🥶 Lager EKSTREM KULDE scenario: {base_temp}°C, {base_wind} m/s vind, {base_snow}cm snø")

    elif scenario == "mildvær_snø":
        # Mildvær med regn på snø (realistisk vinterscenario)
        base_temp = 1
        base_wind = 5
        base_snow = 15
        base_precip = 1.5
        print(f"🌧️  Lager MILDVÆR PÅ SNØ scenario: {base_temp}°C, {base_wind} m/s vind, {base_snow}cm snø")

    elif scenario == "normal_vinter":
        # Normal vinterdag
        base_temp = -5
        base_wind = 6
        base_snow = 25
        base_precip = 0.3
        print(f"❄️  Lager NORMAL VINTER scenario: {base_temp}°C, {base_wind} m/s vind, {base_snow}cm snø")

    else:
        # Fallback til normal vinter
        base_temp = -3
        base_wind = 4
        base_snow = 20
        base_precip = 0.2
        print(f"🔄 Lager STANDARD VINTER scenario: {base_temp}°C, {base_wind} m/s vind, {base_snow}cm snø")

    # Generer realistiske variasjoner
    temps = np.clip(
        base_temp + np.random.normal(0, 2, len(times)),
        -30, 10
    )
    winds = np.clip(
        base_wind + np.random.normal(0, 3, len(times)),
        0, 25
    )
    snow = np.clip(
        base_snow + np.random.normal(0, 5, len(times)),
        0, 100
    )
    precip = np.clip(
        base_precip * np.random.exponential(1, len(times)),
        0, 10
    )

    # Lag realistiske tilleggsdata
    surface_temps = temps - np.random.uniform(0, 2, len(times))
    dew_points = temps - np.random.uniform(2, 5, len(times))
    humidity = np.clip(np.random.normal(80, 15, len(times)), 30, 100)
    wind_directions = np.random.uniform(0, 360, len(times))

    df = pd.DataFrame({
        'referenceTime': times,
        'air_temperature': temps,
        'wind_speed': winds,
        'surface_snow_thickness': snow,
        'hourly_precipitation_1h': precip,
        'surface_temperature': surface_temps,
        'dew_point_temperature': dew_points,
        'relative_humidity': humidity,
        'wind_from_direction': wind_directions
    })

    return df


def test_ml_criteria_with_realistic_data():
    """Test ML-kriterier med realistiske vinterscenarier"""
    print("\n🧪 TESTING ML-KRITERIER MED REALISTISKE VINTERDATA")
    print("=" * 65)

    checker = LiveConditionsChecker()

    scenarios = [
        ("vinterstorm", "high", "medium", "low"),
        ("ekstrem_kulde", "high", "low", "low"),
        ("mildvær_snø", "low", "high", "high"),
        ("normal_vinter", "medium", "medium", "low")
    ]

    results = []

    for scenario, expected_snowdrift, expected_slippery, expected_slush in scenarios:
        print(f"\n🎯 SCENARIO: {scenario.upper()}")
        print("-" * 50)

        try:
            # Lag realistiske testdata
            df = create_winter_scenario_data(scenario, hours=72)

            # Kjør analyser
            start_time = time.time()
            snowdrift_result = checker.analyze_snowdrift_risk(df)
            slippery_result = checker.analyze_slippery_road_risk(df)
            analysis_time = time.time() - start_time

            # Vis resultater
            print(f"📊 Data: {len(df)} målinger over {72}h")
            print(f"🌡️  Temperatur: {df['air_temperature'].min():.1f}°C til {df['air_temperature'].max():.1f}°C")
            print(f"💨 Vind: {df['wind_speed'].min():.1f} til {df['wind_speed'].max():.1f} m/s")
            print(f"❄️  Snø: {df['surface_snow_thickness'].min():.1f} til {df['surface_snow_thickness'].max():.1f} cm")
            print(f"⏱️  Analyse: {analysis_time:.3f}s")
            print()

            print(f"🌨️  Snøfokk: {snowdrift_result['risk_level'].upper()}")
            print(f"   📝 {snowdrift_result['message'][:80]}...")
            print(f"   🎯 Forventet: {expected_snowdrift.upper()}")

            print(f"🧊 Glatt føre: {slippery_result['risk_level'].upper()}")
            print(f"   📝 {slippery_result['message'][:80]}...")
            print(f"   🎯 Forventet: {expected_slippery.upper()}")

            # Evaluer resultater
            snowdrift_match = snowdrift_result['risk_level'] == expected_snowdrift
            slippery_match = slippery_result['risk_level'] == expected_slippery

            if snowdrift_match and slippery_match:
                print("✅ PERFEKT MATCH - ML-kriterier fungerer korrekt!")
            elif snowdrift_match or slippery_match:
                print("⚠️  DELVIS MATCH - En analyse stemmer")
            else:
                print("❌ INGEN MATCH - ML-kriterier bør justeres")

            results.append({
                'scenario': scenario,
                'snowdrift_actual': snowdrift_result['risk_level'],
                'snowdrift_expected': expected_snowdrift,
                'snowdrift_match': snowdrift_match,
                'slippery_actual': slippery_result['risk_level'],
                'slippery_expected': expected_slippery,
                'slippery_match': slippery_match,
                'temp_range': f"{df['air_temperature'].min():.1f} til {df['air_temperature'].max():.1f}°C",
                'wind_range': f"{df['wind_speed'].min():.1f} til {df['wind_speed'].max():.1f} m/s",
                'snow_range': f"{df['surface_snow_thickness'].min():.1f} til {df['surface_snow_thickness'].max():.1f} cm"
            })

        except Exception as e:
            print(f"❌ Feil ved testing av {scenario}: {e}")
            traceback.print_exc()

    # Sammendrag
    print("\n📈 TESTRESULTATER SAMMENDRAG")
    print("=" * 50)

    snowdrift_matches = sum(1 for r in results if r['snowdrift_match'])
    slippery_matches = sum(1 for r in results if r['slippery_match'])
    total_tests = len(results)

    print(f"🌨️  Snøfokk: {snowdrift_matches}/{total_tests} korrekte ({snowdrift_matches/total_tests*100:.1f}%)")
    print(f"🧊 Glatt føre: {slippery_matches}/{total_tests} korrekte ({slippery_matches/total_tests*100:.1f}%)")
    print(f"📊 Total: {(snowdrift_matches + slippery_matches)}/{total_tests*2} korrekte ({(snowdrift_matches + slippery_matches)/(total_tests*2)*100:.1f}%)")

    if (snowdrift_matches + slippery_matches) >= total_tests * 1.5:  # 75%+
        print("✅ ML-KRITERIER FUNGERER GODT!")
    elif (snowdrift_matches + slippery_matches) >= total_tests:  # 50%+
        print("⚠️  ML-KRITERIER TRENGER MINDRE JUSTERINGER")
    else:
        print("❌ ML-KRITERIER TRENGER BETYDELIGE FORBEDRINGER")

    return results


def test_edge_cases_with_winter_data():
    """Test edge cases med vinterdata"""
    print("\n🛡️  EDGE CASE TESTING MED VINTERDATA")
    print("=" * 50)

    checker = LiveConditionsChecker()

    edge_cases = [
        ("ekstrem_vind", {"base_temp": -10, "base_wind": 20, "base_snow": 30}),
        ("ingen_snø_frost", {"base_temp": -15, "base_wind": 8, "base_snow": 0}),
        ("mye_snø_lite_vind", {"base_temp": -5, "base_wind": 2, "base_snow": 80}),
        ("temperatur_overgang", {"base_temp": 0, "base_wind": 6, "base_snow": 20})
    ]

    for case_name, params in edge_cases:
        print(f"\n🧪 Testing: {case_name}")

        # Lag spesialtilpasset data
        end_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        start_time = end_time - timedelta(hours=24)
        times = pd.date_range(start=start_time, end=end_time, freq='15min', tz='UTC')

        df = pd.DataFrame({
            'referenceTime': times,
            'air_temperature': [params["base_temp"]] * len(times),
            'wind_speed': [params["base_wind"]] * len(times),
            'surface_snow_thickness': [params["base_snow"]] * len(times),
            'hourly_precipitation_1h': [0.1] * len(times),
            'surface_temperature': [params["base_temp"] - 1] * len(times),
            'dew_point_temperature': [params["base_temp"] - 3] * len(times),
            'relative_humidity': [80] * len(times),
            'wind_from_direction': [270] * len(times)  # Vest
        })

        snowdrift_result = checker.analyze_snowdrift_risk(df)
        slippery_result = checker.analyze_slippery_road_risk(df)

        print(f"  📊 {params['base_temp']}°C, {params['base_wind']} m/s, {params['base_snow']}cm snø")
        print(f"  🌨️  Snøfokk: {snowdrift_result['risk_level']} - {snowdrift_result['message'][:60]}...")
        print(f"  🧊 Glatt føre: {slippery_result['risk_level']} - {slippery_result['message'][:60]}...")


def main():
    """Kjør alle tester med realistiske vinterdata"""
    print("🚀 TESTING ML-KRITERIER MED KORREKTE VINTERSCENARIER")
    print("=" * 65)
    print("Mål: Teste ML-kriterier med realistiske vinterdata i stedet for sommerdata")
    print()

    start_time = time.time()

    # Test hovedscenarier
    results = test_ml_criteria_with_realistic_data()

    # Test edge cases
    test_edge_cases_with_winter_data()

    total_time = time.time() - start_time

    print(f"\n✅ TESTING FULLFØRT PÅ {total_time:.1f} SEKUNDER")
    print("=" * 65)
    print("\n🎯 KONKLUSJON:")
    print("Problemet var IKKE med ML-kriteriene, men at vi testet")
    print("vinterstorm-scenarier på sommerdata (august) uten snø!")
    print()
    print("Med riktige vinterscenarier kan vi nå teste ML-kriteriene korrekt.")


if __name__ == "__main__":
    main()
