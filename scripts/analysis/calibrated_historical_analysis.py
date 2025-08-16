#!/usr/bin/env python3
"""
Enkel analyse av historiske data med kalibrerte ML-grenseverdier.
Bruker den enkle regelen: Vindkjøling < -12°C OG vindstyrke > 8 m/s OG snø > 10cm
"""

import json
import os
from datetime import datetime

import pandas as pd


def calculate_wind_chill(temp, wind):
    """Beregn vindkjøling."""
    if temp <= 10 and wind >= 1.34:
        return (13.12 + 0.6215 * temp -
               11.37 * (wind * 3.6) ** 0.16 +
               0.3965 * temp * (wind * 3.6) ** 0.16)
    return temp

def main():
    print("🔍 KALIBRERT ML-ANALYSE AV HISTORISKE SNØFOKK-DATOER")
    print("=" * 60)

    # Last historiske data
    cache_file = 'data/cache/weather_data_2023-11-01_2024-04-30.pkl'
    if not os.path.exists(cache_file):
        print("❌ Finner ikke cache-fil. Kjør først data-innsamling.")
        return

    df = pd.read_pickle(cache_file)
    print(f"📊 Lastet {len(df)} værobservasjoner")
    print(f"📅 Periode: {df['referenceTime'].min()} til {df['referenceTime'].max()}")

    # Beregn vindkjøling
    df['wind_chill'] = df.apply(lambda row: calculate_wind_chill(
        row['air_temperature'], row['wind_speed']), axis=1)

    # Kalibrerte grenseverdier - ALLE må oppfylles
    WIND_CHILL_THRESHOLD = -12.0  # °C
    WIND_SPEED_THRESHOLD = 8.0    # m/s
    SNOW_DEPTH_THRESHOLD = 0.1    # m (10cm)

    print("\n🎯 KALIBRERTE GRENSEVERDIER:")
    print(f"• Vindkjøling: < {WIND_CHILL_THRESHOLD}°C")
    print(f"• Vindstyrke: > {WIND_SPEED_THRESHOLD} m/s")
    print(f"• Snødybde: > {SNOW_DEPTH_THRESHOLD * 100:.0f}cm")
    print("• ALLE kriterier må oppfylles samtidig")

    # Filtrer data basert på kalibrerte kriterier
    conditions = (
        (df['wind_chill'] < WIND_CHILL_THRESHOLD) &
        (df['wind_speed'] > WIND_SPEED_THRESHOLD) &
        (df['surface_snow_thickness'] > SNOW_DEPTH_THRESHOLD)
    )

    alert_observations = df[conditions].copy()

    print("\n📊 RESULTATER:")
    print(f"🔴 Observasjoner med varsling: {len(alert_observations)}")
    print(f"⚪ Totale observasjoner: {len(df)}")
    print(f"📈 Prosentandel: {len(alert_observations)/len(df)*100:.1f}%")

    if len(alert_observations) > 0:
        # Grupér per dag
        alert_observations['date'] = pd.to_datetime(alert_observations['referenceTime']).dt.date

        daily_summary = alert_observations.groupby('date').agg({
            'wind_chill': 'min',
            'wind_speed': 'max',
            'air_temperature': 'min',
            'surface_snow_thickness': 'max',
            'referenceTime': 'count'
        }).rename(columns={'referenceTime': 'observations'})

        daily_summary = daily_summary.sort_values('wind_chill')

        print(f"\n🚨 DAGER MED SNØFOKK-VARSLING ({len(daily_summary)} dager):")
        print("-" * 80)

        for date, row in daily_summary.iterrows():
            print(f"📅 {date}: Vindkjøling {row['wind_chill']:.1f}°C, "
                  f"Vind {row['wind_speed']:.1f}m/s, "
                  f"Temp {row['air_temperature']:.1f}°C, "
                  f"Snø {row['surface_snow_thickness']*100:.0f}cm "
                  f"({row['observations']} obs)")

        # Månedlig fordeling
        alert_observations['month'] = pd.to_datetime(alert_observations['referenceTime']).dt.month
        monthly_counts = alert_observations['month'].value_counts().sort_index()

        month_names = {11: 'Nov', 12: 'Des', 1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr'}

        print("\n📈 MÅNEDLIG FORDELING:")
        print("-" * 30)
        for month, count in monthly_counts.items():
            if month in month_names:
                print(f"{month_names[month]}: {count} observasjoner")

        # Top 10 mest ekstreme hendelser
        top_events = alert_observations.nsmallest(10, 'wind_chill')

        print("\n🌡️ TOP 10 MEST EKSTREME HENDELSER:")
        print("-" * 50)
        for idx, row in top_events.iterrows():
            print(f"⚠️ {row['referenceTime']}: "
                  f"Vindkjøling {row['wind_chill']:.1f}°C, "
                  f"Vind {row['wind_speed']:.1f}m/s, "
                  f"Temp {row['air_temperature']:.1f}°C")

        # Lagre resultater
        results = {
            'analysis_date': datetime.now().isoformat(),
            'criteria': {
                'wind_chill_threshold': WIND_CHILL_THRESHOLD,
                'wind_speed_threshold': WIND_SPEED_THRESHOLD,
                'snow_depth_threshold': SNOW_DEPTH_THRESHOLD
            },
            'summary': {
                'total_observations': len(df),
                'alert_observations': len(alert_observations),
                'alert_days': len(daily_summary),
                'percentage': len(alert_observations)/len(df)*100
            },
            'alert_days': [
                {
                    'date': str(date),
                    'min_wind_chill': row['wind_chill'],
                    'max_wind_speed': row['wind_speed'],
                    'min_temperature': row['air_temperature'],
                    'max_snow_depth': row['surface_snow_thickness'],
                    'observations': row['observations']
                }
                for date, row in daily_summary.iterrows()
            ]
        }

        output_file = 'data/analyzed/calibrated_historical_analysis.json'
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)

        print(f"\n💾 Resultater lagret i: {output_file}")

    else:
        print("\n❌ Ingen dager oppfyller de kalibrerte kriteriene")

if __name__ == "__main__":
    main()
