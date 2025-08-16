#!/usr/bin/env python3
"""
ML-basert optimalisering av snøfokk-grenseverdier
Bruker systematisk søk og statistisk analyse for å finne optimale terskler
"""

import json

import numpy as np
import pandas as pd


def calculate_wind_chill(temperature, wind_speed):
    """Beregn vindkjøling basert på standardformelen."""
    if temperature <= 10 and wind_speed >= 1.34:  # 4.8 km/h = 1.34 m/s
        return (13.12 + 0.6215 * temperature -
               11.37 * (wind_speed * 3.6) ** 0.16 +
               0.3965 * temperature * (wind_speed * 3.6) ** 0.16)
    return temperature

def evaluate_thresholds(df, wind_chill_thresh, wind_speed_thresh, temp_thresh, snow_thresh):
    """
    Evaluer et sett med grenseverdier og returner antall alarmdager.
    """
    # Filter for 2023-2024 sesongen
    df_season = df[
        ((df['timestamp'] >= '2023-11-01') & (df['timestamp'] <= '2024-04-30'))
    ].copy()

    # Beregn vindkjøling
    df_season['wind_chill'] = df_season.apply(
        lambda row: calculate_wind_chill(row['air_temperature'], row['wind_speed'])
        if pd.notna(row['air_temperature']) and pd.notna(row['wind_speed'])
        else np.nan, axis=1
    )

    # Konverter snødybde til meter (hvis det er i cm)
    snow_depth_m = df_season['surface_snow_thickness'] / 100 if df_season['surface_snow_thickness'].max() > 10 else df_season['surface_snow_thickness']

    # Identifiser alarmdager basert på kriterier
    alerts = df_season[
        (df_season['wind_chill'] < wind_chill_thresh) &
        (df_season['wind_speed'] > wind_speed_thresh) &
        (df_season['air_temperature'] < temp_thresh) &
        (snow_depth_m > snow_thresh)
    ].copy()

    if len(alerts) == 0:
        return 0, []

    # Grupper til dager
    alerts['date'] = pd.to_datetime(alerts['timestamp']).dt.date
    alert_days = alerts['date'].unique()

    return len(alert_days), list(alert_days)

