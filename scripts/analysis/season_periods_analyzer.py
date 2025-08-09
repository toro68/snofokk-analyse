#!/usr/bin/env python3
"""
Forenklet Brøytesesong Snøfokk-Analyse med Vindretning og Riktig Periodegruppering
Bruker samme datahenting som fungerende scripts
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import requests
import os
from typing import Dict, List, Tuple, Any
import matplotlib.pyplot as plt
from dotenv import load_dotenv

# Last miljøvariabler
load_dotenv()

class SimpleSeasonSnowdriftAnalyzer:
    """Forenklet analyse for hele brøytesesongen."""
    
    def __init__(self):
        self.client_id = os.getenv('FROST_CLIENT_ID')
        if not self.client_id:
            raise ValueError("FROST_CLIENT_ID ikke funnet i miljøvariabler")
    
    def fetch_season_data(self) -> pd.DataFrame:
        """Hent værdata for hele brøytesesongen 2023-2024."""
        print("📅 Henter data for brøytesesong 2023-2024 (1. nov - 30. apr)...")
        
        # Brøytesesong parameters
        station_id = "SN46220"  # Gullingen
        start_date = "2023-11-01T00:00:00.000Z"
        end_date = "2024-04-30T23:59:59.000Z"
        
        # API endepunkt og parametere
        endpoint = 'https://frost.met.no/observations/v0.jsonld'
        parameters = {
            'sources': station_id,
            'referencetime': f'{start_date}/{end_date}',
            'elements': ','.join([
                'air_temperature',
                'wind_speed',
                'max(wind_speed PT1H)',
                'wind_from_direction',
                'surface_snow_thickness',
                'relative_humidity',
                'sum(precipitation_amount PT1H)',
                'min(air_temperature PT1H)',
                'max(air_temperature PT1H)'
            ])
        }
        
        try:
            # Gjør API-kall
            response = requests.get(endpoint, parameters, auth=(self.client_id, ''))
            
            if response.status_code != 200:
                print(f"❌ API feil {response.status_code}: {response.text}")
                return pd.DataFrame()
            
            data = response.json()
            
            if 'data' not in data or not data['data']:
                print("❌ Ingen data mottatt fra API")
                return pd.DataFrame()
            
            print(f"✅ Mottatt {len(data['data'])} datapunkter fra API")
            
            # Normaliser til DataFrame (samme metode som fungerende scripts)
            df = pd.json_normalize(data['data'])
            
            if 'observations' in df.columns:
                # Utvid observations
                obs_df = df.explode('observations')
                obs_normalized = pd.json_normalize(obs_df['observations'])
                
                # Kombiner med hoveddata
                result_df = pd.concat([
                    obs_df[['sourceId', 'referenceTime']].reset_index(drop=True),
                    obs_normalized.reset_index(drop=True)
                ], axis=1)
            else:
                result_df = df
            
            print(f"📊 DataFrame form etter normalisering: {result_df.shape}")
            
            # Pivot for enklere analyse
            if 'elementId' in result_df.columns and 'value' in result_df.columns:
                pivoted = result_df.pivot_table(
                    index='referenceTime',
                    columns='elementId',
                    values='value',
                    aggfunc='first'
                ).reset_index()
                
                print(f"📊 DataFrame form etter pivot: {pivoted.shape}")
                print(f"Kolonner etter pivot: {list(pivoted.columns)}")
                
                # Konverter referenceTime til datetime
                pivoted['referenceTime'] = pd.to_datetime(pivoted['referenceTime'])
                
                return pivoted
            else:
                print("❌ Forventet kolonner ikke funnet")
                return pd.DataFrame()
                
        except Exception as e:
            print(f"❌ Feil ved API-kall: {e}")
            return pd.DataFrame()
    
    def identify_continuous_periods(self, df: pd.DataFrame) -> List[Dict]:
        """Identifiser sammenhengende snøfokk-perioder."""
        print("🔍 Identifiserer sammenhengende snøfokk-perioder...")
        
        # Kriterier for snøfokk
        wind_threshold = 6.0     # m/s
        temp_threshold = -1.0    # °C
        snow_threshold = 3.0     # cm
        
        periods = []
        current_period = None
        
        # Sorter etter tid
        df = df.sort_values('referenceTime').reset_index(drop=True)
        
        for idx, row in df.iterrows():
            # Sjekk snøfokk-kriterier
            wind_speed = row.get('wind_speed', 0)
            air_temp = row.get('air_temperature', 0)
            snow_depth = row.get('surface_snow_thickness', 0)
            wind_direction = row.get('wind_from_direction', np.nan)
            
            # Håndter NaN-verdier
            if pd.isna(wind_speed) or pd.isna(air_temp) or pd.isna(snow_depth):
                # Avslutt periode hvis aktiv
                if current_period:
                    periods.append(self.finalize_period(current_period))
                    current_period = None
                continue
            
            # Evaluer snøfokk-kondisjon
            meets_criteria = (
                wind_speed >= wind_threshold and
                air_temp <= temp_threshold and
                snow_depth >= snow_threshold
            )
            
            if meets_criteria:
                if current_period is None:
                    # Start ny periode
                    current_period = {
                        'start_time': row['referenceTime'],
                        'end_time': row['referenceTime'],
                        'data_points': [row],
                        'wind_directions': [wind_direction] if not pd.isna(wind_direction) else [],
                        'wind_speeds': [wind_speed],
                        'temperatures': [air_temp],
                        'snow_depths': [snow_depth]
                    }
                else:
                    # Sjekk om dette er sammenhengende (innen 3 timer)
                    time_gap = (row['referenceTime'] - current_period['end_time']).total_seconds() / 3600
                    
                    if time_gap <= 3.0:  # Maks 3 timer gap for å være liberal
                        # Utvid eksisterende periode
                        current_period['end_time'] = row['referenceTime']
                        current_period['data_points'].append(row)
                        current_period['wind_speeds'].append(wind_speed)
                        current_period['temperatures'].append(air_temp)
                        current_period['snow_depths'].append(snow_depth)
                        if not pd.isna(wind_direction):
                            current_period['wind_directions'].append(wind_direction)
                    else:
                        # Gap for stort - avslutt periode og start ny
                        if len(current_period['data_points']) >= 1:  # Lagre selv korte perioder
                            periods.append(self.finalize_period(current_period))
                        current_period = {
                            'start_time': row['referenceTime'],
                            'end_time': row['referenceTime'],
                            'data_points': [row],
                            'wind_directions': [wind_direction] if not pd.isna(wind_direction) else [],
                            'wind_speeds': [wind_speed],
                            'temperatures': [air_temp],
                            'snow_depths': [snow_depth]
                        }
            else:
                # Ikke snøfokk - avslutt periode hvis aktiv
                if current_period and len(current_period['data_points']) >= 1:
                    periods.append(self.finalize_period(current_period))
                    current_period = None
        
        # Avslutt siste periode
        if current_period and len(current_period['data_points']) >= 1:
            periods.append(self.finalize_period(current_period))
        
        print(f"✅ Identifiserte {len(periods)} sammenhengende perioder")
        return periods
    
    def finalize_period(self, period: Dict) -> Dict:
        """Ferdigstill periode med beregninger."""
        # Beregn varighet
        duration = (period['end_time'] - period['start_time']).total_seconds() / 3600
        period['duration_hours'] = round(duration + 1, 1)  # +1 for å inkludere starttimen
        
        # Beregn statistikker
        period['max_wind_speed'] = max(period['wind_speeds'])
        period['avg_wind_speed'] = np.mean(period['wind_speeds'])
        period['min_temperature'] = min(period['temperatures'])
        period['max_temperature'] = max(period['temperatures'])
        period['snow_depth_start'] = period['snow_depths'][0]
        period['snow_depth_end'] = period['snow_depths'][-1]
        period['snow_change'] = period['snow_depth_end'] - period['snow_depth_start']
        
        # Beregn gjennomsnittlig vindretning (sirkulær)
        if period['wind_directions']:
            directions_rad = np.radians(period['wind_directions'])
            avg_x = np.mean(np.cos(directions_rad))
            avg_y = np.mean(np.sin(directions_rad))
            avg_direction = np.degrees(np.arctan2(avg_y, avg_x)) % 360
            period['predominant_wind_direction'] = round(avg_direction, 1)
        else:
            period['predominant_wind_direction'] = None
        
        # Klassifiser snøfokk-type
        if abs(period['snow_change']) < 0.5:
            period['drift_type'] = 'invisible_drift'  # Usynlig
        elif period['snow_change'] > 0.5:
            period['drift_type'] = 'accumulating_drift'  # Akkumulering
        else:
            period['drift_type'] = 'eroding_drift'  # Erosjon
        
        # Vindretning risiko
        direction_risk = self.analyze_wind_direction_risk(period['predominant_wind_direction'])
        period['wind_direction_risk'] = direction_risk
        
        # Samlet risikoscore
        wind_factor = min(period['max_wind_speed'] / 20.0, 1.0)
        temp_factor = min(abs(period['min_temperature']) / 20.0, 1.0)
        direction_multiplier = 1.5 if direction_risk == 'high' else 1.0
        
        period['risk_score'] = min((wind_factor + temp_factor) * direction_multiplier / 2.0, 1.0)
        
        # Faregrad
        if period['risk_score'] >= 0.7 or direction_risk == 'high':
            period['road_danger'] = 'HIGH'
        elif period['risk_score'] >= 0.4:
            period['road_danger'] = 'MEDIUM'
        else:
            period['road_danger'] = 'LOW'
        
        return period
    
    def analyze_wind_direction_risk(self, direction: float) -> str:
        """Analyser risiko basert på vindretning."""
        if direction is None or pd.isna(direction):
            return 'unknown'
        
        # Kritiske vindretninger for Gullingen
        # NW-NE (315-45°) og SE-SW (135-225°)
        if (315 <= direction <= 360) or (0 <= direction <= 45):
            return 'high'  # NW-NE
        elif 135 <= direction <= 225:
            return 'high'  # SE-SW
        else:
            return 'medium'
    
    def create_season_summary(self, periods: List[Dict]) -> Dict:
        """Lag sesongsammendrag."""
        if not periods:
            return {}
        
        total_periods = len(periods)
        total_hours = sum(p['duration_hours'] for p in periods)
        
        # Type fordeling
        type_counts = {}
        for period in periods:
            ptype = period['drift_type']
            type_counts[ptype] = type_counts.get(ptype, 0) + 1
        
        # Faregrad fordeling
        danger_counts = {}
        for period in periods:
            danger = period['road_danger']
            danger_counts[danger] = danger_counts.get(danger, 0) + 1
        
        # Månedlig fordeling
        monthly_counts = {}
        for period in periods:
            month = period['start_time'].month
            monthly_counts[month] = monthly_counts.get(month, 0) + 1
        
        # Vindretning analyse
        direction_stats = {}
        for period in periods:
            if period['predominant_wind_direction'] is not None:
                # Grupper i 22.5° segmenter (16 retninger)
                direction_bin = int(period['predominant_wind_direction'] / 22.5) * 22.5
                if direction_bin not in direction_stats:
                    direction_stats[direction_bin] = 0
                direction_stats[direction_bin] += 1
        
        return {
            'total_periods': total_periods,
            'total_hours': total_hours,
            'avg_duration': total_hours / total_periods,
            'longest_period': max(p['duration_hours'] for p in periods),
            'type_distribution': type_counts,
            'danger_distribution': danger_counts,
            'monthly_distribution': monthly_counts,
            'wind_direction_distribution': direction_stats
        }
    
    def generate_report(self, periods: List[Dict], summary: Dict):
        """Generer omfattende rapport."""
        month_names = {
            11: 'November 2023', 12: 'Desember 2023',
            1: 'Januar 2024', 2: 'Februar 2024',
            3: 'Mars 2024', 4: 'April 2024'
        }
        
        report = f"""
