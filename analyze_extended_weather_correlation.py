#!/usr/bin/env python3
"""
Utvidet analyse med alternative værelementer for vinterveivedlikehold.
Fokuserer på vindkjøling, vindkast, temperaturvariasjoner og andre faktorer
som kan være kritiske for snøfokk og vedlikeholdsbehov.
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

class ExtendedMaintenanceWeatherAnalyzer:
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
        
        # Utvidede værelementer med fokus på snøfokk-faktorer
        self.extended_elements = [
            # Vindkjøling og vindkast (kritisk for snøfokk)
            "max(wind_speed_of_gust PT1H)",
            "max(wind_speed PT1H)", 
            "mean(wind_speed_of_gust P1D)",
            "max(wind_speed_of_gust P1D)",
            
            # Temperaturvariasjoner (viktig for snøkonsistens)
            "max(air_temperature P1D)",
            "min(air_temperature P1D)",
            "mean(air_temperature P1D)",
            "max(surface_temperature P1D)",
            "min(surface_temperature P1D)",
            
            # Nedbør i forskjellige timeperioder
            "sum(precipitation_amount P1D)",
            "max(precipitation_amount_hourly P1D)",
            "sum(precipitation_amount PT6H)",
            
            # Snøforhold
            "max(surface_snow_thickness P1D)",
            "mean(surface_snow_thickness P1D)",
            
            # Andre relevante faktorer
            "min(relative_humidity P1D)",
            "max(relative_humidity P1D)",
            "mean(relative_humidity P1D)"
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
        
        # Forbedret heuristikk for å identifisere snøfokk-situasjoner
        if duration > 6:
            return "extreme_storm"  # Ekstreme værforhold
        elif duration > 4:
            return "major_storm"  # Store snøfall
        elif distance > 30:
            return "extensive_clearing"  # Omfattende rydding (kan indikere snøfokk)
        elif distance > 20 and duration > 2:
            return "moderate_storm_with_drift"  # Moderat snøfall med mulig fokk
        elif duration > 2:
            return "moderate_snow"  # Moderat snøfall
        elif distance > 15:
            return "drift_clearing"  # Sannsynlig snøfokk-rydding
        elif duration < 0.5:
            return "spot_treatment"  # Punktbehandling/strøing
        else:
            return "routine_plowing"  # Rutinemessig brøyting

    def get_weather_data(self, start_date: datetime, end_date: datetime, 
                        elements: List[str]) -> Dict:
        """Hent værdata fra Frost API"""
        print(f"🌡️ Henter utvidede værdata for {start_date.date()} til {end_date.date()}")
        
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
        """Analyser korrelasjon mellom vedlikehold og utvidede værelementer"""
        print("🔍 Analyserer utvidede værhendelser rundt vedlikeholdsoperasjoner...")
        
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
        
        # Fokuser på dager med høy aktivitet og potensielle snøfokk-indikatorer
        high_activity_days = daily_maintenance[
            (daily_maintenance['duration_hours'] > 3) | 
            (daily_maintenance['distance_km'] > 20) |
            (daily_maintenance['operation_type'].apply(
                lambda ops: any('storm' in op or 'drift' in op or 'extensive' in op for op in ops)
            ))
        ].copy()
        
        print(f"Identifiserte {len(high_activity_days)} dager med høy aktivitet eller potensial snøfokk")
        
        # Analyser bare første 20 dager for å unngå for mange API-kall
        sample_days = high_activity_days.head(20)
        print(f"Analyserer sample på {len(sample_days)} dager")
        
        # Hent værdata for kritiske perioder
        for idx, day_data in sample_days.iterrows():
            date = day_data['datetime']
            start_time = date - timedelta(hours=12)  # 12 timer før
            end_time = date + timedelta(hours=12)    # 12 timer etter
            
            print(f"\n📅 Analyserer {date.date()}: {day_data['operation_type']}")
            
            weather_data = self.get_weather_data(start_time, end_time, self.extended_elements)
            
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
                'std_24h': data['value'].std(),  # Ny: standardavvik for variabilitet
                'range_24h': data['value'].max() - data['value'].min(),  # Ny: range
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

    def identify_extended_indicators(self, correlations: Dict) -> Dict:
        """Identifiser viktigste utvidede værindikatorer for vedlikeholdsbehov"""
        print("\n🎯 Identifiserer utvidede værindikatorer...")
        
        # Definer kategorikonstanter
        CATEGORY_SNOFOKK = 'snøfokk_og_drift'
        CATEGORY_EKSTREM = 'ekstreme_forhold'
        CATEGORY_MODERAT = 'moderat_snøfall'
        CATEGORY_RUTINE = 'rutinevedlikehold'
        
        indicators = {
            CATEGORY_SNOFOKK: [],
            CATEGORY_EKSTREM: [],
            CATEGORY_MODERAT: [],
            CATEGORY_RUTINE: []
        }
        
        for date, data in correlations.items():
            maintenance = data['maintenance']
            weather = data['weather']
            
            # Klassifiser vedlikeholdstype basert på operasjoner
            ops = maintenance['operation_type']
            
            if any('extreme' in op or 'extensive' in op or 'drift' in op for op in ops):
                category = CATEGORY_SNOFOKK
            elif any('major_storm' in op for op in ops):
                category = CATEGORY_EKSTREM
            elif any('moderate' in op for op in ops):
                category = CATEGORY_MODERAT
            else:
                category = CATEGORY_RUTINE
            
            # Ekstraher relevante værparametre med utvidede statistikker
            weather_summary = {}
            for element, stats in weather.items():
                if stats:
                    weather_summary[element] = {
                        'value': stats['value_at_event'],
                        'trend_before': stats['trend_before'],
                        'variability': stats.get('std_24h', 0),
                        'range': stats.get('range_24h', 0),
                        'extremeness': abs(stats['value_at_event'] - stats['mean_24h'])
                    }
            
            indicators[category].append({
                'date': date,
                'weather': weather_summary,
                'maintenance_hours': maintenance['duration_hours'],
                'distance_km': maintenance['distance_km']
            })
        
        return indicators

    def generate_extended_recommendations(self, indicators: Dict) -> Dict:
        """Generer anbefalinger basert på utvidede analyser"""
        print("\n📋 Genererer utvidede anbefalinger...")
        
        recommendations = {}
        
        for category, events in indicators.items():
            if not events:
                continue
                
            print(f"\n{category.upper()}:")
            print(f"  Antall hendelser: {len(events)}")
            
            # Analyser hvilke parametre som er mest relevante
            param_importance = self._analyze_extended_parameter_importance(events)
            
            # Beregn viktighet for hver parameter
            element_scores = self._calculate_extended_element_scores(param_importance)
            
            # Sorter etter viktighet
            sorted_elements = sorted(element_scores.items(), key=lambda x: x[1], reverse=True)
            
            recommendations[category] = {
                'primary_indicators': sorted_elements[:5],  # Top 5 for utvidet analyse
                'all_scores': sorted_elements,
                'event_count': len(events)
            }
            
            print("  Viktigste indikatorer:")
            for element, score in sorted_elements[:5]:
                print(f"    {element}: {score:.2f}")
        
        return recommendations

    def _analyze_extended_parameter_importance(self, events: List[Dict]) -> Dict:
        """Analyser viktighet av parametre med utvidede faktorer"""
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
                    'variability': stats.get('variability', 0),
                    'range': stats.get('range', 0),
                    'extremeness': stats.get('extremeness', 0),
                    'weight': weight
                })
        
        return param_importance

    def _calculate_extended_element_scores(self, param_importance: Dict) -> Dict:
        """Beregn skår for hvert værelement med utvidede faktorer"""
        element_scores = {}
        
        for element, measurements in param_importance.items():
            if measurements:
                weighted_score = sum(
                    (m['value'] * 0.3 + 
                     m['trend'] * 0.2 + 
                     m['variability'] * 0.2 + 
                     m['range'] * 0.15 + 
                     m['extremeness'] * 0.15) * m['weight']
                    for m in measurements
                ) / len(measurements)
                element_scores[element] = weighted_score
        
        return element_scores

    def save_extended_analysis(self, correlations: Dict, indicators: Dict, recommendations: Dict):
        """Lagre utvidede analyseresultater"""
        results = {
            'analysis_date': datetime.now().isoformat(),
            'analysis_type': 'extended_weather_elements',
            'station_id': self.station_id,
            'elements_tested': self.extended_elements,
            'correlations': {str(k): v for k, v in correlations.items()},
            'indicators': indicators,
            'recommendations': recommendations,
            'summary': {
                'total_events_analyzed': len(correlations),
                'elements_tested_count': len(self.extended_elements),
                'recommendations_by_category': {
                    cat: [elem[0] for elem in rec['primary_indicators']] 
                    for cat, rec in recommendations.items()
                }
            }
        }
        
        # Lagre som JSON
        with open('data/analyzed/extended_maintenance_weather_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        print("\n💾 Utvidet analyse lagret til data/analyzed/extended_maintenance_weather_analysis.json")
        
        # Generer oppsummering
        self._print_extended_summary(recommendations)

    def _print_extended_summary(self, recommendations: Dict):
        """Print oppsummering av utvidede anbefalinger"""
        print("\n" + "="*70)
        print("📊 UTVIDET ANALYSE: ALTERNATIVE VÆRELEMENTER FOR SNØFOKK")
        print("="*70)
        
        print("\n🎯 TOP 5 ANBEFALTE ELEMENTER FOR HVER KATEGORI:")
        
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
        
        print(f"\n📈 TILGJENGELIGE AV {len(self.extended_elements)} TESTEDE ELEMENTER")
        
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
    analyzer = ExtendedMaintenanceWeatherAnalyzer()
    
    # Last vedlikeholdsdata
    maintenance_df = analyzer.load_maintenance_data()
    
    # Analyser korrelasjoner med utvidede elementer
    correlations = analyzer.analyze_correlations(maintenance_df)
    
    # Identifiser nøkkelindikatorer
    indicators = analyzer.identify_extended_indicators(correlations)
    
    # Generer anbefalinger
    recommendations = analyzer.generate_extended_recommendations(indicators)
    
    # Lagre resultater
    analyzer.save_extended_analysis(correlations, indicators, recommendations)

if __name__ == "__main__":
    main()
