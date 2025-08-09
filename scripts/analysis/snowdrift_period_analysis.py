#!/usr/bin/env python3
"""
Snøfokk Periode Analyse - Brøytesesong 2023-2024
Grupperer sammenhengende snøfokk-timer til perioder
Analyserer hele brøytesesongen: 1. november 2023 - 30. april 2024
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from typing import List, Dict, Any, Tuple

# Legg til src til Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from snofokk.services.weather import WeatherService
from snofokk.config.settings import Settings

def detect_snowdrift_conditions(df: pd.DataFrame) -> pd.DataFrame:
    """Detekter snøfokk-forhold basert på justerte terskler."""
    
    # Konverter kolonnenavn til standard format
    df = df.copy()
    df.columns = [
        'referenceTime', 'temperature', 'max_temp', 'max_wind_speed', 
        'min_temp', 'humidity', 'precipitation', 'snow_depth', 
        'wind_direction', 'wind_speed'
    ]
    
    # Fyll manglende verdier
    df = df.fillna(method='ffill').fillna(method='bfill')
    
    # Deteksjonsterskler
    WIND_THRESHOLD = 6.0  # m/s
    TEMP_THRESHOLD = -1.0  # °C
    SNOW_THRESHOLD = 3.0   # cm
    
    # Lag deteksjonskolonner
    df['wind_ok'] = df['wind_speed'] >= WIND_THRESHOLD
    df['temp_ok'] = df['temperature'] <= TEMP_THRESHOLD
    df['snow_ok'] = df['snow_depth'] >= SNOW_THRESHOLD
    
    # Hovedkriterium: vind + temperatur + snø
    df['snowdrift_detected'] = df['wind_ok'] & df['temp_ok'] & df['snow_ok']
    
    return df

def group_consecutive_periods(df: pd.DataFrame, max_gap_hours: int = 2) -> List[Dict[str, Any]]:
    """Grupper sammenhengende snøfokk-timer til perioder."""
    
    # Filtrer kun detekterte snøfokk-timer
    snowdrift_hours = df[df['snowdrift_detected']].copy()
    
    if snowdrift_hours.empty:
        return []
    
    # Sorter etter tid
    snowdrift_hours = snowdrift_hours.sort_values('referenceTime')
    snowdrift_hours['datetime'] = pd.to_datetime(snowdrift_hours['referenceTime'])
    
    periods = []
    current_period_start = None
    current_period_data = []
    last_datetime = None
    
    for idx, row in snowdrift_hours.iterrows():
        current_datetime = row['datetime']
        
        if current_period_start is None:
            # Start ny periode
            current_period_start = current_datetime
            current_period_data = [row]
        else:
            # Sjekk om det er sammenhengende (innenfor gap-toleranse)
            time_gap = (current_datetime - last_datetime).total_seconds() / 3600
            
            if time_gap <= max_gap_hours + 1:  # +1 for normal time interval
                # Fortsett samme periode
                current_period_data.append(row)
            else:
                # Avslutt forrige periode og start ny
                if len(current_period_data) > 0:
                    periods.append(create_period_summary(current_period_start, last_datetime, current_period_data))
                
                current_period_start = current_datetime
                current_period_data = [row]
        
        last_datetime = current_datetime
    
    # Legg til siste periode
    if len(current_period_data) > 0:
        periods.append(create_period_summary(current_period_start, last_datetime, current_period_data))
    
    return periods

def create_period_summary(start_time: datetime, end_time: datetime, data: List[pd.Series]) -> Dict[str, Any]:
    """Lag sammendrag for en snøfokk-periode."""
    
    df_period = pd.DataFrame(data)
    
    duration_hours = (end_time - start_time).total_seconds() / 3600 + 1  # +1 for inclusive end
    
    # Beregn snøendring
    snow_start = df_period['snow_depth'].iloc[0]
    snow_end = df_period['snow_depth'].iloc[-1]
    snow_change = snow_end - snow_start
    
    # Klassifiser hendelsestype
    drift_type = classify_drift_type(snow_change, duration_hours, df_period)
    
    # Beregn risikoscore
    risk_score = calculate_risk_score(df_period, duration_hours)
    
    # Er det usynlig snøfokk?
    invisible_drift = abs(snow_change) < 1.0  # Mindre enn 1cm endring
    
    return {
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat(),
        'duration_hours': round(duration_hours, 1),
        'max_wind_speed': round(df_period['wind_speed'].max(), 1),
        'max_wind_gust': round(df_period['max_wind_speed'].max(), 1),
        'min_temperature': round(df_period['temperature'].min(), 1),
        'avg_temperature': round(df_period['temperature'].mean(), 1),
        'snow_depth_start': round(snow_start, 1),
        'snow_depth_end': round(snow_end, 1),
        'snow_change': round(snow_change, 1),
        'drift_type': drift_type,
        'risk_score': round(risk_score, 2),
        'invisible_drift': invisible_drift,
        'total_hours': len(data),
        'avg_wind_speed': round(df_period['wind_speed'].mean(), 1),
        'wind_direction': round(df_period['wind_direction'].mean(), 0)
    }

def classify_drift_type(snow_change: float, duration: float, df_period: pd.DataFrame) -> Dict[str, str]:
    """Klassifiser type snøfokk og faregrad."""
    
    avg_wind = df_period['wind_speed'].mean()
    
    if abs(snow_change) < 1.0:
        # Usynlig snøfokk
        drift_type = "invisible_drift"
        danger = "HIGH" if avg_wind > 8.0 else "MEDIUM"
    elif snow_change > 2.0:
        # Akkumulerende snøfokk
        drift_type = "accumulating_drift"
        danger = "MEDIUM" if duration < 6 else "HIGH"
    elif snow_change < -2.0:
        # Eroderende snøfokk
        drift_type = "eroding_drift"
        danger = "HIGH"
    else:
        # Ukjent/variabel
        drift_type = "variable_drift"
        danger = "MEDIUM"
    
    return {
        'type': drift_type,
        'road_danger': danger
    }

def calculate_risk_score(df_period: pd.DataFrame, duration: float) -> float:
    """Beregn risikoscore for periode."""
    
    wind_factor = min(df_period['wind_speed'].max() / 15.0, 1.0)
    temp_factor = min(abs(df_period['temperature'].min()) / 10.0, 1.0)
    duration_factor = min(duration / 12.0, 1.0)
    
    return (wind_factor * 0.4 + temp_factor * 0.3 + duration_factor * 0.3)

def analyze_winter_season_periods() -> Dict[str, Any]:
    """Analyser hele brøytesesongen 2023-2024."""
    
    print("🏔️ SNØFOKK PERIODE ANALYSE - BRØYTESESONG 2023-2024")
    print("=" * 60)
    print("📅 Periode: 1. november 2023 - 30. april 2024")
    print("🎯 Grupperer sammenhengende snøfokk-timer til perioder")
    print()
    
    # Initialiser WeatherService
    settings = Settings()
    weather_service = WeatherService(settings.frost_client_id)
    
    # Hent data for hele brøytesesongen
    start_date = "2023-11-01"
    end_date = "2024-04-30"
    
    print(f"📡 Henter værdata fra {start_date} til {end_date}...")
    
    try:
        data = weather_service.get_weather_data(
            station_id="SN46220",
            start_date=start_date,
            end_date=end_date
        )
        
        if data.empty:
            print("❌ Ingen data hentet fra API")
            return {}
        
        print(f"✅ Hentet {len(data)} datapunkter")
        print(f"📊 Kolonner: {list(data.columns)}")
        
        # Detekter snøfokk-forhold
        print("\n🔍 Detekterer snøfokk-forhold...")
        df_with_detection = detect_snowdrift_conditions(data)
        
        snowdrift_hours = df_with_detection[df_with_detection['snowdrift_detected']]
        print(f"⚡ Fant {len(snowdrift_hours)} timer med snøfokk-forhold")
        
        # Grupper til perioder
        print("\n🔗 Grupperer til sammenhengende perioder...")
        periods = group_consecutive_periods(df_with_detection, max_gap_hours=2)
        
        print(f"📋 Gruppert til {len(periods)} snøfokk-perioder")
        
        # Analyser perioder
        analysis = analyze_periods(periods, start_date, end_date)
        
        return analysis
        
    except Exception as e:
        print(f"❌ Feil under analyse: {e}")
        import traceback
        traceback.print_exc()
        return {}

def analyze_periods(periods: List[Dict[str, Any]], start_date: str, end_date: str) -> Dict[str, Any]:
    """Analyser snøfokk-perioder."""
    
    if not periods:
        return {
            'period': {'start': start_date, 'end': end_date},
            'summary': {'total_periods': 0},
            'periods': []
        }
    
    # Grunnleggende statistikk
    total_periods = len(periods)
    total_hours = sum(p['duration_hours'] for p in periods)
    avg_duration = total_hours / total_periods if total_periods > 0 else 0
    
    # Fordeling etter type
    type_distribution = {}
    danger_distribution = {}
    invisible_count = 0
    high_risk_count = 0
    
    for period in periods:
        drift_type = period['drift_type']['type']
        danger_level = period['drift_type']['road_danger']
        
        type_distribution[drift_type] = type_distribution.get(drift_type, 0) + 1
        danger_distribution[danger_level] = danger_distribution.get(danger_level, 0) + 1
        
        if period['invisible_drift']:
            invisible_count += 1
        
        if period['risk_score'] >= 0.8:
            high_risk_count += 1
    
    # Månedlig fordeling
    monthly_distribution = {}
    for period in periods:
        month = datetime.fromisoformat(period['start_time']).strftime('%Y-%m')
        monthly_distribution[month] = monthly_distribution.get(month, 0) + 1
    
    # Finn lengste periode
    longest_period = max(periods, key=lambda x: x['duration_hours']) if periods else None
    
    # Finn farligste periode
    most_dangerous = max(periods, key=lambda x: x['risk_score']) if periods else None
    
    summary = {
        'total_periods': total_periods,
        'total_hours': round(total_hours, 1),
        'avg_duration_hours': round(avg_duration, 1),
        'invisible_drift_periods': invisible_count,
        'high_risk_periods': high_risk_count,
        'type_distribution': type_distribution,
        'danger_distribution': danger_distribution,
        'monthly_distribution': monthly_distribution,
        'longest_period': longest_period,
        'most_dangerous_period': most_dangerous
    }
    
    analysis = {
        'analysis_type': 'snowdrift_period_analysis',
        'analysis_date': datetime.now().isoformat(),
        'period': {
            'start': start_date,
            'end': end_date,
            'description': 'Brøytesesong 2023-2024'
        },
        'station': {
            'id': 'SN46220',
            'name': 'Gullingen Skisenter'
        },
        'methodology': {
            'grouping': 'consecutive_periods',
            'max_gap_hours': 2,
            'thresholds': {
                'wind_speed': 6.0,
                'temperature': -1.0,
                'snow_depth': 3.0
            }
        },
        'summary': summary,
        'periods': periods
    }
    
    return analysis

def print_period_report(analysis: Dict[str, Any]) -> None:
    """Skriv ut detaljert periode-rapport."""
    
    if not analysis or not analysis.get('periods'):
        print("❌ Ingen data å rapportere")
        return
    
    summary = analysis['summary']
    periods = analysis['periods']
    
    print("\n" + "="*60)
    print("📊 SNØFOKK PERIODE RAPPORT")
    print("="*60)
    
    print(f"""
