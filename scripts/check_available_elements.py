#!/usr/bin/env python3
"""Sjekk hvilke elementer som faktisk har data på Gullingen."""

import os
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv('FROST_CLIENT_ID')
if not client_id:
    print("FROST_CLIENT_ID ikke funnet i .env")
    exit(1)

# Elementer å teste
elements_to_test = [
    # Brukes i dag
    'air_temperature',
    'wind_speed',
    'wind_from_direction',
    'surface_snow_thickness',
    'sum(precipitation_amount PT1H)',
    'dew_point_temperature',
    'relative_humidity',

    # Potensielt nyttige
    'surface_temperature',
    'max(wind_speed_of_gust PT1H)',
    'sum(duration_of_precipitation PT1H)',
    'min(air_temperature PT1H)',
    'max(air_temperature PT1H)',
    'accumulated(precipitation_amount)',
]

url = "https://frost.met.no/observations/v0.jsonld"

# Test siste 7 dager
end_date = datetime.now()
start_date = end_date - timedelta(days=7)
ref_time = f"{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"

print("=" * 70)
print("SJEKK AV TILGJENGELIGE ELEMENTER PÅ SN46220 GULLINGEN")
print(f"Periode: {ref_time}")
print("=" * 70)
print()

results = {}

for element in elements_to_test:
    params = {
        'sources': 'SN46220',
        'elements': element,
        'referencetime': ref_time,
    }

    try:
        response = requests.get(url, params=params, auth=(client_id, ''), timeout=10)

        if response.status_code == 200:
            data = response.json()
            obs_count = len(data.get('data', []))

            if obs_count > 0:
                # Hent noen verdier for å vise
                values = []
                for obs in data.get('data', [])[:5]:
                    for o in obs.get('observations', []):
                        values.append(o.get('value'))

                results[element] = {
                    'status': 'OK',
                    'count': obs_count,
                    'sample': values[:3]
                }
                print(f"  {element}")
                print(f"    Observasjoner: {obs_count}")
                print(f"    Eksempel: {values[:3]}")
                print()
            else:
                results[element] = {'status': 'INGEN DATA', 'count': 0}
                print(f"  {element}")
                print("    INGEN DATA i perioden")
                print()
        else:
            results[element] = {'status': f'FEIL {response.status_code}', 'count': 0}
            print(f"  {element}")
            print(f"    FEIL: HTTP {response.status_code}")
            print()

    except Exception as e:
        results[element] = {'status': f'FEIL: {str(e)}', 'count': 0}
        print(f"  {element}")
        print(f"    FEIL: {e}")
        print()

print("=" * 70)
print("OPPSUMMERING")
print("=" * 70)
print()
print("Elementer med data:")
for elem, info in results.items():
    if info['status'] == 'OK':
        print(f"  {elem}: {info['count']} obs")

print()
print("Elementer UTEN data:")
for elem, info in results.items():
    if info['status'] != 'OK':
        print(f"  {elem}: {info['status']}")
