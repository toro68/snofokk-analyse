#!/usr/bin/env python3
"""
TEST AV BALANSERTE ML-KRITERIER
Tester de justerte kriteriene mot gamle og nye
"""

from datetime import datetime

import pandas as pd


def detect_snowdrift_risk_balanced(weather_data):
    """Balanserte snøfokk-kriterier"""

    temp = weather_data.get('temperatur', 0)
    wind_speed = weather_data.get('vindstyrke', 0)
    snow_depth = weather_data.get('snødybde', 0)
    snow_change = weather_data.get('snødybdeendring', 0)

    # Vindkjøling (justert terskel)
    wind_chill = temp - (wind_speed * 2)

    # Høy risiko (strenge kriterier fra gamle systemet)
    if wind_chill <= -15 and wind_speed >= 7:
        return 'high', f"Ekstrem vindkjøling {wind_chill:.1f}°C + høy vind {wind_speed:.1f}m/s"

    if snow_depth >= 30 and wind_speed >= 8:
        return 'high', f"Mye snø {snow_depth:.1f}cm + høy vind {wind_speed:.1f}m/s"

    # Medium risiko (justerte terskler)
    if wind_chill <= -6 and wind_speed >= 3:  # Justert fra -8 til -6
        return 'medium', f"Vindkjøling {wind_chill:.1f}°C + vind {wind_speed:.1f}m/s"

    if snow_depth >= 15 and wind_speed >= 5:
        return 'medium', f"Moderat snø {snow_depth:.1f}cm + vind {wind_speed:.1f}m/s"

    if abs(snow_change) >= 3 and wind_speed >= 4:
        return 'medium', f"Snøendring {snow_change:.1f}cm + vind {wind_speed:.1f}m/s"

    return 'low', "Ingen kriterier oppfylt for snøfokk-risiko"

def detect_slippery_risk_balanced(weather_data):
    """Balanserte glattføre-kriterier"""

    temp = weather_data.get('temperatur', 0)
    precipitation = weather_data.get('nedbør', 0)
    snow_depth = weather_data.get('snødybde', 0)
    snow_change = weather_data.get('snødybdeendring', 0)

    # Regn på snø (justerte terskler)
    if (temp > -2 and precipitation >= 0.2 and snow_depth >= 1 and  # Justert fra 0.5 til 0.2
        snow_change <= 0):  # Negativ eller null endring = regn
        return 'high', f"Regn på snø: {temp:.1f}°C, {snow_depth:.1f}cm snø, {precipitation:.1f}mm nedbør"

    # Mildvær etter frost
    if temp > 2 and snow_depth >= 5:
        return 'medium', f"Mildvær {temp:.1f}°C etter frost, {snow_depth:.1f}cm snø"

    return 'low', "Ingen kriterier oppfylt for glattføre-risiko"

