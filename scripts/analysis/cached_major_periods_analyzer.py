#!/usr/bin/env python3
"""
Cached Snøfokk-Analyse med Bedre Periodegruppering
Implementerer caching og mer realistisk gruppering av snøfokk-perioder
"""

import json
import os
import pickle
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

# Last miljøvariabler
load_dotenv()

class CachedSnowdriftAnalyzer:
    """Snøfokk-analyse med caching og bedre gruppering."""

    def __init__(self):
        self.client_id = os.getenv('FROST_CLIENT_ID')
        if not self.client_id:
            raise ValueError("FROST_CLIENT_ID ikke funnet i miljøvariabler")

        self.cache_dir = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/cache'
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_cache_filename(self, start_date: str, end_date: str) -> str:
        """Generer cache-filnavn basert på datoer."""
        return os.path.join(self.cache_dir, f'weather_data_{start_date}_{end_date}.pkl')

    def load_cached_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Last inn cached data hvis tilgjengelig."""
        cache_file = self.get_cache_filename(start_date, end_date)

        if os.path.exists(cache_file):
            try:
                print(f"📁 Laster cached data fra {cache_file}")
                with open(cache_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"⚠️ Kunne ikke laste cache: {e}")
                return pd.DataFrame()

        return pd.DataFrame()

    def save_cached_data(self, df: pd.DataFrame, start_date: str, end_date: str):
        """Lagre data til cache."""
        cache_file = self.get_cache_filename(start_date, end_date)

        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(df, f)
            print(f"💾 Lagret data til cache: {cache_file}")
        except Exception as e:
            print(f"⚠️ Kunne ikke lagre cache: {e}")

    def fetch_season_data(self) -> pd.DataFrame:
        """Hent værdata for hele brøytesesongen med caching."""
        print("📅 Henter data for brøytesesong 2023-2024...")

        start_date = "2023-11-01"
        end_date = "2024-04-30"

        # Sjekk cache først
        cached_data = self.load_cached_data(start_date, end_date)
        if not cached_data.empty:
            print(f"✅ Bruker cached data: {len(cached_data)} datapunkter")
            return cached_data

        # Hvis ikke cached, hent fra API
        print("🌐 Henter fra Frost API...")

        station_id = "SN46220"  # Gullingen
        start_api = f"{start_date}T00:00:00.000Z"
        end_api = f"{end_date}T23:59:59.000Z"

        endpoint = 'https://frost.met.no/observations/v0.jsonld'
        parameters = {
            'sources': station_id,
            'referencetime': f'{start_api}/{end_api}',
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
            response = requests.get(endpoint, parameters, auth=(self.client_id, ''))

            if response.status_code != 200:
                print(f"❌ API feil {response.status_code}: {response.text}")
                return pd.DataFrame()

            data = response.json()

            if 'data' not in data or not data['data']:
                print("❌ Ingen data mottatt fra API")
                return pd.DataFrame()

            print(f"✅ Mottatt {len(data['data'])} datapunkter fra API")

            # Normaliser til DataFrame
            df = pd.json_normalize(data['data'])

            if 'observations' in df.columns:
                obs_df = df.explode('observations')
                obs_normalized = pd.json_normalize(obs_df['observations'])

                result_df = pd.concat([
                    obs_df[['sourceId', 'referenceTime']].reset_index(drop=True),
                    obs_normalized.reset_index(drop=True)
                ], axis=1)
            else:
                result_df = df

            # Pivot for analyse
            if 'elementId' in result_df.columns and 'value' in result_df.columns:
                pivoted = result_df.pivot_table(
                    index='referenceTime',
                    columns='elementId',
                    values='value',
                    aggfunc='first'
                ).reset_index()

                pivoted['referenceTime'] = pd.to_datetime(pivoted['referenceTime'])

                # Lagre til cache
                self.save_cached_data(pivoted, start_date, end_date)

                return pivoted
            else:
                print("❌ Forventet kolonner ikke funnet")
                return pd.DataFrame()

        except Exception as e:
            print(f"❌ Feil ved API-kall: {e}")
            return pd.DataFrame()

    def identify_major_snowdrift_periods(self, df: pd.DataFrame) -> list[dict]:
        """Identifiser STORE snøfokk-perioder med realistisk gruppering."""
        print("🔍 Identifiserer STORE snøfokk-perioder (mer realistisk gruppering)...")

        # Mer balanserte kriterier for å fange reelle perioder
        wind_threshold = 6.0     # Tilbake til 6 m/s
        temp_threshold = -1.0    # Tilbake til -1°C
        snow_threshold = 3.0     # Tilbake til 3 cm
        min_duration = 2         # Minimum 2 timer for å telle som periode

        periods = []
        current_period = None

        df = df.sort_values('referenceTime').reset_index(drop=True)

        for idx, row in df.iterrows():
            wind_speed = row.get('wind_speed', 0)
            air_temp = row.get('air_temperature', 0)
            snow_depth = row.get('surface_snow_thickness', 0)
            wind_direction = row.get('wind_from_direction', np.nan)

            # Håndter NaN-verdier
            if pd.isna(wind_speed) or pd.isna(air_temp) or pd.isna(snow_depth):
                if current_period and len(current_period['data_points']) >= min_duration:
                    periods.append(self.finalize_major_period(current_period))
                current_period = None
                continue

            # Evaluer snøfokk-kondisjon med strengere kriterier
            meets_criteria = (
                wind_speed >= wind_threshold and
                air_temp <= temp_threshold and
                snow_depth >= snow_threshold
            )

            if meets_criteria:
                if current_period is None:
                    current_period = {
                        'start_time': row['referenceTime'],
                        'end_time': row['referenceTime'],
                        'data_points': [row],
                        'wind_directions': [wind_direction] if not pd.isna(wind_direction) else [],
                        'wind_speeds': [wind_speed],
                        'temperatures': [air_temp],
                        'snow_depths': [snow_depth],
                        'max_wind_gusts': [row.get('max(wind_speed PT1H)', wind_speed)]
                    }
                else:
                    # Intelligent gappbrugging - kortere gap (2-4 timer) for å lage realistiske perioder
                    time_gap = (row['referenceTime'] - current_period['end_time']).total_seconds() / 3600

                    if time_gap <= 4.0:  # Redusert til 4 timer gap
                        # Utvid periode
                        current_period['end_time'] = row['referenceTime']
                        current_period['data_points'].append(row)
                        current_period['wind_speeds'].append(wind_speed)
                        current_period['temperatures'].append(air_temp)
                        current_period['snow_depths'].append(snow_depth)
                        current_period['max_wind_gusts'].append(row.get('max(wind_speed PT1H)', wind_speed))
                        if not pd.isna(wind_direction):
                            current_period['wind_directions'].append(wind_direction)
                    else:
                        # Gap for stort - ferdigstill hvis lang nok
                        if len(current_period['data_points']) >= min_duration:
                            periods.append(self.finalize_major_period(current_period))

                        # Start ny periode
                        current_period = {
                            'start_time': row['referenceTime'],
                            'end_time': row['referenceTime'],
                            'data_points': [row],
                            'wind_directions': [wind_direction] if not pd.isna(wind_direction) else [],
                            'wind_speeds': [wind_speed],
                            'temperatures': [air_temp],
                            'snow_depths': [snow_depth],
                            'max_wind_gusts': [row.get('max(wind_speed PT1H)', wind_speed)]
                        }
            else:
                # Ikke snøfokk - ferdigstill periode hvis lang nok
                if current_period and len(current_period['data_points']) >= min_duration:
                    periods.append(self.finalize_major_period(current_period))
                current_period = None

        # Ferdigstill siste periode
        if current_period and len(current_period['data_points']) >= min_duration:
            periods.append(self.finalize_major_period(current_period))

        print(f"✅ Identifiserte {len(periods)} STORE snøfokk-perioder (minimum {min_duration} timer)")
        return periods

    def finalize_major_period(self, period: dict) -> dict:
        """Ferdigstill stor periode med omfattende statistikker."""
        # Beregn varighet
        duration = (period['end_time'] - period['start_time']).total_seconds() / 3600
        period['duration_hours'] = round(duration + 1, 1)

        # Vindstatistikk
        period['max_wind_speed'] = max(period['wind_speeds'])
        period['avg_wind_speed'] = round(np.mean(period['wind_speeds']), 1)
        period['max_wind_gust'] = max(period['max_wind_gusts'])

        # Temperaturstatistikk
        period['min_temperature'] = min(period['temperatures'])
        period['max_temperature'] = max(period['temperatures'])
        period['avg_temperature'] = round(np.mean(period['temperatures']), 1)

        # Snøstatistikk
        period['snow_depth_start'] = period['snow_depths'][0]
        period['snow_depth_end'] = period['snow_depths'][-1]
        period['snow_change'] = round(period['snow_depth_end'] - period['snow_depth_start'], 1)
        period['min_snow_depth'] = min(period['snow_depths'])
        period['max_snow_depth'] = max(period['snow_depths'])

        # Vindretning analyse
        if period['wind_directions']:
            directions_rad = np.radians(period['wind_directions'])
            avg_x = np.mean(np.cos(directions_rad))
            avg_y = np.mean(np.sin(directions_rad))
            avg_direction = np.degrees(np.arctan2(avg_y, avg_x)) % 360
            period['predominant_wind_direction'] = round(avg_direction, 1)

            # Vindretning konsistens
            direction_std = np.std(period['wind_directions'])
            period['wind_direction_consistency'] = 'stable' if direction_std < 30 else 'variable'
        else:
            period['predominant_wind_direction'] = None
            period['wind_direction_consistency'] = 'unknown'

        # Klassifiser snøfokk-type
        abs_change = abs(period['snow_change'])
        if abs_change < 1.0:
            period['drift_type'] = 'invisible_drift'
        elif period['snow_change'] > 1.0:
            period['drift_type'] = 'accumulating_drift'
        else:
            period['drift_type'] = 'eroding_drift'

        # Intensitetsklassifikasjon
        if period['max_wind_speed'] >= 15.0:
            period['intensity'] = 'extreme'
        elif period['max_wind_speed'] >= 12.0:
            period['intensity'] = 'severe'
        elif period['max_wind_speed'] >= 10.0:
            period['intensity'] = 'moderate'
        else:
            period['intensity'] = 'light'

        # Vindretning risiko
        direction_risk = self.analyze_wind_direction_risk(period['predominant_wind_direction'])
        period['wind_direction_risk'] = direction_risk

        # Samlet risikoscore
        wind_factor = min(period['max_wind_speed'] / 20.0, 1.0)
        temp_factor = min(abs(period['min_temperature']) / 20.0, 1.0)
        duration_factor = min(period['duration_hours'] / 24.0, 1.0)
        direction_multiplier = 1.5 if direction_risk == 'high' else 1.0

        period['risk_score'] = min((wind_factor + temp_factor + duration_factor) * direction_multiplier / 3.0, 1.0)

        # Faregrad
        if period['risk_score'] >= 0.8 or period['intensity'] in ['extreme', 'severe']:
            period['road_danger'] = 'EXTREME'
        elif period['risk_score'] >= 0.6 or period['intensity'] == 'moderate':
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
        if (315 <= direction <= 360) or (0 <= direction <= 45):
            return 'high'  # NW-NE
        elif 135 <= direction <= 225:
            return 'high'  # SE-SW
        else:
            return 'medium'

    def analyze_february_crisis(self, periods: list[dict]) -> dict:
        """Spesiell analyse av februar 2024 krisen."""
        print("🚨 Analyserer februar 2024 snøfokk-krise...")

        feb_periods = []
        for period in periods:
            if period['start_time'].month == 2 and period['start_time'].year == 2024:
                feb_periods.append(period)

        if not feb_periods:
            return {'found': False, 'message': 'Ingen store perioder funnet i februar 2024'}

        # Sorter etter starttid
        feb_periods.sort(key=lambda x: x['start_time'])

        # Se etter perioder rundt 8-11 februar
        crisis_periods = []
        for period in feb_periods:
            day = period['start_time'].day
            if 8 <= day <= 11:
                crisis_periods.append(period)

        crisis_analysis = {
            'found': len(crisis_periods) > 0,
            'total_february_periods': len(feb_periods),
            'crisis_period_count': len(crisis_periods),
            'crisis_dates': [p['start_time'].strftime('%d.%m.%Y %H:%M') for p in crisis_periods],
            'crisis_periods': crisis_periods,
            'february_summary': {
                'total_hours': sum(p['duration_hours'] for p in feb_periods),
                'max_wind_speed': max(p['max_wind_speed'] for p in feb_periods) if feb_periods else 0,
                'min_temperature': min(p['min_temperature'] for p in feb_periods) if feb_periods else 0,
                'extreme_periods': len([p for p in feb_periods if p['road_danger'] == 'EXTREME'])
            }
        }

        return crisis_analysis

    def generate_detailed_report(self, periods: list[dict], feb_analysis: dict) -> str:
        """Generer detaljert rapport."""
        if not periods:
            return "Ingen store snøfokk-perioder identifisert."

        total_hours = sum(p['duration_hours'] for p in periods)
        avg_duration = total_hours / len(periods)
        longest_period = max(p['duration_hours'] for p in periods)

        # Intensitetsfordeling
        intensity_counts = {}
        for period in periods:
            intensity = period['intensity']
            intensity_counts[intensity] = intensity_counts.get(intensity, 0) + 1

        # Månedlig fordeling
        monthly_counts = {}
        for period in periods:
            month = period['start_time'].month
            month_name = {11: 'Nov', 12: 'Des', 1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr'}[month]
            monthly_counts[month_name] = monthly_counts.get(month_name, 0) + 1

        report = f"""
