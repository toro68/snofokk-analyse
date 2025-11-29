#!/usr/bin/env python3
"""
Korrelasjon mellom brøytedata og værdata med nye elementer.
Inkluderer surface_temperature og wind_speed_gust.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# Paths
DATA_DIR = Path('/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data')
WEATHER_FILE = DATA_DIR / 'raw/winter_seasons/historical_winter_all.csv'
BROYTING_FILE = DATA_DIR / 'analyzed/Rapport 2022-2025.csv'

def parse_norwegian_date(date_str: str, time_str: str) -> datetime:
    """Parse norsk datoformat."""
    month_map = {
        'jan.': 1, 'feb.': 2, 'mars': 3, 'apr.': 4, 'mai': 5, 'jun.': 6,
        'jul.': 7, 'aug.': 8, 'sep.': 9, 'okt.': 10, 'nov.': 11, 'des.': 12
    }
    
    parts = date_str.split()
    day = int(parts[0].rstrip('.'))
    month = month_map.get(parts[1], 1)
    year = int(parts[2])
    
    time_parts = time_str.split(':')
    hour = int(time_parts[0])
    minute = int(time_parts[1])
    
    return datetime(year, month, day, hour, minute)


def load_broyting_data() -> pd.DataFrame:
    """Last brøytedata."""
    df = pd.read_csv(BROYTING_FILE, sep=';')
    df = df[df['Dato'] != 'Totalt']
    
    # Parse datoer
    datetimes = []
    for _, row in df.iterrows():
        try:
            dt = parse_norwegian_date(row['Dato'], row['Starttid'])
            datetimes.append(dt)
        except:
            datetimes.append(None)
    
    df['datetime'] = datetimes
    df = df.dropna(subset=['datetime'])
    
    return df


def load_weather_data() -> pd.DataFrame:
    """Last værdata."""
    df = pd.read_csv(WEATHER_FILE)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def get_weather_before(weather_df: pd.DataFrame, dt: datetime, hours: int = 6) -> pd.DataFrame:
    """Hent værdata X timer før et tidspunkt."""
    start = dt - timedelta(hours=hours)
    mask = (weather_df['timestamp'] >= start) & (weather_df['timestamp'] <= dt)
    return weather_df[mask]


def analyze_correlation():
    """Analyser korrelasjon mellom brøyting og vær."""
    
    print("=" * 70)
    print("KORRELASJON: BRØYTING VS VÆR (MED NYE ELEMENTER)")
    print("=" * 70)
    
    # Last data
    print("\nLaster data...")
    broyting = load_broyting_data()
    weather = load_weather_data()
    
    print(f"  Brøyteepisoder: {len(broyting)}")
    print(f"  Værobservasjoner: {len(weather)}")
    print(f"  Værperiode: {weather['timestamp'].min()} til {weather['timestamp'].max()}")
    
    # Analyser hver brøyteepisode
    results = []
    
    for _, row in broyting.iterrows():
        dt = row['datetime']
        
        # Hent vær 6 timer før
        wx = get_weather_before(weather, dt, hours=6)
        
        if wx.empty:
            continue
        
        result = {
            'dato': row['Dato'],
            'datetime': dt,
            
            # Lufttemperatur
            'air_temp_avg': wx['air_temperature'].mean(),
            'air_temp_min': wx['air_temperature'].min(),
            
            # NYTT: Bakketemperatur
            'surface_temp_avg': wx['surface_temperature'].mean() if 'surface_temperature' in wx else None,
            'surface_temp_min': wx['surface_temperature'].min() if 'surface_temperature' in wx else None,
            
            # Temperaturforskjell luft vs bakke
            'temp_diff': (wx['air_temperature'].mean() - wx['surface_temperature'].mean()) if 'surface_temperature' in wx else None,
            
            # Vind
            'wind_avg': wx['wind_speed'].mean(),
            'wind_max': wx['wind_speed'].max(),
            
            # NYTT: Vindkast
            'gust_max': wx['wind_speed_gust'].max() if 'wind_speed_gust' in wx else None,
            
            # Nedbør
            'precip_total': wx['precipitation'].sum() if 'precipitation' in wx else 0,
            'precip_duration': wx['duration_of_precipitation'].sum() if 'duration_of_precipitation' in wx else 0,
            
            # Snø
            'snow_depth': wx['surface_snow_thickness'].mean(),
            'snow_change': wx['surface_snow_thickness'].iloc[-1] - wx['surface_snow_thickness'].iloc[0] if len(wx) > 1 else 0,
            
            # Fuktighet
            'humidity_avg': wx['relative_humidity'].mean(),
            'dew_point_avg': wx['dew_point_temperature'].mean() if 'dew_point_temperature' in wx else None,
        }
        
        # Klassifiser scenario
        if result['air_temp_avg'] is not None:
            temp = result['air_temp_avg']
            precip = result['precip_total'] or 0
            surface_temp = result['surface_temp_avg']
            
            if temp > 0 and precip > 5:
                result['scenario'] = 'SLAPS'
            elif temp <= 0 and precip > 2:
                result['scenario'] = 'NYSNØ'
            elif surface_temp is not None and surface_temp < 0 and temp > 0:
                result['scenario'] = 'FRYSEFARE'
            elif result['wind_avg'] and result['wind_avg'] > 6 and temp < -1:
                result['scenario'] = 'SNØFOKK'
            else:
                result['scenario'] = 'ANNET'
        else:
            result['scenario'] = 'UKJENT'
        
        results.append(result)
    
    df = pd.DataFrame(results)
    
    # Statistikk
    print()
    print("=" * 70)
    print("RESULTATER")
    print("=" * 70)
    
    print(f"\nAnalyserte episoder: {len(df)}")
    
    # Scenariofordeling
    print("\nScenariofordeling:")
    for scenario, count in df['scenario'].value_counts().items():
        pct = count / len(df) * 100
        print(f"  {scenario}: {count} ({pct:.1f}%)")
    
    # Temperaturanalyse
    print("\nTemperaturanalyse:")
    print(f"  Lufttemperatur snitt: {df['air_temp_avg'].mean():.1f}°C")
    if df['surface_temp_avg'].notna().any():
        print(f"  Bakketemperatur snitt: {df['surface_temp_avg'].mean():.1f}°C")
        print(f"  Diff luft-bakke snitt: {df['temp_diff'].mean():.1f}°C")
    
    # NYTT: Bakketemperatur vs lufttemperatur
    print("\nBakketemperatur-innsikt:")
    cold_ground = df[df['surface_temp_avg'] < 0]
    warm_air = df[(df['air_temp_avg'] > 0) & (df['surface_temp_avg'] < 0)]
    print(f"  Episoder med bakke < 0°C: {len(cold_ground)}")
    print(f"  Episoder med luft > 0 OG bakke < 0 (FRYSEFARE): {len(warm_air)}")
    
    # Vindkast-analyse
    print("\nVindkast-analyse:")
    if df['gust_max'].notna().any():
        print(f"  Max vindkast snitt: {df['gust_max'].mean():.1f} m/s")
        print(f"  Max vindkast høyeste: {df['gust_max'].max():.1f} m/s")
        high_gust = df[df['gust_max'] > 15]
        print(f"  Episoder med vindkast > 15 m/s: {len(high_gust)}")
    
    # Korrelasjon med værfaktorer
    print("\nKorrelasjon med brøytebehov:")
    
    numeric_cols = ['air_temp_avg', 'surface_temp_avg', 'temp_diff', 
                    'wind_avg', 'wind_max', 'gust_max',
                    'precip_total', 'snow_depth', 'humidity_avg']
    
    for col in numeric_cols:
        if col in df and df[col].notna().any():
            # Korreler med "intensitet" (antall episoder per dag er proxy)
            pass  # Trenger mer data for ekte korrelasjon
    
    # Per-scenario statistikk
    print("\nVærforhold per scenario:")
    for scenario in ['SLAPS', 'NYSNØ', 'FRYSEFARE', 'SNØFOKK']:
        subset = df[df['scenario'] == scenario]
        if len(subset) > 0:
            print(f"\n  {scenario} ({len(subset)} episoder):")
            print(f"    Lufttemp: {subset['air_temp_avg'].mean():.1f}°C")
            if subset['surface_temp_avg'].notna().any():
                print(f"    Bakketemp: {subset['surface_temp_avg'].mean():.1f}°C")
            print(f"    Nedbør: {subset['precip_total'].mean():.1f}mm")
            print(f"    Vind: {subset['wind_avg'].mean():.1f} m/s")
            if subset['gust_max'].notna().any():
                print(f"    Vindkast: {subset['gust_max'].mean():.1f} m/s")
    
    # Lagre resultater
    output_file = DATA_DIR / 'analyzed/broyting_weather_correlation_2025.csv'
    df.to_csv(output_file, index=False)
    print(f"\nResultater lagret: {output_file}")
    
    return df


if __name__ == '__main__':
    analyze_correlation()
