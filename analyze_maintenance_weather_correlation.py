#!/usr/bin/env python3
"""
Analyser korrelasjon mellom brøytedata og værelementer fra Gullingen stasjon
for å identifisere optimale parametere for deteksjon av:
- Nysnø (utløser brøyting)
- Glatte veier (utløser strøing)
- Snøfokk (utløser ekstra vedlikehold)
"""

import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta
import os
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
import seaborn as sns

class MaintenanceWeatherAnalyzer:
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
        
        # Kritiske værelementer for analyse
        self.key_elements = [
            "air_temperature",
            "surface_temperature", 
            "sum(precipitation_amount PT1H)",
            "accumulated(precipitation_amount)",
            "surface_snow_thickness",
            "wind_speed",
            "wind_from_direction",
            "relative_humidity",
            "dew_point_temperature"
        ]

    def load_maintenance_data(self) -> pd.DataFrame:
        """Last brøytedata og konverter til standardformat"""
        print("📊 Laster brøytedata...")
        
        # Les CSV med korrekt separator
        df = pd.read_csv('data/analyzed/Rapport 2022-2025.csv', sep=';')
        
        # Fjern totalsumraden
        df = df[df['Dato'] != 'Totalt']
        
        print(f"Antall vedlikeholdsoperasjoner: {len(df)}")
        print(f"Periode: {df['Dato'].min()} til {df['Dato'].max()}")
        
        # Konverter dato og tid med manuell månedsmapping
        month_mapping = {
            'jan.': '01', 'feb.': '02', 'mars': '03', 'apr.': '04',
            'mai': '05', 'jun.': '06', 'jul.': '07', 'aug.': '08',
            'sep.': '09', 'okt.': '10', 'nov.': '11', 'des.': '12'
        }
        
        def convert_norwegian_date(date_str, time_str):
            try:
                # Parse "21. des. 2022" format
                parts = date_str.split()
                if len(parts) >= 3:
                    day = parts[0].rstrip('.')
                    month = month_mapping.get(parts[1], '01')
                    year = parts[2]
                    
                    return pd.to_datetime(f"{year}-{month}-{day.zfill(2)} {time_str}")
            except (ValueError, IndexError, KeyError):
                pass
            return pd.NaT
        
        df['datetime'] = df.apply(lambda x: convert_norwegian_date(x['Dato'], x['Starttid']), axis=1)
        
        # Fjern rader uten gyldig dato
        df = df.dropna(subset=['datetime'])
        
        # Analyser operasjonstyper basert på varighet og distanse
        df['duration_hours'] = df['Varighet'].apply(self._parse_duration)
        df['distance_km'] = df['Distanse (km)']
        
        # Klassifiser operasjoner
        df['operation_type'] = df.apply(self._classify_operation, axis=1)
        
        print("Operasjonstyper:")
        print(df['operation_type'].value_counts())
        
        return df.sort_values('datetime')

    def _parse_duration(self, duration_str: str) -> float:
        """Konverter varighet til timer"""
        try:
            if ':' in duration_str:
                parts = duration_str.split(':')
                hours = float(parts[0])
                minutes = float(parts[1])
                seconds = float(parts[2]) if len(parts) > 2 else 0
                return hours + minutes/60 + seconds/3600
        except (ValueError, TypeError):
            pass
        return 0.0

    def _classify_operation(self, row) -> str:
        """Klassifiser operasjonstype basert på varighet og distanse"""
        duration = row['duration_hours']
        distance = row['distance_km']
        
        # Heuristikk basert på observerte mønstre
        if duration > 4:
            return "major_storm"  # Store snøfall
        elif duration > 2:
            return "moderate_snow"  # Moderat snøfall
        elif distance > 20:
            return "extensive_clearing"  # Omfattende rydding
        elif duration < 0.5:
            return "spot_treatment"  # Punktbehandling/strøing
        else:
            return "routine_plowing"  # Rutinemessig brøyting

    def get_weather_data(self, start_date: datetime, end_date: datetime, 
                        elements: List[str]) -> Dict:
        """Hent værdata fra Frost API"""
        print(f"🌡️ Henter værdata for {start_date.date()} til {end_date.date()}")
        
        weather_data = {}
        
        for element in elements:
            try:
                params = {
                    'sources': self.station_id,
                    'elements': element,
                    'referencetime': f"{start_date.isoformat()}/{end_date.isoformat()}"
                }
                
                response = requests.get(
                    self.base_url, 
                    params=params,
                    auth=(self.frost_client_id, '')
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data:
                        weather_data[element] = self._process_weather_data(data['data'])
                        print(f"  ✅ {element}: {len(weather_data[element])} observasjoner")
                    else:
                        print(f"  ❌ {element}: Ingen data")
                else:
                    print(f"  ❌ {element}: HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"  ❌ {element}: Feil - {e}")
        
        return weather_data

    def _process_weather_data(self, api_data: List) -> pd.DataFrame:
        """Prosesser værdata fra API til DataFrame"""
        records = []
        
        for item in api_data:
            for obs in item.get('observations', []):
                records.append({
                    'datetime': pd.to_datetime(item['referenceTime']),
                    'value': obs.get('value'),
                    'unit': obs.get('unit')
                })
        
        if records:
            df = pd.DataFrame(records)
            return df.set_index('datetime').sort_index()
        return pd.DataFrame()

    def analyze_correlations(self, maintenance_df: pd.DataFrame) -> Dict:
        """Analyser korrelasjon mellom vedlikehold og vær"""
        print("🔍 Analyserer værhendelser rundt vedlikeholdsoperasjoner...")
        
        correlations = {}
        
        # Grupper vedlikehold etter dag for å redusere API-kall
        daily_maintenance = maintenance_df.groupby(maintenance_df['datetime'].dt.date).agg({
            'operation_type': lambda x: list(x),
            'duration_hours': 'sum',
            'distance_km': 'sum',
            'datetime': 'min'
        })
        daily_maintenance = daily_maintenance.reset_index(drop=True)
        
        print(f"Analyserer {len(daily_maintenance)} dager med vedlikehold")
        
        # Analyser perioder med høy aktivitet
        high_activity_days = daily_maintenance[
            (daily_maintenance['duration_hours'] > 3) | 
            (daily_maintenance['distance_km'] > 20)
        ].copy()
        
        print(f"Identifiserte {len(high_activity_days)} dager med høy aktivitet")
        
        # Hent værdata for kritiske perioder
        for idx, day_data in high_activity_days.iterrows():
            date = day_data['datetime']
            start_time = date - timedelta(hours=12)  # 12 timer før
            end_time = date + timedelta(hours=12)    # 12 timer etter
            
            print(f"\n📅 Analyserer {date.date()}: {day_data['operation_type']}")
            
            weather_data = self.get_weather_data(start_time, end_time, self.key_elements)
            
            # Analyser værforhold
            analysis = self._analyze_weather_conditions(weather_data, date)
            correlations[date.date()] = {
                'maintenance': day_data.to_dict(),
                'weather': analysis
            }
        
        return correlations

    def _analyze_weather_conditions(self, weather_data: Dict, event_time: datetime) -> Dict:
        """Analyser værforhold rundt en vedlikeholdshendelse"""
        analysis = {}
        
        # Konverter event_time til UTC hvis det ikke allerede har timezone
        if event_time.tzinfo is None:
            import pytz
            event_time = pytz.timezone('Europe/Oslo').localize(event_time)
        
        for element, data in weather_data.items():
            if data.empty:
                continue
                
            # Finn nærmeste observasjoner til hendelsen
            time_diff = abs(data.index - event_time)
            closest_idx = time_diff.argmin()
            
            analysis[element] = {
                'value_at_event': data.iloc[closest_idx]['value'],
                'min_24h': data['value'].min(),
                'max_24h': data['value'].max(),
                'mean_24h': data['value'].mean(),
                'trend_before': self._calculate_trend(data, event_time, hours_before=6),
                'trend_after': self._calculate_trend(data, event_time, hours_after=6)
            }
        
        return analysis

    def _calculate_trend(self, data: pd.DataFrame, reference_time: datetime, 
                        hours_before: int = 0, hours_after: int = 0) -> float:
        """Beregn trend i data før eller etter referansetidspunkt"""
        # Konverter reference_time til samme timezone som data
        if reference_time.tzinfo is None:
            import pytz
            reference_time = pytz.timezone('Europe/Oslo').localize(reference_time)
        
        if hours_before > 0:
            period_data = data[
                (data.index >= reference_time - timedelta(hours=hours_before)) &
                (data.index <= reference_time)
            ]
        elif hours_after > 0:
            period_data = data[
                (data.index >= reference_time) &
                (data.index <= reference_time + timedelta(hours=hours_after))
            ]
        else:
            return 0.0
        
        if len(period_data) < 2:
            return 0.0
        
        # Enkel lineær trend
        x = np.arange(len(period_data))
        y = period_data['value'].values
        return np.polyfit(x, y, 1)[0]  # Slope

    def identify_key_indicators(self, correlations: Dict) -> Dict:
        """Identifiser viktigste værindikatorer for vedlikeholdsbehov"""
        print("\n🎯 Identifiserer viktigste værindikatorer...")
        
        # Definer kategorikonstanter
        CATEGORY_NYSNO = 'nysnø'
        CATEGORY_GLATT = 'glatte_veier'
        CATEGORY_SNOFOKK = 'snøfokk'
        
        indicators = {
            CATEGORY_NYSNO: [],
            CATEGORY_GLATT: [],
            CATEGORY_SNOFOKK: []
        }
        
        for date, data in correlations.items():
            maintenance = data['maintenance']
            weather = data['weather']
            
            # Klassifiser vedlikeholdstype basert på operasjoner
            ops = maintenance['operation_type']
            
            if any('storm' in op or 'extensive' in op for op in ops):
                category = CATEGORY_NYSNO
            elif any('spot' in op for op in ops):
                category = CATEGORY_GLATT
            elif any('moderate' in op for op in ops):
                category = CATEGORY_SNOFOKK
            else:
                category = CATEGORY_NYSNO  # Default
            
            # Ekstraher relevante værparametre
            weather_summary = {}
            for element, stats in weather.items():
                if stats:
                    weather_summary[element] = {
                        'value': stats['value_at_event'],
                        'trend_before': stats['trend_before'],
                        'min_max_diff': stats['max_24h'] - stats['min_24h']
                    }
            
            indicators[category].append({
                'date': date,
                'weather': weather_summary,
                'maintenance_hours': maintenance['duration_hours'],
                'distance_km': maintenance['distance_km']
            })
        
        return indicators

    def generate_recommendations(self, indicators: Dict) -> Dict:
        """Generer anbefalinger for hvilke værelementer som bør brukes"""
        print("\n📋 Genererer anbefalinger...")
        
        recommendations = {}
        
        for category, events in indicators.items():
            if not events:
                continue
                
            print(f"\n{category.upper()}:")
            print(f"  Antall hendelser: {len(events)}")
            
            # Analyser hvilke parametre som er mest relevante
            param_importance = self._analyze_parameter_importance(events)
            
            # Beregn viktighet for hver parameter
            element_scores = self._calculate_element_scores(param_importance)
            
            # Sorter etter viktighet
            sorted_elements = sorted(element_scores.items(), key=lambda x: x[1], reverse=True)
            
            recommendations[category] = {
                'primary_indicators': sorted_elements[:3],
                'all_scores': sorted_elements,
                'event_count': len(events)
            }
            
            print("  Viktigste indikatorer:")
            for element, score in sorted_elements[:3]:
                print(f"    {element}: {score:.2f}")
        
        return recommendations

    def _analyze_parameter_importance(self, events: List[Dict]) -> Dict:
        """Analyser viktighet av parametre basert på hendelser"""
        param_importance = {}
        
        for event in events:
            for element, stats in event['weather'].items():
                if element not in param_importance:
                    param_importance[element] = []
                
                # Vekt basert på vedlikeholdsintensitet
                weight = event['maintenance_hours'] + event['distance_km'] / 10
                param_importance[element].append({
                    'value': abs(stats.get('value', 0)),
                    'trend': abs(stats.get('trend_before', 0)),
                    'variability': stats.get('min_max_diff', 0),
                    'weight': weight
                })
        
        return param_importance

    def _calculate_element_scores(self, param_importance: Dict) -> Dict:
        """Beregn skår for hvert værelement"""
        element_scores = {}
        
        for element, measurements in param_importance.items():
            if measurements:
                weighted_score = sum(
                    (m['value'] * 0.4 + m['trend'] * 0.3 + m['variability'] * 0.3) * m['weight']
                    for m in measurements
                ) / len(measurements)
                element_scores[element] = weighted_score
        
        return element_scores

    def save_analysis(self, correlations: Dict, indicators: Dict, recommendations: Dict):
        """Lagre analyseresultater"""
        results = {
            'analysis_date': datetime.now().isoformat(),
            'station_id': self.station_id,
            'correlations': {str(k): v for k, v in correlations.items()},
            'indicators': indicators,
            'recommendations': recommendations,
            'summary': {
                'total_events_analyzed': len(correlations),
                'key_elements_tested': self.key_elements,
                'recommendations_by_category': {
                    cat: [elem[0] for elem in rec['primary_indicators']] 
                    for cat, rec in recommendations.items()
                }
            }
        }
        
        # Lagre som JSON
        with open('data/analyzed/maintenance_weather_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        print("\n💾 Analyse lagret til data/analyzed/maintenance_weather_analysis.json")
        
        # Generer oppsummering
        self._print_summary(recommendations)

    def _print_summary(self, recommendations: Dict):
        """Print oppsummering av anbefalinger"""
        print("\n" + "="*60)
        print("📊 OPPSUMMERING: OPTIMALE VÆRELEMENTER")
        print("="*60)
        
        print("\n🎯 ANBEFALTE ELEMENTER FRA GULLINGEN FOR HVER KATEGORI:")
        
        all_recommended = set()
        
        for category, data in recommendations.items():
            print(f"\n{category.upper()}:")
            for i, (element, score) in enumerate(data['primary_indicators'], 1):
                print(f"  {i}. {element} (viktighet: {score:.1f})")
                all_recommended.add(element)
            print(f"  Basert på {data['event_count']} hendelser")
        
        print(f"\n🔑 TOTALT {len(all_recommended)} UNIKE ELEMENTER ANBEFALT:")
        for element in sorted(all_recommended):
            print(f"  - {element}")
        
        print(f"\n📈 TILGJENGELIGE AV {len(self.key_elements)} TESTEDE ELEMENTER")
        
        # Sjekk tilgjengelighet i gullingen_available_elements.json
        try:
            with open('data/gullingen_available_elements.json', 'r') as f:
                available_elements = json.load(f)
            
            available_ids = {item['elementId'] for item in available_elements['data']}
            
            print("\n✅ TILGJENGELIGE ELEMENTER PÅ GULLINGEN:")
            available_recommended = all_recommended.intersection(available_ids)
            for element in sorted(available_recommended):
                print(f"  ✅ {element}")
            
            print("\n❌ IKKE TILGJENGELIGE ELEMENTER:")
            missing_recommended = all_recommended - available_ids
            for element in sorted(missing_recommended):
                print(f"  ❌ {element}")
            
            print(f"\n📊 DEKNING: {len(available_recommended)}/{len(all_recommended)} "
                  f"({100*len(available_recommended)/len(all_recommended):.1f}%)")
                  
        except FileNotFoundError:
            print("⚠️  Kunne ikke sjekke tilgjengelighet - gullingen_available_elements.json ikke funnet")

def main():
    analyzer = MaintenanceWeatherAnalyzer()
    
    # Last vedlikeholdsdata
    maintenance_df = analyzer.load_maintenance_data()
    
    # Analyser korrelasjoner
    correlations = analyzer.analyze_correlations(maintenance_df)
    
    # Identifiser nøkkelindikatorer
    indicators = analyzer.identify_key_indicators(correlations)
    
    # Generer anbefalinger
    recommendations = analyzer.generate_recommendations(indicators)
    
    # Lagre resultater
    analyzer.save_analysis(correlations, indicators, recommendations)

if __name__ == "__main__":
    main()
