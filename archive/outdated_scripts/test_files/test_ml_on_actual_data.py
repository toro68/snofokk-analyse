#!/usr/bin/env python3
"""
Test ML-detektoren på 2023-2024 data for å se hvilke datoer som blir identifisert
"""

import sys

import pandas as pd

sys.path.append('src')
from datetime import datetime

from ml_snowdrift_detector import MLSnowdriftDetector


def test_ml_on_actual_data():
    print("=== TEST ML-DETEKTOR PÅ 2023-2024 DATA ===")

    # Last data
    df = pd.read_csv('data/raw/historical_data.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Filtrer til 2023-2024 sesong
    season_data = df[(df['timestamp'] >= '2023-11-01') & (df['timestamp'] <= '2024-04-30')].copy()
    print(f"Data for 2023-2024 sesong: {len(season_data)} observasjoner")

    # Initialiser ML-detektor
    detector = MLSnowdriftDetector()

    # Konverter kolonnavn for kompatibilitet
    season_data = season_data.rename(columns={
        'timestamp': 'referenceTime'
    })

    # Test på hele datasettet
    print("\n=== TESTING ML-GRENSEVERDIER ===")
    print("Kritiske terskler:")
    print(f"- Vindkjøling: < {detector.critical_thresholds['wind_chill']}°C")
    print(f"- Vindstyrke: > {detector.critical_thresholds['wind_speed']} m/s")
    print(f"- Lufttemperatur: < {detector.critical_thresholds['air_temperature']}°C")
    print(f"- Snødybde: > {detector.critical_thresholds['surface_snow_thickness']*100} cm")

    # Finn dager med høy snøfokk-risiko
    high_risk_days = []

    # Test dag for dag
    season_data['date'] = season_data['referenceTime'].dt.date
    unique_dates = season_data['date'].unique()

    for date in unique_dates:
        day_data = season_data[season_data['date'] == date]

        if len(day_data) == 0:
            continue

        try:
            result = detector.analyze_snowdrift_risk_ml(day_data)

            if result.get('risk_level') == 'high':
                # Hent representativ data for dagen
                latest = day_data.iloc[-1]
                temp = latest.get('air_temperature', 0)
                wind = latest.get('wind_speed', 0)
                snow = latest.get('surface_snow_thickness', 0)
                wind_chill = detector.calculate_wind_chill(temp, wind)

                high_risk_days.append({
                    'date': date,
                    'temp': temp,
                    'wind': wind,
                    'snow_cm': snow * 100,
                    'wind_chill': wind_chill,
                    'message': result.get('message', '')
                })

        except Exception as e:
            print(f"Feil for {date}: {e}")

    print("\n=== RESULTATER ===")
    print(f"Antall dager med HØY snøfokk-risiko: {len(high_risk_days)}")

    if high_risk_days:
        print("\nIdentifiserte høyrisiko-dager:")
        for day in sorted(high_risk_days, key=lambda x: x['date']):
            date_str = day['date'].strftime('%d.%m.%Y')
            print(f"📅 {date_str}: Vindkjøling {day['wind_chill']:.1f}°C, "
                  f"Vind {day['wind']:.1f}m/s, Temp {day['temp']:.1f}°C, "
                  f"Snø {day['snow_cm']:.0f}cm")

        # Månedlig fordeling
        monthly = {}
        for day in high_risk_days:
            month = day['date'].strftime('%Y-%m')
            monthly[month] = monthly.get(month, 0) + 1

        print("\nMånedlig fordeling:")
        for month, count in sorted(monthly.items()):
            month_name = datetime.strptime(month, '%Y-%m').strftime('%B %Y')
            print(f"- {month_name}: {count} dager")

    else:
        print("Ingen dager med høy snøfokk-risiko identifisert.")
        print("Grenseverdiene kan være for strenge.")

    return len(high_risk_days)

if __name__ == "__main__":
    result = test_ml_on_actual_data()
    print(f"\n🎯 MÅLOPPNÅELSE: {result}/8-10 dager (mål: 8-10 dager)")

    if result < 8:
        print("⚠️  FOR FÅ DAGER - grenseverdiene er for strenge")
        print("💡 Anbefaling: Senk tersklene (vindkjøling mindre negativ, lavere vindkrav)")
    elif result > 10:
        print("⚠️  FOR MANGE DAGER - grenseverdiene er for løse")
        print("💡 Anbefaling: Hev tersklene (vindkjøling mer negativ, høyere vindkrav)")
    else:
        print("✅ PERFEKT KALIBRERING - treffer målet!")
