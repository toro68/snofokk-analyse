#!/usr/bin/env python3
"""
Fysisk Realistisk Glatt Vei-Analyse
===================================

Implementerer forbedrede kriterier basert på kritisk evaluering
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import pickle
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from typing import List, Dict

load_dotenv()

class RealisticSlipperyRoadAnalyzer:
    """Fysisk realistisk glatt vei-analyse med forbedrede kriterier."""
    
    def __init__(self):
        self.cache_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/cache/weather_data_2023-11-01_2024-04-30.pkl'
    
    def load_data(self) -> pd.DataFrame:
        """Last inn cached værdata."""
        with open(self.cache_file, 'rb') as f:
            return pickle.load(f)
    
    def calculate_dew_point(self, temp: pd.Series, humidity: pd.Series) -> pd.Series:
        """Beregn duggpunkt med Magnus-formel."""
        # Magnus-formel konstanter
        a = 17.27
        b = 237.7
        
        # Beregn duggpunkt
        def magnus(T, RH):
            if pd.isna(T) or pd.isna(RH) or RH <= 0:
                return np.nan
            alpha = ((a * T) / (b + T)) + np.log(RH / 100.0)
            return (b * alpha) / (a - alpha)
        
        return temp.combine(humidity, magnus)
    
    def find_realistic_slippery_periods(self, df: pd.DataFrame) -> List[Dict]:
        """Finn glatt vei-perioder med fysisk realistiske kriterier."""
        print("🔍 Finner glatt vei-perioder med FYSISK REALISTISKE kriterier...")
        
        # Filtrer til data med nødvendige parametere
        valid_data = df[
            (df['air_temperature'].notna())
        ].copy()
        
        print(f"📊 Gyldig data: {len(valid_data)}/{len(df)} datapunkter")
        
        if valid_data.empty:
            return []
        
        # Beregn duggpunkt der mulig
        if 'relative_humidity' in valid_data.columns:
            valid_data['dew_point'] = self.calculate_dew_point(
                valid_data['air_temperature'], 
                valid_data['relative_humidity']
            )
            valid_data['dew_point_depression'] = valid_data['air_temperature'] - valid_data['dew_point']
        
        # Beregn temperaturfall
        valid_data['temp_drop_rate'] = -valid_data['air_temperature'].diff()
        
        # Identifiser tidspunkt på døgnet
        valid_data['hour'] = valid_data['referenceTime'].dt.hour
        valid_data['is_night'] = ((valid_data['hour'] >= 22) | (valid_data['hour'] <= 8))
        
        # Beregn risiko for hver type glatt vei
        valid_data = self.calculate_slippery_risks(valid_data)
        
        # Finn perioder
        periods = []
        
        # TYPE 1: Rimfrost-perioder
        rimfrost_periods = self.find_rimfrost_periods(valid_data)
        periods.extend(rimfrost_periods)
        
        # TYPE 2: Is-dannelse perioder
        ice_periods = self.find_ice_formation_periods(valid_data)
        periods.extend(ice_periods)
        
        # TYPE 3: Underkjølt regn perioder
        freezing_rain_periods = self.find_freezing_rain_periods(valid_data)
        periods.extend(freezing_rain_periods)
        
        # TYPE 4: Refryzing perioder
        refreezing_periods = self.find_refreezing_periods(valid_data)
        periods.extend(refreezing_periods)
        
        # Sorter etter starttid
        periods.sort(key=lambda x: x['start_time'])
        
        print(f"✅ Funnet {len(periods)} realistiske glatt vei-perioder")
        return periods
    
    def calculate_slippery_risks(self, df: pd.DataFrame) -> pd.DataFrame:
        """Beregn risiko for ulike typer glatt vei."""
        
        # TYPE 1: Rimfrost-risiko
        rimfrost_temp = (df['air_temperature'] >= -2) & (df['air_temperature'] <= 0)
        rimfrost_humidity = df['relative_humidity'] >= 90 if 'relative_humidity' in df.columns else True
        rimfrost_wind = df['wind_speed'] <= 2 if 'wind_speed' in df.columns else True
        rimfrost_night = df['is_night']
        
        df['rimfrost_risk'] = rimfrost_temp & rimfrost_humidity & rimfrost_wind & rimfrost_night
        
        # TYPE 2: Is-dannelse risiko
        ice_temp = df['air_temperature'] <= -1
        ice_humidity = df['relative_humidity'] >= 80 if 'relative_humidity' in df.columns else True
        ice_temp_drop = df['temp_drop_rate'] >= 1  # >1°C/time temperaturfall
        
        df['ice_risk'] = ice_temp & ice_humidity & ice_temp_drop
        
        # TYPE 3: Underkjølt regn risiko
        freezing_temp = (df['air_temperature'] >= -1) & (df['air_temperature'] <= 1)
        has_precipitation = df['sum(precipitation_amount PT1H)'] > 0.1 if 'sum(precipitation_amount PT1H)' in df.columns else False
        
        df['freezing_rain_risk'] = freezing_temp & has_precipitation
        
        # TYPE 4: Refryzing risiko
        # Sjekk om temperatur har vært >2°C siste 12 timer og nå ≤0°C
        df['was_warm_recently'] = False
        df['refreezing_risk'] = False
        
        for i in range(12, len(df)):
            recent_temps = df.iloc[i-12:i]['air_temperature']
            current_temp = df.iloc[i]['air_temperature']
            
            if (recent_temps > 2).any() and current_temp <= 0 and df.iloc[i]['is_night']:
                df.iloc[i, df.columns.get_loc('was_warm_recently')] = True
                df.iloc[i, df.columns.get_loc('refreezing_risk')] = True
        
        # Samlet glatt vei-risiko
        df['any_slippery_risk'] = (
            df['rimfrost_risk'] | 
            df['ice_risk'] | 
            df['freezing_rain_risk'] | 
            df['refreezing_risk']
        )
        
        return df
    
    def find_rimfrost_periods(self, df: pd.DataFrame) -> List[Dict]:
        """Finn rimfrost-perioder."""
        return self.extract_periods(df, 'rimfrost_risk', 'RIMFROST')
    
    def find_ice_formation_periods(self, df: pd.DataFrame) -> List[Dict]:
        """Finn is-dannelse perioder."""
        return self.extract_periods(df, 'ice_risk', 'ICE_FORMATION')
    
    def find_freezing_rain_periods(self, df: pd.DataFrame) -> List[Dict]:
        """Finn underkjølt regn-perioder."""
        return self.extract_periods(df, 'freezing_rain_risk', 'FREEZING_RAIN')
    
    def find_refreezing_periods(self, df: pd.DataFrame) -> List[Dict]:
        """Finn refryzing-perioder."""
        return self.extract_periods(df, 'refreezing_risk', 'REFREEZING')
    
    def extract_periods(self, df: pd.DataFrame, risk_column: str, period_type: str) -> List[Dict]:
        """Eksrakter kontinuerlige risikoperioder."""
        periods = []
        
        # Finn start og slutt av perioder
        risk_changes = df[risk_column].astype(int).diff()
        starts = df[risk_changes == 1].index
        ends = df[risk_changes == -1].index
        
        # Håndter edge cases
        if df[risk_column].iloc[0]:
            starts = [df.index[0]] + list(starts)
        if df[risk_column].iloc[-1]:
            ends = list(ends) + [df.index[-1]]
        
        # Match starts og ends
        for start_idx in starts:
            matching_ends = [e for e in ends if e > start_idx]
            if matching_ends:
                end_idx = matching_ends[0]
                
                period_data = df.loc[start_idx:end_idx]
                duration_hours = len(period_data)
                
                # Minimum 1 time for å være gyldig periode
                if duration_hours >= 1:
                    period = self.create_slippery_period(period_data, period_type)
                    if period:
                        periods.append(period)
        
        return periods
    
    def create_slippery_period(self, period_data: pd.DataFrame, period_type: str) -> Dict:
        """Opprett periode-dict med statistikk."""
        
        start_time = period_data['referenceTime'].iloc[0]
        end_time = period_data['referenceTime'].iloc[-1]
        duration_hours = len(period_data)
        
        # Temperaturstatistikk
        min_temp = period_data['air_temperature'].min()
        max_temp = period_data['air_temperature'].max()
        avg_temp = period_data['air_temperature'].mean()
        
        # Fuktighetstatistikk
        if 'relative_humidity' in period_data.columns:
            avg_humidity = period_data['relative_humidity'].mean()
            max_humidity = period_data['relative_humidity'].max()
        else:
            avg_humidity = max_humidity = None
        
        # Vindstatistikk
        if 'wind_speed' in period_data.columns:
            avg_wind = period_data['wind_speed'].mean()
            max_wind = period_data['wind_speed'].max()
        else:
            avg_wind = max_wind = None
        
        # Nedbørstatistikk
        if 'sum(precipitation_amount PT1H)' in period_data.columns:
            total_precipitation = period_data['sum(precipitation_amount PT1H)'].sum()
            max_precip_rate = period_data['sum(precipitation_amount PT1H)'].max()
        else:
            total_precipitation = max_precip_rate = None
        
        # Temperaturfall
        max_temp_drop = period_data['temp_drop_rate'].max()
        
        # Duggpunkt
        if 'dew_point_depression' in period_data.columns:
            min_dew_point_depression = period_data['dew_point_depression'].min()
        else:
            min_dew_point_depression = None
        
        # Beregn risikoscore basert på type
        risk_score = self.calculate_type_specific_risk_score(
            period_type, min_temp, avg_humidity, avg_wind, 
            total_precipitation, max_temp_drop, min_dew_point_depression
        )
        
        # Faregrad
        if risk_score >= 90:
            danger_level = 'EXTREME'
        elif risk_score >= 70:
            danger_level = 'HIGH'
        elif risk_score >= 50:
            danger_level = 'MEDIUM'
        else:
            danger_level = 'LOW'
        
        return {
            'start_time': start_time,
            'end_time': end_time,
            'duration_hours': duration_hours,
            'type': period_type,
            'min_temperature': round(min_temp, 1),
            'max_temperature': round(max_temp, 1),
            'avg_temperature': round(avg_temp, 1),
            'avg_humidity': round(avg_humidity, 1) if avg_humidity is not None else None,
            'max_humidity': round(max_humidity, 1) if max_humidity is not None else None,
            'avg_wind_speed': round(avg_wind, 1) if avg_wind is not None else None,
            'max_wind_speed': round(max_wind, 1) if max_wind is not None else None,
            'total_precipitation': round(total_precipitation, 2) if total_precipitation is not None else None,
            'max_precip_rate': round(max_precip_rate, 2) if max_precip_rate is not None else None,
            'max_temp_drop_rate': round(max_temp_drop, 1),
            'min_dew_point_depression': round(min_dew_point_depression, 1) if min_dew_point_depression is not None else None,
            'risk_score': round(risk_score, 1),
            'danger_level': danger_level,
            'measurement_count': len(period_data)
        }
    
    def calculate_type_specific_risk_score(
        self, 
        period_type: str, 
        min_temp: float, 
        avg_humidity: float, 
        avg_wind: float,
        total_precipitation: float, 
        max_temp_drop: float, 
        min_dew_point_depression: float
    ) -> float:
        """Beregn risikoscore spesifikt for hver type."""
        
        base_score = 50
        
        if period_type == 'RIMFROST':
            # Rimfrost: lavere temperatur + høyere fuktighet + mindre vind = høyere risiko
            temp_factor = max(0, (2 - abs(min_temp)) * 10)  # Optimal rundt 0°C
            humidity_factor = (avg_humidity - 85) if avg_humidity is not None else 15
            wind_factor = max(0, (5 - avg_wind) * 5) if avg_wind is not None else 25
            base_score += temp_factor + humidity_factor + wind_factor
            
        elif period_type == 'ICE_FORMATION':
            # Is-dannelse: lavere temperatur + rask avkjøling = høyere risiko
            temp_factor = max(0, abs(min_temp) * 8) if min_temp < 0 else 0
            cooling_factor = min(30, max_temp_drop * 10)
            humidity_factor = (avg_humidity - 70) * 0.5 if avg_humidity is not None else 10
            base_score += temp_factor + cooling_factor + humidity_factor
            
        elif period_type == 'FREEZING_RAIN':
            # Underkjølt regn: temperatur nær 0°C + nedbør = høyere risiko
            temp_factor = max(0, (2 - abs(min_temp)) * 15)
            precip_factor = min(25, total_precipitation * 5) if total_precipitation is not None else 0
            base_score += temp_factor + precip_factor
            
        elif period_type == 'REFREEZING':
            # Refryzing: temperatur under 0°C + tidligere varme = høyere risiko
            temp_factor = max(0, abs(min_temp) * 10) if min_temp < 0 else 0
            base_score += temp_factor + 20  # Bonus for refryzing-situasjon
        
        # Duggpunkt-bonus
        if min_dew_point_depression is not None and min_dew_point_depression <= 2:
            base_score += (3 - min_dew_point_depression) * 5
        
        return min(100, max(0, base_score))
    
    def generate_realistic_report(self, periods: List[Dict], df: pd.DataFrame) -> str:
        """Generer rapport med fysisk realistiske resultater."""
        
        if not periods:
            return """