📅 ANALYSEPERIODE
    Fra: {analysis['period']['start']}
    Til: {analysis['period']['end']}
    Beskrivelse: {analysis['period']['description']}

📋 SAMMENDRAG
    Totalt antall perioder: {summary['total_periods']}
    Total varighet: {summary['total_hours']} timer
    Gjennomsnittlig varighet: {summary['avg_duration_hours']} timer
    Usynlig snøfokk perioder: {summary['invisible_drift_periods']}
    Høyrisiko perioder: {summary['high_risk_periods']}
""")
    
    print("🏷️ PERIODE TYPER:")
    for drift_type, count in summary['type_distribution'].items():
        percentage = (count / summary['total_periods']) * 100
        print(f"    {drift_type.replace('_', ' ').title()}: {count} ({percentage:.1f}%)")
    
    print("\n⚠️ FAREGRAD FORDELING:")
    for danger, count in summary['danger_distribution'].items():
        percentage = (count / summary['total_periods']) * 100
        print(f"    {danger}: {count} ({percentage:.1f}%)")
    
    print("\n📅 MÅNEDLIG FORDELING:")
    for month, count in sorted(summary['monthly_distribution'].items()):
        month_name = datetime.strptime(month, '%Y-%m').strftime('%B %Y')
        print(f"    {month_name}: {count} perioder")
    
    # Lengste periode
    if summary['longest_period']:
        lp = summary['longest_period']
        print(f"""
