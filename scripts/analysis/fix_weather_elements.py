#!/usr/bin/env python3
"""
Fix Weather Data Elements - Finn korrekte element-IDer som faktisk leverer data
"""
import sys
from pathlib import Path
import asyncio
from datetime import datetime, date, timedelta
import json
import aiohttp

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

class WeatherElementFixer:
    """Finn og test korrekte element-IDer"""
    
    def __init__(self):
        self.station_id = 'SN46220'  # Gullingen Skisenter
        self.load_frost_key()
    
    def load_frost_key(self):
        """Last Frost API-nøkkel"""
        env_file = Path(__file__).parent.parent.parent / '.env'
        if env_file.exists():
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('FROST_CLIENT_ID='):
                        self.client_id = line.split('=', 1)[1].strip()
                        break
        else:
            raise FileNotFoundError("❌ .env fil ikke funnet")
    
    async def test_single_element(self, element_id, start_date, end_date):
        """Test ett enkelt element for å se om det leverer data"""
        
        url = "https://frost.met.no/observations/v0.jsonld"
        
        params = {
            'sources': self.station_id,
            'elements': element_id,
            'referencetime': f"{start_date}/{end_date}",
            'fields': 'sourceId,referenceTime,elementId,value,unit',
            'timeoffsets': 'PT0H',
            'timeresolutions': 'PT1H'
        }
        
        headers = {
            'User-Agent': 'snofokk-analyse/1.0'
        }
        
        auth = aiohttp.BasicAuth(self.client_id, '')
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, auth=auth) as response:
                if response.status == 200:
                    data = await response.json()
                    observations = data.get('data', [])
                    
                    # Finn verdier som ikke er None
                    valid_values = [obs['value'] for obs in observations if obs.get('value') is not None]
                    
                    return {
                        'element_id': element_id,
                        'total_observations': len(observations),
                        'valid_values': len(valid_values),
                        'success_rate': len(valid_values) / len(observations) * 100 if observations else 0,
                        'sample_values': valid_values[:5] if valid_values else [],
                        'unit': observations[0].get('unit', 'N/A') if observations else 'N/A'
                    }
                else:
                    return {
                        'element_id': element_id,
                        'error': f"API error: {response.status}",
                        'total_observations': 0,
                        'valid_values': 0,
                        'success_rate': 0
                    }
    
    async def find_working_elements(self):
        """Finn element-IDer som faktisk leverer data"""
        
        print("🔧 FINNER KORREKTE ELEMENT-IDer")
        print("=" * 60)
        
        # Test periode
        start_date = date(2024, 2, 15)  # Kort testperiode
        end_date = date(2024, 2, 16)
        
        print(f"🧪 Testperiode: {start_date} til {end_date}")
        
        # Element-IDer fra tilgjengelige data (basert på forrige analyse)
        test_elements = [
            # Vind (prioritet)
            'wind_speed',
            'max(wind_speed_of_gust PT1H)',
            'max(wind_speed PT1H)',
            'mean(wind_speed P1D)',
            'max_wind_speed(wind_from_direction PT1H)',
            'wind_from_direction',
            
            # Temperatur (prioritet)
            'air_temperature',
            'max(air_temperature PT1H)',
            'min(air_temperature PT1H)',
            'mean(air_temperature P1D)',
            'surface_temperature',
            
            # Snø (kritisk)
            'surface_snow_thickness',
            'mean(surface_snow_thickness P1M)',
            
            # Nedbør
            'sum(precipitation_amount PT1H)',
            'sum(precipitation_amount P1D)',
            'accumulated(precipitation_amount)',
            
            # Fuktighet
            'relative_humidity',
            'mean(relative_humidity P1D)'
        ]
        
        working_elements = {}
        failed_elements = []
        
        print(f"\n📊 TESTER {len(test_elements)} ELEMENT-IDer:")
        print()
        
        for element in test_elements:
            result = await self.test_single_element(element, start_date, end_date)
            
            if result.get('error'):
                failed_elements.append(element)
                print(f"❌ {element}: {result['error']}")
            elif result['valid_values'] > 0:
                working_elements[element] = result
                print(f"✅ {element}: {result['valid_values']}/{result['total_observations']} verdier ({result['success_rate']:.1f}%)")
                print(f"   Enhet: {result['unit']}, Eksempel: {result['sample_values']}")
            else:
                print(f"⚠️ {element}: {result['total_observations']} observasjoner, men ingen gyldige verdier")
        
        print(f"\n🎯 SAMMENDRAG:")
        print(f"✅ Fungerende elementer: {len(working_elements)}")
        print(f"❌ Feilede elementer: {len(failed_elements)}")
        print(f"⚠️ Tomme elementer: {len(test_elements) - len(working_elements) - len(failed_elements)}")
        
        # Kategoriser fungerende elementer
        if working_elements:
            print(f"\n📋 FUNGERENDE ELEMENTER KATEGORISERT:")
            
            categories = {
                'Vind': [],
                'Temperatur': [],
                'Snø': [],
                'Nedbør': [],
                'Fuktighet': [],
                'Andre': []
            }
            
            for element_id, result in working_elements.items():
                element_lower = element_id.lower()
                
                if any(word in element_lower for word in ['wind', 'vind']):
                    categories['Vind'].append((element_id, result))
                elif any(word in element_lower for word in ['temp', 'temperature']):
                    categories['Temperatur'].append((element_id, result))
                elif any(word in element_lower for word in ['snow', 'snø']):
                    categories['Snø'].append((element_id, result))
                elif any(word in element_lower for word in ['precip', 'rain', 'sum(']):
                    categories['Nedbør'].append((element_id, result))
                elif any(word in element_lower for word in ['humid', 'fukt']):
                    categories['Fuktighet'].append((element_id, result))
                else:
                    categories['Andre'].append((element_id, result))
            
            for category, items in categories.items():
                if items:
                    print(f"\n🏷️ {category.upper()}:")
                    for element_id, result in items:
                        print(f"   • {element_id} ({result['success_rate']:.1f}% data)")
        
        # Generer oppdatert kode
        if working_elements:
            print(f"\n💻 OPPDATERT KODE FOR ENHANCED DETECTOR:")
            print("critical_elements = [")
            
            # Prioriter elementer
            priority_elements = []
            
            # Finn beste element for hver kategori
            wind_elements = [elem for elem in working_elements.keys() if 'wind_speed' in elem]
            temp_elements = [elem for elem in working_elements.keys() if 'air_temperature' in elem]
            snow_elements = [elem for elem in working_elements.keys() if 'snow' in elem]
            precip_elements = [elem for elem in working_elements.keys() if 'precipitation' in elem]
            humid_elements = [elem for elem in working_elements.keys() if 'humidity' in elem]
            
            if wind_elements:
                best_wind = max(wind_elements, key=lambda x: working_elements[x]['success_rate'])
                priority_elements.append(f"    '{best_wind}',  # Vind")
            
            if temp_elements:
                best_temp = max(temp_elements, key=lambda x: working_elements[x]['success_rate'])
                priority_elements.append(f"    '{best_temp}',  # Temperatur")
            
            if snow_elements:
                best_snow = max(snow_elements, key=lambda x: working_elements[x]['success_rate'])
                priority_elements.append(f"    '{best_snow}',  # Snødybde")
            
            if precip_elements:
                best_precip = max(precip_elements, key=lambda x: working_elements[x]['success_rate'])
                priority_elements.append(f"    '{best_precip}',  # Nedbør")
            
            if humid_elements:
                best_humid = max(humid_elements, key=lambda x: working_elements[x]['success_rate'])
                priority_elements.append(f"    '{best_humid}',  # Fuktighet")
            
            for elem in priority_elements:
                print(elem)
            print("]")
        
        return working_elements

async def main():
    fixer = WeatherElementFixer()
    await fixer.find_working_elements()

if __name__ == '__main__':
    asyncio.run(main())
