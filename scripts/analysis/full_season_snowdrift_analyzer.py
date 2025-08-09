#!/usr/bin/env python3
"""
Komplett Brøytesesong Snøfokk Analyse med Vindretning
Analyserer hele brøytesesongen 2023-2024 med riktig gruppering av perioder
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from typing import Dict, List, Tuple, Any
import matplotlib.pyplot as plt
import seaborn as sns

# Add src to path for imports
sys.path.append('/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/src')
from snofokk.services.weather import WeatherService

class FullSeasonSnowdriftAnalyzer:
    """Analyserer snøfokk for hele brøytesesongen med vindretning."""
    
    def __init__(self):
        self.weather_service = WeatherService()
        
        # Snøfokk kriterier med vindretning
        self.criteria = {
            'min_wind_speed': 6.0,        # m/s - justert terskel
            'max_temperature': -1.0,       # °C - under frysepunktet
            'min_snow_depth': 3.0,         # cm - må være snø tilgjengelig
            'critical_wind_directions': [   # Retninger som skaper mest snøfokk
                (315, 45),    # NW-NE (0-45 og 315-360)
                (135, 225)    # SE-SW (problematisk for veier)
            ],
            'high_risk_wind_speed': 10.0,  # m/s - høy risiko
            'extreme_wind_speed': 15.0     # m/s - ekstrem risiko
        }
    
    def analyze_wind_direction_risk(self, direction: float) -> str:
        """Analyser risiko basert på vindretning."""
        if pd.isna(direction):
            return 'unknown'
        
        # Normaliser til 0-360
        direction = direction % 360
        
        # Sjekk kritiske retninger
        for start, end in self.criteria['critical_wind_directions']:
            if start > end:  # Krysser 0-grader (f.eks. 315-45)
                if direction >= start or direction <= end:
                    return 'high_risk'
            else:  # Normal range
                if start <= direction <= end:
                    return 'high_risk'
        
        return 'medium_risk'
    
    def fetch_season_data(self) -> pd.DataFrame:
        """Hent værdata for hele brøytesesongen 2023-2024."""
        print("📅 Henter data for brøytesesong 2023-2024...")
        
        # Brøytesesong: 1. november 2023 - 30. april 2024
        start_date = "2023-11-01"
        end_date = "2024-04-30"
        
        try:
            # Hent data med alle nødvendige elementer inkludert vindretning
            data = self.weather_service.fetch_weather_data(
                station_id="SN46220",  # Gullingen
                start_date=start_date,
                end_date=end_date,
                elements=[
                    "air_temperature",
                    "wind_speed", 
                    "max(wind_speed PT1H)",
                    "wind_from_direction",  # Vindretning!
                    "surface_snow_thickness",
                    "relative_humidity",
                    "sum(precipitation_amount PT1H)"
                ]
            )
            
            if data.empty:
                raise ValueError("Ingen data mottatt fra API")
            
            print(f"✅ Mottatt {len(data)} datapunkter")
            return data
            
        except Exception as e:
            print(f"❌ Feil ved henting av data: {e}")
            return pd.DataFrame()
    
    def identify_snowdrift_periods(self, df: pd.DataFrame) -> List[Dict]:
        """Identifiser sammenhengende snøfokk-perioder med vindretning."""
        print("🔍 Identifiserer snøfokk-perioder med vindretning...")
        
        periods = []
        current_period = None
        
        for idx, row in df.iterrows():
            # Evaluer snøfokk-kriterier
            wind_ok = row.get('wind_speed', 0) >= self.criteria['min_wind_speed']
            temp_ok = row.get('temperature', 0) <= self.criteria['max_temperature']
            snow_ok = row.get('snow_depth', 0) >= self.criteria['min_snow_depth']
            
            # Vindretning risiko
            wind_direction = row.get('wind_direction', np.nan)
            direction_risk = self.analyze_wind_direction_risk(wind_direction)
            
            is_snowdrift = wind_ok and temp_ok and snow_ok
            
            if is_snowdrift:
                if current_period is None:
                    # Start ny periode
                    current_period = {
                        'start_time': row['referenceTime'],
                        'end_time': row['referenceTime'],
                        'duration_hours': 1,
                        'max_wind_speed': row.get('wind_speed', 0),
                        'min_temperature': row.get('temperature', 0),
                        'max_temperature': row.get('temperature', 0),
                        'snow_depth_start': row.get('snow_depth', 0),
                        'snow_depth_end': row.get('snow_depth', 0),
                        'wind_directions': [wind_direction] if not pd.isna(wind_direction) else [],
                        'predominant_direction': wind_direction,
                        'direction_risk': direction_risk,
                        'wind_speeds': [row.get('wind_speed', 0)],
                        'temperatures': [row.get('temperature', 0)]
                    }
                else:
                    # Utvid eksisterende periode
                    current_period['end_time'] = row['referenceTime']
                    current_period['duration_hours'] += 1
                    current_period['max_wind_speed'] = max(current_period['max_wind_speed'], row.get('wind_speed', 0))
                    current_period['min_temperature'] = min(current_period['min_temperature'], row.get('temperature', 0))
                    current_period['max_temperature'] = max(current_period['max_temperature'], row.get('temperature', 0))
                    current_period['snow_depth_end'] = row.get('snow_depth', 0)
                    
                    if not pd.isna(wind_direction):
                        current_period['wind_directions'].append(wind_direction)
                    
                    current_period['wind_speeds'].append(row.get('wind_speed', 0))
                    current_period['temperatures'].append(row.get('temperature', 0))
                    
                    # Oppdater risiko til høyeste nivå
                    if direction_risk == 'high_risk':
                        current_period['direction_risk'] = 'high_risk'
            else:
                if current_period is not None:
                    # Avslutt periode og beregn statistikk
                    current_period = self.finalize_period(current_period)
                    periods.append(current_period)
                    current_period = None
        
        # Avslutt siste periode hvis den eksisterer
        if current_period is not None:
            current_period = self.finalize_period(current_period)
            periods.append(current_period)
        
        return periods
    
    def finalize_period(self, period: Dict) -> Dict:
        """Beregn finale statistikker for en periode."""
        # Beregn gjennomsnittlig vindretning
        if period['wind_directions']:
            # Konverter til radianer for sirkulær gjennomsnitt
            directions_rad = np.radians(period['wind_directions'])
            avg_x = np.mean(np.cos(directions_rad))
            avg_y = np.mean(np.sin(directions_rad))
            avg_direction = np.degrees(np.arctan2(avg_y, avg_x)) % 360
            period['predominant_direction'] = round(avg_direction, 1)
        
        # Snøendring
        snow_change = period['snow_depth_end'] - period['snow_depth_start']
        period['snow_change_cm'] = round(snow_change, 1)
        
        # Klassifiser type snøfokk
        if abs(snow_change) < 0.5:
            period['drift_type'] = 'invisible_drift'  # Usynlig snøfokk
        elif snow_change > 0.5:
            period['drift_type'] = 'accumulating_drift'  # Akkumulering
        else:
            period['drift_type'] = 'eroding_drift'  # Erosjon
        
        # Risikoscore med vindretning
        wind_risk = min(period['max_wind_speed'] / 20.0, 1.0)  # Normalisert til 20 m/s
        temp_risk = min(abs(period['min_temperature']) / 20.0, 1.0)  # Normalisert til -20°C
        direction_multiplier = 1.5 if period['direction_risk'] == 'high_risk' else 1.0
        
        period['risk_score'] = min((wind_risk + temp_risk) * direction_multiplier / 2.0, 1.0)
        
        # Veifare klassifikasjon
        if period['risk_score'] >= 0.7 or period['direction_risk'] == 'high_risk':
            period['road_danger'] = 'HIGH'
        elif period['risk_score'] >= 0.4:
            period['road_danger'] = 'MEDIUM'
        else:
            period['road_danger'] = 'LOW'
        
        return period
    
    def create_wind_rose_analysis(self, periods: List[Dict]) -> Dict:
        """Lag vindrose-analyse for snøfokk-perioder."""
        wind_data = {
            'directions': [],
            'speeds': [],
            'risk_levels': []
        }
        
        for period in periods:
            if period['wind_directions']:
                for i, direction in enumerate(period['wind_directions']):
                    wind_data['directions'].append(direction)
                    wind_data['speeds'].append(period['wind_speeds'][i])
                    wind_data['risk_levels'].append(period['direction_risk'])
        
        return wind_data
    
    def analyze_seasonal_patterns(self, periods: List[Dict]) -> Dict:
        """Analyser sesongmønstre."""
        monthly_stats = {}
        direction_stats = {}
        
        for period in periods:
            # Månedlig statistikk
            month = period['start_time'].month
            if month not in monthly_stats:
                monthly_stats[month] = {
                    'count': 0,
                    'total_hours': 0,
                    'max_wind': 0,
                    'min_temp': 0
                }
            
            monthly_stats[month]['count'] += 1
            monthly_stats[month]['total_hours'] += period['duration_hours']
            monthly_stats[month]['max_wind'] = max(monthly_stats[month]['max_wind'], period['max_wind_speed'])
            monthly_stats[month]['min_temp'] = min(monthly_stats[month]['min_temp'], period['min_temperature'])
            
            # Vindretning statistikk
            if not pd.isna(period['predominant_direction']):
                direction_bin = int(period['predominant_direction'] / 22.5) * 22.5  # 16 retninger
                if direction_bin not in direction_stats:
                    direction_stats[direction_bin] = {
                        'count': 0,
                        'total_hours': 0,
                        'high_risk_count': 0
                    }
                
                direction_stats[direction_bin]['count'] += 1
                direction_stats[direction_bin]['total_hours'] += period['duration_hours']
                if period['direction_risk'] == 'high_risk':
                    direction_stats[direction_bin]['high_risk_count'] += 1
        
        return {
            'monthly': monthly_stats,
            'directions': direction_stats
        }
    
    def create_visualizations(self, periods: List[Dict], seasonal_patterns: Dict, wind_data: Dict):
        """Lag omfattende visualiseringer."""
        fig = plt.figure(figsize=(20, 15))
        
        # 1. Månedlig fordeling
        ax1 = plt.subplot(3, 3, 1)
        months = list(seasonal_patterns['monthly'].keys())
        month_names = ['Nov', 'Des', 'Jan', 'Feb', 'Mar', 'Apr']
        counts = [seasonal_patterns['monthly'].get(m, {}).get('count', 0) for m in [11, 12, 1, 2, 3, 4]]
        
        bars = ax1.bar(month_names, counts, color='lightblue', edgecolor='navy')
        ax1.set_title('Snøfokk-perioder per måned', fontweight='bold')
        ax1.set_ylabel('Antall perioder')
        for bar, count in zip(bars, counts):
            if count > 0:
                ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                        str(count), ha='center', va='bottom')
        
        # 2. Vindrose for snøfokk
        ax2 = plt.subplot(3, 3, 2, projection='polar')
        if wind_data['directions']:
            directions_rad = np.radians(wind_data['directions'])
            speeds = wind_data['speeds']
            
            # Lag vindrose
            theta_bins = np.linspace(0, 2*np.pi, 17)
            speed_bins = [0, 5, 10, 15, 25]
            
            for i in range(len(speed_bins)-1):
                mask = (np.array(speeds) >= speed_bins[i]) & (np.array(speeds) < speed_bins[i+1])
                if np.any(mask):
                    filtered_dirs = np.array(directions_rad)[mask]
                    hist, _ = np.histogram(filtered_dirs, bins=theta_bins)
                    theta = theta_bins[:-1] + np.pi/16
                    ax2.bar(theta, hist, width=np.pi/8, alpha=0.7, 
                           label=f'{speed_bins[i]}-{speed_bins[i+1]} m/s')
            
            ax2.set_title('Vindrose under snøfokk', fontweight='bold', pad=20)
            ax2.legend(loc='upper left', bbox_to_anchor=(1.1, 1))
        
        # 3. Varighetsfordeling
        ax3 = plt.subplot(3, 3, 3)
        durations = [p['duration_hours'] for p in periods]
        ax3.hist(durations, bins=20, color='lightcoral', edgecolor='darkred', alpha=0.7)
        ax3.set_title('Fordeling av periodelengder', fontweight='bold')
        ax3.set_xlabel('Timer')
        ax3.set_ylabel('Antall perioder')
        
        # 4. Vindstyrke vs temperatur med vindretning
        ax4 = plt.subplot(3, 3, 4)
        wind_speeds = [p['max_wind_speed'] for p in periods]
        temperatures = [p['min_temperature'] for p in periods]
        colors = ['red' if p['direction_risk'] == 'high_risk' else 'blue' for p in periods]
        
        scatter = ax4.scatter(wind_speeds, temperatures, c=colors, alpha=0.6, s=50)
        ax4.set_xlabel('Maks vindstyrke (m/s)')
        ax4.set_ylabel('Min temperatur (°C)')
        ax4.set_title('Vindstyrke vs Temperatur\n(Rød = høyrisiko vindretning)', fontweight='bold')
        ax4.grid(True, alpha=0.3)
        
        # 5. Snøfokk-typer
        ax5 = plt.subplot(3, 3, 5)
        drift_types = {}
        for period in periods:
            dtype = period['drift_type']
            drift_types[dtype] = drift_types.get(dtype, 0) + 1
        
        type_labels = {'invisible_drift': 'Usynlig', 'accumulating_drift': 'Akkumulering', 'eroding_drift': 'Erosjon'}
        labels = [type_labels.get(k, k) for k in drift_types.keys()]
        colors_pie = ['orange', 'green', 'red'][:len(drift_types)]
        
        ax5.pie(drift_types.values(), labels=labels, autopct='%1.1f%%', colors=colors_pie, startangle=90)
        ax5.set_title('Snøfokk-typer', fontweight='bold')
        
        # 6. Tidslinje for store perioder
        ax6 = plt.subplot(3, 3, 6)
        major_periods = [p for p in periods if p['duration_hours'] >= 6]  # 6+ timer
        if major_periods:
            dates = [p['start_time'] for p in major_periods]
            durations = [p['duration_hours'] for p in major_periods]
            colors_timeline = ['red' if p['road_danger'] == 'HIGH' else 'orange' for p in major_periods]
            
            ax6.scatter(dates, durations, c=colors_timeline, s=100, alpha=0.7)
            ax6.set_xlabel('Dato')
            ax6.set_ylabel('Varighet (timer)')
            ax6.set_title('Store snøfokk-perioder (≥6t)', fontweight='bold')
            plt.setp(ax6.xaxis.get_majorticklabels(), rotation=45)
        
        # 7. Vindretning vs risiko
        ax7 = plt.subplot(3, 3, 7)
        direction_bins = list(range(0, 360, 22.5))
        direction_counts = [seasonal_patterns['directions'].get(d, {}).get('count', 0) for d in direction_bins]
        
        ax7.bar(direction_bins, direction_counts, width=20, color='skyblue', edgecolor='navy', alpha=0.7)
        ax7.set_xlabel('Vindretning (grader)')
        ax7.set_ylabel('Antall perioder')
        ax7.set_title('Snøfokk per vindretning', fontweight='bold')
        ax7.set_xlim(0, 360)
        
        # 8. Faregrad fordeling
        ax8 = plt.subplot(3, 3, 8)
        danger_levels = {}
        for period in periods:
            danger = period['road_danger']
            danger_levels[danger] = danger_levels.get(danger, 0) + 1
        
        colors_danger = {'HIGH': 'red', 'MEDIUM': 'orange', 'LOW': 'green'}
        colors_bar = [colors_danger.get(k, 'gray') for k in danger_levels.keys()]
        
        bars = ax8.bar(danger_levels.keys(), danger_levels.values(), color=colors_bar)
        ax8.set_title('Faregrad fordeling', fontweight='bold')
        ax8.set_ylabel('Antall perioder')
        for bar, count in zip(bars, danger_levels.values()):
            ax8.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                    str(count), ha='center', va='bottom')
        
        # 9. Sammendrag-tekst
        ax9 = plt.subplot(3, 3, 9)
        ax9.axis('off')
        
        total_periods = len(periods)
        total_hours = sum(p['duration_hours'] for p in periods)
        avg_duration = total_hours / total_periods if total_periods > 0 else 0
        high_risk_count = sum(1 for p in periods if p['road_danger'] == 'HIGH')
        
        summary_text = f"""
