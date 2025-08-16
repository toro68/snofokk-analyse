#!/usr/bin/env python3
"""
Simple Weather Data Test - Test med enkleste element-IDer og forskjellige oppløsninger
"""
import asyncio
import json
import sys
from datetime import date, datetime
from pathlib import Path

import aiohttp

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

class SimpleWeatherTester:
    """Test enkle element-IDer med forskjellige oppløsninger"""

    def __init__(self):
        self.station_id = 'SN46220'  # Gullingen Skisenter
        self.load_frost_key()

    def load_frost_key(self):
        """Last Frost API-nøkkel"""
        env_file = Path(__file__).parent.parent.parent / '.env'
        if env_file.exists():
            with open(env_file, encoding='utf-8') as f:
                for line in f:
                    if line.startswith('FROST_CLIENT_ID='):
                        self.client_id = line.split('=', 1)[1].strip()
                        break
        else:
            raise FileNotFoundError("❌ .env fil ikke funnet")

    async def test_element_with_resolutions(self, element_id, start_date, end_date):
        """Test ett element med forskjellige tidsoppløsninger"""

        resolutions = ['PT10M', 'PT1H', 'P1D']
        results = {}

        for resolution in resolutions:
            url = "https://frost.met.no/observations/v0.jsonld"

            params = {
                'sources': self.station_id,
                'elements': element_id,
                'referencetime': f"{start_date}/{end_date}",
                'fields': 'sourceId,referenceTime,elementId,value,unit',
                'timeoffsets': 'PT0H',
                'timeresolutions': resolution
            }

            headers = {
                'User-Agent': 'snofokk-analyse/1.0'
            }

            auth = aiohttp.BasicAuth(self.client_id, '')

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params, headers=headers, auth=auth) as response:
                        if response.status == 200:
                            data = await response.json()
                            observations = data.get('data', [])

                            valid_values = [obs['value'] for obs in observations if obs.get('value') is not None]

                            results[resolution] = {
                                'total_obs': len(observations),
                                'valid_values': len(valid_values),
                                'success_rate': len(valid_values) / len(observations) * 100 if observations else 0,
                                'sample_values': valid_values[:3] if valid_values else [],
                                'unit': observations[0].get('unit', 'N/A') if observations else 'N/A'
                            }
                        else:
                            results[resolution] = {'error': f"HTTP {response.status}"}
            except Exception as e:
                results[resolution] = {'error': str(e)}

        return results

    async def test_core_elements(self):
        """Test kjerne-elementer som bør finnes"""

        print("🧪 TESTER KJERNE VÆRELEMENTER")
        print("=" * 60)

        # Test periode - nyere data
        start_date = date(2024, 8, 1)
        end_date = date(2024, 8, 2)

        print(f"📅 Testperiode: {start_date} til {end_date}")

        # Enkleste mulige element-IDer
        core_elements = [
            'air_temperature',
            'surface_snow_thickness',
            'wind_speed',
            'wind_from_direction',
            'relative_humidity',
            'sum(precipitation_amount PT1H)',
            'surface_temperature'
        ]

        print(f"\n📊 TESTER {len(core_elements)} KJERNE-ELEMENTER:")
        print()

        working_combinations = []

        for element in core_elements:
            print(f"🔍 Tester: {element}")

            results = await self.test_element_with_resolutions(element, start_date, end_date)

            best_resolution = None
            best_success_rate = 0

            for resolution, result in results.items():
                if 'error' in result:
                    print(f"   ❌ {resolution}: {result['error']}")
                else:
                    success_rate = result['success_rate']
                    print(f"   📊 {resolution}: {result['valid_values']}/{result['total_obs']} verdier ({success_rate:.1f}%)")

                    if success_rate > best_success_rate:
                        best_success_rate = success_rate
                        best_resolution = resolution

                    if result['sample_values']:
                        print(f"      Eksempel: {result['sample_values']} {result['unit']}")

            if best_resolution and best_success_rate > 0:
                working_combinations.append({
                    'element': element,
                    'resolution': best_resolution,
                    'success_rate': best_success_rate,
                    'unit': results[best_resolution]['unit']
                })
                print(f"   ✅ BESTE: {best_resolution} ({best_success_rate:.1f}%)")
            else:
                print("   ❌ INGEN GYLDIGE DATA")

            print()

        return working_combinations

    async def generate_working_configuration(self, working_combinations):
        """Generer funksjonell konfigurasjon"""

        print("🛠️ GENERERER FUNKSJONELL KONFIGURASJON")
        print("=" * 60)

        if not working_combinations:
            print("❌ Ingen fungerende elementer funnet")
            return

        print("✅ FUNGERENDE ELEMENT-KOMBINASJONER:")
        for combo in working_combinations:
            print(f"   • {combo['element']} ({combo['resolution']}) - {combo['success_rate']:.1f}% data")

        # Generer kode
        print("\n💻 OPPDATERT ENHANCED DETECTOR KODE:")
        print("```python")
        print("# Korrekte element-IDer med tidsoppløsninger")
        print("critical_elements = [")

        element_mapping = {}

        for combo in working_combinations:
            element = combo['element']
            resolution = combo['resolution']

            # Lag unikt navn for hver kombinasjon
            if resolution == 'PT10M':
                key_name = element.replace('(', '_').replace(')', '_').replace(' ', '_') + '_10m'
            elif resolution == 'PT1H':
                key_name = element.replace('(', '_').replace(')', '_').replace(' ', '_') + '_1h'
            elif resolution == 'P1D':
                key_name = element.replace('(', '_').replace(')', '_').replace(' ', '_') + '_1d'
            else:
                key_name = element.replace('(', '_').replace(')', '_').replace(' ', '_')

            element_mapping[key_name] = {
                'element_id': element,
                'resolution': resolution,
                'unit': combo['unit']
            }

            print(f"    '{element}',  # {combo['unit']} - {resolution}")

        print("]")
        print("```")

        # Lag oppdatert konfig fil
        config_data = {
            'station_id': self.station_id,
            'station_name': 'Gullingen Skisenter',
            'working_elements': element_mapping,
            'test_date': datetime.now().isoformat(),
            'test_period': f"{date(2024, 8, 1)} to {date(2024, 8, 2)}",
            'success_rate': len(working_combinations)
        }

        output_file = Path(__file__).parent.parent.parent / 'config' / 'working_weather_elements.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Konfigurasjon lagret i {output_file}")

        # Forslag til neste steg
        print("\n🎯 NESTE STEG:")
        if len(working_combinations) >= 4:
            print("✅ Nok elementer for snøfokk-deteksjon")
            print("1. Oppdater enhanced_snowdrift_detector.py med nye element-IDer")
            print("2. Test snøfokk-deteksjon med ekte data")
            print("3. Juster terskler basert på faktiske verdier")
        else:
            print("⚠️ For få elementer - trenger flere værparametre")
            print("1. Test flere element-IDer")
            print("2. Sjekk om data er tilgjengelig for andre perioder")
            print("3. Vurder alternative stasjoner")

async def main():
    tester = SimpleWeatherTester()
    working_combinations = await tester.test_core_elements()
    await tester.generate_working_configuration(working_combinations)

if __name__ == '__main__':
    asyncio.run(main())
