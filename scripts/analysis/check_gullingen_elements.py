#!/usr/bin/env python3
"""
Gullingen Available Elements - Sjekker hvilke elementer som er tilgjengelige
"""
import json
from pathlib import Path

import requests


def check_available_elements():
    """Sjekk tilgjengelige elementer for Gullingen Skisenter"""

    # Last Frost API key
    env_file = Path(__file__).parent.parent.parent / '.env'
    if env_file.exists():
        with open(env_file, encoding='utf-8') as f:
            for line in f:
                if line.startswith('FROST_CLIENT_ID='):
                    client_id = line.split('=', 1)[1].strip()
                    break
    else:
        print("❌ .env fil ikke funnet")
        return

    station_id = 'SN46220'  # Gullingen Skisenter

    print("🏔️ GULLINGEN SKISENTER - TILGJENGELIGE ELEMENTER")
    print("=" * 60)

    # Hent alle tilgjengelige elementer for stasjonen
    url = "https://frost.met.no/sources/v0.jsonld"

    params = {
        'ids': station_id,
        'fields': 'id,name,geometry,masl,validFrom,validTo'
    }

    headers = {
        'User-Agent': 'snofokk-analyse/1.0'
    }

    try:
        # Først hent stasjonsinformasjon
        response = requests.get(url, params=params, auth=(client_id, ''), headers=headers, timeout=30)

        if response.status_code == 200:
            data = response.json()
            sources = data.get('data', [])

            if sources:
                station = sources[0]
                print(f"📍 Stasjon: {station.get('name', 'N/A')}")
                print(f"🎯 ID: {station.get('id', 'N/A')}")
                print(f"⛰️ Høyde: {station.get('masl', 'N/A')} m.o.h.")

                coords = station.get('geometry', {}).get('coordinates', [])
                if len(coords) >= 2:
                    print(f"🌍 Koordinater: {coords[1]:.4f}, {coords[0]:.4f}")

                print(f"📅 Gyldig fra: {station.get('validFrom', 'N/A')}")
                print(f"📅 Gyldig til: {station.get('validTo', 'Aktiv')}")

        # Så hent tilgjengelige elementer
        elements_url = "https://frost.met.no/observations/availableTimeSeries/v0.jsonld"
        elements_params = {
            'sources': station_id,
            'fields': 'sourceId,elementId,validFrom,validTo,timeOffset,timeResolution,timeSeriesId'
        }

        print("\n📊 TILGJENGELIGE DATAELEMENTER:")
        print("=" * 60)

        response = requests.get(elements_url, params=elements_params, auth=(client_id, ''), headers=headers, timeout=30)

        if response.status_code == 200:
            elements_data = response.json()
            time_series = elements_data.get('data', [])

            print(f"✅ Fant {len(time_series)} tilgjengelige tidsserier")

            # Grupper elementer
            elements_dict = {}

            for ts in time_series:
                element_id = ts.get('elementId', '')
                time_resolution = ts.get('timeResolution', '')
                valid_from = ts.get('validFrom', '')
                valid_to = ts.get('validTo', '')

                if element_id not in elements_dict:
                    elements_dict[element_id] = []

                elements_dict[element_id].append({
                    'resolution': time_resolution,
                    'valid_from': valid_from,
                    'valid_to': valid_to
                })

            # Kategoriser elementer
            categories = {
                'Vind': [],
                'Temperatur': [],
                'Snø': [],
                'Nedbør': [],
                'Fuktighet': [],
                'Trykk': [],
                'Stråling': [],
                'Andre': []
            }

            for element_id, time_series_list in elements_dict.items():
                element_lower = element_id.lower()

                if any(word in element_lower for word in ['wind', 'vind']):
                    categories['Vind'].append((element_id, time_series_list))
                elif any(word in element_lower for word in ['temp', 'temperature']):
                    categories['Temperatur'].append((element_id, time_series_list))
                elif any(word in element_lower for word in ['snow', 'snø']):
                    categories['Snø'].append((element_id, time_series_list))
                elif any(word in element_lower for word in ['precip', 'rain', 'nedbør', 'sum(']):
                    categories['Nedbør'].append((element_id, time_series_list))
                elif any(word in element_lower for word in ['humid', 'fukt']):
                    categories['Fuktighet'].append((element_id, time_series_list))
                elif any(word in element_lower for word in ['pressure', 'trykk']):
                    categories['Trykk'].append((element_id, time_series_list))
                elif any(word in element_lower for word in ['radiation', 'stråling', 'solar']):
                    categories['Stråling'].append((element_id, time_series_list))
                else:
                    categories['Andre'].append((element_id, time_series_list))

            # Presenter resultater
            for category, items in categories.items():
                if items:
                    print(f"\n🏷️ {category.upper()}:")
                    for element_id, ts_list in items:
                        print(f"   • {element_id}")

                        # Vis aktive tidsserier
                        active_series = [ts for ts in ts_list if not ts['valid_to'] or ts['valid_to'] > '2025-01-01']

                        if active_series:
                            for ts in active_series:
                                status = "AKTIV" if not ts['valid_to'] else f"til {ts['valid_to'][:10]}"
                                print(f"     → {ts['resolution']} ({status})")
                        else:
                            print("     → Ingen aktive tidsserier")

            # Analyser snøfokk-relevans
            print("\n🎯 SNØFOKK-RELEVANS ANALYSE:")
            print("=" * 60)

            critical_for_snowdrift = {
                'Vindstyrke': ['wind_speed', 'max_wind_speed', 'mean_wind_speed'],
                'Vindretning': ['wind_from_direction'],
                'Vindkast': ['max_wind_speed', 'wind_speed_gust'],
                'Temperatur': ['air_temperature', 'min_temperature', 'max_temperature'],
                'Snødybde': ['surface_snow_thickness'],
                'Nedbør': ['sum(precipitation_amount'],
                'Sikt': ['visibility', 'horizontal_visibility'],
                'Fuktighet': ['relative_humidity']
            }

            available_critical = {}
            missing_critical = []

            for critical_name, search_terms in critical_for_snowdrift.items():
                found = []

                for element_id in elements_dict.keys():
                    for term in search_terms:
                        if term in element_id:
                            found.append(element_id)
                            break

                if found:
                    available_critical[critical_name] = found
                else:
                    missing_critical.append(critical_name)

            print("✅ TILGJENGELIGE KRITISKE PARAMETRE:")
            for param_name, element_ids in available_critical.items():
                print(f"   🔹 {param_name}:")
                for elem_id in element_ids:
                    # Finn aktive tidsserier
                    active_count = len([ts for ts in elements_dict[elem_id] if not ts['valid_to'] or ts['valid_to'] > '2025-01-01'])
                    print(f"     • {elem_id} ({active_count} aktive tidsserier)")

            if missing_critical:
                print("\n❌ MANGLENDE KRITISKE PARAMETRE:")
                for param_name in missing_critical:
                    print(f"   • {param_name}")

            # Lagre resultater
            output_file = Path(__file__).parent.parent.parent / 'data' / 'analyzed' / 'gullingen_available_elements.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'station_id': station_id,
                    'station_name': 'Gullingen Skisenter',
                    'analysis_date': '2025-08-09',
                    'total_time_series': len(time_series),
                    'unique_elements': len(elements_dict),
                    'elements': {elem_id: ts_list for elem_id, ts_list in elements_dict.items()},
                    'categories': {cat: [item[0] for item in items] for cat, items in categories.items()},
                    'snowdrift_critical': {
                        'available': available_critical,
                        'missing': missing_critical
                    }
                }, f, indent=2, ensure_ascii=False)

            print(f"\n💾 Detaljerte resultater lagret i {output_file}")

            # Vurdering av snøfokk-deteksjonskapabilitet
            score = len(available_critical) / len(critical_for_snowdrift) * 100

            print(f"\n📈 SNØFOKK-DETEKSJON KAPABILITET: {score:.1f}%")

            if score >= 80:
                print("   🏆 UTMERKET - Fullstendig snøfokk-analyse mulig")
            elif score >= 60:
                print("   ✅ GOD - Pålitelig snøfokk-deteksjon mulig")
            elif score >= 40:
                print("   ⚠️ BEGRENSET - Grunnleggende deteksjon mulig")
            else:
                print("   ❌ UTILSTREKKELIG - Snøfokk-deteksjon vanskelig")

        else:
            print(f"❌ API-feil ved elementer: {response.status_code}")
            print(f"Response: {response.text}")

    except Exception as e:
        print(f"❌ Feil: {e}")

if __name__ == '__main__':
    check_available_elements()
