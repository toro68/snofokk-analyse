#!/usr/bin/env python3
"""
Diagnostisk analyse av snøfokk-data for å forstå hvorfor vi ikke finner perioder
"""

import os
import pickle

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

def load_cached_data():
    """Last inn cached data for analyse."""
    cache_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/cache/weather_data_2023-11-01_2024-04-30.pkl'

    if os.path.exists(cache_file):
        with open(cache_file, 'rb') as f:
            return pickle.load(f)
    return pd.DataFrame()

def diagnose_data():
    """Diagnostiser datainnholdet."""
    print("🔍 DIAGNOSTISK ANALYSE AV VÆRDATA")
    print("=" * 40)

    df = load_cached_data()
    if df.empty:
        print("❌ Ingen cached data funnet")
        return

    print(f"📊 Total datapunkter: {len(df)}")
    print(f"📅 Periode: {df['referenceTime'].min()} til {df['referenceTime'].max()}")
    print(f"📋 Kolonner: {list(df.columns)}")

    # Sjekk for NaN-verdier
    print("\n🔍 NaN-ANALYSE:")
    for col in df.columns:
        if col != 'referenceTime':
            nan_count = df[col].isna().sum()
            total = len(df)
            percentage = (nan_count / total) * 100
            print(f"  {col}: {nan_count}/{total} NaN ({percentage:.1f}%)")

    # Analyser nøkkelparametre
    print("\n📊 PARAMETER STATISTIKK:")

    key_params = ['wind_speed', 'air_temperature', 'surface_snow_thickness', 'wind_from_direction']

    for param in key_params:
        if param in df.columns:
            data = df[param].dropna()
            if len(data) > 0:
                print(f"\n{param}:")
                print(f"  Min: {data.min():.2f}")
                print(f"  Max: {data.max():.2f}")
                print(f"  Gjennomsnitt: {data.mean():.2f}")
                print(f"  Gyldige verdier: {len(data)}/{len(df)}")

    # Sjekk snøfokk-kriterier med ulike terskler
    print("\n🌪️ SNØFOKK-KRITERIER TESTING:")

    test_criteria = [
        (4.0, 0.0, 1.0),    # Milde kriterier
        (5.0, -0.5, 2.0),   # Lett strengere
        (6.0, -1.0, 3.0),   # Standard
        (7.0, -1.5, 4.0),   # Strenge
        (8.0, -2.0, 5.0)    # Meget strenge
    ]

    for wind_thresh, temp_thresh, snow_thresh in test_criteria:
        # Tell timer som oppfyller kriteriene
        wind_ok = df['wind_speed'] >= wind_thresh
        temp_ok = df['air_temperature'] <= temp_thresh
        snow_ok = df['surface_snow_thickness'] >= snow_thresh

        # Kombiner alle kriterier
        all_criteria = wind_ok & temp_ok & snow_ok

        valid_count = all_criteria.sum()
        print(f"  Vind≥{wind_thresh}, Temp≤{temp_thresh}, Snø≥{snow_thresh}: {valid_count} timer")

        if valid_count > 0:
            # Analyser februar spesielt
            df_feb = df[(df['referenceTime'].dt.month == 2) & (df['referenceTime'].dt.year == 2024)]
            if not df_feb.empty:
                feb_criteria = (df_feb['wind_speed'] >= wind_thresh) & \
                              (df_feb['air_temperature'] <= temp_thresh) & \
                              (df_feb['surface_snow_thickness'] >= snow_thresh)
                feb_count = feb_criteria.sum()
                print(f"    - Februar 2024: {feb_count} timer")

                # Sjekk 8-11 februar spesifikt
                df_crisis = df_feb[(df_feb['referenceTime'].dt.day >= 8) &
                                  (df_feb['referenceTime'].dt.day <= 11)]
                if not df_crisis.empty:
                    crisis_criteria = (df_crisis['wind_speed'] >= wind_thresh) & \
                                    (df_crisis['air_temperature'] <= temp_thresh) & \
                                    (df_crisis['surface_snow_thickness'] >= snow_thresh)
                    crisis_count = crisis_criteria.sum()
                    print(f"    - 8-11 februar: {crisis_count} timer")

    # Se på februar 8-11 spesifikt
    print("\n🚨 FEBRUAR 8-11, 2024 DETALJANALYSE:")
    df_crisis = df[(df['referenceTime'].dt.month == 2) &
                   (df['referenceTime'].dt.year == 2024) &
                   (df['referenceTime'].dt.day >= 8) &
                   (df['referenceTime'].dt.day <= 11)]

    if not df_crisis.empty:
        print(f"Datapunkter 8-11 feb: {len(df_crisis)}")

        for param in ['wind_speed', 'air_temperature', 'surface_snow_thickness', 'wind_from_direction']:
            if param in df_crisis.columns:
                data = df_crisis[param].dropna()
                if len(data) > 0:
                    print(f"{param}: Min={data.min():.1f}, Max={data.max():.1f}, Snitt={data.mean():.1f}")

        # Vis noen eksempelrader
        print("\nEksempel data 8-11 februar:")
        sample_data = df_crisis[['referenceTime', 'wind_speed', 'air_temperature',
                               'surface_snow_thickness', 'wind_from_direction']].head(10)
        for _, row in sample_data.iterrows():
            print(f"  {row['referenceTime']}: Vind={row['wind_speed']:.1f}, "
                  f"Temp={row['air_temperature']:.1f}, Snø={row['surface_snow_thickness']:.1f}")
    else:
        print("❌ Ingen data funnet for 8-11 februar 2024")

def main():
    diagnose_data()

if __name__ == "__main__":
    main()