🏔️ REALISTISK BRØYTESESONG SNØFOKK-ANALYSE 2023-2024
====================================================

📊 STORE SNØFOKK-PERIODER (Minimum 3 timer, strengere kriterier)
Total antall STORE perioder: {len(periods)}
Samlet varighet: {total_hours:.1f} timer
Gjennomsnittlig periodelengde: {avg_duration:.1f} timer
Lengste periode: {longest_period:.1f} timer

🌪️ INTENSITETSFORDELING
"""

        for intensity, count in intensity_counts.items():
            percentage = (count / len(periods)) * 100
            report += f"  • {intensity.upper()}: {count} perioder ({percentage:.1f}%)\n"

        report += """
📅 MÅNEDLIG FORDELING
"""
        for month in ['Nov', 'Des', 'Jan', 'Feb', 'Mar', 'Apr']:
            if month in monthly_counts:
                count = monthly_counts[month]
                percentage = (count / len(periods)) * 100
                report += f"  • {month}: {count} perioder ({percentage:.1f}%)\n"

        # Februar 2024 krise-analyse
        if feb_analysis['found']:
            report += f"""

🚨 FEBRUAR 2024 SNØFOKK-KRISE BEKREFTET!
========================================
Perioder rundt 8-11 februar: {feb_analysis['crisis_period_count']}
Total februar perioder: {feb_analysis['total_february_periods']}
Total februar timer: {feb_analysis['february_summary']['total_hours']:.1f}
Maks vindstyrke: {feb_analysis['february_summary']['max_wind_speed']:.1f} m/s
Min temperatur: {feb_analysis['february_summary']['min_temperature']:.1f}°C
Ekstreme perioder: {feb_analysis['february_summary']['extreme_periods']}

