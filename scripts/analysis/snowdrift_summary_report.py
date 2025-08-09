#!/usr/bin/env python3
"""
Snøfokk Sammendrag Rapport
Genererer en detaljert sammendragsrapport av snøfokk-analysene
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any
import matplotlib.pyplot as plt

def load_analysis_results(file_path: str) -> Dict[str, Any]:
    """Last inn analyserte resultater fra JSON fil."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def create_summary_statistics(data: Dict[str, Any]) -> Dict[str, Any]:
    """Lag sammendragsstatistikk fra analysedataene."""
    events = data['events']
    df = pd.DataFrame(events)
    
    # Konverter tidsstempler til datetime
    df['start_time'] = pd.to_datetime(df['start_time'])
    df['end_time'] = pd.to_datetime(df['end_time'])
    
    # Klassifiser hendelsestyper
    drift_types = df['drift_type'].apply(lambda x: x['type']).value_counts()
    danger_levels = df['drift_type'].apply(lambda x: x['road_danger']).value_counts()
    
    # Tidsanalyse
    df['hour'] = df['start_time'].dt.hour
    df['day'] = df['start_time'].dt.day
    hourly_counts = df['hour'].value_counts().sort_index()
    daily_counts = df['day'].value_counts().sort_index()
    
    # Værforhold
    wind_stats = {
        'mean_wind': df['max_wind_speed'].mean(),
        'max_wind': df['max_wind_speed'].max(),
        'mean_gust': df['max_wind_gust'].mean(),
        'max_gust': df['max_wind_gust'].max()
    }
    
    temp_stats = {
        'mean_temp': df['min_temperature'].mean(),
        'min_temp': df['min_temperature'].min(),
        'max_temp': df['min_temperature'].max()
    }
    
    # Risikoscore statistikk
    risk_stats = {
        'mean_risk': df['risk_score'].mean(),
        'high_risk_events': len(df[df['risk_score'] >= 0.8]),
        'medium_risk_events': len(df[(df['risk_score'] >= 0.5) & (df['risk_score'] < 0.8)]),
        'low_risk_events': len(df[df['risk_score'] < 0.5])
    }
    
    return {
        'total_events': len(df),
        'drift_types': drift_types.to_dict(),
        'danger_levels': danger_levels.to_dict(),
        'hourly_distribution': hourly_counts.to_dict(),
        'daily_distribution': daily_counts.to_dict(),
        'wind_statistics': wind_stats,
        'temperature_statistics': temp_stats,
        'risk_statistics': risk_stats,
        'invisible_drift_count': len(df[df['invisible_drift'] == True])
    }

def create_visualization_report(data: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """Lag visualiseringer av snøfokk-dataene."""
    events = data['events']
    df = pd.DataFrame(events)
    df['start_time'] = pd.to_datetime(df['start_time'])
    df['hour'] = df['start_time'].dt.hour
    df['day'] = df['start_time'].dt.day
    
    # Set up plotting style
    plt.style.use('seaborn-v0_8')
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('Snøfokk Analyse - Januar 2024', fontsize=16, fontweight='bold')
    
    # 1. Timefordeling
    hourly_data = pd.Series(summary['hourly_distribution'])
    axes[0, 0].bar(hourly_data.index, hourly_data.values, color='skyblue', alpha=0.7)
    axes[0, 0].set_title('Snøfokk hendelser per time i døgnet')
    axes[0, 0].set_xlabel('Time i døgnet')
    axes[0, 0].set_ylabel('Antall hendelser')
    axes[0, 0].grid(True, alpha=0.3)
    
    # 2. Daglig fordeling
    daily_data = pd.Series(summary['daily_distribution'])
    axes[0, 1].plot(daily_data.index, daily_data.values, marker='o', linewidth=2, markersize=6)
    axes[0, 1].set_title('Snøfokk hendelser per dag i januar')
    axes[0, 1].set_xlabel('Dag i januar')
    axes[0, 1].set_ylabel('Antall hendelser')
    axes[0, 1].grid(True, alpha=0.3)
    
    # 3. Faregrad fordeling
    danger_data = pd.Series(summary['danger_levels'])
    colors = {'HIGH': 'red', 'MEDIUM': 'orange', 'LOW': 'green'}
    danger_colors = [colors.get(level, 'gray') for level in danger_data.index]
    axes[1, 0].pie(danger_data.values, labels=danger_data.index, autopct='%1.1f%%', 
                   colors=danger_colors, startangle=90)
    axes[1, 0].set_title('Fordeling av faregrad')
    
    # 4. Vind vs temperatur scatter
    df['danger_color'] = df['drift_type'].apply(lambda x: colors.get(x['road_danger'], 'gray'))
    axes[1, 1].scatter(df['max_wind_speed'], df['min_temperature'], 
                      c=df['danger_color'], alpha=0.6, s=50)
    axes[1, 1].set_xlabel('Maks vindstyrke (m/s)')
    axes[1, 1].set_ylabel('Min temperatur (°C)')
    axes[1, 1].set_title('Vindstyrke vs Temperatur (farget etter faregrad)')
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/snowdrift_summary_visualization.png', 
                dpi=300, bbox_inches='tight')
    plt.close()

