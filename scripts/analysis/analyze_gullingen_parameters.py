#!/usr/bin/env python3
"""
Gullingen Weather Parameters Explorer - Detaljert analyse av tilgjengelige parametre
"""
import asyncio
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

async def get_weather_data_direct(station_id, start_date, end_date, client_id):
    """Hent værdata direkte fra Frost API"""
    import aiohttp

    url = "https://frost.met.no/observations/v0.jsonld"

    params = {
        'sources': station_id,
        'referencetime': f"{start_date}/{end_date}",
        'fields': 'sourceId,referenceTime,elementId,value,unit,timeOffset',
        'timeoffsets': 'PT0H'  # Kun nåtidsdata
    }

    headers = {
        'User-Agent': 'snofokk-analyse/1.0'
    }

    auth = aiohttp.BasicAuth(client_id, '')

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers, auth=auth) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"❌ API-feil: {response.status}")
                return None

async def analyze_gullingen_parameters():
    """Analyser alle tilgjengelige parametre for Gullingen Skisenter"""

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

    print("🏔️ GULLINGEN SKISENTER (SN46220) - PARAMETERANALYSE")
    print("=" * 70)

    # Hent nylige data for å se hvilke parametre som faktisk leveres
    end_date = date.today()
    start_date = end_date - timedelta(days=7)  # Siste uke

    print(f"📊 Analyserer data fra {start_date} til {end_date}")

    data = await get_weather_data_direct(station_id, start_date, end_date, client_id)

    if not data:
        print("❌ Ingen data mottatt")
        return

    observations = data.get('data', [])
    print(f"✅ Mottatt {len(observations)} observasjoner")

    if not observations:
        print("❌ Ingen observasjoner i dataset")
        return

    # Analyser alle unike elementer
    elements = {}

    for obs in observations:
        element_id = obs.get('elementId', '')
        value = obs.get('value', None)
        unit = obs.get('unit', '')
        ref_time = obs.get('referenceTime', '')

        if element_id not in elements:
            elements[element_id] = {
                'unit': unit,
                'values': [],
                'latest_time': ref_time,
                'count': 0
            }

        if value is not None:
            elements[element_id]['values'].append(value)
            elements[element_id]['count'] += 1
            if ref_time > elements[element_id]['latest_time']:
                elements[element_id]['latest_time'] = ref_time

    # Kategoriser elementer for snøfokk-analyse
    print(f"\n🔍 TILGJENGELIGE PARAMETRE ({len(elements)} totalt):")
    print("=" * 70)

    categories = {
        'Vind': [],
        'Temperatur': [],
        'Snø': [],
        'Nedbør': [],
        'Fuktighet': [],
        'Trykk': [],
        'Sikt/Visibilitet': [],
        'Andre': []
    }

    # Kategoriser basert på element-ID
    for element_id, data in elements.items():
        element_lower = element_id.lower()

        if any(word in element_lower for word in ['wind', 'vind']):
            categories['Vind'].append((element_id, data))
        elif any(word in element_lower for word in ['temp', 'temperature']):
            categories['Temperatur'].append((element_id, data))
        elif any(word in element_lower for word in ['snow', 'snø']):
            categories['Snø'].append((element_id, data))
        elif any(word in element_lower for word in ['precip', 'rain', 'nedbør']):
            categories['Nedbør'].append((element_id, data))
        elif any(word in element_lower for word in ['humid', 'fukt']):
            categories['Fuktighet'].append((element_id, data))
        elif any(word in element_lower for word in ['pressure', 'trykk']):
            categories['Trykk'].append((element_id, data))
        elif any(word in element_lower for word in ['vis', 'sight']):
            categories['Sikt/Visibilitet'].append((element_id, data))
        else:
            categories['Andre'].append((element_id, data))

    # Presenter kategoriserte resultater
    for category, items in categories.items():
        if items:
            print(f"\n🏷️ {category.upper()}:")
            for element_id, data in items:
                if data['values']:
                    avg_val = sum(data['values']) / len(data['values'])
                    min_val = min(data['values'])
                    max_val = max(data['values'])

                    print(f"   • {element_id}")
                    print(f"     Enhet: {data['unit']}")
                    print(f"     Observasjoner: {data['count']}")
                    print(f"     Verdiområde: {min_val:.1f} - {max_val:.1f} (avg: {avg_val:.1f})")
                    print(f"     Siste: {data['latest_time']}")
                else:
                    print(f"   • {element_id} (ingen verdier)")

    # Spesifikk snøfokk-analyse
    await analyze_snowdrift_capabilities(elements)

    # Lagre detaljerte resultater
    output_file = Path(__file__).parent.parent.parent / 'data' / 'analyzed' / 'gullingen_parameters.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        # Konverter til JSON-serialiserbar format
        serializable_elements = {}
        for elem_id, data in elements.items():
            serializable_elements[elem_id] = {
                'unit': data['unit'],
                'count': data['count'],
                'latest_time': data['latest_time'],
                'min_value': min(data['values']) if data['values'] else None,
                'max_value': max(data['values']) if data['values'] else None,
                'avg_value': sum(data['values']) / len(data['values']) if data['values'] else None
            }

        json.dump({
            'station_id': station_id,
            'station_name': 'Gullingen Skisenter',
            'analysis_date': datetime.now().isoformat(),
            'data_period': f"{start_date} to {end_date}",
            'total_observations': len(observations),
            'unique_elements': len(elements),
            'elements': serializable_elements,
            'categories': {cat: [item[0] for item in items] for cat, items in categories.items()}
        }, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Detaljerte resultater lagret i {output_file}")

async def analyze_snowdrift_capabilities(elements):
    """Analyser spesifikke kapabiliteter for snøfokk-deteksjon"""

    print("\n🎯 SNØFOKK-DETEKSJON KAPABILITETER")
    print("=" * 70)

    # Kritiske parametre for snøfokk
    critical_elements = {
        'wind_speed': ['wind_speed', 'wind', 'vind'],
        'wind_direction': ['wind_direction', 'wind_from_direction'],
        'wind_gust': ['max_wind_speed', 'wind_gust', 'vindkast'],
        'temperature': ['air_temperature', 'temperature', 'temp'],
        'snow_depth': ['surface_snow_thickness', 'snow_depth', 'snødybde'],
        'precipitation': ['sum(precipitation_amount', 'precip'],
        'humidity': ['relative_humidity', 'humidity'],
        'visibility': ['visibility', 'horizontal_visibility', 'sikt']
    }

    available_critical = {}
    missing_critical = []

    for critical_type, search_terms in critical_elements.items():
        found = []

        for element_id in elements.keys():
            element_lower = element_id.lower()

            for term in search_terms:
                if term.lower() in element_lower:
                    found.append(element_id)
                    break

        if found:
            available_critical[critical_type] = found
        else:
            missing_critical.append(critical_type)

    print("✅ TILGJENGELIGE KRITISKE PARAMETRE:")
    for param_type, element_ids in available_critical.items():
        print(f"   🔹 {param_type.replace('_', ' ').title()}:")
        for elem_id in element_ids:
            data = elements[elem_id]
            print(f"     • {elem_id} ({data['unit']}) - {data['count']} observasjoner")

    if missing_critical:
        print("\n❌ MANGLENDE KRITISKE PARAMETRE:")
        for param_type in missing_critical:
            print(f"   • {param_type.replace('_', ' ').title()}")

    # Vurder snøfokk-deteksjonsmuligheter
    print("\n📋 SNØFOKK-DETEKSJON VURDERING:")

    capabilities = {
        'primary_detection': 0,  # Primære indikatorer
        'secondary_detection': 0,  # Sekundære indikatorer
        'confirmation': 0  # Bekreftelse
    }

    # Primære indikatorer
    if 'wind_speed' in available_critical:
        capabilities['primary_detection'] += 1
        print("   ✅ Vindstyrke - PRIMÆR indikator")

    if 'temperature' in available_critical:
        capabilities['primary_detection'] += 1
        print("   ✅ Temperatur - PRIMÆR indikator")

    if 'snow_depth' in available_critical:
        capabilities['primary_detection'] += 1
        print("   ✅ Snødybde - PRIMÆR indikator")

    # Sekundære indikatorer
    if 'wind_direction' in available_critical:
        capabilities['secondary_detection'] += 1
        print("   ✅ Vindretning - SEKUNDÆR indikator")

    if 'wind_gust' in available_critical:
        capabilities['secondary_detection'] += 1
        print("   ✅ Vindkast - SEKUNDÆR indikator")

    if 'humidity' in available_critical:
        capabilities['secondary_detection'] += 1
        print("   ✅ Luftfuktighet - SEKUNDÆR indikator")

    # Bekreftelse
    if 'visibility' in available_critical:
        capabilities['confirmation'] += 1
        print("   ✅ Sikt - BEKREFTELSE indikator")

    if 'precipitation' in available_critical:
        capabilities['confirmation'] += 1
        print("   ✅ Nedbør - BEKREFTELSE indikator")

    # Samlet vurdering
    total_score = capabilities['primary_detection'] * 3 + capabilities['secondary_detection'] * 2 + capabilities['confirmation'] * 1
    max_score = 3 * 3 + 3 * 2 + 2 * 1  # 3 primære, 3 sekundære, 2 bekreftelse

    score_percent = (total_score / max_score) * 100

    print(f"\n🎯 SAMLET KAPABILITET: {score_percent:.1f}%")

    if score_percent >= 80:
        print("   🏆 UTMERKET - Full snøfokk-deteksjon mulig")
    elif score_percent >= 60:
        print("   ✅ GOD - Pålitelig snøfokk-deteksjon mulig")
    elif score_percent >= 40:
        print("   ⚠️ BEGRENSET - Grunnleggende snøfokk-deteksjon mulig")
    else:
        print("   ❌ UTILSTREKKELIG - Snøfokk-deteksjon vanskelig")

    # Spesifikke anbefalinger basert på dine observasjoner
    print("\n💡 ANBEFALINGER BASERT PÅ FYSISKE REALITETER:")
    print("1. Snøfokk kan ØKE snødybden ved målestasjon:")
    print("   → Bruk: Vindstyrke + positiv snødybde-endring")

    print("\n2. Snøfokk kan REDUSERE snødybden ved målestasjon:")
    print("   → Bruk: Vindstyrke + negativ snødybde-endring")

    print("\n3. 'USYNLIG' snøfokk (ingen snødybde-endring):")
    print("   → Bruk: Vindstyrke + temperatur + tilgjengelig snø")
    print("   → VIKTIG: Kan blokkere veier selv uten snødybde-endring!")

    print("\n4. Forbedret deteksjonsalgoritme:")
    if 'visibility' in available_critical:
        print("   ✅ Bruk siktdata som direkte snøfokk-indikator")
    if 'wind_gust' in available_critical:
        print("   ✅ Bruk vindkast for å identifisere turbulens")
    if 'precipitation' in available_critical:
        print("   ✅ Identifiser aktivt snøfall vs omblåsing")

    return capabilities

async def main():
    await analyze_gullingen_parameters()

if __name__ == '__main__':
    asyncio.run(main())