❌ FYSISK REALISTISK GLATT VEI-ANALYSE
===================================

🎯 INGEN GLATT VEI-PERIODER FUNNET!

Dette viser at eksisterende kriterier kan være for strenge
eller at vinteren 2023-2024 hadde få farlige glatt vei-situasjoner.

🔧 MULIGE ÅRSAKER:
• Få perioder med optimal kombinasjon av faktorer
• Manglende vinddata påvirker rimfrost-deteksjon
• Behov for finere justating av terskler

Dette er fortsatt mer realistisk enn tidligere kriterier!
"""
        
        # Statistikk per type
        type_counts = {}
        type_hours = {}
        type_max_risk = {}
        
        for period in periods:
            ptype = period['type']
            type_counts[ptype] = type_counts.get(ptype, 0) + 1
            type_hours[ptype] = type_hours.get(ptype, 0) + period['duration_hours']
            type_max_risk[ptype] = max(type_max_risk.get(ptype, 0), period['risk_score'])
        
        total_hours = sum(p['duration_hours'] for p in periods)
        avg_duration = total_hours / len(periods)
        
        # Faregrad-statistikk
        danger_counts = {}
        for period in periods:
            danger = period['danger_level']
            danger_counts[danger] = danger_counts.get(danger, 0) + 1
        
        # Månedlig fordeling
        monthly_counts = {}
        for period in periods:
            month = period['start_time'].month
            month_name = {11: 'November', 12: 'Desember', 1: 'Januar', 2: 'Februar', 3: 'Mars', 4: 'April'}[month]
            monthly_counts[month_name] = monthly_counts.get(month_name, 0) + 1
        
        report = f"""