def generate_text_report(data: Dict[str, Any], summary: Dict[str, Any]) -> str:
    """Generer en tekstbasert rapport."""
    period = data['period']
    station = data['station']
    methodology = data['methodology']
    
    report = f"""
🏔️ SNØFOKK ANALYSE RAPPORT - {station['name']}
==================================================

📅 ANALYSEPERIODE
    Fra: {period['start']}
    Til: {period['end']}
    Stasjon: {station['name']} ({station['id']})

📊 SAMMENDRAG
    Totalt antall hendelser: {summary['total_events']}
    Usynlig snøfokk: {summary['invisible_drift_count']} hendelser
    Gjennomsnittlig risikoscore: {summary['risk_statistics']['mean_risk']:.2f}

🏷️ HENDELSESTYPER
"""
    
    for drift_type, count in summary['drift_types'].items():
        percentage = (count / summary['total_events']) * 100
        report += f"    {drift_type.replace('_', ' ').title()}: {count} ({percentage:.1f}%)\n"
    
    report += """
⚠️ FAREGRAD FORDELING
"""
    
    for danger_level, count in summary['danger_levels'].items():
        percentage = (count / summary['total_events']) * 100
        report += f"    {danger_level}: {count} ({percentage:.1f}%)\n"
    
    report += f"""
🌬️ VINDFORHOLD
    Gjennomsnittlig vindstyrke: {summary['wind_statistics']['mean_wind']:.1f} m/s
    Maks vindstyrke: {summary['wind_statistics']['max_wind']:.1f} m/s
    Gjennomsnittlig vindkast: {summary['wind_statistics']['mean_gust']:.1f} m/s
    Maks vindkast: {summary['wind_statistics']['max_gust']:.1f} m/s

🌡️ TEMPERATURFORHOLD
    Gjennomsnittlig temperatur: {summary['temperature_statistics']['mean_temp']:.1f}°C
    Laveste temperatur: {summary['temperature_statistics']['min_temp']:.1f}°C
    Høyeste temperatur: {summary['temperature_statistics']['max_temp']:.1f}°C

🎯 RISIKOKATEGORIER
    Høy risiko (≥0.8): {summary['risk_statistics']['high_risk_events']} hendelser
    Medium risiko (0.5-0.8): {summary['risk_statistics']['medium_risk_events']} hendelser
    Lav risiko (<0.5): {summary['risk_statistics']['low_risk_events']} hendelser

⏰ TIDSANALYSE
    Mest aktive timer: {sorted(summary['hourly_distribution'].items(), key=lambda x: x[1], reverse=True)[:3]}
    Mest aktive dager: {sorted(summary['daily_distribution'].items(), key=lambda x: x[1], reverse=True)[:3]}

🔧 METODIKK
    Justerte terskler:
        - Vindstyrke: ≥{methodology['adjusted_thresholds']['wind_speed']} m/s
        - Temperatur: ≤{methodology['adjusted_thresholds']['temperature']}°C
        - Snødybde: ≥{methodology['adjusted_thresholds']['snow_depth']} cm
        - Risikoterksel: ≥{methodology['adjusted_thresholds']['risk_threshold']}

🚨 KRITISKE OBSERVASJONER
    • {summary['invisible_drift_count']} tilfeller av 'usynlig snøfokk' - farlig for veier!
    • {summary['danger_levels'].get('HIGH', 0)} hendelser klassifisert som høy faregrad
    • {summary['risk_statistics']['high_risk_events']} hendelser med høy risikoscore (≥0.8)

📈 ANBEFALT OPPFØLGING
    1. Fokuser på time {max(summary['hourly_distribution'], key=summary['hourly_distribution'].get)} - mest aktiv periode
    2. Økt overvåking ved {summary['danger_levels'].get('HIGH', 0)} høyrisiko hendelser
    3. Spesiell oppmerksomhet på usynlig snøfokk som kan blokkere veier
"""
    
    return report

def main():
    """Hovedfunksjon for å generere sammendragsrapport."""
    print("🏔️ SNØFOKK SAMMENDRAG RAPPORT")
    print("=" * 50)
    
    # Last inn resultatene
    analysis_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/fixed_enhanced_snowdrift_analysis.json'
    
    try:
        data = load_analysis_results(analysis_file)
        print(f"✅ Lastet inn {len(data['events'])} hendelser")
        
        # Lag sammendragsstatistikk
        summary = create_summary_statistics(data)
        print("📊 Generert sammendragsstatistikk")
        
        # Lag visualiseringer
        create_visualization_report(data, summary)
        print("📈 Lagret visualiseringer til data/analyzed/snowdrift_summary_visualization.png")
        
        # Generer tekstrapport
        text_report = generate_text_report(data, summary)
        
        # Lagre tekstrapport
        report_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/snowdrift_summary_report.txt'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(text_report)
        
        print(f"📄 Lagret tekstrapport til {report_file}")
        print("\n" + text_report)
        
    except Exception as e:
        print(f"❌ Feil: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
