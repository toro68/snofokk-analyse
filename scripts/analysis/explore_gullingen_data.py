#!/usr/bin/env python3
"""
Gullingen Weather Station Data Explorer - Utforsker tilgjengelige værdata fra Gullingen
"""
import sys
from pathlib import Path
import asyncio
from datetime import datetime, date, timedelta

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from snofokk.config import settings
from snofokk.services.weather import WeatherService

class GullingenDataExplorer:
    """Utforsker værdata fra Gullingen værstasjon"""
    
    def __init__(self):
        self.weather_service = WeatherService()
        self.gullingen_stations = [
            # Mulige Gullingen-stasjoner (vi må finne riktig ID)
            'SN18700',  # Gullknapp
            'SN18701',  # Mulig Gullingen
            'SN18702',  # Alternativ
            'SN47270',  # Gullingen automatisk
            'SN25830',  # Gullingen manuell
        ]
    
    async def find_gullingen_station(self):
        """Finn riktig Gullingen stasjon-ID"""
        print("🔍 SØKER ETTER GULLINGEN VÆRSTASJON")
        print("=" * 60)
        
        # Test ulike potensielle stasjons-IDer
        for station_id in self.gullingen_stations:
            print(f"\n📡 Tester stasjon {station_id}...")
            
            try:
                # Test med nylig data
                test_data = await self.weather_service.get_historical_data(
                    station_id=station_id,
                    start_date=date(2025, 8, 1),
                    end_date=date(2025, 8, 8)
                )
                
                if test_data:
                    print(f"   ✅ Fant data: {len(test_data)} datapunkter")
                    await self.analyze_station_details(station_id, test_data[:5])  # Vis første 5 punkter
                else:
                    print(f"   ❌ Ingen data tilgjengelig")
                    
            except Exception as e:
                print(f"   ❌ Feil: {e}")
        
        # Prøv også å søke generelt etter Gullingen
        await self.search_by_name()
    
    async def search_by_name(self):
        """Søk etter stasjoner med 'Gullingen' i navnet"""
        print(f"\n🔍 GENERELT SØK ETTER 'GULLINGEN'")
        print("(Dette krever manuell sjekk av Frost API dokumentasjon)")
        print("Vanlige Gullingen-stasjoner i Norge:")
        print("   • Gullingen (Oppland)")
        print("   • Gullingen (Troms)")
        print("   • Gulliksen")
        print("   • Gullknapp")
        
        # Prøv noen vanlige formater
        common_formats = [
            'GULLINGEN',
            'Gullingen', 
            'gullingen',
            'GULLKNAPP',
            'Gulliksen'
        ]
        
        print(f"\nAnbefaling: Sjekk https://frost.met.no/stations for eksakt stasjon-ID")
    
    async def analyze_station_details(self, station_id, sample_data):
        """Analyser detaljene for en stasjon"""
        print(f"\n📊 DETALJER FOR STASJON {station_id}:")
        
        if not sample_data:
            print("   Ingen prøvedata tilgjengelig")
            return
        
        # Analyser første datapunkt for å se tilgjengelige parametre
        first_point = sample_data[0]
        
        print(f"   Timestamp: {first_point.get('timestamp', 'N/A')}")
        print(f"   Tilgjengelige parametre:")
        
        for key, value in first_point.items():
            if key != 'timestamp':
                unit = ""
                if 'temperature' in key.lower():
                    unit = "°C"
                elif 'wind' in key.lower():
                    unit = "m/s" if 'speed' in key.lower() else "°"
                elif 'precipitation' in key.lower():
                    unit = "mm"
                elif 'snow' in key.lower():
                    unit = "cm"
                elif 'humidity' in key.lower():
                    unit = "%"
                elif 'pressure' in key.lower():
                    unit = "hPa"
                
                print(f"     • {key}: {value} {unit}")
    
    async def comprehensive_parameter_analysis(self, station_id):
        """Omfattende analyse av alle tilgjengelige parametre"""
        print(f"\n🔬 OMFATTENDE PARAMETERANALYSE FOR {station_id}")
        print("=" * 60)
        
        # Hent data fra en vinterperiode for å få alle snø-relaterte parametre
        winter_data = await self.weather_service.get_historical_data(
            station_id=station_id,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31)
        )
        
        if not winter_data:
            print("❌ Ingen vinterdata tilgjengelig")
            return
        
        print(f"📈 Analyserer {len(winter_data)} vinter-datapunkter...")
        
        # Samle alle unike parametre
        all_parameters = set()
        for point in winter_data:
            all_parameters.update(point.keys())
        
        # Kategoriser parametre
        categories = {
            'temperature': [],
            'wind': [],
            'snow': [],
            'precipitation': [],
            'humidity': [],
            'pressure': [],
            'visibility': [],
            'other': []
        }
        
        for param in sorted(all_parameters):
            if param == 'timestamp':
                continue
            
            param_lower = param.lower()
            if 'temp' in param_lower:
                categories['temperature'].append(param)
            elif 'wind' in param_lower:
                categories['wind'].append(param)
            elif 'snow' in param_lower:
                categories['snow'].append(param)
            elif 'precip' in param_lower or 'rain' in param_lower:
                categories['precipitation'].append(param)
            elif 'humid' in param_lower:
                categories['humidity'].append(param)
            elif 'pressure' in param_lower:
                categories['pressure'].append(param)
            elif 'vis' in param_lower:
                categories['visibility'].append(param)
            else:
                categories['other'].append(param)
        
        # Presenter kategoriserte parametre
        print("\n📋 TILGJENGELIGE PARAMETRE (KATEGORISERT):")
        
        for category, params in categories.items():
            if params:
                print(f"\n🏷️ {category.upper()}:")
                for param in params:
                    # Finn eksempelverdi
                    example_value = None
                    for point in winter_data[:10]:  # Sjekk første 10 punkter
                        if param in point and point[param] is not None:
                            example_value = point[param]
                            break
                    
                    if example_value is not None:
                        print(f"   • {param}: {example_value}")
                    else:
                        print(f"   • {param}: (ingen data)")
        
        # Analyser relevans for snøfokk-deteksjon
        await self.analyze_snowdrift_relevance(winter_data, categories)
    
    async def analyze_snowdrift_relevance(self, data, categories):
        """Analyser hvilke parametre som er mest relevante for snøfokk-deteksjon"""
        print(f"\n🎯 SNØFOKK-RELEVANS ANALYSE")
        print("=" * 60)
        
        # Viktige parametre for snøfokk
        critical_params = {
            'wind_speed': '💨 Kritisk for snøfokk-dannelse',
            'wind_direction': '🧭 Viktig for snøfokk-retning',
            'wind_gust': '💨 Kan indikere turbulens',
            'temperature': '🌡️ Påvirker snøkvalitet',
            'snow_depth': '❄️ Tilgjengelig snø for transport',
            'precipitation': '🌨️ Aktivt snøfall',
            'humidity': '💧 Påvirker snøadhesjon',
            'visibility': '👁️ Direkte mål på snøfokk-intensitet',
            'pressure': '🌀 Indikerer værsystemer'
        }
        
        print("🔍 PARAMETERRELEVANS FOR SNØFOKK:")
        
        available_critical = []
        missing_critical = []
        
        all_params = set()
        for point in data:
            all_params.update(point.keys())
        
        for param_type, description in critical_params.items():
            found_params = [p for p in all_params if param_type.replace('_', '') in p.lower().replace('_', '')]
            
            if found_params:
                available_critical.extend(found_params)
                print(f"   ✅ {description}")
                for param in found_params:
                    print(f"      → {param}")
            else:
                missing_critical.append(param_type)
                print(f"   ❌ {description} - IKKE TILGJENGELIG")
        
        # Spesifikk analyse for snøfokk-fysikk
        print(f"\n🧪 SNØFOKK-FYSIKK ANALYSE:")
        print("Basert på dine observasjoner:")
        
        print("\n1️⃣ SNØFOKK KAN ØKE SNØDYBDEN:")
        print("   • Snø transporteres til målestasjon")
        print("   • Snøhauger dannes rundt måleutstyr")
        print("   • Behov: Vinddata + snødybde-økning")
        
        print("\n2️⃣ SNØFOKK KAN REDUSERE SNØDYBDEN:")
        print("   • Snø blåses vekk fra måleområde")
        print("   • Eksponerte områder blir snøbare")
        print("   • Behov: Vinddata + snødybde-reduksjon")
        
        print("\n3️⃣ 'USYNLIG' SNØFOKK (INGEN SNØDYBDE-ENDRING):")
        print("   • Snø blåser forbi uten å akkumulere")
        print("   • Konstant transport uten netto endring")
        print("   • KRITISK: Kan blokkere veier likevel!")
        print("   • Behov: Vinddata + temperatur + visibilitet")
        
        # Forslag til forbedret deteksjon
        print(f"\n💡 FORBEDRET DETEKSJONSMETODE:")
        print("1. Primærindikatorer:")
        print("   • Vindstyrke > 9 m/s")
        print("   • Temperatur < -3°C")
        print("   • Tilgjengelig snø (dybde eller nylig snøfall)")
        
        print("\n2. Sekundærindikatorer:")
        print("   • Vindkast (turbulens)")
        print("   • Redusert sikt/visibilitet")
        print("   • Luftfuktighet")
        
        print("\n3. Bekreftelsessignaler:")
        print("   • Snødybde-endring (økning ELLER reduksjon)")
        print("   • Vedvarende vind i samme retning")
        print("   • Aktivt snøfall eller nylig snøfall")
        
        print("\n4. Spesialcaser:")
        print("   • ADVARSEL ved høy vind + tilgjengelig snø, selv uten snødybde-endring")
        print("   • Ekstra fokus på veikryss og eksponerte strekninger")
        
        return available_critical, missing_critical

async def main():
    explorer = GullingenDataExplorer()
    await explorer.find_gullingen_station()
    
    # Hvis vi finner en gyldig stasjon, gjør omfattende analyse
    print(f"\n" + "="*60)
    print("📋 NESTE STEG:")
    print("1. Identifiser korrekt Gullingen stasjon-ID")
    print("2. Implementer multi-parameter snøfokk-deteksjon")
    print("3. Test ny deteksjonsmetode mot kjente hendelser")
    print("4. Integrer med vei-spesifikke algoritmer")

if __name__ == '__main__':
    asyncio.run(main())
