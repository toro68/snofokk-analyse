#!/usr/bin/env python3
"""
Test de ML-optimaliserte grenseverdiene
"""

import sys

sys.path.append('src')


import pandas as pd

from ml_snowdrift_detector import MLSnowdriftDetector


def test_ml_optimized_thresholds():
    print("=== TEST AV ML-OPTIMALISERTE GRENSEVERDIER ===")

    # Last data
    df = pd.read_csv('data/raw/historical_data.csv')
    print(f"Data lastet: {len(df)} rader")

    # Filter for 2023-2024 sesongen
    df_season = df[
        ((df['timestamp'] >= '2023-11-01') & (df['timestamp'] <= '2024-04-30'))
    ].copy()
    print(f"2023-2024 sesong: {len(df_season)} rader")

    # Opprett ML-detektor
    detector = MLSnowdriftDetector()

    print("\n📊 ML-OPTIMALISERTE GRENSEVERDIER:")
    print(f"- Vindkjøling: < {detector.critical_thresholds['wind_chill']}°C")
    print(f"- Vindstyrke: > {detector.critical_thresholds['wind_speed']} m/s")
    print(f"- Temperatur: < {detector.critical_thresholds['air_temperature']}°C")
    print(f"- Snødybde: > {detector.critical_thresholds['surface_snow_thickness']:.2f}m ({detector.critical_thresholds['surface_snow_thickness']*100:.0f}cm)")

    # Test på noen utvalgte dager
    print("\n⚡ TESTING ML-DETEKTOR:")

    # Finn dager med potensial for snøfokk (kalde dager med vind og snø)
    test_conditions = df_season[
        (df_season['air_temperature'] < -3) &
        (df_season['wind_speed'] > 3) &
        (df_season['surface_snow_thickness'] > 0.1)
    ]

    print(f"Dager med potensial for snøfokk: {len(test_conditions)}")

    # Test ML-detektoren på noen eksempler
    high_risk_days = 0
    medium_risk_days = 0

    # Test på utvalgte dager
    dates_tested = []
    for i in range(0, min(len(test_conditions), 20), 5):  # Test hvert 5. element
        row = test_conditions.iloc[i:i+1]
        if len(row) > 0:
            result = detector.analyze_snowdrift_risk_ml(row)
            date_str = row['timestamp'].iloc[0][:10]  # YYYY-MM-DD
            dates_tested.append(date_str)

            temp = row['air_temperature'].iloc[0]
            wind = row['wind_speed'].iloc[0]
            snow = row['surface_snow_thickness'].iloc[0] * 100
            wind_chill = detector.calculate_wind_chill(temp, wind)

            if result['risk_level'] == 'high':
                high_risk_days += 1
                print(f"🔴 {date_str}: HØY RISIKO - Temp {temp:.1f}°C, Vind {wind:.1f}m/s, Snø {snow:.0f}cm, Vindkjøling {wind_chill:.1f}°C")
            elif result['risk_level'] == 'medium':
                medium_risk_days += 1
                print(f"🟡 {date_str}: MEDIUM RISIKO - Temp {temp:.1f}°C, Vind {wind:.1f}m/s, Snø {snow:.0f}cm, Vindkjøling {wind_chill:.1f}°C")

    print("\n✅ RESULTAT FRA TESTING:")
    print(f"Høy risiko dager: {high_risk_days}/{len(dates_tested)}")
    print(f"Medium risiko dager: {medium_risk_days}/{len(dates_tested)}")
    print(f"Totalt testede dager: {len(dates_tested)}")

    # Beregn hvor mange dager som ville oppfylt kritisk kombinasjon
    critical_combo_days = df_season[
        (df_season['air_temperature'] < detector.critical_thresholds['air_temperature']) &
        (df_season['wind_speed'] > detector.critical_thresholds['wind_speed']) &
        (df_season['surface_snow_thickness'] > detector.critical_thresholds['surface_snow_thickness'])
    ]

    # Beregn vindkjøling for disse dagene
    critical_days_with_windchill = []
    for _, row in critical_combo_days.iterrows():
        wind_chill = detector.calculate_wind_chill(row['air_temperature'], row['wind_speed'])
        if wind_chill < detector.critical_thresholds['wind_chill']:
            critical_days_with_windchill.append({
                'date': row['timestamp'][:10],
                'wind_chill': wind_chill,
                'temp': row['air_temperature'],
                'wind': row['wind_speed'],
                'snow': row['surface_snow_thickness'] * 100
            })

    print("\n🎯 KRITISK KOMBINASJON ANALYSE:")
    print(f"Dager som oppfyller ALLE ML-optimaliserte kriterier: {len(critical_days_with_windchill)}")

    for day in critical_days_with_windchill[:10]:  # Vis første 10
        print(f"📅 {day['date']}: Vindkjøling {day['wind_chill']:.1f}°C, Temp {day['temp']:.1f}°C, Vind {day['wind']:.1f}m/s, Snø {day['snow']:.0f}cm")

    return {
        'total_critical_days': len(critical_days_with_windchill),
        'high_risk_tested': high_risk_days,
        'medium_risk_tested': medium_risk_days,
        'days_tested': len(dates_tested)
    }

if __name__ == "__main__":
    test_ml_optimized_thresholds()