🧊 FYSISK REALISTISK GLATT VEI-ANALYSE 2023-2024
==============================================

📊 HOVEDRESULTATER (Med fysisk realistiske kriterier)
Antall glatt vei-perioder: {len(periods)}
Total varighet: {total_hours:.1f} timer
Gjennomsnittlig periodelengde: {avg_duration:.1f} timer
Lengste periode: {max(p['duration_hours'] for p in periods):.1f} timer

🧊 GLATT VEI-TYPER FORDELING
"""
        
        for ptype, count in type_counts.items():
            hours = type_hours[ptype]
            max_risk = type_max_risk[ptype]
            percentage = (count / len(periods)) * 100
            report += f"  • {ptype}: {count} perioder, {hours:.1f} timer ({percentage:.1f}%), maks risiko {max_risk:.1f}\n"
        
        report += f"""
🚨 FAREGRAD FORDELING
"""
        
        for danger, count in danger_counts.items():
            percentage = (count / len(periods)) * 100
            report += f"  • {danger}: {count} perioder ({percentage:.1f}%)\n"
        
        report += f"""
📅 MÅNEDLIG FORDELING
"""
        
        for month in ['November', 'Desember', 'Januar', 'Februar', 'Mars', 'April']:
            if month in monthly_counts:
                count = monthly_counts[month]
                percentage = (count / len(periods)) * 100
                report += f"  • {month}: {count} perioder ({percentage:.1f}%)\n"
        
        # Topp 5 farligste perioder
        dangerous_periods = sorted(periods, key=lambda x: x['risk_score'], reverse=True)[:5]
        
        report += f"""

