#!/usr/bin/env python3
"""
KOMPLETT ANALYSE AV TILGJENGELIGE VÆRELEMENTER FOR GULLINGEN
Tester ALLE elementer fra gullingen_available_elements.json og identifiserer
hvilke som faktisk returnerer data vs HTTP 412/404 errors.
"""

import json
import requests
import os
from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, List, Tuple

class CompleteWeatherElementAnalyzer:
    def __init__(self):
        self.frost_client_id = os.getenv('FROST_CLIENT_ID')
        if not self.frost_client_id:
            with open('.env', 'r') as f:
                for line in f:
                    if line.startswith('FROST_CLIENT_ID='):
                        self.frost_client_id = line.split('=')[1].strip()
                        break
        
        self.station_id = "SN46220"  # Gullingen
        self.base_url = "https://frost.met.no/observations/v0.jsonld"
        
        # Test periode (kort for å spare API-kvoter)
        self.test_start = datetime(2023, 1, 10)
        self.test_end = datetime(2023, 1, 12)

    def load_all_available_elements(self) -> List[str]:
        """Last alle tilgjengelige elementer fra JSON-filen"""
        print("📊 Laster alle tilgjengelige elementer fra gullingen_available_elements.json...")
        
        with open('data/gullingen_available_elements.json', 'r') as f:
            data = json.load(f)
        
        elements = []
        for item in data['data']:
            elements.append(item['elementId'])
        
        # Fjern duplikater og sorter
        unique_elements = sorted(list(set(elements)))
        
        print(f"Totalt {len(unique_elements)} unike elementer funnet")
        return unique_elements

    def categorize_elements(self, elements: List[str]) -> Dict[str, List[str]]:
        """Kategoriser elementer etter type for bedre oversikt"""
        categories = {
            'nedbør': [],
            'temperatur': [],
            'vind': [],
            'snø': [],
            'fuktighet': [],
            'trykk': [],
            'skydekke': [],
            'sol_og_stråling': [],
            'sikt': [],
            'andre': []
        }
        
        for element in elements:
            element_lower = element.lower()
            
            if any(word in element_lower for word in ['precipitation', 'rain', 'duration_of_precipitation']):
                categories['nedbør'].append(element)
            elif any(word in element_lower for word in ['temperature', 'dew_point']):
                categories['temperatur'].append(element)
            elif any(word in element_lower for word in ['wind', 'gust']):
                categories['vind'].append(element)
            elif any(word in element_lower for word in ['snow', 'surface_snow']):
                categories['snø'].append(element)
            elif any(word in element_lower for word in ['humidity', 'relative_humidity']):
                categories['fuktighet'].append(element)
            elif any(word in element_lower for word in ['pressure', 'air_pressure']):
                categories['trykk'].append(element)
            elif any(word in element_lower for word in ['cloud', 'cloud_area_fraction']):
                categories['skydekke'].append(element)
            elif any(word in element_lower for word in ['radiation', 'sunshine', 'global_radiation']):
                categories['sol_og_stråling'].append(element)
            elif any(word in element_lower for word in ['visibility']):
                categories['sikt'].append(element)
            else:
                categories['andre'].append(element)
        
        return categories

    def test_element_availability(self, elements: List[str]) -> Dict[str, Dict]:
        """Test tilgjengelighet for alle elementer"""
        print(f"\n🧪 Tester tilgjengelighet for {len(elements)} elementer...")
        print(f"Testperiode: {self.test_start.date()} til {self.test_end.date()}")
        
        results = {
            'available': [],
            'unavailable': [],
            'errors': {},
            'data_counts': {}
        }
        
        for i, element in enumerate(elements, 1):
            print(f"  {i:3d}/{len(elements)}: {element[:50]}{'...' if len(element) > 50 else ''}", end=' ')
            
            try:
                params = {
                    'sources': self.station_id,
                    'elements': element,
                    'referencetime': f"{self.test_start.isoformat()}/{self.test_end.isoformat()}"
                }
                
                response = requests.get(
                    self.base_url, 
                    params=params,
                    auth=(self.frost_client_id, ''),
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data and data['data']:
                        observation_count = sum(len(item.get('observations', [])) for item in data['data'])
                        results['available'].append(element)
                        results['data_counts'][element] = observation_count
                        print(f"✅ ({observation_count} obs)")
                    else:
                        results['unavailable'].append(element)
                        results['errors'][element] = 'Ingen data i respons'
                        print("⚠️ (ingen data)")
                elif response.status_code == 412:
                    results['unavailable'].append(element)
                    results['errors'][element] = 'HTTP 412 - Ikke tilgjengelig'
                    print("❌ (412)")
                elif response.status_code == 404:
                    results['unavailable'].append(element)
                    results['errors'][element] = 'HTTP 404 - Ikke funnet'
                    print("❌ (404)")
                else:
                    results['unavailable'].append(element)
                    results['errors'][element] = f'HTTP {response.status_code}'
                    print(f"❌ ({response.status_code})")
                    
            except Exception as e:
                results['unavailable'].append(element)
                results['errors'][element] = f'Feil: {str(e)}'
                print(f"❌ (feil)")
        
        return results

    def identify_operationally_relevant_elements(self, available_elements: List[str]) -> Dict[str, List[str]]:
        """Identifiser operasjonelt relevante elementer basert på brøytekriterier"""
        
        operational_categories = {
            'nysnø_deteksjon': [],
            'snøfokk_prediksjon': [],
            'glattføre_varsling': [],
            'nedbørtype_klassifisering': [],
            'vindkjøling': [],
            'temperatur_overganger': [],
            'akkumulering_tracking': [],
            'datakvalitet_støtte': []
        }
        
        for element in available_elements:
            element_lower = element.lower()
            
            # Nysnø-deteksjon (6cm våt / 12cm tørr)
            if any(word in element_lower for word in [
                'surface_snow_thickness', 'snow_depth', 'precipitation_amount', 
                'accumulated(precipitation', 'sum(precipitation'
            ]):
                operational_categories['nysnø_deteksjon'].append(element)
            
            # Snøfokk-prediksjon (vindblåst løssnø)
            if any(word in element_lower for word in [
                'wind_speed', 'wind_gust', 'wind_from_direction', 
                'max(wind', 'mean(wind', 'surface_snow'
            ]):
                operational_categories['snøfokk_prediksjon'].append(element)
            
            # Glattføre-varsling (regn på snø, rimfrost)
            if any(word in element_lower for word in [
                'surface_temperature', 'dew_point', 'relative_humidity',
                'precipitation', 'rain', 'temperature'
            ]):
                operational_categories['glattføre_varsling'].append(element)
            
            # Nedbørtype-klassifisering
            if any(word in element_lower for word in [
                'precipitation', 'duration_of_precipitation', 'rain',
                'air_temperature', 'wind_speed'
            ]):
                operational_categories['nedbørtype_klassifisering'].append(element)
            
            # Vindkjøling (kombinert effekt)
            if any(word in element_lower for word in [
                'wind', 'air_temperature', 'surface_temperature'
            ]):
                operational_categories['vindkjøling'].append(element)
            
            # Temperaturoverganger (kritisk for nedbørtype)
            if any(word in element_lower for word in [
                'max(air_temperature', 'min(air_temperature', 
                'air_temperature', 'surface_temperature'
            ]):
                operational_categories['temperatur_overganger'].append(element)
            
            # Akkumulering-tracking (tunbrøyting-vurdering)
            if any(word in element_lower for word in [
                'sum(', 'accumulated(', 'max(', 'mean(', 'p1d', 'p1w'
            ]):
                operational_categories['akkumulering_tracking'].append(element)
            
            # Datakvalitet-støtte (for robusthet)
            if any(word in element_lower for word in [
                'pt1h', 'pt12h', 'p1d', 'quality', 'max(', 'min(', 'mean('
            ]):
                operational_categories['datakvalitet_støtte'].append(element)
        
        # Fjern duplikater
        for category in operational_categories:
            operational_categories[category] = list(set(operational_categories[category]))
        
        return operational_categories

    def generate_comprehensive_recommendations(self, 
                                            categorized_elements: Dict[str, List[str]],
                                            availability_results: Dict[str, Dict],
                                            operational_relevance: Dict[str, List[str]]) -> Dict:
        """Generer omfattende anbefalinger for værdata-bruk"""
        
        recommendations = {
            'critical_elements': [],
            'high_priority': [],
            'medium_priority': [],
            'supplementary': [],
            'operational_mapping': {},
            'missing_elements': [],
            'data_quality_assessment': {}
        }
        
        available_elements = availability_results['available']
        
        # Kritiske elementer (må ha for grunnleggende funksjonalitet)
        critical_candidates = [
            'air_temperature',
            'surface_temperature', 
            'wind_speed',
            'surface_snow_thickness',
            'sum(precipitation_amount PT1H)',
            'accumulated(precipitation_amount)',
            'relative_humidity'
        ]
        
        for element in critical_candidates:
            if element in available_elements:
                recommendations['critical_elements'].append(element)
            else:
                recommendations['missing_elements'].append(element)
        
        # Høy prioritet (viktig for presisjon)
        high_priority_candidates = [
            'max(wind_speed_of_gust PT1H)',
            'wind_from_direction',
            'dew_point_temperature',
            'sum(precipitation_amount P1D)',
            'max(air_temperature P1D)',
            'min(air_temperature P1D)',
            'sum(duration_of_precipitation PT1H)'
        ]
        
        for element in high_priority_candidates:
            if element in available_elements:
                recommendations['high_priority'].append(element)
        
        # Medium prioritet (nyttig for forbedret analyse)
        medium_priority_candidates = [
            'max(air_temperature PT1H)',
            'min(air_temperature PT1H)',
            'mean(air_temperature P1D)',
            'max(wind_speed P1D)',
            'mean(wind_speed P1D)',
            'sum(precipitation_amount PT12H)'
        ]
        
        for element in medium_priority_candidates:
            if element in available_elements:
                recommendations['medium_priority'].append(element)
        
        # Operasjonell mapping
        for op_category, elements in operational_relevance.items():
            available_for_category = [e for e in elements if e in available_elements]
            recommendations['operational_mapping'][op_category] = available_for_category
        
        # Datakvalitetsvurdering
        for element in available_elements:
            data_count = availability_results['data_counts'].get(element, 0)
            recommendations['data_quality_assessment'][element] = {
                'data_points': data_count,
                'quality': 'høy' if data_count >= 20 else 'moderat' if data_count >= 8 else 'lav',
                'frequency': data_count / 2 if data_count > 0 else 0  # Per dag over 2-dagers test
            }
        
        return recommendations

    def save_complete_analysis(self, 
                             all_elements: List[str],
                             categorized: Dict[str, List[str]],
                             availability: Dict[str, Dict],
                             operational: Dict[str, List[str]],
                             recommendations: Dict):
        """Lagre komplett analyse"""
        
        complete_analysis = {
            'analysis_date': datetime.now().isoformat(),
            'station_id': self.station_id,
            'test_period': {
                'start': self.test_start.isoformat(),
                'end': self.test_end.isoformat()
            },
            'summary': {
                'total_elements_tested': len(all_elements),
                'available_elements': len(availability['available']),
                'unavailable_elements': len(availability['unavailable']),
                'availability_rate': len(availability['available']) / len(all_elements) * 100
            },
            'categorized_elements': categorized,
            'availability_results': availability,
            'operational_relevance': operational,
            'recommendations': recommendations
        }
        
        # Lagre som JSON
        with open('data/analyzed/complete_weather_elements_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(complete_analysis, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n💾 Komplett analyse lagret til data/analyzed/complete_weather_elements_analysis.json")
        
        # Print oppsummering
        self._print_comprehensive_summary(all_elements, categorized, availability, operational, recommendations)

    def _print_comprehensive_summary(self, 
                                   all_elements: List[str],
                                   categorized: Dict[str, List[str]],
                                   availability: Dict[str, Dict],
                                   operational: Dict[str, List[str]],
                                   recommendations: Dict):
        """Print omfattende oppsummering"""
        
        print("\n" + "="*100)
        print("📊 KOMPLETT ANALYSE AV VÆRELEMENTER FOR GULLINGEN (SN46220)")
        print("="*100)
        
        print(f"\n📈 OVERORDNET STATISTIKK:")
        print(f"  Totalt testet: {len(all_elements)} elementer")
        print(f"  Tilgjengelige: {len(availability['available'])} elementer ({len(availability['available'])/len(all_elements)*100:.1f}%)")
        print(f"  Ikke tilgjengelige: {len(availability['unavailable'])} elementer ({len(availability['unavailable'])/len(all_elements)*100:.1f}%)")
        
        print(f"\n🗂️ KATEGORISERING AV ALLE ELEMENTER:")
        for category, elements in categorized.items():
            available_in_category = [e for e in elements if e in availability['available']]
            print(f"  {category.upper()}: {len(elements)} totalt, {len(available_in_category)} tilgjengelige")
        
        print(f"\n🎯 OPERASJONELLE ANBEFALINGER:")
        
        print(f"\n❗ KRITISKE ELEMENTER (må ha):")
        for element in recommendations['critical_elements']:
            data_quality = recommendations['data_quality_assessment'][element]
            print(f"  ✅ {element} ({data_quality['quality']} kvalitet, {data_quality['data_points']} datapunkter)")
        
        if recommendations['missing_elements']:
            print(f"\n⚠️ MANGLENDE KRITISKE ELEMENTER:")
            for element in recommendations['missing_elements']:
                print(f"  ❌ {element}")
        
        print(f"\n🔥 HØY PRIORITET:")
        for element in recommendations['high_priority']:
            data_quality = recommendations['data_quality_assessment'][element]
            print(f"  ✅ {element} ({data_quality['quality']} kvalitet, {data_quality['data_points']} datapunkter)")
        
        print(f"\n📊 MEDIUM PRIORITET:")
        for element in recommendations['medium_priority']:
            data_quality = recommendations['data_quality_assessment'][element]
            print(f"  ✅ {element} ({data_quality['quality']} kvalitet, {data_quality['data_points']} datapunkter)")
        
        print(f"\n🎯 OPERASJONELL DEKNING:")
        for op_category, elements in recommendations['operational_mapping'].items():
            print(f"  {op_category.upper()}: {len(elements)} tilgjengelige elementer")
            for element in elements[:3]:  # Vis top 3
                print(f"    - {element}")
            if len(elements) > 3:
                print(f"    ... og {len(elements)-3} flere")
        
        print(f"\n❌ VANLIGE FEILTYPER:")
        error_summary = {}
        for element, error in availability['errors'].items():
            error_type = error.split(' ')[0:2]  # First two words
            error_key = ' '.join(error_type)
            error_summary[error_key] = error_summary.get(error_key, 0) + 1
        
        for error_type, count in sorted(error_summary.items(), key=lambda x: x[1], reverse=True):
            print(f"  {error_type}: {count} elementer")
        
        print(f"\n🔑 ANBEFALTE KJERNEELEMENTER FOR APPEN:")
        all_recommended = (recommendations['critical_elements'] + 
                          recommendations['high_priority'])
        for i, element in enumerate(all_recommended, 1):
            print(f"  {i:2d}. {element}")
        
        print(f"\n📋 TOTAL ANBEFALING: {len(all_recommended)} kjerneelementer av {len(availability['available'])} tilgjengelige")

def main():
    analyzer = CompleteWeatherElementAnalyzer()
    
    # Last alle tilgjengelige elementer
    all_elements = analyzer.load_all_available_elements()
    
    # Kategoriser elementer
    categorized_elements = analyzer.categorize_elements(all_elements)
    
    # Test tilgjengelighet for alle elementer
    availability_results = analyzer.test_element_availability(all_elements)
    
    # Identifiser operasjonelt relevante elementer
    operational_relevance = analyzer.identify_operationally_relevant_elements(availability_results['available'])
    
    # Generer omfattende anbefalinger
    recommendations = analyzer.generate_comprehensive_recommendations(
        categorized_elements, availability_results, operational_relevance)
    
    # Lagre komplett analyse
    analyzer.save_complete_analysis(
        all_elements, categorized_elements, availability_results, 
        operational_relevance, recommendations)

if __name__ == "__main__":
    main()
