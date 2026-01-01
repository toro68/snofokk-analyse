import os
import logging
import requests
from datetime import datetime

# Direkte konfigurasjon
FROST_CLIENT_ID = os.getenv('FROST_CLIENT_ID', '43fefca2-a26b-415b-954d-ba9af37e3e1f')

# Komplett liste over elementer med PT1H oppløsning
FROST_ELEMENTS = [
    # Temperatur
    'air_temperature',
    'min(air_temperature PT1H)',
    'max(air_temperature PT1H)',
    'surface_temperature',
    'dew_point_temperature',
    
    # Nedbør
    'accumulated(precipitation_amount)',
    'sum(precipitation_amount PT1H)',
    'sum(duration_of_precipitation PT1H)',
    'over_time(gauge_content_difference PT1H)',
    
    # Vind
    'wind_speed',
    'max(wind_speed PT1H)',
    'max(wind_speed_of_gust PT1H)',
    'max_wind_speed(wind_from_direction PT1H)',
    'wind_from_direction',
    
    # Fuktighet
    'relative_humidity',
    
    # Snø
    'surface_snow_thickness',
    
    # Annet
    'battery_voltage'
]

def test_frost_parameters():
    """Tester tilgjengelighet av hver parameter fra Frost API"""
    print("\n=== START: FROST API PARAMETER TEST ===")
    print(f"Testing {len(FROST_ELEMENTS)} parametre med PT1H oppløsning\n")
    
    results = {}
    for element in FROST_ELEMENTS:
        print(f"\nTester: {element}")
        try:
            params = {
                'sources': 'SN46220',
                'referencetime': '2024-01-01/2024-01-02',
                'elements': element,
                'timeresolutions': 'PT1H'
            }
            
            response = requests.get(
                'https://frost.met.no/observations/v0.jsonld',
                params=params,
                auth=(FROST_CLIENT_ID, '')
            )
            
            print(f"Status kode: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data'):
                    first_value = data['data'][0]['observations'][0]['value']
                    unit = data['data'][0]['observations'][0].get('unit', 'ukjent')
                    print(f"Første verdi: {first_value} {unit}")
                    results[element] = {
                        'status': 'OK', 
                        'value': first_value,
                        'unit': unit,
                        'from': '2018-02-06'
                    }
                else:
                    print("Ingen data returnert")
                    results[element] = {'status': 'NO_DATA'}
            else:
                print(f"API Feil: {response.text}")
                results[element] = {'status': 'ERROR', 'code': response.status_code}
                
        except Exception as e:
            print(f"Feil: {str(e)}")
            results[element] = {'status': 'ERROR', 'error': str(e)}
    
    return results

if __name__ == "__main__":
    print("\nStarter Frost API test...")
    results = test_frost_parameters()
    
    print("\n=== OPPSUMMERING ===")
    print("\nTilgjengelige parametre med PT1H oppløsning:")
    for param, result in results.items():
        if result['status'] == 'OK':
            unit = result.get('unit', '')
            print(f"✓ {param}: {result['value']} {unit}")
    
    print("\nUtilgjengelige parametre:")
    for param, result in results.items():
        if result['status'] != 'OK':
            print(f"✗ {param}: {result['status']}")
    
    print("\nTest fullført")
    