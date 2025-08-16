#!/usr/bin/env python3
"""
UTVIDET ANALYSE MED ALLE 19 ANBEFALTE VÆRELEMENTER
Inkluderer kritiske tillegg som surface_temperature, dew_point_temperature,
høyoppløselig nedbør og kvalitetskontroll-elementer.
"""

import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta
import os
from typing import Dict, List, Tuple

class ExtendedWeatherAnalyzer:
    def __init__(self):
        self.frost_client_id = os.getenv('FROST_CLIENT_ID')
        if not self.frost_client_id:
            with open('.env', 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('FROST_CLIENT_ID='):
                        self.frost_client_id = line.split('=')[1].strip()
                        break
        
        self.station_id = "SN46220"  # Gullingen
        self.base_url = "https://frost.met.no/observations/v0.jsonld"
        
        # UTVIDEDE KRITISKE ELEMENTER (19 totalt)
        self.extended_critical_elements = [
            # Eksisterende validerte (5)
            "accumulated(precipitation_amount)",
            "wind_from_direction", 
            "max_wind_speed(wind_from_direction PT1H)",
            "sum(duration_of_precipitation PT1H)",
            "relative_humidity",
            
            # Kritiske tillegg (4)
            "surface_temperature",           # Veioverflate-temperatur
            "dew_point_temperature",         # Rimfrost-varsling  
            "max(air_temperature PT1H)",     # Korte tineperioder
            "min(air_temperature PT1H)",     # Korte frostperioder
            
            # Høyoppløselig nedbør (2)
            "sum(precipitation_amount PT10M)",  # 10-min oppløsning
            "over_time(gauge_content_difference PT1H)",  # Direkte måling
            
            # Standard elementer (4) 
            "air_temperature",               # Grunnleggende
            "wind_speed",                    # Grunnleggende
            "surface_snow_thickness",        # Snødybde
            "sum(precipitation_amount PT1H)", # Timeakkumulering
            
            # Vind-detaljer (3)
            "max(wind_speed_of_gust PT1H)",  # Vindkast
            "max(wind_speed PT1H)",          # Maksimal vind
            "mean(wind_speed P1D)",          # Daglig gjennomsnitt
            
            # Kvalitetskontroll (1)
            "battery_voltage"                # Sensor-pålitelighet
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
        
        # Forbedret klassifisering basert på operasjonelle kriterier
        df['operation_type'] = df.apply(self._classify_operation_enhanced, axis=1)
        
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

    def _classify_operation_enhanced(self, row) -> str:
        """Forbedret klassifisering basert på operasjonelle kriterier"""
        duration = row['duration_hours']
        distance = row['distance_km']
        
        # Basert på claude.md krav og operasjonell erfaring
        if duration > 8:
            return "ekstrem_storm"  # Omfattende operasjoner
        elif duration > 6:
            return "major_storm"  # Store snøfall
        elif distance > 30 and duration > 3:
            return "tunbrøyting_fredag"  # Hytteruter (fredager)
        elif distance > 25:
            return "omfattende_snøfokk"  # Lange ruter = snøfokk problemer
        elif duration > 4:
            return "moderat_storm"  # Moderat snøfall
        elif distance > 15 and duration > 1:
            return "snøfokk_rydding"  # Kort men lang distanse = drift
        elif duration < 0.5:
            return "strøing_glattføre"  # Kort behandling = strøing
        elif distance < 5:
            return "punktbehandling"  # Lokal behandling
        else:
            return "rutine_brøyting"  # Standard brøyting

    def get_extended_weather_data(self, start_date: datetime, end_date: datetime) -> Dict:
        """Hent værdata fra Frost API med utvidede 19 elementer"""
        print(f"🌡️ Henter UTVIDEDE værdata for {start_date.date()} til {end_date.date()}")
        print(f"Tester {len(self.extended_critical_elements)} kritiske elementer...")
        
        weather_data = {}
        
        for i, element in enumerate(self.extended_critical_elements, 1):
            try:
                print(f"  {i:2d}/{len(self.extended_critical_elements)}: {element[:50]}{'...' if len(element) > 50 else ''}", end=' ')
                
                params = {
                    'sources': self.station_id,
                    'elements': element,
                    'referencetime': f"{start_date.isoformat()}/{end_date.isoformat()}"
                }
                
                response = requests.get(
                    self.base_url, 
                    params=params,
                    auth=(self.frost_client_id, ''),
                    timeout=15
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data and data['data']:
                        weather_data[element] = self._process_weather_data(data['data'])
                        obs_count = len(weather_data[element])
                        print(f"✅ ({obs_count} obs)")
                    else:
                        print("⚠️ (ingen data)")
                elif response.status_code == 412:
                    print("❌ (412)")
                elif response.status_code == 404:
                    print("❌ (404)")
                else:
                    print(f"❌ ({response.status_code})")
                    
            except Exception as e:
                print(f"❌ (feil: {str(e)[:30]})")
        
        print(f"\n✅ Hentet data for {len(weather_data)} av {len(self.extended_critical_elements)} elementer")
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

    def analyze_extended_correlations(self, maintenance_df: pd.DataFrame) -> Dict:
        """Analyser korrelasjon med utvidede værelementer"""
        print("🔍 Analyserer korrelasjon med UTVIDEDE værelementer...")
        
        correlations = {}
        
        # Grupper vedlikehold etter dag
        daily_maintenance = maintenance_df.groupby(maintenance_df['datetime'].dt.date).agg({
            'operation_type': lambda x: list(x),
            'duration_hours': 'sum',
            'distance_km': 'sum',
            'datetime': 'min'
        })
        daily_maintenance = daily_maintenance.reset_index(drop=True)
        
        # Fokuser på operasjonelt interessante dager
        interesting_days = daily_maintenance[
            (daily_maintenance['duration_hours'] > 2) | 
            (daily_maintenance['distance_km'] > 15) |
            (daily_maintenance['operation_type'].apply(
                lambda ops: any('storm' in op or 'snøfokk' in op or 'tunbrøyting' in op or 'strøing' in op for op in ops)
            ))
        ].copy()
        
        print(f"Identifiserte {len(interesting_days)} operasjonelt interessante dager")
        
        # Analyser utvalgte dager (utvid til 20 for bedre statistikk)
        sample_days = interesting_days.head(20)
        print(f"Analyserer sample på {len(sample_days)} dager")
        
        # Hent værdata for utvalgte perioder
        for idx, day_data in sample_days.iterrows():
            date = day_data['datetime']
            start_time = date - timedelta(hours=18)  # 18 timer før
            end_time = date + timedelta(hours=6)     # 6 timer etter
            
            print(f"\n📅 Analyserer {date.date()}: {day_data['operation_type']}")
            
            weather_data = self.get_extended_weather_data(start_time, end_time)
            
            # Analyser værforhold med utvidede elementer
            analysis = self._analyze_extended_weather_conditions(weather_data, date)
            correlations[date.date()] = {
                'maintenance': day_data.to_dict(),
                'weather': analysis
            }
        
        return correlations

    def _analyze_extended_weather_conditions(self, weather_data: Dict, event_time: datetime) -> Dict:
        """Analyser værforhold med fokus på utvidede parametere"""
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
                'std_24h': data['value'].std(),
                'range_24h': data['value'].max() - data['value'].min(),
                'trend_before': self._calculate_trend(data, event_time, hours_before=6),
                'trend_after': self._calculate_trend(data, event_time, hours_after=3),
                'data_count': len(data),
                'data_frequency': len(data) / 24,  # Observasjoner per time
                'quality_score': min(len(data) / 50, 1.0)  # 0-1 kvalitetsskår
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
        
        # Fjern NaN verdier
        valid_mask = ~np.isnan(y)
        if np.sum(valid_mask) < 2:
            return 0.0
            
        return np.polyfit(x[valid_mask], y[valid_mask], 1)[0]  # Slope

    def identify_extended_operational_indicators(self, correlations: Dict) -> Dict:
        """Identifiser operasjonelle indikatorer med utvidede elementer"""
        print("\n🎯 Identifiserer UTVIDEDE operasjonelle værindikatorer...")
        
        # Operasjonelle kategorier
        categories = {
            'nysnø_brøyting': [],
            'snøfokk_drift': [],
            'glattføre_strøing': [],
            'tunbrøyting_fredag': [],
            'ekstreme_forhold': []
        }
        
        for date, data in correlations.items():
            maintenance = data['maintenance']
            weather = data['weather']
            
            # Klassifiser basert på operasjonstyper
            ops = maintenance['operation_type']
            
            if any('tunbrøyting' in op for op in ops):
                category = 'tunbrøyting_fredag'
            elif any('snøfokk' in op or 'drift' in op for op in ops):
                category = 'snøfokk_drift'
            elif any('strøing' in op or 'glattføre' in op for op in ops):
                category = 'glattføre_strøing'
            elif any('ekstrem' in op for op in ops):
                category = 'ekstreme_forhold'
            else:
                category = 'nysnø_brøyting'  # Default: nysnø
            
            # Ekstraher utvidede værparametre
            weather_summary = {}
            for element, stats in weather.items():
                if stats and stats.get('data_count', 0) > 0:
                    weather_summary[element] = {
                        'value': stats['value_at_event'],
                        'trend_before': stats['trend_before'],
                        'variability': stats.get('std_24h', 0),
                        'range': stats.get('range_24h', 0),
                        'extremeness': abs(stats['value_at_event'] - stats['mean_24h']) if stats['mean_24h'] else 0,
                        'data_quality': stats['quality_score'],  # Ny: kvalitetsskår
                        'data_frequency': stats['data_frequency']  # Ny: frekvens
                    }
            
            categories[category].append({
                'date': date,
                'weather': weather_summary,
                'maintenance_hours': maintenance['duration_hours'],
                'distance_km': maintenance['distance_km']
            })
        
        return categories

    def generate_extended_recommendations(self, indicators: Dict) -> Dict:
        """Generer utvidede anbefalinger med nye elementer"""
        print("\n📋 Genererer UTVIDEDE operasjonelle anbefalinger...")
        
        recommendations = {}
        
        for category, events in indicators.items():
            if not events:
                continue
                
            print(f"\n{category.upper()}:")
            print(f"  Antall hendelser: {len(events)}")
            
            # Analyser parametre med fokus på datakvalitet og frekvens
            param_importance = self._analyze_extended_parameter_importance(events)
            
            # Beregn viktighet med kvalitets- og frekvensvekting
            element_scores = self._calculate_extended_scores(param_importance)
            
            # Sorter etter viktighet
            sorted_elements = sorted(element_scores.items(), key=lambda x: x[1], reverse=True)
            
            # Identifiser spesialiserte indikatorer
            specialized_indicators = self._identify_specialized_indicators(category, sorted_elements)
            
            recommendations[category] = {
                'primary_indicators': sorted_elements[:7],  # Top 7 (utvid fra 5)
                'specialized_indicators': specialized_indicators,
                'all_scores': sorted_elements,
                'event_count': len(events),
                'data_reliability': self._assess_extended_data_reliability(param_importance),
                'operational_insights': self._generate_operational_insights(category, sorted_elements[:7])
            }
            
            print("  Viktigste indikatorer:")
            for element, score in sorted_elements[:7]:
                print(f"    {element}: {score:.2f}")
        
        return recommendations

    def _analyze_extended_parameter_importance(self, events: List[Dict]) -> Dict:
        """Analyser viktighet med utvidede kvalitetsmetrikker"""
        param_importance = {}
        
        for event in events:
            for element, stats in event['weather'].items():
                if element not in param_importance:
                    param_importance[element] = []
                
                # Vekt basert på vedlikeholdsintensitet, datakvalitet og frekvens
                maintenance_weight = event['maintenance_hours'] + event['distance_km'] / 10
                data_quality_weight = stats.get('data_quality', 0) * 3  # 0-3x boost
                frequency_weight = min(stats.get('data_frequency', 0) / 2, 2)  # 0-2x boost
                
                total_weight = maintenance_weight * (1 + data_quality_weight + frequency_weight)
                
                param_importance[element].append({
                    'value': abs(stats.get('value', 0)),
                    'trend': abs(stats.get('trend_before', 0)),
                    'variability': stats.get('variability', 0),
                    'range': stats.get('range', 0),
                    'extremeness': stats.get('extremeness', 0),
                    'weight': total_weight,
                    'data_quality': stats.get('data_quality', 0),
                    'data_frequency': stats.get('data_frequency', 0)
                })
        
        return param_importance

    def _calculate_extended_scores(self, param_importance: Dict) -> Dict:
        """Beregn skår med utvidede kvalitetsmetrikker"""
        element_scores = {}
        
        for element, measurements in param_importance.items():
            if measurements:
                # Filtrer ut målinger med lav datakvalitet
                quality_measurements = [m for m in measurements if m['data_quality'] >= 0.3]
                
                if quality_measurements:
                    # Utvidet vektingsmodell
                    weighted_score = sum(
                        (m['value'] * 0.20 + 
                         m['trend'] * 0.20 + 
                         m['variability'] * 0.15 + 
                         m['range'] * 0.15 + 
                         m['extremeness'] * 0.15 +
                         m['data_quality'] * 100 * 0.10 +  # Ny: kvalitetsbonus
                         m['data_frequency'] * 50 * 0.05) * m['weight']  # Ny: frekvensbonus
                        for m in quality_measurements
                    ) / len(quality_measurements)
                    element_scores[element] = weighted_score
        
        return element_scores

    def _identify_specialized_indicators(self, category: str, sorted_elements: List[Tuple[str, float]]) -> Dict:
        """Identifiser spesialiserte indikatorer per kategori"""
        specialized = {
            'temperatur_indikatorer': [],
            'nedbør_indikatorer': [],
            'vind_indikatorer': [],
            'kvalitets_indikatorer': []
        }
        
        for element, score in sorted_elements:
            element_lower = element.lower()
            
            if any(word in element_lower for word in ['temperature', 'dew_point']):
                specialized['temperatur_indikatorer'].append((element, score))
            elif any(word in element_lower for word in ['precipitation', 'duration', 'gauge']):
                specialized['nedbør_indikatorer'].append((element, score))
            elif any(word in element_lower for word in ['wind', 'gust']):
                specialized['vind_indikatorer'].append((element, score))
            elif any(word in element_lower for word in ['battery', 'quality']):
                specialized['kvalitets_indikatorer'].append((element, score))
        
        # Behold kun top 3 per kategori
        for key in specialized:
            specialized[key] = specialized[key][:3]
        
        return specialized

    def _assess_extended_data_reliability(self, param_importance: Dict) -> Dict:
        """Utvidet vurdering av datapålitelighet"""
        reliability = {}
        
        for element, measurements in param_importance.items():
            if measurements:
                avg_quality = np.mean([m['data_quality'] for m in measurements])
                avg_frequency = np.mean([m['data_frequency'] for m in measurements])
                
                # Kombiner kvalitet og frekvens
                combined_score = (avg_quality * 0.7 + min(avg_frequency / 2, 1.0) * 0.3)
                
                reliability[element] = {
                    'quality_score': avg_quality,
                    'frequency_score': avg_frequency,
                    'combined_score': combined_score,
                    'recommendation': 'høy' if combined_score >= 0.7 else 'moderat' if combined_score >= 0.4 else 'lav'
                }
        
        return reliability

    def _generate_operational_insights(self, category: str, top_elements: List[Tuple[str, float]]) -> List[str]:
        """Generer operasjonelle innsikter per kategori"""
        insights = []
        
        element_names = [elem[0] for elem in top_elements]
        
        if category == 'glattføre_strøing':
            if 'surface_temperature' in element_names:
                insights.append("Veioverflatetemperatur er kritisk for glattføre-deteksjon")
            if 'dew_point_temperature' in element_names:
                insights.append("Duggpunkt vs lufttemperatur indikerer rimfrost-risiko")
        
        elif category == 'snøfokk_drift':
            if any('wind' in elem for elem in element_names):
                insights.append("Vindretning og -styrke er avgjørende for snøfokk-prediksjon")
            if 'surface_snow_thickness' in element_names:
                insights.append("Snødybde kombinert med vind gir snøfokk-risiko")
        
        elif category == 'nysnø_brøyting':
            if any('precipitation' in elem for elem in element_names):
                insights.append("Høyoppløselig nedbørdata forbedrer nysnø-deteksjon")
            if 'surface_snow_thickness' in element_names:
                insights.append("Direkte snødybde-måling er mest pålitelig")
        
        # Generelle innsikter
        if 'battery_voltage' in element_names:
            insights.append("Batterispenning indikerer sensorpålitelighet")
        
        if any('PT10M' in elem for elem in element_names):
            insights.append("10-minutters oppløsning gir presis timing")
            
        return insights

    def save_extended_analysis(self, correlations: Dict, indicators: Dict, recommendations: Dict):
        """Lagre utvidet analyseresultat"""
        results = {
            'analysis_date': datetime.now().isoformat(),
            'analysis_type': 'extended_19_critical_elements',
            'station_id': self.station_id,
            'elements_analyzed': self.extended_critical_elements,
            'total_elements': len(self.extended_critical_elements),
            'correlations': {str(k): v for k, v in correlations.items()},
            'indicators': indicators,
            'recommendations': recommendations,
            'operational_criteria': {
                'nysnø_terskler': {'våt_snø': '6cm', 'tørr_snø': '12cm'},
                'tunbrøyting': 'akkumulert snø siste uke, hovedsakelig fredager',
                'glattføre': 'regn på snø, rimfrost (surface_temperature kritisk)',
                'snøfokk': 'vindblåst løssnø (vind kan blåse snø vekk fra radar)',
                'nye_elementer': {
                    'surface_temperature': 'veioverflate for glattføre',
                    'dew_point_temperature': 'rimfrost-varsling',
                    'sum(precipitation_amount PT10M)': '10-min høyoppløselig nedbør',
                    'battery_voltage': 'sensorpålitelighet'
                }
            },
            'summary': {
                'total_events_analyzed': len(correlations),
                'elements_with_data': len([e for e in self.extended_critical_elements if any(e in corr['weather'] for corr in correlations.values())]),
                'top_recommendations_by_category': {
                    cat: [elem[0] for elem in rec['primary_indicators'][:3]] 
                    for cat, rec in recommendations.items()
                }
            }
        }
        
        # Lagre som JSON
        with open('data/analyzed/extended_19_elements_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        print("\n💾 Utvidet analyse lagret til data/analyzed/extended_19_elements_analysis.json")
        
        # Generer omfattende oppsummering
        self._print_extended_summary(recommendations)

    def _print_extended_summary(self, recommendations: Dict):
        """Print omfattende oppsummering av utvidet analyse"""
        print("\n" + "="*100)
        print("📊 UTVIDET ANALYSE: 19 KRITISKE VÆRELEMENTER")
        print("="*100)
        
        print(f"\n🎯 TOP 7 UTVIDEDE ELEMENTER FOR HVER OPERASJONELL KATEGORI:")
        
        all_recommended = set()
        
        for category, data in recommendations.items():
            print(f"\n{category.upper()}:")
            print(f"  Basert på {data['event_count']} hendelser")
            
            for i, (element, score) in enumerate(data['primary_indicators'], 1):
                print(f"  {i}. {element} (viktighet: {score:.1f})")
                all_recommended.add(element)
            
            # Print spesialiserte indikatorer
            if data['specialized_indicators']:
                print("  Spesialiserte indikatorer:")
                for spec_type, indicators in data['specialized_indicators'].items():
                    if indicators:
                        print(f"    {spec_type}: {indicators[0][0]} ({indicators[0][1]:.1f})")
            
            # Print operasjonelle innsikter
            if data['operational_insights']:
                print("  Operasjonelle innsikter:")
                for insight in data['operational_insights']:
                    print(f"    • {insight}")
        
        print(f"\n🔑 TOTALT {len(all_recommended)} UNIKE ELEMENTER ANBEFALT AV 19 TESTEDE")
        
        print(f"\n📊 KRITISKE TILLEGG VALIDERT:")
        critical_additions = [
            'surface_temperature',
            'dew_point_temperature', 
            'max(air_temperature PT1H)',
            'min(air_temperature PT1H)',
            'sum(precipitation_amount PT10M)',
            'over_time(gauge_content_difference PT1H)',
            'battery_voltage'
        ]
        
        for addition in critical_additions:
            if addition in all_recommended:
                print(f"  ✅ {addition} - VALIDERT som kritisk")
            else:
                print(f"  ⚠️ {addition} - Ikke i top anbefalinger")
        
        print(f"\n🏆 UTVIDET SYSTEM GIR:")
        print("  • Presis glattføre-deteksjon (surface_temperature + dew_point)")
        print("  • Høyoppløselig nedbøranalyse (10-minutters data)")
        print("  • Temperaturekstremer (time-maksimum/minimum)")
        print("  • Kvalitetskontroll (batterispenning)")
        print("  • Forbedret snøfokk-prediksjon")
        print("  • Direktemåling av akkumulering")

def main():
    analyzer = ExtendedWeatherAnalyzer()
    
    # Last vedlikeholdsdata
    maintenance_df = analyzer.load_maintenance_data()
    
    # Analyser korrelasjoner med utvidede elementer
    correlations = analyzer.analyze_extended_correlations(maintenance_df)
    
    # Identifiser utvidede operasjonelle indikatorer
    indicators = analyzer.identify_extended_operational_indicators(correlations)
    
    # Generer utvidede anbefalinger
    recommendations = analyzer.generate_extended_recommendations(indicators)
    
    # Lagre resultater
    analyzer.save_extended_analysis(correlations, indicators, recommendations)

if __name__ == "__main__":
    main()
