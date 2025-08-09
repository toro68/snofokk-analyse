#!/usr/bin/env python3
"""
Gullingen Station Finder - Finner riktig Gullingen værstasjon
"""
import os
import requests
from pathlib import Path
import json

def find_gullingen_station():
    """Søk etter Gullingen værstasjon via Frost API"""
    
    # Last Frost API key
    env_file = Path(__file__).parent.parent.parent / '.env'
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                if line.startswith('FROST_CLIENT_ID='):
                    client_id = line.split('=', 1)[1].strip()
                    break
    else:
        print("❌ .env fil ikke funnet")
        return
    
    print("🔍 SØKER ETTER GULLINGEN VÆRSTASJON")
    print("=" * 60)
    
    # Søk etter stasjoner med 'Gullingen' i navnet
    url = "https://frost.met.no/sources/v0.jsonld"
    
    headers = {
        'User-Agent': 'snofokk-analyse/1.0'
    }
    
    params = {
        'ids': '',  # Tom for å søke alle
        'types': 'SensorSystem',
        'fields': 'id,name,geometry,masl,validFrom,validTo',
        'country': 'NO'
    }
    
    try:
        response = requests.get(url, params=params, auth=(client_id, ''), headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            sources = data.get('data', [])
            
            print(f"📊 Fant {len(sources)} værstasjoner totalt")
            
            # Filtrer på navn som inneholder 'Gullingen' eller lignende
            gullingen_candidates = []
            
            search_terms = ['gullingen', 'gull', 'gullik', 'gulliksenbakken']
            
            for source in sources:
                name = source.get('name', '').lower()
                source_id = source.get('id', '')
                
                for term in search_terms:
                    if term in name:
                        gullingen_candidates.append({
                            'id': source_id,
                            'name': source.get('name', ''),
                            'elevation': source.get('masl', 'N/A'),
                            'valid_from': source.get('validFrom', ''),
                            'valid_to': source.get('validTo', ''),
                            'geometry': source.get('geometry', {})
                        })
                        break
            
            print(f"\n🎯 GULLINGEN KANDIDATER:")
            
            if gullingen_candidates:
                for i, candidate in enumerate(gullingen_candidates, 1):
                    coords = candidate.get('geometry', {}).get('coordinates', [])
                    lat = coords[1] if len(coords) > 1 else 'N/A'
                    lon = coords[0] if len(coords) > 0 else 'N/A'
                    
                    print(f"\n{i}. {candidate['name']}")
                    print(f"   ID: {candidate['id']}")
                    print(f"   Høyde: {candidate['elevation']} m.o.h.")
                    print(f"   Koordinater: {lat}, {lon}")
                    print(f"   Gyldig fra: {candidate['valid_from']}")
                    print(f"   Gyldig til: {candidate['valid_to'] or 'Aktiv'}")
            else:
                print("❌ Ingen stasjoner funnet med 'Gullingen' i navnet")
                
                # Prøv bredere søk på område (hvis vi kjenner omtrentlig lokasjon)
                print("\n🌍 ALTERNATIV: SØK I LOKALT OMRÅDE")
                print("Kan du oppgi omtrentlige koordinater for Gullingen?")
                print("Eller sjekk https://frost.met.no/stations for manuelt søk")
            
            # Lagre alle kandidater for videre analyse
            if gullingen_candidates:
                output_file = Path(__file__).parent.parent.parent / 'data' / 'gullingen_station_candidates.json'
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(gullingen_candidates, f, indent=2, ensure_ascii=False)
                print(f"\n💾 Kandidater lagret i {output_file}")
                
                return gullingen_candidates
        else:
            print(f"❌ API-feil: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Feil ved API-kall: {e}")
    
    return None

def test_station_data_availability(candidates):
    """Test datatilgjengelighet for kandidat-stasjoner"""
    
    if not candidates:
        return
    
    print(f"\n🧪 TESTER DATATILGJENGELIGHET")
    print("=" * 60)
    
    # Last Frost API key
    env_file = Path(__file__).parent.parent.parent / '.env'
    with open(env_file, 'r') as f:
        for line in f:
            if line.startswith('FROST_CLIENT_ID='):
                client_id = line.split('=', 1)[1].strip()
                break
    
    for candidate in candidates:
        station_id = candidate['id']
        station_name = candidate['name']
        
        print(f"\n📡 Tester {station_name} ({station_id})...")
        
        # Test tilgjengelige elementer (værparametre)
        url = "https://frost.met.no/elements/v0.jsonld"
        params = {
            'ids': station_id,
            'fields': 'id,name,description,unit'
        }
        
        try:
            response = requests.get(url, params=params, auth=(client_id, ''), timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                elements = data.get('data', [])
                
                if elements:
                    print(f"   ✅ {len(elements)} tilgjengelige parametre")
                    
                    # Kategoriser viktige parametre
                    important_elements = {
                        'wind': [],
                        'temperature': [],
                        'snow': [],
                        'precipitation': [],
                        'visibility': [],
                        'other': []
                    }
                    
                    for element in elements:
                        elem_id = element.get('id', '').lower()
                        elem_name = element.get('name', '').lower()
                        
                        if 'wind' in elem_id or 'wind' in elem_name:
                            important_elements['wind'].append(element)
                        elif 'temp' in elem_id or 'temp' in elem_name:
                            important_elements['temperature'].append(element)
                        elif 'snow' in elem_id or 'snow' in elem_name:
                            important_elements['snow'].append(element)
                        elif 'precip' in elem_id or 'precip' in elem_name or 'rain' in elem_id:
                            important_elements['precipitation'].append(element)
                        elif 'vis' in elem_id or 'visibility' in elem_name:
                            important_elements['visibility'].append(element)
                        else:
                            important_elements['other'].append(element)
                    
                    # Vis kritiske parametre
                    for category, elements in important_elements.items():
                        if elements and category in ['wind', 'temperature', 'snow', 'visibility']:
                            print(f"     🏷️ {category.upper()}: {len(elements)} parametre")
                            for elem in elements[:3]:  # Vis første 3
                                print(f"       • {elem.get('id', '')}: {elem.get('name', '')}")
                else:
                    print(f"   ❌ Ingen tilgjengelige parametre")
            else:
                print(f"   ❌ API-feil: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Feil: {e}")

def main():
    candidates = find_gullingen_station()
    if candidates:
        test_station_data_availability(candidates)
        
        print(f"\n🎯 ANBEFALING:")
        print("1. Velg stasjon med best datatilgjengelighet")
        print("2. Fokuser på stasjoner med vind-, snø- og siktdata")
        print("3. Test med nylige data for å bekrefte aktiv drift")

if __name__ == '__main__':
    main()