🏔️ BRØYTESESONG 2023-2024 SNØFOKK-ANALYSE
================================================

📅 PERIODE: 1. november 2023 - 30. april 2024
🏔️ STASJON: Gullingen Skisenter (SN46220)

📊 HOVEDRESULTATER
Total antall snøfokk-PERIODER: {summary['total_periods']}
(Ikke timer - men sammenhengende perioder!)

Samlet varighet: {summary['total_hours']:.1f} timer
Gjennomsnittlig periodelengde: {summary['avg_duration']:.1f} timer
Lengste periode: {summary['longest_period']:.1f} timer

🏷️ SNØFOKK-TYPER
"""
        
        for drift_type, count in summary['type_distribution'].items():
            percentage = (count / summary['total_periods']) * 100
            type_name = {
                'invisible_drift': 'Usynlig snøfokk',
                'accumulating_drift': 'Akkumulerende snøfokk', 
                'eroding_drift': 'Eroderende snøfokk'
            }.get(drift_type, drift_type)
            report += f"  • {type_name}: {count} perioder ({percentage:.1f}%)\n"
        
        report += "\n⚠️ FAREGRAD FORDELING\n"
        for danger, count in summary['danger_distribution'].items():
            percentage = (count / summary['total_periods']) * 100
            report += f"  • {danger}: {count} perioder ({percentage:.1f}%)\n"
        
        report += "\n📅 MÅNEDLIG FORDELING\n"
        for month in [11, 12, 1, 2, 3, 4]:
            if month in summary['monthly_distribution']:
                count = summary['monthly_distribution'][month]
                percentage = (count / summary['total_periods']) * 100
                report += f"  • {month_names[month]}: {count} perioder ({percentage:.1f}%)\n"
        
        report += "\n🌬️ VINDRETNING ANALYSE\n"
        if summary['wind_direction_distribution']:
            # Topp 3 retninger
            top_directions = sorted(summary['wind_direction_distribution'].items(), 
                                  key=lambda x: x[1], reverse=True)[:3]
            
            for direction, count in top_directions:
                direction_name = self.get_direction_name(direction)
                percentage = (count / summary['total_periods']) * 100
                report += f"  • {direction}° ({direction_name}): {count} perioder ({percentage:.1f}%)\n"
        
        report += f"""