def ml_optimize_thresholds():
    """
    Bruk ML-inspirerte metoder for å optimalisere grenseverdier.
    """
    print("=== ML-BASERT OPTIMALISERING AV GRENSEVERDIER ===")

    # Last data
    print("1. Laster historiske data...")
    df = pd.read_csv('data/raw/historical_data.csv')
    print(f"Data lastet: {len(df)} rader")

    # Definer søkeområder for hver parameter
    # Basert på domain knowledge og tidligere resultater
    print("\n2. Definerer søkeområder...")
    wind_chill_range = np.arange(-20, -8, 0.5)  # -20°C til -8°C, 0.5°C steg
    wind_speed_range = np.arange(5, 15, 0.5)    # 5-15 m/s, 0.5 m/s steg
    temp_range = np.arange(-15, -3, 0.5)        # -15°C til -3°C, 0.5°C steg
    snow_range = np.arange(0.1, 0.4, 0.02)      # 10-40cm snø, 2cm steg

    print("Søkeområder:")
    print(f"- Vindkjøling: {wind_chill_range.min():.1f} til {wind_chill_range.max():.1f}°C ({len(wind_chill_range)} verdier)")
    print(f"- Vindstyrke: {wind_speed_range.min():.1f} til {wind_speed_range.max():.1f} m/s ({len(wind_speed_range)} verdier)")
    print(f"- Temperatur: {temp_range.min():.1f} til {temp_range.max():.1f}°C ({len(temp_range)} verdier)")
    print(f"- Snødybde: {snow_range.min():.2f} til {snow_range.max():.2f}m ({len(snow_range)} verdier)")

    # Grid search med smart sampling
    print("\n3. Kjører grid search (target: 8-10 alarmdager)...")

    best_candidates = []
    total_combinations = len(wind_chill_range) * len(wind_speed_range) * len(temp_range) * len(snow_range)
    print(f"Totalt {total_combinations:,} kombinasjoner å teste")

    # Smart sampling: test hver 2. verdi først for rask screening
    sample_step = 2
    tested = 0

    for wc in wind_chill_range[::sample_step]:
        for ws in wind_speed_range[::sample_step]:
            for temp in temp_range[::sample_step]:
                for snow in snow_range[::sample_step]:
                    tested += 1

                    if tested % 1000 == 0:
                        print(f"  Testet {tested:,} kombinasjoner...")

                    num_days, alert_days = evaluate_thresholds(df, wc, ws, temp, snow)

                    # Interessert i 8-10 dager (med litt margin)
                    if 7 <= num_days <= 12:
                        best_candidates.append({
                            'wind_chill': wc,
                            'wind_speed': ws,
                            'temperature': temp,
                            'snow_depth': snow,
                            'num_days': num_days,
                            'alert_days': alert_days,
                            'distance_from_target': abs(num_days - 9)  # Target: 9 dager
                        })

    print(f"\n4. Fant {len(best_candidates)} lovende kandidater (7-12 dager)")

    # Sortér etter nærhet til målet (9 dager)
    best_candidates.sort(key=lambda x: (x['distance_from_target'], -x['num_days']))

    # Vis top 10 kandidater
    print("\n5. TOP 10 KANDIDATER:")
    print("Rank | Dager | Wind Chill | Wind Speed | Temperature | Snow Depth")
    print("-" * 70)

    for i, candidate in enumerate(best_candidates[:10]):
        print(f"{i+1:4d} | {candidate['num_days']:5d} | "
              f"{candidate['wind_chill']:10.1f} | "
              f"{candidate['wind_speed']:10.1f} | "
              f"{candidate['temperature']:11.1f} | "
              f"{candidate['snow_depth']:10.2f}")

    # Analyser beste kandidat i detalj
    if best_candidates:
        best = best_candidates[0]
        print("\n6. BESTE KANDIDAT ANALYSE:")
        print("Grenseverdier:")
        print(f"- Vindkjøling: < {best['wind_chill']}°C")
        print(f"- Vindstyrke: > {best['wind_speed']} m/s")
        print(f"- Temperatur: < {best['temperature']}°C")
        print(f"- Snødybde: > {best['snow_depth']:.2f}m ({best['snow_depth']*100:.0f}cm)")
        print(f"- Alarmdager: {best['num_days']}")

        print("\nAlarmdager i 2023-2024:")
        for day in sorted(best['alert_days']):
            print(f"  📅 {day}")

        # Test på fullt datasett for validering
        print("\n7. VALIDERING MOT FULLT DATASETT (2018-2024):")
        total_days, _ = evaluate_thresholds_full_period(df, best)
        print(f"Totalt over hele perioden: {total_days} alarmdager")
        print(f"Gjennomsnitt per sesong: {total_days / 6:.1f} dager")

        # Lagre beste resultat
        with open('data/analyzed/ml_optimized_thresholds.json', 'w') as f:
            json.dump(best, f, indent=2, default=str)
        print("\n✅ Beste grenseverdier lagret i: data/analyzed/ml_optimized_thresholds.json")

        return best
    else:
        print("❌ Ingen gode kandidater funnet!")
        return None

def evaluate_thresholds_full_period(df, thresholds):
    """Evaluer grenseverdier på hele perioden 2018-2024."""
    # Filter for vintersesonger
    winter_data = []
    for year in range(2018, 2025):
        # Vinter = nov (year-1) til april (year)
        start_date = f"{year-1}-11-01" if year > 2018 else "2018-11-01"
        end_date = f"{year}-04-30"

        season_data = df[
            (df['timestamp'] >= start_date) &
            (df['timestamp'] <= end_date)
        ]
        winter_data.append(season_data)

    df_winter = pd.concat(winter_data, ignore_index=True)

    # Beregn vindkjøling
    df_winter['wind_chill'] = df_winter.apply(
        lambda row: calculate_wind_chill(row['air_temperature'], row['wind_speed'])
        if pd.notna(row['air_temperature']) and pd.notna(row['wind_speed'])
        else np.nan, axis=1
    )

    # Konverter snødybde
    snow_depth_m = df_winter['surface_snow_thickness'] / 100 if df_winter['surface_snow_thickness'].max() > 10 else df_winter['surface_snow_thickness']

    # Identifiser alarmdager
    alerts = df_winter[
        (df_winter['wind_chill'] < thresholds['wind_chill']) &
        (df_winter['wind_speed'] > thresholds['wind_speed']) &
        (df_winter['air_temperature'] < thresholds['temperature']) &
        (snow_depth_m > thresholds['snow_depth'])
    ].copy()

    if len(alerts) == 0:
        return 0, []

    alerts['date'] = pd.to_datetime(alerts['timestamp']).dt.date
    alert_days = alerts['date'].unique()

    return len(alert_days), list(alert_days)

if __name__ == "__main__":
    best_thresholds = ml_optimize_thresholds()

    if best_thresholds:
        print("\n🎯 ML-OPTIMALISERING FULLFØRT!")
        print(f"Beste grenseverdier gir {best_thresholds['num_days']} alarmdager i 2023-2024 sesongen")
