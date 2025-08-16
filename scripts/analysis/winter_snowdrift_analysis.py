#!/usr/bin/env python3
"""
Snøfokk Winter Analysis - Analyserer vintermåneder for snøfokk-mønstre
"""
import sys
from datetime import datetime
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))


# Import the analyzer class directly
sys.path.insert(0, str(Path(__file__).parent))
from snowdrift_pattern_analyzer import SnowDriftPatternAnalyzer


def analyze_winter_periods():
    """Analyser historiske vintermåneder for snøfokk"""
    analyzer = SnowDriftPatternAnalyzer()

    # Definer vinterperioder (når snø faktisk forekommer)
    winter_periods = [
        ('2024-12-01', '2025-03-31', 'Vinter 2024-2025'),
        ('2023-12-01', '2024-03-31', 'Vinter 2023-2024'),
        ('2022-12-01', '2023-03-31', 'Vinter 2022-2023'),
    ]

    all_results = []

    for start_str, end_str, period_name in winter_periods:
        print(f"\n{'='*60}")
        print(f"Analyserer {period_name}")
        print(f"{'='*60}")

        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_str, '%Y-%m-%d')

            # Hent data for perioden
            weather_data = analyzer.fetch_historical_data(start_date, end_date)

            if weather_data.empty:
                print(f"❌ Ingen værdata for {period_name}")
                continue

            # Kjør analyse
            data_with_scores = analyzer.detect_snowdrift_conditions(weather_data)
            events = analyzer.find_snowdrift_events(data_with_scores)
            patterns = analyzer.analyze_snowdrift_patterns(events)

            # Vis resultater
            print(f"📊 Datapunkter: {len(weather_data)}")
            print(f"❄️  Høyrisiko-perioder: {(data_with_scores['high_snowdrift_risk'] == True).sum()}")
            print(f"🌨️  Snøfokk-hendelser: {patterns['total_events']}")

            if patterns['total_events'] > 0:
                print(f"⏱️  Total varighet: {patterns['total_duration']:.1f} timer")
                print(f"📈 Gjennomsnittlig varighet: {patterns['avg_duration']:.1f} timer")
                print(f"🏔️  Lengste hendelse: {patterns['max_duration']:.1f} timer")

                # Vis detaljerte mønstre
                wind = patterns['patterns']['wind']
                temp = patterns['patterns']['temperature']
                snow = patterns['patterns']['snow']

                print(f"\n🔍 MØNSTRE FOR {period_name}:")
                print(f"   💨 Vind: {wind['avg_max_wind']:.1f} m/s (range: {wind['optimal_wind_range']})")
                print(f"   🌡️  Temp: {temp['avg_min_temp']:.1f}°C (range: {temp['optimal_temp_range']})")
                print(f"   ❄️  Snø: Start {snow['avg_depth_at_start']:.1f} cm, endring {snow['avg_depth_change']:.1f} cm")

                print("\n💡 ANBEFALINGER:")
                for rec in patterns['recommendations']:
                    print(f"   • {rec}")
            else:
                print("ℹ️  Ingen snøfokk-hendelser funnet")

            # Lagre resultater
            result = {
                'period': period_name,
                'start_date': start_str,
                'end_date': end_str,
                'data_points': len(weather_data),
                'patterns': patterns
            }
            all_results.append(result)

        except Exception as e:
            print(f"❌ Feil ved analyse av {period_name}: {e}")

    # Sammenlign trender på tvers av år
    if len(all_results) > 1:
        print(f"\n{'='*60}")
        print("TRENDER PÅ TVERS AV ÅR")
        print(f"{'='*60}")

        total_events = sum(r['patterns']['total_events'] for r in all_results)
        total_hours = sum(r['patterns']['total_duration'] for r in all_results)

        print(f"📊 Totalt antall snøfokk-hendelser: {total_events}")
        print(f"⏱️  Total tid med snøfokk: {total_hours:.1f} timer")

        if total_events > 0:
            avg_events_per_year = total_events / len(all_results)
            print(f"📈 Gjennomsnitt per år: {avg_events_per_year:.1f} hendelser")

            # Finn beste/verste år
            events_per_year = [(r['period'], r['patterns']['total_events']) for r in all_results]
            events_per_year.sort(key=lambda x: x[1], reverse=True)

            print(f"🏆 Mest snøfokk: {events_per_year[0][0]} ({events_per_year[0][1]} hendelser)")
            print(f"🏅 Minst snøfokk: {events_per_year[-1][0]} ({events_per_year[-1][1]} hendelser)")

    # Lagre sammendrag
    import json
    output_file = Path(__file__).parent.parent.parent / 'data' / 'analyzed' / 'winter_snowdrift_analysis.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n💾 Detaljert analyse lagret i {output_file}")

if __name__ == '__main__':
    analyze_winter_periods()