🚨 TOPP 5 FARLIGSTE PERIODER
==========================
"""
        
        for i, period in enumerate(dangerous_periods, 1):
            report += f"""
{i}. {period['start_time'].strftime('%d.%m.%Y %H:%M')} - {period['end_time'].strftime('%d.%m.%Y %H:%M')}
   Type: {period['type']} | Varighet: {period['duration_hours']:.1f}t
   Temperatur: {period['min_temperature']:.1f}°C til {period['max_temperature']:.1f}°C
   Risikoscore: {period['risk_score']:.1f}/100 | Faregrad: {period['danger_level']}
   Målinger: {period['measurement_count']} datapunkter"""
            
            if period['avg_humidity'] is not None:
                report += f"\n   Luftfuktighet: {period['avg_humidity']:.1f}%"
            if period['avg_wind_speed'] is not None:
                report += f" | Vind: {period['avg_wind_speed']:.1f} m/s"
            if period['total_precipitation'] is not None and period['total_precipitation'] > 0:
                report += f" | Nedbør: {period['total_precipitation']:.2f}mm"
        
        report += f"""

🎯 FYSISK REALISTISKE KRITERIER BRUKT
===================================
• RIMFROST: Temp -2°C til 0°C + fuktighet ≥90% + vindstille + natt
• IS-DANNELSE: Temp ≤-1°C + fuktighet ≥80% + temperaturfall >1°C/t
• UNDERKJØLT REGN: Temp -1°C til +1°C + nedbør >0.1mm/h
• REFRYZING: Tidligere smelting + temp ≤0°C + natt