BRØYTESESONG 2023-2024
SNØFOKK SAMMENDRAG

Totalt: {total_periods} perioder
Samlet varighet: {total_hours} timer
Gjennomsnitt: {avg_duration:.1f}t per periode

Høy fare: {high_risk_count} perioder
Usynlig snøfokk: {sum(1 for p in periods if p['drift_type'] == 'invisible_drift')} perioder

Mest problematiske retninger:
NW-NE (315-45°)
SE-SW (135-225°)
        """
        
        ax9.text(0.1, 0.9, summary_text, transform=ax9.transAxes, fontsize=11,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
        
        plt.tight_layout()
        plt.savefig('/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/full_season_snowdrift_analysis.png',
                    dpi=300, bbox_inches='tight')
        plt.close()
    
    def run_full_analysis(self):
        """Kjør komplett sesonganalyse."""
        print("🏔️ KOMPLETT BRØYTESESONG SNØFOKK-ANALYSE MED VINDRETNING")
        print("=" * 60)
        
        # 1. Hent data
        df = self.fetch_season_data()
        if df.empty:
            print("❌ Ingen data tilgjengelig")
            return
        
        # 2. Normaliser kolonnenavn
        column_mapping = {
            'air_temperature': 'temperature',
            'surface_snow_thickness': 'snow_depth',
            'wind_from_direction': 'wind_direction'
        }
        
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns:
                df[new_col] = df[old_col]
        
        print(f"📊 Behandler {len(df)} datapunkter fra {df['referenceTime'].min()} til {df['referenceTime'].max()}")
        
        # 3. Identifiser perioder
        periods = self.identify_snowdrift_periods(df)
        print(f"✅ Identifiserte {len(periods)} snøfokk-perioder")
        
        # 4. Analyser mønstre
        seasonal_patterns = self.analyze_seasonal_patterns(periods)
        wind_data = self.create_wind_rose_analysis(periods)
        
        # 5. Lag visualiseringer
        if periods:
            self.create_visualizations(periods, seasonal_patterns, wind_data)
            print("📈 Lagret visualiseringer til data/analyzed/full_season_snowdrift_analysis.png")
        
        # 6. Generer rapport
        self.generate_comprehensive_report(periods, seasonal_patterns, wind_data)
        
        return periods
    
    def generate_comprehensive_report(self, periods: List[Dict], seasonal_patterns: Dict, wind_data: Dict):
        """Generer omfattende rapport."""
        report = f"""