🚨 KRITISKE OBSERVASJONER
• Vindretning er kritisk for snøfokk-risiko
• NW-NE (315-45°) og SE-SW (135-225°) mest problematisk
• Usynlig snøfokk dominerer (ingen endring i snødybde)
• Brøytesesongen 2023-2024 hadde {summary['total_periods']} distinkte snøfokk-perioder

🎯 FORKLARING AV "USYNLIG SNØFOKK"
Usynlig snøfokk oppstår når:
• Vind flytter allerede liggende snø horisontalt
• Snødybde ved målestasjon endres ikke merkbart
• Veier kan likevel bli dekket av snø som blåser inn
• Særlig farlig fordi det ikke registreres av snøsensorer

🔧 ANBEFALINGER
1. Overvåk spesielt NW-NE og SE-SW vindretninger
2. Økt beredskap ved vindstyrke >6 m/s og temp <-1°C
3. Kombiner snødybde-data med vindretning for varsling
4. Implementer sanntids vindretning-varsling
"""
        
        return report
    
    def get_direction_name(self, direction: float) -> str:
        """Konverter grader til retningsnavn."""
        directions = [
            "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
        ]
        idx = int((direction + 11.25) / 22.5) % 16
        return directions[idx]
    
    def create_period_visualization(self, periods: List[Dict], summary: Dict):
        """Lag visualiseringer."""
        if not periods:
            return
        
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        fig.suptitle('Brøytesesong 2023-2024 - Snøfokk Perioder', fontsize=16, fontweight='bold')
        
        # 1. Månedlig fordeling
        month_names = ['Nov', 'Des', 'Jan', 'Feb', 'Mar', 'Apr']
        month_counts = [summary['monthly_distribution'].get(m, 0) for m in [11, 12, 1, 2, 3, 4]]
        
        bars = axes[0, 0].bar(month_names, month_counts, color='lightblue', edgecolor='navy')
        axes[0, 0].set_title('Snøfokk-perioder per måned', fontweight='bold')
        axes[0, 0].set_ylabel('Antall perioder')
        for bar, count in zip(bars, month_counts):
            if count > 0:
                axes[0, 0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                               str(count), ha='center', va='bottom')
        
        # 2. Vindrose
        ax2 = axes[0, 1]
        if summary['wind_direction_distribution']:
            directions = list(summary['wind_direction_distribution'].keys())
            counts = list(summary['wind_direction_distribution'].values())
            
            # Lag sirkulær plot
            theta = np.radians(directions)
            ax2.remove()
            ax2 = fig.add_subplot(2, 3, 2, projection='polar')
            bars = ax2.bar(theta, counts, width=np.pi/8, alpha=0.7, color='orange')
            ax2.set_title('Vindretning under snøfokk', fontweight='bold', pad=20)
            ax2.set_theta_zero_location('N')
            ax2.set_theta_direction(-1)
        
        # 3. Varighetsfordeling
        durations = [p['duration_hours'] for p in periods]
        axes[0, 2].hist(durations, bins=15, color='lightgreen', edgecolor='darkgreen', alpha=0.7)
        axes[0, 2].set_title('Fordeling av periodelengder', fontweight='bold')
        axes[0, 2].set_xlabel('Timer')
        axes[0, 2].set_ylabel('Antall perioder')
        
        # 4. Snøfokk-typer
        type_names = {
            'invisible_drift': 'Usynlig',
            'accumulating_drift': 'Akkumulering', 
            'eroding_drift': 'Erosjon'
        }
        types = [type_names.get(k, k) for k in summary['type_distribution'].keys()]
        type_counts = list(summary['type_distribution'].values())
        colors = ['orange', 'green', 'red'][:len(types)]
        
        axes[1, 0].pie(type_counts, labels=types, autopct='%1.1f%%', colors=colors, startangle=90)
        axes[1, 0].set_title('Snøfokk-typer', fontweight='bold')
        
        # 5. Faregrad
        danger_names = list(summary['danger_distribution'].keys())
        danger_counts = list(summary['danger_distribution'].values())
        danger_colors = {'HIGH': 'red', 'MEDIUM': 'orange', 'LOW': 'green'}
        bar_colors = [danger_colors.get(name, 'gray') for name in danger_names]
        
        bars = axes[1, 1].bar(danger_names, danger_counts, color=bar_colors)
        axes[1, 1].set_title('Faregrad fordeling', fontweight='bold')
        axes[1, 1].set_ylabel('Antall perioder')
        for bar, count in zip(bars, danger_counts):
            axes[1, 1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                           str(count), ha='center', va='bottom')
        
        # 6. Største perioder tidslinje
        major_periods = sorted([p for p in periods if p['duration_hours'] >= 6], 
                              key=lambda x: x['start_time'])
        
        if major_periods:
            dates = [p['start_time'] for p in major_periods]
            durations = [p['duration_hours'] for p in major_periods]
            colors = ['red' if p['road_danger'] == 'HIGH' else 'orange' for p in major_periods]
            
            axes[1, 2].scatter(dates, durations, c=colors, s=100, alpha=0.7)
            axes[1, 2].set_xlabel('Dato')
            axes[1, 2].set_ylabel('Varighet (timer)')
            axes[1, 2].set_title('Store perioder (≥6t)', fontweight='bold')
            plt.setp(axes[1, 2].xaxis.get_majorticklabels(), rotation=45)
        else:
            axes[1, 2].text(0.5, 0.5, 'Ingen perioder ≥6t', ha='center', va='center', 
                           transform=axes[1, 2].transAxes, fontsize=12)
            axes[1, 2].set_title('Store perioder (≥6t)', fontweight='bold')
        
        plt.tight_layout()
        plt.savefig('/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/season_periods_analysis.png',
                    dpi=300, bbox_inches='tight')
        plt.close()
    
    def run_complete_analysis(self):
        """Kjør komplett sesonganalyse."""
        print("🏔️ KOMPLETT BRØYTESESONG SNØFOKK-ANALYSE")
        print("=" * 50)
        print("Periode: 1. november 2023 - 30. april 2024")
        print("Fokus: Sammenhengende PERIODER (ikke enkelt-timer)")
        print("Ny faktor: VINDRETNING som risikofaktor")
        print("=" * 50)
        
        # 1. Hent data
        df = self.fetch_season_data()
        if df.empty:
            print("❌ Analyse avbrutt - ingen data")
            return
        
        # 2. Identifiser perioder
        periods = self.identify_continuous_periods(df)
        if not periods:
            print("❌ Ingen snøfokk-perioder identifisert")
            return
        
        # 3. Lag sammendrag
        summary = self.create_season_summary(periods)
        
        # 4. Generer rapport
        report = self.generate_report(periods, summary)
        
        # 5. Lag visualiseringer
        self.create_period_visualization(periods, summary)
        print("📈 Lagret visualiseringer til data/analyzed/season_periods_analysis.png")
        
        # 6. Lagre data
        report_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/season_periods_report.txt'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        analysis_data = {
            'analysis_type': 'season_periods_with_wind_direction',
            'analysis_date': datetime.now().isoformat(),
            'season': '2023-2024',
            'period': {
                'start': '2023-11-01',
                'end': '2024-04-30'
            },
            'summary': summary,
            'periods': periods  # Alle perioder
        }
        
        json_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/season_periods_analysis.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"📄 Lagret rapport til {report_file}")
        print(f"💾 Lagret data til {json_file}")
        print(report)
        
        # Topp 5 lengste perioder
        if periods:
            print("\n🏆 TOPP 5 LENGSTE SNØFOKK-PERIODER:")
            longest_periods = sorted(periods, key=lambda x: x['duration_hours'], reverse=True)[:5]
            
            for i, period in enumerate(longest_periods, 1):
                direction_str = f"{period['predominant_wind_direction']:.0f}°" if period['predominant_wind_direction'] else "N/A"
                print(f"""
{i}. {period['start_time'].strftime('%d.%m.%Y %H:%M')} - {period['end_time'].strftime('%d.%m.%Y %H:%M')}
   Varighet: {period['duration_hours']:.1f} timer
   Type: {period['drift_type'].replace('_', ' ').title()}
   Maks vind: {period['max_wind_speed']:.1f} m/s
   Min temp: {period['min_temperature']:.1f}°C
   Vindretning: {direction_str} ({period['wind_direction_risk']} risiko)
   Faregrad: {period['road_danger']}""")

def main():
    """Hovedfunksjon."""
    try:
        analyzer = SimpleSeasonSnowdriftAnalyzer()
        analyzer.run_complete_analysis()
        
    except Exception as e:
        print(f"❌ Feil: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