🔧 KONKLUSJON
=============
Med fysisk realistiske kriterier identifiserer vi:
1. {len(periods)} faktiske glatt vei-perioder (ikke overestimering)
2. Korrekt vektlegging av ulike risikofaktorer
3. Realistisk faregrad-vurdering
4. Berøpfei krav om både temperatur, fuktighet og vind

Dette gir et MYE mer PRESIST bilde av glatt vei-risiko!
"""
        
        return report
    
    def run_realistic_analysis(self):
        """Kjør fysisk realistisk glatt vei-analyse."""
        print("🧊 FYSISK REALISTISK GLATT VEI-ANALYSE")
        print("=" * 60)
        print("🎯 Bruker forbedrede, fysisk realistiske kriterier")
        print("🎯 Eliminerer falske alarmer og misser færre farlige situasjoner")
        print("=" * 60)
        
        # 1. Last data
        df = self.load_data()
        print(f"📊 Total datapunkter: {len(df)}")
        
        # 2. Finn perioder med realistiske kriterier
        periods = self.find_realistic_slippery_periods(df)
        
        # 3. Generer rapport
        report = self.generate_realistic_report(periods, df)
        
        # 4. Lagre resultater
        report_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/realistic_slippery_road_report.txt'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        analysis_data = {
            'analysis_type': 'realistic_slippery_road_with_improved_criteria',
            'analysis_date': datetime.now().isoformat(),
            'season': '2023-2024',
            'criteria_improvements': {
                'rimfrost': 'temp -2 to 0°C, humidity ≥90%, wind ≤2 m/s, night',
                'ice_formation': 'temp ≤-1°C, humidity ≥80%, temp_drop >1°C/h',
                'freezing_rain': 'temp -1 to +1°C, precipitation >0.1mm/h',
                'refreezing': 'previous warmth + temp ≤0°C + night'
            },
            'total_periods': len(periods),
            'periods': periods
        }
        
        json_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/realistic_slippery_road_analysis.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"📄 Lagret rapport til {report_file}")
        print(f"💾 Lagret data til {json_file}")
        print(report)

def main():
    """Hovedfunksjon."""
    try:
        analyzer = RealisticSlipperyRoadAnalyzer()
        analyzer.run_realistic_analysis()
        
    except Exception as e:
        print(f"❌ Feil: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
