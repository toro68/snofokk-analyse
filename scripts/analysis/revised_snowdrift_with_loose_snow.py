#!/usr/bin/env python3
"""
REVIDERT Snøfokk-analyse med løssnø-kriterier
"""

import json
import pickle
from datetime import datetime

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

class RevisedSnowdriftAnalyzer:
    """Revidert snøfokk-analyse som inkluderer løssnø-tilgjengelighet."""

    def __init__(self):
        self.cache_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/cache/weather_data_2023-11-01_2024-04-30.pkl'
        self.loose_snow_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/cache/loose_snow_analysis.pkl'

    def load_data(self) -> pd.DataFrame:
        """Last inn data med løssnø-analyse."""
        with open(self.loose_snow_file, 'rb') as f:
            return pickle.load(f)

    def find_realistic_snowdrift_with_loose_snow(self, df: pd.DataFrame) -> list[dict]:
        """Finn snøfokk-perioder med krav om løssnø-tilgjengelighet."""
        print("🔍 Finner snøfokk-perioder med LØSSNØ-kriterier...")

        # Filtrer til kun rader med gyldig vinddata OG løssnø tilgjengelig
        valid_data = df[
            (df['wind_speed'].notna()) &
            (df['wind_from_direction'].notna()) &
            (df['loose_snow_available'] == True)
        ].copy()

        print(f"📊 Gyldige data med løssnø: {len(valid_data)}/{len(df)} datapunkter")
        print(f"📊 Reduksjon fra løssnø-krav: {len(df.dropna(subset=['wind_speed'])) - len(valid_data)} timer eliminert")

        if valid_data.empty:
            return []

        # Snøfokk-kriterier (strengere pga løssnø-krav)
        wind_threshold = 6.0
        temp_threshold = -1.0
        snow_threshold = 3.0

        periods = []

        # Sorter etter tid
        valid_data = valid_data.sort_values('referenceTime').reset_index(drop=True)

        # Gruppe sammenhengende snøfokk-timer
        current_period = None
        max_gap_hours = 4  # Strengere gap-toleranse pga løssnø kan ødelegges raskt

        for idx, row in valid_data.iterrows():
            wind_speed = row['wind_speed']
            air_temp = row['air_temperature']
            snow_depth = row['surface_snow_thickness']
            wind_direction = row['wind_from_direction']
            timestamp = row['referenceTime']
            hours_since_mild = row['hours_since_mild']
            frost_duration = row['frost_duration']

            # Sjekk snøfokk-kriterier
            meets_criteria = (
                wind_speed >= wind_threshold and
                air_temp <= temp_threshold and
                snow_depth >= snow_threshold and
                hours_since_mild >= 24 and  # Minst 24t siden mildvær
                frost_duration >= 12        # Minst 12t sammenhengende frost
            )

            if meets_criteria:
                if current_period is None:
                    # Start ny periode
                    current_period = {
                        'start_time': timestamp,
                        'end_time': timestamp,
                        'measurements': [row],
                        'wind_speeds': [wind_speed],
                        'temperatures': [air_temp],
                        'snow_depths': [snow_depth],
                        'wind_directions': [wind_direction],
                        'hours_since_mild': [hours_since_mild],
                        'frost_durations': [frost_duration]
                    }
                else:
                    # Sjekk gap til forrige måling
                    time_gap = (timestamp - current_period['end_time']).total_seconds() / 3600

                    if time_gap <= max_gap_hours:
                        # Utvid periode
                        current_period['end_time'] = timestamp
                        current_period['measurements'].append(row)
                        current_period['wind_speeds'].append(wind_speed)
                        current_period['temperatures'].append(air_temp)
                        current_period['snow_depths'].append(snow_depth)
                        current_period['wind_directions'].append(wind_direction)
                        current_period['hours_since_mild'].append(hours_since_mild)
                        current_period['frost_durations'].append(frost_duration)
                    else:
                        # Gap for stort - ferdigstill periode og start ny
                        if len(current_period['measurements']) >= 2:  # Minst 2 målinger for løssnø
                            periods.append(self.finalize_loose_snow_period(current_period))

                        current_period = {
                            'start_time': timestamp,
                            'end_time': timestamp,
                            'measurements': [row],
                            'wind_speeds': [wind_speed],
                            'temperatures': [air_temp],
                            'snow_depths': [snow_depth],
                            'wind_directions': [wind_direction],
                            'hours_since_mild': [hours_since_mild],
                            'frost_durations': [frost_duration]
                        }
            else:
                # Ikke snøfokk - ferdigstill periode
                if current_period and len(current_period['measurements']) >= 2:
                    periods.append(self.finalize_loose_snow_period(current_period))
                    current_period = None

        # Ferdigstill siste periode
        if current_period and len(current_period['measurements']) >= 2:
            periods.append(self.finalize_loose_snow_period(current_period))

        print(f"✅ Funnet {len(periods)} realistiske snøfokk-perioder MED løssnø")
        return periods

    def finalize_loose_snow_period(self, period: dict) -> dict:
        """Ferdigstill periode med løssnø-statistikk."""
        start_time = period['start_time']
        end_time = period['end_time']
        duration_hours = (end_time - start_time).total_seconds() / 3600

        period['estimated_duration_hours'] = round(max(duration_hours + 1, 1), 1)
        period['measurement_count'] = len(period['measurements'])

        # Vindstatistikk
        period['max_wind_speed'] = max(period['wind_speeds'])
        period['avg_wind_speed'] = round(np.mean(period['wind_speeds']), 1)
        period['min_wind_speed'] = min(period['wind_speeds'])

        # Temperaturstatistikk
        period['min_temperature'] = min(period['temperatures'])
        period['max_temperature'] = max(period['temperatures'])
        period['avg_temperature'] = round(np.mean(period['temperatures']), 1)

        # Snøstatistikk
        period['snow_depth_start'] = period['snow_depths'][0]
        period['snow_depth_end'] = period['snow_depths'][-1]
        period['snow_change'] = round(period['snow_depth_end'] - period['snow_depth_start'], 1)
        period['avg_snow_depth'] = round(np.mean(period['snow_depths']), 1)

        # Løssnø-kvalitet
        period['min_hours_since_mild'] = min(period['hours_since_mild'])
        period['avg_hours_since_mild'] = round(np.mean(period['hours_since_mild']), 1)
        period['min_frost_duration'] = min(period['frost_durations'])
        period['avg_frost_duration'] = round(np.mean(period['frost_durations']), 1)

        # Løssnø-kvalitet vurdering
        avg_hours_since_mild = period['avg_hours_since_mild']
        avg_frost_duration = period['avg_frost_duration']

        if avg_hours_since_mild >= 72 and avg_frost_duration >= 48:
            period['snow_quality'] = 'excellent'
        elif avg_hours_since_mild >= 48 and avg_frost_duration >= 24:
            period['snow_quality'] = 'good'
        elif avg_hours_since_mild >= 24 and avg_frost_duration >= 12:
            period['snow_quality'] = 'acceptable'
        else:
            period['snow_quality'] = 'poor'

        # Vindretning
        if period['wind_directions']:
            directions_rad = np.radians(period['wind_directions'])
            avg_x = np.mean(np.cos(directions_rad))
            avg_y = np.mean(np.sin(directions_rad))
            avg_direction = np.degrees(np.arctan2(avg_y, avg_x)) % 360
            period['predominant_wind_direction'] = round(avg_direction, 1)
        else:
            period['predominant_wind_direction'] = None

        # Intensitet (justert for løssnø)
        max_wind = period['max_wind_speed']
        snow_quality_multiplier = {
            'excellent': 1.3,
            'good': 1.1,
            'acceptable': 1.0,
            'poor': 0.8
        }[period['snow_quality']]

        effective_wind = max_wind * snow_quality_multiplier

        if effective_wind >= 15.0:
            period['intensity'] = 'extreme'
        elif effective_wind >= 12.0:
            period['intensity'] = 'severe'
        elif effective_wind >= 9.0:
            period['intensity'] = 'moderate'
        else:
            period['intensity'] = 'light'

        # Vindretning risiko
        direction = period['predominant_wind_direction']
        if direction is not None:
            if (315 <= direction <= 360) or (0 <= direction <= 45) or (135 <= direction <= 225):
                period['wind_direction_risk'] = 'high'
            else:
                period['wind_direction_risk'] = 'medium'
        else:
            period['wind_direction_risk'] = 'unknown'

        # Risikoscore (justert for løssnø-kvalitet)
        wind_factor = min(effective_wind / 20.0, 1.0)
        temp_factor = min(abs(period['min_temperature']) / 20.0, 1.0)
        snow_quality_factor = snow_quality_multiplier / 1.3  # Normalisert
        direction_multiplier = 1.3 if period['wind_direction_risk'] == 'high' else 1.0

        period['risk_score'] = min((wind_factor + temp_factor + snow_quality_factor) * direction_multiplier / 3.0, 1.0)

        # Faregrad
        if period['intensity'] == 'extreme' or period['risk_score'] >= 0.8:
            period['road_danger'] = 'EXTREME'
        elif period['intensity'] == 'severe' or period['risk_score'] >= 0.6:
            period['road_danger'] = 'HIGH'
        elif period['intensity'] == 'moderate' or period['risk_score'] >= 0.4:
            period['road_danger'] = 'MEDIUM'
        else:
            period['road_danger'] = 'LOW'

        return period

    def analyze_february_crisis_with_loose_snow(self, periods: list[dict]) -> dict:
        """Analyser februar-krisen med løssnø-kriterier."""
        print("🚨 Februar 8-11 analyse MED løssnø-kriterier...")

        # Filtrer til februar 2024
        feb_periods = [p for p in periods if p['start_time'].month == 2 and p['start_time'].year == 2024]

        # Filtrer til 8-11 februar
        crisis_periods = []
        for period in feb_periods:
            start_day = period['start_time'].day
            end_day = period['end_time'].day

            if (start_day >= 8 and start_day <= 11) or (end_day >= 8 and end_day <= 11):
                crisis_periods.append(period)

        return {
            'crisis_found': len(crisis_periods) > 0,
            'crisis_periods': crisis_periods,
            'total_february_periods': len(feb_periods),
            'crisis_period_count': len(crisis_periods),
            'crisis_summary': {
                'total_estimated_hours': sum(p['estimated_duration_hours'] for p in crisis_periods),
                'max_wind_speed': max(p['max_wind_speed'] for p in crisis_periods) if crisis_periods else 0,
                'min_temperature': min(p['min_temperature'] for p in crisis_periods) if crisis_periods else 0,
                'extreme_periods': len([p for p in crisis_periods if p['road_danger'] == 'EXTREME']),
                'excellent_snow_periods': len([p for p in crisis_periods if p['snow_quality'] == 'excellent'])
            } if crisis_periods else {}
        }

    def generate_revised_report(self, periods: list[dict], feb_analysis: dict, df: pd.DataFrame) -> str:
        """Generer revidert rapport med løssnø-fokus."""

        # Sammenligning med tidligere analyse
        original_wind_hours = len(df.dropna(subset=['wind_speed']))
        loose_snow_hours = df['loose_snow_available'].sum()
        reduction_factor = loose_snow_hours / original_wind_hours if original_wind_hours > 0 else 0

        if not periods:
            return f"""
❌ REVIDERT SNØFOKK-ANALYSE MED LØSSNØ-KRITERIER
===============================================

🎯 INGEN SNØFOKK-PERIODER FUNNET!

Dette er et viktig funn som viser at:
• Kun {loose_snow_hours} av {original_wind_hours} timer hadde løssnø tilgjengelig ({reduction_factor*100:.1f}%)
• Mildvær ødelegger løssnø regelmessig på Gullingen
• Tidligere analyse var MASSIV overestimering

🔧 METODIKK:
• Krav om minst 24t siden mildvær (>0°C)
• Krav om minst 12t sammenhengende frost
• Standard vindstyrke ≥6 m/s, temp ≤-1°C, snø ≥3cm

Dette gir et REALISTISK bilde av snøfokk på Gullingen.
"""

        total_estimated_hours = sum(p['estimated_duration_hours'] for p in periods)
        avg_duration = total_estimated_hours / len(periods)
        longest_period = max(p['estimated_duration_hours'] for p in periods)

        # Snøkvalitet-statistikk
        quality_counts = {}
        for period in periods:
            quality = period['snow_quality']
            quality_counts[quality] = quality_counts.get(quality, 0) + 1

        # Intensitetsstatistikk
        intensity_counts = {}
        for period in periods:
            intensity = period['intensity']
            intensity_counts[intensity] = intensity_counts.get(intensity, 0) + 1

        # Månedlig statistikk
        monthly_counts = {}
        monthly_hours = {}
        for period in periods:
            month = period['start_time'].month
            month_name = {11: 'November', 12: 'Desember', 1: 'Januar', 2: 'Februar', 3: 'Mars', 4: 'April'}[month]

            monthly_counts[month_name] = monthly_counts.get(month_name, 0) + 1
            monthly_hours[month_name] = monthly_hours.get(month_name, 0) + period['estimated_duration_hours']

        report = f"""
❄️ REVIDERT SNØFOKK-ANALYSE MED LØSSNØ-KRITERIER 2023-2024
========================================================

📊 HOVEDRESULTATER (Med fysisk realistiske løssnø-krav)
Antall snøfokk-perioder: {len(periods)}
Estimert total varighet: {total_estimated_hours:.1f} timer
Gjennomsnittlig periodelengde: {avg_duration:.1f} timer  
Lengste periode: {longest_period:.1f} timer

🔄 SAMMENLIGNING MED TIDLIGERE ANALYSE:
• Timer med vinddata: {original_wind_hours}
• Timer med løssnø: {loose_snow_hours} ({reduction_factor*100:.1f}%)
• Reduksjon fra løssnø-krav: {((1-reduction_factor)*100):.1f}%

❄️ SNØ-KVALITETSFORDELING
"""

        for quality, count in quality_counts.items():
            percentage = (count / len(periods)) * 100
            report += f"  • {quality.upper()}: {count} perioder ({percentage:.1f}%)\n"

        report += """
🌪️ INTENSITETSFORDELING
"""

        for intensity, count in intensity_counts.items():
            percentage = (count / len(periods)) * 100
            report += f"  • {intensity.upper()}: {count} perioder ({percentage:.1f}%)\n"

        report += """
📅 MÅNEDLIG FORDELING
"""

        for month in ['November', 'Desember', 'Januar', 'Februar', 'Mars', 'April']:
            if month in monthly_counts:
                count = monthly_counts[month]
                hours = monthly_hours[month]
                percentage = (count / len(periods)) * 100
                report += f"  • {month}: {count} perioder, {hours:.1f} timer ({percentage:.1f}%)\n"

        # Februar krise
        if feb_analysis['crisis_found']:
            crisis = feb_analysis['crisis_summary']
            report += f"""

🚨 FEBRUAR 8-11, 2024 MED LØSSNØ-ANALYSE
=====================================
REVIDERTE FUNN:
• {feb_analysis['crisis_period_count']} snøfokk-perioder med løssnø
• Estimert {crisis['total_estimated_hours']:.1f} timer med ekte snøfokk-forhold
• Maksimal vindstyrke: {crisis['max_wind_speed']:.1f} m/s  
• Laveste temperatur: {crisis['min_temperature']:.1f}°C
• {crisis['extreme_periods']} ekstreme perioder
• {crisis['excellent_snow_periods']} perioder med utmerket snøkvalitet

{'KRISE BEKREFTET SELV MED LØSSNØ-KRITERIER!' if feb_analysis['crisis_period_count'] > 0 else 'Ingen perioder med tilstrekkelig løssnø i krisen.'}
"""
        else:
            report += """

🚨 FEBRUAR 8-11, 2024 ANALYSE
===========================
❌ INGEN snøfokk-perioder funnet med løssnø-kriterier i kriseperioden.
Dette tyder på at mildvær kan ha ødelagt løssnø før/under krisen.
"""

        report += f"""

🎯 REVIDERT METODIKK OG FUNN
===========================
• Strengere kriterier: Minst 24t siden mildvær + 12t frost
• Kun {reduction_factor*100:.1f}% av timer med vinddata hadde løssnø
• Mildvær-perioder ødelegger løssnø regelmessig
• Dette gir det mest FYSISK REALISTISKE bildet av snøfokk

🔧 KONKLUSJON
=============
Med løssnø-kriterier ser vi at:
1. Snøfokk er MYE sjeldnere enn tidligere antatt
2. Mildvær er en kritisk begrensende faktor på Gullingen
3. {"Februar 8-11 hadde EKTE snøfokk-forhold" if feb_analysis['crisis_found'] else "Februar 8-11 hadde IKKE tilstrekkelig løssnø"}
4. Tidligere analyse var en MASSIV overestimering

Dette er den mest REALISTISKE snøfokk-analysen for Gullingen!
"""

        return report

    def run_revised_analysis(self):
        """Kjør revidert analyse med løssnø-kriterier."""
        print("❄️ REVIDERT SNØFOKK-ANALYSE MED LØSSNØ-KRITERIER")
        print("=" * 60)
        print("🎯 Inkluderer fysisk realistiske løssnø-krav")
        print("🎯 Eliminerer perioder etter mildvær")
        print("🎯 Krever sammenhengende frost")
        print("=" * 60)

        # 1. Last data med løssnø-analyse
        df = self.load_data()
        print(f"📊 Total datapunkter: {len(df)}")
        print(f"❄️ Timer med løssnø: {df['loose_snow_available'].sum()}")

        # 2. Finn perioder med løssnø-kriterier
        periods = self.find_realistic_snowdrift_with_loose_snow(df)

        # 3. Analyser februar-krise
        feb_analysis = self.analyze_february_crisis_with_loose_snow(periods)

        # 4. Generer revidert rapport
        report = self.generate_revised_report(periods, feb_analysis, df)

        # 5. Lagre resultater
        report_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/revised_snowdrift_with_loose_snow_report.txt'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        analysis_data = {
            'analysis_type': 'revised_snowdrift_with_loose_snow_criteria',
            'analysis_date': datetime.now().isoformat(),
            'season': '2023-2024',
            'loose_snow_requirements': {
                'min_hours_since_mild': 24,
                'min_frost_duration': 12,
                'max_gap_hours': 4
            },
            'data_quality': {
                'total_datapoints': len(df),
                'wind_data_available': len(df.dropna(subset=['wind_speed'])),
                'loose_snow_available': df['loose_snow_available'].sum(),
                'loose_snow_percentage': (df['loose_snow_available'].sum() / len(df)) * 100
            },
            'february_crisis': feb_analysis,
            'total_periods': len(periods),
            'periods': periods
        }

        json_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/revised_snowdrift_with_loose_snow.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, ensure_ascii=False, indent=2, default=str)

        print(f"📄 Lagret revidert rapport til {report_file}")
        print(f"💾 Lagret data til {json_file}")
        print(report)

        # Vis perioder hvis funnet
        if periods:
            print(f"\n❄️ FUNNET {len(periods)} PERIODER MED LØSSNØ:")
            for i, period in enumerate(periods, 1):
                print(f"""
{i}. {period['start_time'].strftime('%d.%m.%Y %H:%M')} - {period['end_time'].strftime('%d.%m.%Y %H:%M')}
   Varighet: {period['estimated_duration_hours']:.1f}t | Målinger: {period['measurement_count']}
   Vind: {period['max_wind_speed']:.1f} m/s | Temp: {period['min_temperature']:.1f}°C
   Løssnø-kvalitet: {period['snow_quality'].upper()}
   Timer siden mildvær: {period['avg_hours_since_mild']:.0f}t
   Frost-varighet: {period['avg_frost_duration']:.0f}t
   Intensitet: {period['intensity'].upper()} | Fare: {period['road_danger']}""")

def main():
    """Hovedfunksjon."""
    try:
        analyzer = RevisedSnowdriftAnalyzer()
        analyzer.run_revised_analysis()

    except Exception as e:
        print(f"❌ Feil: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
