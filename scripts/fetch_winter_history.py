#!/usr/bin/env python3
"""
Hent historiske vinterdata (nov-apr) fra Frost API for Gullingen.
Lagrer per sesong og som samlet fil.
"""

import requests
import pandas as pd
import os
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Konfigurasjon
STATION = 'SN46220'
OUTPUT_DIR = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/raw/winter_seasons'

# Alle relevante elementer
ELEMENTS = [
    'air_temperature',
    'surface_temperature',
    'surface_snow_thickness',
    'wind_speed',
    'wind_from_direction',
    'relative_humidity',
    'dew_point_temperature',
    'sum(precipitation_amount PT1H)',
    'max(wind_speed_of_gust PT1H)',
    'sum(duration_of_precipitation PT1H)',
    'min(air_temperature PT1H)',
    'max(air_temperature PT1H)',
]

# Vintersesonger å hente (nov-apr)
SEASONS = [
    ('2018-2019', '2018-11-01', '2019-04-30'),
    ('2019-2020', '2019-11-01', '2020-04-30'),
    ('2020-2021', '2020-11-01', '2021-04-30'),
    ('2021-2022', '2021-11-01', '2022-04-30'),
    ('2022-2023', '2022-11-01', '2023-04-30'),
    ('2023-2024', '2023-11-01', '2024-04-30'),
    ('2024-2025', '2024-11-01', '2025-04-30'),  # Pågående sesong
]

def fetch_season_data(client_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Hent data for én sesong."""
    
    url = "https://frost.met.no/observations/v0.jsonld"
    
    # Juster sluttdato hvis i fremtiden
    today = datetime.now().strftime('%Y-%m-%d')
    if end_date > today:
        end_date = today
    
    params = {
        'sources': STATION,
        'elements': ','.join(ELEMENTS),
        'referencetime': f'{start_date}/{end_date}',
        'timeresolutions': 'PT1H',
    }
    
    print(f"  Henter {start_date} til {end_date}...")
    
    response = requests.get(url, params=params, auth=(client_id, ''), timeout=120)
    
    if response.status_code != 200:
        print(f"  FEIL: HTTP {response.status_code}")
        return pd.DataFrame()
    
    data = response.json()
    observations = data.get('data', [])
    
    if not observations:
        print(f"  Ingen data funnet")
        return pd.DataFrame()
    
    print(f"  Mottok {len(observations)} tidspunkter")
    
    # Konverter til DataFrame
    rows = []
    for obs in observations:
        timestamp = obs['referenceTime'][:19].replace('T', ' ')
        row = {'timestamp': timestamp}
        
        for elem in obs.get('observations', []):
            elem_id = elem['elementId']
            value = elem['value']
            
            # Forenkle kolonnenavn
            col_name = elem_id.replace('sum(', '').replace('max(', '').replace('min(', '')
            col_name = col_name.replace(' PT1H)', '').replace(')', '')
            col_name = col_name.replace('_amount', '').replace('_of_gust', '_gust')
            
            row[col_name] = value
        
        rows.append(row)
    
    df = pd.DataFrame(rows)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').drop_duplicates(subset=['timestamp'])
    
    return df


def main():
    client_id = os.getenv('FROST_CLIENT_ID')
    if not client_id:
        print("FROST_CLIENT_ID ikke funnet i .env")
        return
    
    # Opprett output-mappe
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 60)
    print("HENTER HISTORISKE VINTERDATA FRA GULLINGEN")
    print(f"Stasjon: {STATION}")
    print(f"Elementer: {len(ELEMENTS)} stk")
    print("=" * 60)
    
    all_seasons = []
    
    for season_name, start_date, end_date in SEASONS:
        print(f"\nSesong {season_name}:")
        
        df = fetch_season_data(client_id, start_date, end_date)
        
        if df.empty:
            print(f"  Hopper over - ingen data")
            continue
        
        # Lagre sesongfil
        season_file = os.path.join(OUTPUT_DIR, f'winter_{season_name}.csv')
        df.to_csv(season_file, index=False)
        print(f"  Lagret: {season_file} ({len(df)} rader)")
        
        all_seasons.append(df)
        
        # Pause mellom API-kall
        time.sleep(1)
    
    # Kombiner alle sesonger
    if all_seasons:
        combined = pd.concat(all_seasons, ignore_index=True)
        combined = combined.sort_values('timestamp').drop_duplicates(subset=['timestamp'])
        
        combined_file = os.path.join(OUTPUT_DIR, 'historical_winter_all.csv')
        combined.to_csv(combined_file, index=False)
        
        print()
        print("=" * 60)
        print("FERDIG!")
        print(f"Samlet fil: {combined_file}")
        print(f"Totalt: {len(combined)} rader")
        print(f"Periode: {combined['timestamp'].min()} til {combined['timestamp'].max()}")
        print(f"Kolonner: {list(combined.columns)}")
        print("=" * 60)


if __name__ == '__main__':
    main()
