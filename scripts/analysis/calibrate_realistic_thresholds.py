#!/usr/bin/env python3
"""
Kalibrerer ML-grenseverdier til realistiske nivåer basert på faktiske snøfokk-hendelser.
Justerer fra 91% til ~2-3% (4-5 dager av 180 vinterdager).
"""

import json
from datetime import datetime

import pandas as pd


def calibrate_realistic_thresholds():
    """Kalibrerer grenseverdier til realistiske nivåer."""

    print("🎯 KALIBRERING TIL REALISTISKE GRENSEVERDIER")
    print("=" * 60)

    # Last værdata
    cache_file = "data/cache/weather_data_2023-11-01_2024-04-30.pkl"
    df = pd.read_pickle(cache_file)

    print(f"📊 Analyserer {len(df)} observasjoner")
    print("🎯 Målsetting: 4-5 dager med varsling (2-3% av perioden)")

    # Beregn vindkjøling
    def calculate_wind_chill(temp, wind):
        if temp <= 10 and wind >= 1.34:
            return (13.12 + 0.6215 * temp -
                   11.37 * (wind * 3.6) ** 0.16 +
                   0.3965 * temp * (wind * 3.6) ** 0.16)
        return temp

    df['wind_chill'] = df.apply(lambda row: calculate_wind_chill(
        row['air_temperature'], row['wind_speed']
    ), axis=1)

    # Test forskjellige terskelverdier
    print("\n🔬 TESTING FORSKJELLIGE GRENSEVERDIER:")
    print("-" * 50)

    # Test vindkjøling-terskler
    wind_chill_thresholds = [-20, -15, -12, -10, -8, -6, -4]
    for threshold in wind_chill_thresholds:
        alerts = len(df[df['wind_chill'] < threshold])
        days = len(df[df['wind_chill'] < threshold].groupby(pd.to_datetime(df['referenceTime']).dt.date))
        print(f"Vindkjøling < {threshold}°C: {alerts} obs, {days} dager ({days/180*100:.1f}%)")

    print("\n" + "-" * 50)

    # Test vindstyrke-terskler
    wind_speed_thresholds = [12, 10, 8, 6, 5, 4]
    for threshold in wind_speed_thresholds:
        alerts = len(df[df['wind_speed'] > threshold])
        days = len(df[df['wind_speed'] > threshold].groupby(pd.to_datetime(df['referenceTime']).dt.date))
        print(f"Vindstyrke > {threshold} m/s: {alerts} obs, {days} dager ({days/180*100:.1f}%)")

    print("\n" + "-" * 50)

    # Test kombinerte kriterier
    combo_tests = [
        {'wind_chill': -15, 'wind_speed': 8, 'name': 'Strenge kriterier'},
        {'wind_chill': -12, 'wind_speed': 6, 'name': 'Moderate kriterier'},
        {'wind_chill': -10, 'wind_speed': 5, 'name': 'Milde kriterier'},
    ]

    print("KOMBINERTE KRITERIER:")
    for test in combo_tests:
        condition = (df['wind_chill'] < test['wind_chill']) & (df['wind_speed'] > test['wind_speed'])
        alerts = len(df[condition])
        days = len(df[condition].groupby(pd.to_datetime(df['referenceTime']).dt.date))
        print(f"{test['name']}: {alerts} obs, {days} dager ({days/180*100:.1f}%)")

    # Identifiser mest ekstreme dager (top 1% = ~5 dager)
    print("\n🔥 IDENTIFISERING AV MEST EKSTREME DAGER:")
    print("-" * 40)

    # Kombiner vindkjøling og vindstyrke for en "ekstrem-score"
    df['extreme_score'] = (
        (df['wind_chill'] * -1) +  # Jo lavere vindkjøling, jo høyere score
        (df['wind_speed'] * 2)     # Vektlegg vindstyrke
    )

    # Finn dager med høyest ekstrem-score
    df['date'] = pd.to_datetime(df['referenceTime']).dt.date
    daily_max_scores = df.groupby('date')['extreme_score'].max().sort_values(ascending=False)

    print("TOP 10 MEST EKSTREME DAGER (etter kombinert score):")
    for i, (date, score) in enumerate(daily_max_scores.head(10).items(), 1):
        day_data = df[df['date'] == date]
        max_row = day_data.loc[day_data['extreme_score'].idxmax()]

        print(f"{i:2d}. {date}: Score {score:.1f} | "
              f"Vindkjøling {max_row['wind_chill']:.1f}°C, "
              f"Vind {max_row['wind_speed']:.1f}m/s, "
              f"Temp {max_row['air_temperature']:.1f}°C")

    # Foreslå kalibrerte grenseverdier
    print("\n🎯 FORESLÅTTE KALIBRERTE GRENSEVERDIER:")
    print("-" * 45)

    # Basert på top 5 dager (2.8% av perioden)
    top_5_threshold_score = daily_max_scores.iloc[4]  # 5. høyeste score

    # Analyser hva som gir omtrent 5 dager med varsling
    optimal_wind_chill = -12  # Gir ca 4-6 dager
    optimal_wind_speed = 8    # Gir ca 5-7 dager
    optimal_combo_days = len(df[(df['wind_chill'] < optimal_wind_chill) &
                               (df['wind_speed'] > optimal_wind_speed)].groupby('date'))

    print(f"🎯 VINDKJØLING: < {optimal_wind_chill}°C")
    print(f"💨 VINDSTYRKE: > {optimal_wind_speed} m/s")
    print(f"🔗 KOMBINERT: {optimal_combo_days} dager med varsling")
    print(f"📊 PROSENTANDEL: {optimal_combo_days/180*100:.1f}% av vinteren")

    # Alternative terskelverdier
    alternatives = [
        {'wind_chill': -15, 'wind_speed': 10, 'name': 'Ultrastrenge'},
        {'wind_chill': -12, 'wind_speed': 8, 'name': 'Strenge (anbefalt)'},
        {'wind_chill': -10, 'wind_speed': 6, 'name': 'Moderate'},
    ]

    print("\n📊 ALTERNATIVE INNSTILLINGER:")
    for alt in alternatives:
        condition = (df['wind_chill'] < alt['wind_chill']) & (df['wind_speed'] > alt['wind_speed'])
        days = len(df[condition].groupby('date'))
        print(f"{alt['name']:15}: {days:2d} dager ({days/180*100:.1f}%)")

    # Lagre kalibrerte grenseverdier
    calibrated_thresholds = {
        'calibration_date': datetime.now().isoformat(),
        'target_days_per_season': '4-5 dager',
        'target_percentage': '2-3%',
        'recommended_thresholds': {
            'wind_chill_critical': -12.0,  # Fra 3.9 til -12
            'wind_speed_critical': 8.0,    # Fra 2.0 til 8.0
            'air_temperature_critical': -8.0,  # Fra -4.1 til -8.0
            'combined_required': True,      # Krev begge kriterier
            'surface_snow_threshold': 0.1   # 10cm minimum snø
        },
        'alternative_thresholds': {
            'ultrastrenge': {'wind_chill': -15, 'wind_speed': 10},
            'strenge': {'wind_chill': -12, 'wind_speed': 8},
            'moderate': {'wind_chill': -10, 'wind_speed': 6}
        },
        'validation': {
            'original_ml_days': 182,
            'calibrated_days': optimal_combo_days,
            'reduction_factor': 182 / optimal_combo_days if optimal_combo_days > 0 else 'N/A'
        }
    }

    # Lagre resultater
    output_file = "data/analyzed/calibrated_thresholds.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(calibrated_thresholds, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Kalibrerte grenseverdier lagret i: {output_file}")

    # Test med kalibrerte verdier
    print("\n✅ VALIDERING MED KALIBRERTE VERDIER:")
    final_condition = (df['wind_chill'] < -12) & (df['wind_speed'] > 8) & (df['surface_snow_thickness'] > 0.1)
    final_days = df[final_condition].groupby('date')

    print(f"📅 DAGER MED VARSLING ({len(final_days)} dager):")
    for date, group in final_days:
        max_event = group.loc[group['extreme_score'].idxmax()]
        print(f"• {date}: Vindkjøling {max_event['wind_chill']:.1f}°C, "
              f"Vind {max_event['wind_speed']:.1f}m/s, "
              f"Snø {max_event['surface_snow_thickness']*100:.0f}cm")

if __name__ == "__main__":
    calibrate_realistic_thresholds()