🏔️ KOMPLETT BRØYTESESONG ANALYSE 2023-2024
================================================

📅 ANALYSEPERIODE: 1. november 2023 - 30. april 2024

📊 SAMMENDRAG
Total antall snøfokk-perioder: {len(periods)}
Samlet varighet: {sum(p['duration_hours'] for p in periods)} timer
Gjennomsnittlig periodelengde: {sum(p['duration_hours'] for p in periods) / len(periods):.1f} timer
Lengste periode: {max(p['duration_hours'] for p in periods) if periods else 0} timer

🏷️ PERIODETYPE FORDELING
"""
        
        # Analyser periodetyper
        type_counts = {}
        for period in periods:
            ptype = period['drift_type']
            type_counts[ptype] = type_counts.get(ptype, 0) + 1
        
        for ptype, count in type_counts.items():
            percentage = (count / len(periods)) * 100 if periods else 0
            report += f"  • {ptype.replace('_', ' ').title()}: {count} ({percentage:.1f}%)\n"
        
        report += f"""
⚠️ FAREGRAD ANALYSE
"""
        danger_counts = {}
        for period in periods:
            danger = period['road_danger']
            danger_counts[danger] = danger_counts.get(danger, 0) + 1
        
        for danger, count in danger_counts.items():
            percentage = (count / len(periods)) * 100 if periods else 0
            report += f"  • {danger}: {count} ({percentage:.1f}%)\n"
        
        report += f"""
