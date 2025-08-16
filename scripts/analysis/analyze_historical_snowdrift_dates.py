#!/usr/bin/env python3
"""
Analyser historiske data for å identifisere når ML-baserte grenseverdier
ville ha utløst snøfokk-varsling.
"""

import json
import os
import sys
from datetime import datetime

import pandas as pd

# Legg til src-mappen i path
sys.path.append('src')

try:
    from ml_snowdrift_detector import MLSnowdriftDetector
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("ML-detektor ikke tilgjengelig")

def calculate_wind_chill(temp, wind):
    """Beregn vindkjøling."""
    if temp <= 10 and wind >= 1.34:
        return (13.12 + 0.6215 * temp -
               11.37 * (wind * 3.6) ** 0.16 +
               0.3965 * temp * (wind * 3.6) ** 0.16)
    return temp

def analyze_historical_snowdrift_dates():
    """Analyser historiske data for snøfokk-datoer basert på ML-grenseverdier."""

    print("🔍 ANALYSERER HISTORISKE SNØFOKK-DATOER MED ML-GRENSEVERDIER")
    print("=" * 70)

    # Last værdata
    cache_file = "data/cache/weather_data_2023-11-01_2024-04-30.pkl"

    if not os.path.exists(cache_file):
        print(f"❌ Finner ikke værdata: {cache_file}")
        return

    df = pd.read_pickle(cache_file)
    print(f"📊 Lastet {len(df)} værobservasjoner")
    print(f"📅 Periode: {df['referenceTime'].min()} til {df['referenceTime'].max()}")

    # Kalibrerte ML-grenseverdier (justert for realistisk varsling-frekvens)
    ml_thresholds = {
        'wind_chill_critical': -12.0,  # °C (kalibrert fra 3.9°C)
        'wind_chill_warning': -10.0,   # °C
        'wind_speed_critical': 8.0,    # m/s (kalibrert fra 2.0 m/s)
        'air_temperature_critical': -8.0,  # °C (kalibrert fra -4.1°C)
        'surface_snow_thickness_critical': 0.1  # 10cm (kalibrert fra 6.3cm)
    }

    # Beregn vindkjøling
    df['wind_chill'] = df.apply(lambda row: calculate_wind_chill(
        row['air_temperature'], row['wind_speed']
    ), axis=1)

    # Beregn snødybde-endringer
    df = df.sort_values('referenceTime')
    df['snow_change_1h'] = df['surface_snow_thickness'].diff()
    df['snow_change_abs'] = abs(df['snow_change_1h'])

    # Identifiser snøfokk-hendelser basert på kalibrerte ML-kriterier
    print("\n🎯 ANVENDTE KALIBRERTE ML-GRENSEVERDIER:")
    print(f"• Kritisk vindkjøling: < {ml_thresholds['wind_chill_critical']}°C")
    print(f"• Kritisk vindstyrke: > {ml_thresholds['wind_speed_critical']} m/s")
    print(f"• Kritisk temperatur: < {ml_thresholds['air_temperature_critical']}°C")
    print(f"• Minimum snødybde: > {ml_thresholds['surface_snow_thickness_critical']*100:.0f}cm")

    # Filtrer på kalibrerte hovedkriterier - BEGGE kriterier må oppfylles
    critical_wind_chill = df['wind_chill'] < ml_thresholds['wind_chill_critical']
    critical_wind_speed = df['wind_speed'] > ml_thresholds['wind_speed_critical']
    sufficient_snow = df['surface_snow_thickness'] > ml_thresholds['surface_snow_thickness_critical']

    # Høy risiko kun når ALLE kriterier oppfylles (kalibrert kombinasjon)
    high_risk = critical_wind_chill & critical_wind_speed & sufficient_snow

    # Filtrer på hovedkriterier
    critical_wind_chill = df['wind_chill'] < ml_thresholds['wind_chill_critical']
    critical_wind_speed = df['wind_speed'] > ml_thresholds['wind_speed_critical']
    critical_temperature = df['air_temperature'] < ml_thresholds['air_temperature_critical']
    significant_snow = df['surface_snow_thickness'] > ml_thresholds['surface_snow_thickness_critical']

    # Kombinasjonsregler (ML-identifisert)
    high_risk_combo = (
        (df['wind_speed'] > 8.3) &
        (df['air_temperature'] < -1.6) &
        (df['surface_snow_thickness'] > 0.0295)
    )

    medium_risk_combo = (
        (df['wind_speed'] >= 2.1) &
        (df['wind_speed'] <= 6.7) &
        (df['air_temperature'] < -5.3)
    )

    # Snødybde-endringer (ny indikator)
    significant_snow_change = df['snow_change_abs'] > 0.015  # 15mm

    # Kombinerte kriterier for forskjellige risikonivåer
    high_risk_events = (
        critical_wind_chill |
        high_risk_combo |
        (critical_wind_speed & critical_temperature & significant_snow) |
        significant_snow_change
    )

    medium_risk_events = (
        (df['wind_chill'] < ml_thresholds['wind_chill_warning']) |
        medium_risk_combo |
        (critical_wind_speed & (critical_temperature | significant_snow))
    ) & ~high_risk_events

    # Analyser resultater
    high_risk_df = df[high_risk_events].copy()
    medium_risk_df = df[medium_risk_events].copy()

    print("\n📊 RESULTATER:")
    print(f"🔴 Høy risiko hendelser: {len(high_risk_df)}")
    print(f"🟡 Medium risiko hendelser: {len(medium_risk_df)}")
    print(f"🟢 Lav risiko: {len(df) - len(high_risk_df) - len(medium_risk_df)}")

    # Grupér per dag for oversikt
    if len(high_risk_df) > 0:
        high_risk_df['date'] = pd.to_datetime(high_risk_df['referenceTime']).dt.date
        high_risk_days = high_risk_df.groupby('date').agg({
            'wind_chill': 'min',
            'wind_speed': 'max',
            'air_temperature': 'min',
            'surface_snow_thickness': 'max',
            'snow_change_abs': 'max',
            'referenceTime': 'count'
        }).rename(columns={'referenceTime': 'observations'})

        print(f"\n🔴 HØY RISIKO DAGER ({len(high_risk_days)} dager):")
        print("-" * 80)

        for date, row in high_risk_days.head(20).iterrows():  # Vis første 20
            print(f"📅 {date}: "
                  f"Vindkjøling {row['wind_chill']:.1f}°C, "
                  f"Vind {row['wind_speed']:.1f}m/s, "
                  f"Temp {row['air_temperature']:.1f}°C, "
                  f"Snø {row['surface_snow_thickness']*100:.1f}cm "
                  f"({row['observations']} obs)")

    if len(medium_risk_df) > 0:
        medium_risk_df['date'] = pd.to_datetime(medium_risk_df['referenceTime']).dt.date
        medium_risk_days = medium_risk_df.groupby('date').agg({
            'wind_chill': 'min',
            'wind_speed': 'max',
            'air_temperature': 'min',
            'surface_snow_thickness': 'max',
            'referenceTime': 'count'
        }).rename(columns={'referenceTime': 'observations'})

        print(f"\n🟡 MEDIUM RISIKO DAGER ({len(medium_risk_days)} dager):")
        print("-" * 80)

        for date, row in medium_risk_days.head(15).iterrows():  # Vis første 15
            print(f"📅 {date}: "
                  f"Vindkjøling {row['wind_chill']:.1f}°C, "
                  f"Vind {row['wind_speed']:.1f}m/s, "
                  f"Temp {row['air_temperature']:.1f}°C, "
                  f"Snø {row['surface_snow_thickness']*100:.1f}cm "
                  f"({row['observations']} obs)")

    # Detaljert analyse av top hendelser
    if len(high_risk_df) > 0:
        print("\n🎯 TOP 10 MEST KRITISKE HENDELSER:")
        print("-" * 60)

        # Sorter etter vindkjøling (viktigste parameter)
        top_events = high_risk_df.nsmallest(10, 'wind_chill')

        for _, event in top_events.iterrows():
            timestamp = event['referenceTime']
            print(f"⚠️ {timestamp}: "
                  f"Vindkjøling {event['wind_chill']:.1f}°C, "
                  f"Vind {event['wind_speed']:.1f}m/s, "
                  f"Temp {event['air_temperature']:.1f}°C")

    # Månedlig fordeling
    if len(high_risk_df) > 0 or len(medium_risk_df) > 0:
        all_risk_df = pd.concat([high_risk_df, medium_risk_df])
        all_risk_df['month'] = pd.to_datetime(all_risk_df['referenceTime']).dt.month
        monthly_counts = all_risk_df['month'].value_counts().sort_index()

        month_names = {11: 'Nov', 12: 'Des', 1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr'}

        print("\n📈 MÅNEDLIG FORDELING AV SNØFOKK-RISIKO:")
        print("-" * 40)
        for month, count in monthly_counts.items():
            month_name = month_names.get(month, f'Måned {month}')
            print(f"{month_name}: {count} hendelser")

    # Lagre detaljerte resultater
    results = {
        'analysis_date': datetime.now().isoformat(),
        'period': f"{df['referenceTime'].min()} - {df['referenceTime'].max()}",
        'total_observations': len(df),
        'ml_thresholds_used': ml_thresholds,
        'summary': {
            'high_risk_observations': len(high_risk_df),
            'medium_risk_observations': len(medium_risk_df),
            'low_risk_observations': len(df) - len(high_risk_df) - len(medium_risk_df),
            'high_risk_days': len(high_risk_days) if len(high_risk_df) > 0 else 0,
            'medium_risk_days': len(medium_risk_days) if len(medium_risk_df) > 0 else 0
        }
    }

    # Legg til top dager hvis tilgjengelig
    if len(high_risk_df) > 0:
        results['top_high_risk_days'] = {str(k): v for k, v in high_risk_days.head(10).to_dict('index').items()}

    if len(medium_risk_df) > 0:
        results['top_medium_risk_days'] = {str(k): v for k, v in medium_risk_days.head(10).to_dict('index').items()}

    # Lagre resultater
    output_file = "data/analyzed/historical_snowdrift_dates_ml.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n💾 Detaljerte resultater lagret i: {output_file}")

if __name__ == "__main__":
    analyze_historical_snowdrift_dates()