KRISE-DATOER:
"""
            for date in feb_analysis['crisis_dates']:
                report += f"  • {date}\n"
        else:
            report += f"""

❓ FEBRUAR 2024 ANALYSE
======================
Fant {feb_analysis['total_february_periods']} perioder i februar 2024
Ingen spesifikke perioder rundt 8-11 februar med strengere kriterier
"""

        return report

    def create_crisis_visualization(self, periods: list[dict], feb_analysis: dict):
        """Lag visualisering med fokus på februar-krisen."""
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Brøytesesong 2023-2024 - Store Snøfokk-Perioder\n(Forbedret gruppering)',
                     fontsize=16, fontweight='bold')

        # 1. Tidslinje alle perioder
        dates = [p['start_time'] for p in periods]
        durations = [p['duration_hours'] for p in periods]
        colors = []
        for p in periods:
            if p['road_danger'] == 'EXTREME':
                colors.append('darkred')
            elif p['road_danger'] == 'HIGH':
                colors.append('red')
            elif p['road_danger'] == 'MEDIUM':
                colors.append('orange')
            else:
                colors.append('yellow')

        axes[0, 0].scatter(dates, durations, c=colors, s=100, alpha=0.7)
        axes[0, 0].set_xlabel('Dato')
        axes[0, 0].set_ylabel('Varighet (timer)')
        axes[0, 0].set_title('Alle store snøfokk-perioder')
        axes[0, 0].grid(True, alpha=0.3)

        # Highlight februar hvis relevant
        if feb_analysis['found']:
            feb_dates = [p['start_time'] for p in feb_analysis['crisis_periods']]
            feb_durations = [p['duration_hours'] for p in feb_analysis['crisis_periods']]
            axes[0, 0].scatter(feb_dates, feb_durations, c='purple', s=200, alpha=0.8,
                              marker='*', label='Februar krise')
            axes[0, 0].legend()

        plt.setp(axes[0, 0].xaxis.get_majorticklabels(), rotation=45)

        # 2. Månedlig fordeling
        monthly_counts = {}
        for period in periods:
            month = period['start_time'].month
            month_name = {11: 'Nov', 12: 'Des', 1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr'}[month]
            monthly_counts[month_name] = monthly_counts.get(month_name, 0) + 1

        months = ['Nov', 'Des', 'Jan', 'Feb', 'Mar', 'Apr']
        counts = [monthly_counts.get(m, 0) for m in months]
        bar_colors = ['purple' if m == 'Feb' and feb_analysis['found'] else 'lightblue' for m in months]

        bars = axes[0, 1].bar(months, counts, color=bar_colors, edgecolor='navy')
        axes[0, 1].set_title('Store perioder per måned')
        axes[0, 1].set_ylabel('Antall perioder')
        for bar, count in zip(bars, counts, strict=False):
            if count > 0:
                axes[0, 1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                               str(count), ha='center', va='bottom')

        # 3. Intensitetsfordeling
        intensity_counts = {}
        for period in periods:
            intensity = period['intensity']
            intensity_counts[intensity] = intensity_counts.get(intensity, 0) + 1

        intensity_colors = {'extreme': 'darkred', 'severe': 'red', 'moderate': 'orange', 'light': 'yellow'}
        colors_pie = [intensity_colors.get(k, 'gray') for k in intensity_counts.keys()]

        axes[1, 0].pie(intensity_counts.values(), labels=list(intensity_counts.keys()),
                      autopct='%1.1f%%', colors=colors_pie, startangle=90)
        axes[1, 0].set_title('Intensitetsfordeling')

        # 4. Detaljert februar analyse
        if feb_analysis['found'] and feb_analysis['crisis_periods']:
            crisis_periods = feb_analysis['crisis_periods']
            crisis_dates = [p['start_time'].day for p in crisis_periods]
            crisis_intensities = [p['max_wind_speed'] for p in crisis_periods]

            axes[1, 1].bar(range(len(crisis_periods)), crisis_intensities, color='darkred', alpha=0.7)
            axes[1, 1].set_xlabel('Periode nummer')
            axes[1, 1].set_ylabel('Maks vindstyrke (m/s)')
            axes[1, 1].set_title('Februar 8-11 krise-perioder')
            axes[1, 1].set_xticks(range(len(crisis_periods)))
            axes[1, 1].set_xticklabels([f'{d}.feb' for d in crisis_dates], rotation=45)
        else:
            axes[1, 1].text(0.5, 0.5, 'Ingen krise-perioder\nfunnet 8-11 feb',
                           ha='center', va='center', transform=axes[1, 1].transAxes, fontsize=12)
            axes[1, 1].set_title('Februar 8-11 analyse')

        plt.tight_layout()
        plt.savefig('/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/major_periods_analysis.png',
                    dpi=300, bbox_inches='tight')
        plt.close()

    def run_improved_analysis(self):
        """Kjør forbedret analyse med caching og bedre gruppering."""
        print("🏔️ FORBEDRET SNØFOKK-ANALYSE MED CACHING")
        print("=" * 50)
        print("🎯 Fokus: STORE perioder (minimum 2 timer)")
        print("🎯 Balanserte kriterier: Vind ≥6 m/s, Temp ≤-1°C, Snø ≥3 cm")
        print("🎯 Spesiell analyse: Februar 8-11, 2024 krise")
        print("=" * 50)

        # 1. Hent data (med caching)
        df = self.fetch_season_data()
        if df.empty:
            print("❌ Analyse avbrutt - ingen data")
            return

        # 2. Identifiser store perioder
        periods = self.identify_major_snowdrift_periods(df)
        if not periods:
            print("❌ Ingen store snøfokk-perioder identifisert")
            return

        # 3. Analyser februar-krisen
        feb_analysis = self.analyze_february_crisis(periods)

        # 4. Generer rapport
        report = self.generate_detailed_report(periods, feb_analysis)

        # 5. Lag visualiseringer
        self.create_crisis_visualization(periods, feb_analysis)
        print("📈 Lagret visualiseringer til data/analyzed/major_periods_analysis.png")

        # 6. Lagre data
        report_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/major_periods_report.txt'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        analysis_data = {
            'analysis_type': 'major_periods_with_february_crisis',
            'analysis_date': datetime.now().isoformat(),
            'season': '2023-2024',
            'criteria': {
                'min_wind_speed': 6.0,
                'max_temperature': -1.0,
                'min_snow_depth': 3.0,
                'min_duration_hours': 2
            },
            'total_periods': len(periods),
            'february_crisis': feb_analysis,
            'periods': periods
        }

        json_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/major_periods_analysis.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, ensure_ascii=False, indent=2, default=str)

        print(f"📄 Lagret rapport til {report_file}")
        print(f"💾 Lagret data til {json_file}")
        print(report)

        # Vis topp perioder
        if periods:
            print("\n🏆 TOPP 5 MEST INTENSE SNØFOKK-PERIODER:")
            top_periods = sorted(periods, key=lambda x: x['risk_score'], reverse=True)[:5]

            for i, period in enumerate(top_periods, 1):
                feb_marker = " 🚨 FEBRUAR KRISE!" if (period['start_time'].month == 2 and
                                                    8 <= period['start_time'].day <= 11) else ""
                print(f"""
{i}. {period['start_time'].strftime('%d.%m.%Y %H:%M')} - {period['end_time'].strftime('%d.%m.%Y %H:%M')}{feb_marker}
   Varighet: {period['duration_hours']:.1f} timer
   Intensitet: {period['intensity'].upper()}
   Maks vind: {period['max_wind_speed']:.1f} m/s (kast: {period['max_wind_gust']:.1f})
   Min temp: {period['min_temperature']:.1f}°C
   Snøendring: {period['snow_change']:+.1f} cm
   Vindretning: {period['predominant_wind_direction']:.0f}° ({period['wind_direction_risk']} risiko)
   Faregrad: {period['road_danger']}
   Risikoscore: {period['risk_score']:.2f}""")

def main():
    """Hovedfunksjon."""
    try:
        analyzer = CachedSnowdriftAnalyzer()
        analyzer.run_improved_analysis()

    except Exception as e:
        print(f"❌ Feil: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
