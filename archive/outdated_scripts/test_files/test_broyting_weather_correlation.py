"""
Test ML-kriterier mot faktiske brøytingsepisoder fra Rapport 2022-2025.csv
Analyserer værforholdene 6 timer før, under og etter brøyting.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# Legg til src-mappen til Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from live_conditions_app import LiveConditionsChecker
    print("✅ Importerte Live Conditions moduler")
except ImportError as e:
    print(f"❌ Feil ved import: {e}")
    sys.exit(1)


def parse_norwegian_date(date_str):
    """Parse norsk datoformat til datetime"""
    months = {
        'jan.': 1, 'feb.': 2, 'mars': 3, 'apr.': 4, 'mai': 5, 'juni': 6,
        'juli': 7, 'aug.': 8, 'sep.': 9, 'okt.': 10, 'nov.': 11, 'des.': 12
    }

    parts = date_str.strip().split()
    day = int(parts[0].rstrip('.'))
    month_str = parts[1]
    year = int(parts[2])

    month = months.get(month_str, 1)
    return datetime(year, month, day)


def load_broyting_data():
    """Last brøytingsdata fra CSV"""
    try:
        df = pd.read_csv('data/analyzed/Rapport 2022-2025.csv',
                        sep=';', encoding='utf-8')

        # Parse datoer og tider
        broyting_events = []
        for _, row in df.iterrows():
            if pd.isna(row['Dato']) or row['Dato'] == 'Totalt':
                continue

            try:
                base_date = parse_norwegian_date(row['Dato'])
                start_time = datetime.strptime(row['Starttid'], '%H:%M:%S').time()
                end_time = datetime.strptime(row['Sluttid'], '%H:%M:%S').time()

                start_datetime = datetime.combine(base_date.date(), start_time)
                end_datetime = datetime.combine(base_date.date(), end_time)

                # Håndter midnatt-overganger
                if end_time < start_time:
                    end_datetime += timedelta(days=1)

                # Parse varighet og distanse
                varighet_parts = row['Varighet'].split(':')
                varighet_timer = float(varighet_parts[0]) + float(varighet_parts[1])/60

                distanse = float(str(row['Distanse (km)']).replace(',', '.'))

                # Klassifiser type brøyting basert på varighet og distanse
                if varighet_timer < 0.5 or distanse < 5:
                    broyting_type = "inspeksjon"
                elif varighet_timer > 4 or distanse > 25:
                    broyting_type = "stor_broyting"
                else:
                    broyting_type = "normal_broyting"

                broyting_events.append({
                    'dato': row['Dato'],
                    'start_datetime': start_datetime,
                    'end_datetime': end_datetime,
                    'rode': row['Rode'],
                    'enhet': row['Enhet'],
                    'varighet_timer': varighet_timer,
                    'distanse_km': distanse,
                    'type': broyting_type
                })

            except Exception as e:
                print(f"  ⚠️  Kunne ikke parse: {row['Dato']} - {e}")
                continue

        print(f"✅ Lastet {len(broyting_events)} brøytingsepisoder")
        return broyting_events

    except Exception as e:
        print(f"❌ Feil ved lasting av brøytingsdata: {e}")
        return []


def analyze_weather_before_during_after_broyting(event, checker):
    """Analyser værforholdene før, under og etter en brøytingsepisode"""

    # Definer tidsperioder (6 timer før, under, 3 timer etter)
    before_start = event['start_datetime'] - timedelta(hours=6)
    before_end = event['start_datetime']
    during_start = event['start_datetime']
    during_end = event['end_datetime']
    after_start = event['end_datetime']
    after_end = event['end_datetime'] + timedelta(hours=3)

    results = {}

    # Analyser periode før brøyting
    print(f"    📊 Analyserer 6t FØR brøyting ({before_start.strftime('%H:%M')}-{before_end.strftime('%H:%M')})...")
    try:
        before_df = checker.get_current_weather_data(
            start_date=before_start.strftime('%Y-%m-%d'),
            end_date=before_end.strftime('%Y-%m-%d')
        )

        if before_df is not None and len(before_df) > 0:
            # Filtrer på tidsperiode
            before_df['referenceTime'] = pd.to_datetime(before_df['referenceTime'])
            mask = (before_df['referenceTime'] >= before_start) & (before_df['referenceTime'] <= before_end)
            before_df = before_df[mask]

            if len(before_df) > 0:
                snowdrift_before = checker.analyze_snowdrift_risk(before_df)
                slippery_before = checker.analyze_slippery_road_risk(before_df)

                # Statistikk
                temp_stats = before_df['air_temperature'].describe() if 'air_temperature' in before_df.columns else {}
                wind_stats = before_df['wind_speed'].describe() if 'wind_speed' in before_df.columns else {}
                snow_stats = before_df['surface_snow_thickness'].describe() if 'surface_snow_thickness' in before_df.columns else {}

                results['before'] = {
                    'snowdrift': snowdrift_before,
                    'slippery': slippery_before,
                    'data_points': len(before_df),
                    'temp_stats': temp_stats.to_dict() if hasattr(temp_stats, 'to_dict') else {},
                    'wind_stats': wind_stats.to_dict() if hasattr(wind_stats, 'to_dict') else {},
                    'snow_stats': snow_stats.to_dict() if hasattr(snow_stats, 'to_dict') else {}
                }
            else:
                results['before'] = {'error': 'Ingen data i tidsperioden'}
        else:
            results['before'] = {'error': 'Ingen værdata tilgjengelig'}

    except Exception as e:
        results['before'] = {'error': f'API feil: {e}'}

    # Analyser periode under brøyting
    print(f"    📊 Analyserer UNDER brøyting ({during_start.strftime('%H:%M')}-{during_end.strftime('%H:%M')})...")
    try:
        during_df = checker.get_current_weather_data(
            start_date=during_start.strftime('%Y-%m-%d'),
            end_date=during_end.strftime('%Y-%m-%d')
        )

        if during_df is not None and len(during_df) > 0:
            # Filtrer på tidsperiode
            during_df['referenceTime'] = pd.to_datetime(during_df['referenceTime'])
            mask = (during_df['referenceTime'] >= during_start) & (during_df['referenceTime'] <= during_end)
            during_df = during_df[mask]

            if len(during_df) > 0:
                snowdrift_during = checker.analyze_snowdrift_risk(during_df)
                slippery_during = checker.analyze_slippery_road_risk(during_df)

                temp_stats = during_df['air_temperature'].describe() if 'air_temperature' in during_df.columns else {}
                wind_stats = during_df['wind_speed'].describe() if 'wind_speed' in during_df.columns else {}
                snow_stats = during_df['surface_snow_thickness'].describe() if 'surface_snow_thickness' in during_df.columns else {}

                results['during'] = {
                    'snowdrift': snowdrift_during,
                    'slippery': slippery_during,
                    'data_points': len(during_df),
                    'temp_stats': temp_stats.to_dict() if hasattr(temp_stats, 'to_dict') else {},
                    'wind_stats': wind_stats.to_dict() if hasattr(wind_stats, 'to_dict') else {},
                    'snow_stats': snow_stats.to_dict() if hasattr(snow_stats, 'to_dict') else {}
                }
            else:
                results['during'] = {'error': 'Ingen data i tidsperioden'}
        else:
            results['during'] = {'error': 'Ingen værdata tilgjengelig'}

    except Exception as e:
        results['during'] = {'error': f'API feil: {e}'}

    # Analyser periode etter brøyting
    print(f"    📊 Analyserer 3t ETTER brøyting ({after_start.strftime('%H:%M')}-{after_end.strftime('%H:%M')})...")
    try:
        after_df = checker.get_current_weather_data(
            start_date=after_start.strftime('%Y-%m-%d'),
            end_date=after_end.strftime('%Y-%m-%d')
        )

        if after_df is not None and len(after_df) > 0:
            # Filtrer på tidsperiode
            after_df['referenceTime'] = pd.to_datetime(after_df['referenceTime'])
            mask = (after_df['referenceTime'] >= after_start) & (after_df['referenceTime'] <= after_end)
            after_df = after_df[mask]

            if len(after_df) > 0:
                snowdrift_after = checker.analyze_snowdrift_risk(after_df)
                slippery_after = checker.analyze_slippery_road_risk(after_df)

                temp_stats = after_df['air_temperature'].describe() if 'air_temperature' in after_df.columns else {}
                wind_stats = after_df['wind_speed'].describe() if 'wind_speed' in after_df.columns else {}
                snow_stats = after_df['surface_snow_thickness'].describe() if 'surface_snow_thickness' in after_df.columns else {}

                results['after'] = {
                    'snowdrift': snowdrift_after,
                    'slippery': slippery_after,
                    'data_points': len(after_df),
                    'temp_stats': temp_stats.to_dict() if hasattr(temp_stats, 'to_dict') else {},
                    'wind_stats': wind_stats.to_dict() if hasattr(wind_stats, 'to_dict') else {},
                    'snow_stats': snow_stats.to_dict() if hasattr(snow_stats, 'to_dict') else {}
                }
            else:
                results['after'] = {'error': 'Ingen data i tidsperioden'}
        else:
            results['after'] = {'error': 'Ingen værdata tilgjengelig'}

    except Exception as e:
        results['after'] = {'error': f'API feil: {e}'}

    return results


def evaluate_broyting_justification(weather_analysis, broyting_event):
    """Evaluer om brøytingen var berettiget basert på værforholdene"""

    justification = {
        'was_justified': False,
        'reasons': [],
        'ml_accuracy': 0.0,
        'weather_triggers': []
    }

    # Sjekk værforholdene før brøyting
    if 'before' in weather_analysis and 'error' not in weather_analysis['before']:
        before = weather_analysis['before']

        # Snøfokk-risiko
        if 'snowdrift' in before and before['snowdrift'].get('risk_level') in ['high', 'medium']:
            justification['reasons'].append('Snøfokk-risiko detektert før brøyting')
            justification['weather_triggers'].append('snowdrift')
            justification['was_justified'] = True

        # Glatt føre-risiko
        if 'slippery' in before and before['slippery'].get('risk_level') in ['high', 'medium']:
            justification['reasons'].append('Glatt føre-risiko detektert før brøyting')
            justification['weather_triggers'].append('slippery')
            justification['was_justified'] = True

        # Værstatistikk som trigger
        temp_stats = before.get('temp_stats', {})
        wind_stats = before.get('wind_stats', {})
        snow_stats = before.get('snow_stats', {})

        if temp_stats.get('min', 0) < -10:
            justification['reasons'].append(f'Ekstrem kulde ({temp_stats.get("min", 0):.1f}°C)')
            justification['weather_triggers'].append('extreme_cold')
            justification['was_justified'] = True

        if wind_stats.get('max', 0) > 10:
            justification['reasons'].append(f'Sterk vind ({wind_stats.get("max", 0):.1f} m/s)')
            justification['weather_triggers'].append('strong_wind')
            justification['was_justified'] = True

        if snow_stats.get('mean', 0) > 20:
            justification['reasons'].append(f'Mye snø ({snow_stats.get("mean", 0):.1f} cm)')
            justification['weather_triggers'].append('heavy_snow')
            justification['was_justified'] = True

    # Inspeksjonsrunder trenger ikke samme begrunnelse
    if broyting_event['type'] == 'inspeksjon':
        justification['was_justified'] = True
        justification['reasons'].append('Inspeksjonsrunde - alltid berettiget')

    # Beregn ML-nøyaktighet
    if justification['was_justified']:
        # Gi høyere score hvis både snøfokk og glatt føre ble detektert
        if 'snowdrift' in justification['weather_triggers'] and 'slippery' in justification['weather_triggers']:
            justification['ml_accuracy'] = 1.0
        elif len(justification['weather_triggers']) > 0:
            justification['ml_accuracy'] = 0.8
        else:
            justification['ml_accuracy'] = 0.6
    else:
        justification['ml_accuracy'] = 0.2  # Lav score hvis ikke berettiget

    return justification


def analyze_seasonal_patterns(broyting_events):
    """Analyser sesongmønstre i brøytingene"""
    patterns = {
        'by_month': {},
        'by_type': {},
        'by_hour': {},
        'recommendations': []
    }

    for event in broyting_events:
        month = event['start_datetime'].month
        hour = event['start_datetime'].hour
        event_type = event['type']

        # Månedsstatistikk
        if month not in patterns['by_month']:
            patterns['by_month'][month] = 0
        patterns['by_month'][month] += 1

        # Type-statistikk
        if event_type not in patterns['by_type']:
            patterns['by_type'][event_type] = 0
        patterns['by_type'][event_type] += 1

        # Time-statistikk
        if hour not in patterns['by_hour']:
            patterns['by_hour'][hour] = 0
        patterns['by_hour'][hour] += 1

    # Generer anbefalinger
    most_active_month = max(patterns['by_month'], key=patterns['by_month'].get)
    most_active_hour = max(patterns['by_hour'], key=patterns['by_hour'].get)

    month_names = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'Mai', 6: 'Jun',
                   7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Okt', 11: 'Nov', 12: 'Des'}

    patterns['recommendations'].append(
        f"Mest aktive måned: {month_names[most_active_month]} ({patterns['by_month'][most_active_month]} brøytinger)"
    )
    patterns['recommendations'].append(
        f"Mest aktive time: {most_active_hour:02d}:00 ({patterns['by_hour'][most_active_hour]} brøytinger)"
    )

    inspection_ratio = patterns['by_type'].get('inspeksjon', 0) / len(broyting_events)
    patterns['recommendations'].append(
        f"Inspeksjonsandel: {inspection_ratio:.1%} av alle brøytinger"
    )

    return patterns


def main():
    """Kjør analyse av brøyting vs. værforhold"""
    print("🚜 BRØYTING vs. VÆRFORHOLD ANALYSE")
    print("=" * 60)

    # Last brøytingsdata
    print("\n📂 Laster brøytingsdata...")
    broyting_events = load_broyting_data()

    if not broyting_events:
        print("❌ Ingen brøytingsdata funnet")
        return

    # Analyser sesongmønstre
    print("\n📈 Analyserer sesongmønstre...")
    seasonal_patterns = analyze_seasonal_patterns(broyting_events)

    print("📊 SESONGMØNSTRE:")
    for recommendation in seasonal_patterns['recommendations']:
        print(f"  • {recommendation}")

    # Velg representative brøytingsepisoder for testing
    print("\n🎯 Velger representative episoder for ML-testing...")

    # Filtrér til store brøytinger i vintersesongen (des-mar)
    winter_events = [e for e in broyting_events
                    if e['start_datetime'].month in [12, 1, 2, 3]
                    and e['type'] in ['normal_broyting', 'stor_broyting']]

    # Velg maksimalt 10 episoder, fordelt over årene
    selected_events = []
    years = {}
    for event in winter_events:
        year = event['start_datetime'].year
        if year not in years:
            years[year] = []
        years[year].append(event)

    # Ta maksimalt 2 per år
    for year, events in years.items():
        events.sort(key=lambda x: x['varighet_timer'], reverse=True)  # Største først
        selected_events.extend(events[:2])

    # Begrens til 10 totalt
    selected_events = selected_events[:10]

    print(f"✅ Valgte {len(selected_events)} episoder for detaljert analyse")

    # Analyser hver episode
    checker = LiveConditionsChecker()
    all_results = []

    for i, event in enumerate(selected_events, 1):
        print(f"\n🚜 EPISODE {i}/{len(selected_events)}: {event['dato']}")
        print(f"    📅 {event['start_datetime'].strftime('%Y-%m-%d %H:%M')} - {event['end_datetime'].strftime('%H:%M')}")
        print(f"    🚛 {event['type'].replace('_', ' ').title()}: {event['varighet_timer']:.1f}t, {event['distanse_km']:.1f}km")

        # Analyser værforhold
        weather_analysis = analyze_weather_before_during_after_broyting(event, checker)

        # Evaluer begrunnelse
        justification = evaluate_broyting_justification(weather_analysis, event)

        # Vis resultater
        print(f"    🎯 Berettiget: {'✅ JA' if justification['was_justified'] else '❌ NEI'}")
        print(f"    📊 ML-nøyaktighet: {justification['ml_accuracy']:.1%}")

        if justification['reasons']:
            print("    💭 Begrunnelser:")
            for reason in justification['reasons']:
                print(f"      • {reason}")

        # Vis værsammendrag
        if 'before' in weather_analysis and 'error' not in weather_analysis['before']:
            before = weather_analysis['before']
            if 'snowdrift' in before:
                print(f"    🌨️  Snøfokk FØR: {before['snowdrift'].get('risk_level', 'unknown').upper()}")
            if 'slippery' in before:
                print(f"    🧊 Glatt føre FØR: {before['slippery'].get('risk_level', 'unknown').upper()}")

        # Lagre for sammendrag
        all_results.append({
            'event': event,
            'weather_analysis': weather_analysis,
            'justification': justification
        })

        # Kort pause for å ikke overbelaste API
        time.sleep(1)

    # Lag sammendrag
    print("\n📊 SAMMENDRAG AV ML-YTELSE")
    print("=" * 50)

    justified_count = sum(1 for r in all_results if r['justification']['was_justified'])
    avg_accuracy = np.mean([r['justification']['ml_accuracy'] for r in all_results])

    weather_triggers = {}
    for result in all_results:
        for trigger in result['justification']['weather_triggers']:
            weather_triggers[trigger] = weather_triggers.get(trigger, 0) + 1

    print(f"✅ Berettiga brøytinger: {justified_count}/{len(all_results)} ({justified_count/len(all_results):.1%})")
    print(f"📈 Gjennomsnittlig ML-nøyaktighet: {avg_accuracy:.1%}")
    print("\n🎯 Hyppigste værtriggere:")
    for trigger, count in sorted(weather_triggers.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {trigger}: {count} ganger")

    # Anbefalinger
    print("\n💡 ANBEFALINGER:")
    if avg_accuracy > 0.8:
        print("  ✅ ML-kriteriene fungerer meget godt for brøytingsbeslutninger")
    elif avg_accuracy > 0.6:
        print("  ⚠️  ML-kriteriene fungerer bra, men kan forbedres")
        print("  💭 Vurder justering av terskelverdier for vind og temperatur")
    else:
        print("  ❌ ML-kriteriene trenger betydelig forbedring")
        print("  🔧 Anbefaler kalibrering mot flere faktiske brøytingsepisoder")

    # Lagre detaljerte resultater
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    output_file = f"data/analyzed/broyting_weather_correlation_{timestamp}.json"

    # Konverter til JSON-serialiserbar format
    json_results = []
    for result in all_results:
        json_result = {
            'event': {
                'dato': result['event']['dato'],
                'start_datetime': result['event']['start_datetime'].isoformat(),
                'end_datetime': result['event']['end_datetime'].isoformat(),
                'type': result['event']['type'],
                'varighet_timer': result['event']['varighet_timer'],
                'distanse_km': result['event']['distanse_km']
            },
            'justification': result['justification']
        }
        json_results.append(json_result)

    try:
        os.makedirs('data/analyzed', exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'summary': {
                    'total_episodes': len(all_results),
                    'justified_count': justified_count,
                    'avg_ml_accuracy': avg_accuracy,
                    'weather_triggers': weather_triggers,
                    'seasonal_patterns': seasonal_patterns
                },
                'detailed_results': json_results
            }, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Detaljerte resultater lagret til: {output_file}")

    except Exception as e:
        print(f"⚠️  Kunne ikke lagre resultater: {e}")

    print("\n✅ BRØYTING-VÆRFORHOLD ANALYSE FULLFØRT")
    print(f"📊 Analyserte {len(selected_events)} brøytingsepisoder")
    print(f"🎯 ML-kriteriene har {avg_accuracy:.1%} nøyaktighet mot faktiske brøytinger")


if __name__ == "__main__":
    main()