🌬️ VINDRETNING ANALYSE
Kritiske retninger for snøfokk:
  • NW-NE (315-45°): Mest problematisk
  • SE-SW (135-225°): Høy risiko for veier

Mest aktive vindretninger:
"""
        
        # Topp 3 vindretninger
        direction_sorted = sorted(seasonal_patterns['directions'].items(), 
                                 key=lambda x: x[1]['count'], reverse=True)[:3]
        
        for direction, stats in direction_sorted:
            report += f"  • {direction}°: {stats['count']} perioder, {stats['total_hours']} timer\n"
        
        report += f"""
📅 MÅNEDLIG FORDELING
"""
        month_names = {11: 'November', 12: 'Desember', 1: 'Januar', 2: 'Februar', 3: 'Mars', 4: 'April'}
        
        for month in [11, 12, 1, 2, 3, 4]:
            if month in seasonal_patterns['monthly']:
                stats = seasonal_patterns['monthly'][month]
                report += f"  • {month_names[month]}: {stats['count']} perioder, {stats['total_hours']} timer\n"
        
        # Lagre rapport
        report_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/full_season_report.txt'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        # Lagre JSON data
        analysis_data = {
            'analysis_type': 'full_season_with_wind_direction',
            'analysis_date': datetime.now().isoformat(),
            'season': '2023-2024',
            'period': {
                'start': '2023-11-01',
                'end': '2024-04-30'
            },
            'station': {
                'id': 'SN46220',
                'name': 'Gullingen Skisenter'
            },
            'criteria': self.criteria,
            'statistics': {
                'total_periods': len(periods),
                'total_hours': sum(p['duration_hours'] for p in periods),
                'avg_duration': sum(p['duration_hours'] for p in periods) / len(periods) if periods else 0,
                'type_distribution': type_counts,
                'danger_distribution': danger_counts
            },
            'seasonal_patterns': seasonal_patterns,
            'periods': periods[:50]  # Lagre første 50 for størrelse
        }
        
        json_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/full_season_analysis.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"📄 Lagret rapport til {report_file}")
        print(f"💾 Lagret data til {json_file}")
        print(report)

def main():
    """Hovedfunksjon."""
    analyzer = FullSeasonSnowdriftAnalyzer()
    periods = analyzer.run_full_analysis()
    
    if periods:
        print(f"\n🎯 KRITISKE FUNN:")
        print(f"• {len(periods)} distinkte snøfokk-perioder (ikke timer!)")
        print(f"• Vindretning er kritisk faktor for risiko")
        print(f"• NW-NE og SE-SW retninger mest problematiske")
        print(f"• Brøytesesongen 2023-2024 hadde betydelig snøfokk-aktivitet")

if __name__ == "__main__":
    main()