def test_balanced_criteria():
    """Test balanserte kriterier mot eksisterende"""

    print("🧪 TESTING AV BALANSERTE ML-KRITERIER")
    print("=" * 42)

    # Les siste værdata fra maintenance correlation
    ml_file = "/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/maintenance_weather_data_20250810_1303.csv"
    ml_df = pd.read_csv(ml_file)

    print(f"✅ Lastet {len(ml_df)} episoder for testing")

    # Test balanserte kriterier
    balanced_results = []

    for idx, row in ml_df.iterrows():
        weather_data = {
            'temperatur': row['temp_mean'],
            'vindstyrke': row['wind_max'],
            'snødybde': row['snow_depth_cm'],
            'snødybdeendring': 0,  # Ikke tilgjengelig i denne filen
            'nedbør': row['precip_total']
        }

        # Test balanserte kriterier
        snowdrift_risk, snowdrift_reason = detect_snowdrift_risk_balanced(weather_data)
        slippery_risk, slippery_reason = detect_slippery_risk_balanced(weather_data)

        balanced_results.append({
            'episode_idx': idx,
            'dato': row['maintenance_date'],
            'kategori': row['snow_response_classification'],
            'er_væravhengig': row['snow_response_classification'] in ['standard_maintenance', 'heavy_plowing'],
            'balanced_snøfokk_risiko': snowdrift_risk,
            'balanced_glattføre_risiko': slippery_risk,
            'balanced_snøfokk_reason': snowdrift_reason,
            'balanced_glattføre_reason': slippery_reason
        })

    balanced_df = pd.DataFrame(balanced_results)

    # Les sammenligning med gamle/nye
    comparison_file = "/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/old_vs_new_criteria_comparison_20250811_2027.csv"
    comparison_df = pd.read_csv(comparison_file)

    # Merge med balanserte resultater
    final_df = comparison_df.merge(balanced_df, on=['episode_idx', 'dato'], how='inner')

    # Analyser væravhengige episoder
    weather_episodes = final_df[final_df['er_væravhengig'] == True]
    non_weather_episodes = final_df[final_df['er_væravhengig'] == False]

    print(f"\n🌤️ VÆRAVHENGIGE EPISODER ({len(weather_episodes)}):")
    print("-" * 45)

    # Gamle kriterier
    old_correct = len(weather_episodes[
        (weather_episodes['old_snøfokk_risiko'].isin(['medium', 'high'])) |
        (weather_episodes['old_glattføre_risiko'].isin(['medium', 'high']))
    ])
    old_accuracy = old_correct / len(weather_episodes) * 100

    # Nye kriterier
    new_correct = len(weather_episodes[
        (weather_episodes['new_snøfokk_risiko'].isin(['medium', 'high'])) |
        (weather_episodes['new_glattføre_risiko'].isin(['medium', 'high']))
    ])
    new_accuracy = new_correct / len(weather_episodes) * 100

    # Balanserte kriterier
    balanced_correct = len(weather_episodes[
        (weather_episodes['balanced_snøfokk_risiko'].isin(['medium', 'high'])) |
        (weather_episodes['balanced_glattføre_risiko'].isin(['medium', 'high']))
    ])
    balanced_accuracy = balanced_correct / len(weather_episodes) * 100

    print(f"GAMLE KRITERIER: {old_correct}/{len(weather_episodes)} ({old_accuracy:.1f}%)")
    print(f"NYE KRITERIER: {new_correct}/{len(weather_episodes)} ({new_accuracy:.1f}%)")
    print(f"BALANSERTE KRITERIER: {balanced_correct}/{len(weather_episodes)} ({balanced_accuracy:.1f}%)")

    # Ikke-væravhengige episoder
    print(f"\n📅 IKKE-VÆRAVHENGIGE EPISODER ({len(non_weather_episodes)}):")
    print("-" * 50)

    # Gamle kriterier (begge lav)
    old_both_low = len(non_weather_episodes[
        (non_weather_episodes['old_snøfokk_risiko'] == 'low') &
        (non_weather_episodes['old_glattføre_risiko'] == 'low')
    ])
    old_non_weather_accuracy = old_both_low / len(non_weather_episodes) * 100

    # Nye kriterier (begge lav)
    new_both_low = len(non_weather_episodes[
        (non_weather_episodes['new_snøfokk_risiko'] == 'low') &
        (non_weather_episodes['new_glattføre_risiko'] == 'low')
    ])
    new_non_weather_accuracy = new_both_low / len(non_weather_episodes) * 100

    # Balanserte kriterier (begge lav)
    balanced_both_low = len(non_weather_episodes[
        (non_weather_episodes['balanced_snøfokk_risiko'] == 'low') &
        (non_weather_episodes['balanced_glattføre_risiko'] == 'low')
    ])
    balanced_non_weather_accuracy = balanced_both_low / len(non_weather_episodes) * 100

    print(f"GAMLE KRITERIER (begge lav): {old_both_low}/{len(non_weather_episodes)} ({old_non_weather_accuracy:.1f}%)")
    print(f"NYE KRITERIER (begge lav): {new_both_low}/{len(non_weather_episodes)} ({new_non_weather_accuracy:.1f}%)")
    print(f"BALANSERTE KRITERIER (begge lav): {balanced_both_low}/{len(non_weather_episodes)} ({balanced_non_weather_accuracy:.1f}%)")

    # Samlet nøyaktighet
    print("\n🏆 SAMLET NØYAKTIGHET:")
    print("-" * 25)

    old_total_correct = old_correct + old_both_low
    new_total_correct = new_correct + new_both_low
    balanced_total_correct = balanced_correct + balanced_both_low
    total_episodes = len(weather_episodes) + len(non_weather_episodes)

    old_total_accuracy = old_total_correct / total_episodes * 100
    new_total_accuracy = new_total_correct / total_episodes * 100
    balanced_total_accuracy = balanced_total_correct / total_episodes * 100

    print(f"GAMLE KRITERIER: {old_total_accuracy:.1f}%")
    print(f"NYE KRITERIER: {new_total_accuracy:.1f}%")
    print(f"BALANSERTE KRITERIER: {balanced_total_accuracy:.1f}%")

    # Forbedring
    improvement_vs_old = balanced_total_accuracy - old_total_accuracy
    improvement_vs_new = balanced_total_accuracy - new_total_accuracy

    print("\n📈 FORBEDRING:")
    print(f"vs Gamle: {improvement_vs_old:+.1f} prosentpoeng")
    print(f"vs Nye: {improvement_vs_new:+.1f} prosentpoeng")

    # Lagre resultater
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = f"/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/balanced_criteria_comparison_{timestamp}.csv"
    final_df.to_csv(output_file, index=False)
    print(f"\n💾 Detaljerte resultater lagret: {output_file}")

    # Spesifikke forbedringer
    print("\n💡 SPESIFIKKE FORBEDRINGER MED BALANSERTE KRITERIER:")
    print("-" * 55)

    # Episoder der balanserte er bedre enn gamle
    balanced_better_than_old = weather_episodes[
        ((weather_episodes['old_snøfokk_risiko'] == 'low') &
         (weather_episodes['old_glattføre_risiko'] == 'low')) &
        ((weather_episodes['balanced_snøfokk_risiko'].isin(['medium', 'high'])) |
         (weather_episodes['balanced_glattføre_risiko'].isin(['medium', 'high'])))
    ]

    print(f"Forbedret {len(balanced_better_than_old)} væravhengige episoder vs gamle:")
    for idx, episode in balanced_better_than_old.iterrows():
        old_risk = f"{episode['old_snøfokk_risiko']}/{episode['old_glattføre_risiko']}"
        balanced_risk = f"{episode['balanced_snøfokk_risiko']}/{episode['balanced_glattføre_risiko']}"
        print(f"  {episode['dato']}: {old_risk} → {balanced_risk}")
        if episode['balanced_snøfokk_reason'] != "Ingen kriterier oppfylt for snøfokk-risiko":
            print(f"    Snøfokk: {episode['balanced_snøfokk_reason']}")
        if episode['balanced_glattføre_reason'] != "Ingen kriterier oppfylt for glattføre-risiko":
            print(f"    Glattføre: {episode['balanced_glattføre_reason']}")

    # Vurdering
    if balanced_total_accuracy > old_total_accuracy and balanced_total_accuracy > new_total_accuracy:
        print("\n✅ ANBEFALING: IMPLEMENTER BALANSERTE KRITERIER")
        print(f"Gir {improvement_vs_old:+.1f}pp forbedring vs gamle kriterier")
    else:
        print("\n❌ ANBEFALING: BEHOLD GAMLE KRITERIER")
        print("Balanserte kriterier gir ikke tilstrekkelig forbedring")

    return final_df

if __name__ == "__main__":
    test_balanced_criteria()