🕒 LENGSTE PERIODE:
    Start: {lp['start_time']}
    Varighet: {lp['duration_hours']} timer
    Type: {lp['drift_type']['type'].replace('_', ' ').title()}
    Maks vind: {lp['max_wind_speed']} m/s
    Min temp: {lp['min_temperature']}°C
""")
    
    # Farligste periode
    if summary['most_dangerous_period']:
        dp = summary['most_dangerous_period']
        print(f"""
🚨 FARLIGSTE PERIODE:
    Start: {dp['start_time']}
    Varighet: {dp['duration_hours']} timer
    Risikoscore: {dp['risk_score']}
    Maks vind: {dp['max_wind_speed']} m/s
    Min temp: {dp['min_temperature']}°C
    Type: {dp['drift_type']['type'].replace('_', ' ').title()}
""")
    
    print("\n🔍 TOP 5 LENGSTE PERIODER:")
    sorted_periods = sorted(periods, key=lambda x: x['duration_hours'], reverse=True)[:5]
    for i, period in enumerate(sorted_periods, 1):
        start_time = datetime.fromisoformat(period['start_time']).strftime('%d.%m.%Y %H:%M')
        print(f"""    {i}. {start_time}
       Varighet: {period['duration_hours']} timer
       Type: {period['drift_type']['type'].replace('_', ' ').title()}
       Vind: {period['max_wind_speed']} m/s, Temp: {period['min_temperature']}°C
       Faregrad: {period['drift_type']['road_danger']}
""")

def main():
    """Hovedfunksjon for periode-analyse."""
    
    try:
        # Utfør analyse
        analysis = analyze_winter_season_periods()
        
        if not analysis:
            print("❌ Analyse feilet")
            return
        
        # Skriv rapport
        print_period_report(analysis)
        
        # Lagre resultater
        output_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/snowdrift_periods_2023_2024.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Resultater lagret i {output_file}")
        
        # Viktige konklusjoner
        if analysis.get('summary'):
            summary = analysis['summary']
            print(f"""
🎯 VIKTIGE KONKLUSJONER:
• {summary['total_periods']} snøfokk-perioder i brøytesesongen 2023-2024
• {summary['invisible_drift_periods']} perioder med usynlig snøfokk
• Gjennomsnittlig varighet: {summary['avg_duration_hours']} timer per periode
• {summary['high_risk_periods']} høyrisiko perioder krever spesiell oppmerksomhet
""")
        
    except Exception as e:
        print(f"❌ Feil: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
