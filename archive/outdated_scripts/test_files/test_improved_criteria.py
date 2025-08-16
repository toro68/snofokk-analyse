"""
Test som sammenligner gamle vs nye ML-kriterier
mot faktiske brøytingsepisoder for å måle forbedring.
"""

import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

# Legg til src-mappen til Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Import forbedrede kriterier
from criteria_analysis_and_proposals import ImprovedMLCriteria


def parse_duration_to_hours(duration_str):
    """Konverter varighet fra format 'H:MM:SS' til desimaltimer"""
    try:
        if pd.isna(duration_str) or duration_str == '':
            return 0.0

        parts = str(duration_str).split(':')
        if len(parts) != 3:
            return 0.0

        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])

        total_hours = hours + minutes/60.0 + seconds/3600.0
        return total_hours

    except (ValueError, IndexError):
        return 0.0


def simulate_weather_conditions(row):
    """Simuler realistiske værforhold basert på dato og kategori (samme som før)"""

    category = row['Kategori']
    month = row['Måned']
    is_winter = row['Er_vintersesong']

    # Basis værforhold basert på sesong
    if is_winter and month in [12, 1, 2]:  # Kald vinter
        base_temp = np.random.normal(-5, 3)
        base_wind = np.random.normal(6, 2)
        base_snow = np.random.normal(20, 10)
        base_precip = np.random.exponential(3)
    elif is_winter and month in [3, 4]:  # Sent vinter/tidlig vår
        base_temp = np.random.normal(0, 4)
        base_wind = np.random.normal(5, 2)
        base_snow = np.random.normal(10, 8)
        base_precip = np.random.exponential(5)
    elif month in [11]:  # Tidlig vinter
        base_temp = np.random.normal(-2, 3)
        base_wind = np.random.normal(5, 2)
        base_snow = np.random.normal(15, 10)
        base_precip = np.random.exponential(4)
    else:  # Sommersesong (skulle ikke ha brøyting)
        base_temp = np.random.normal(10, 5)
        base_wind = np.random.normal(4, 1)
        base_snow = 0
        base_precip = np.random.exponential(2)

    # Juster basert på vedlikeholdskategori
    if category == 'heavy_plowing':
        # Tunbrøyting krever typisk dårlige forhold
        temp = base_temp - np.random.exponential(2)  # Kaldere
        wind = base_wind + np.random.exponential(3)  # Mer vind
        snow = base_snow + np.random.exponential(10)  # Mer snø
        precip = base_precip + np.random.exponential(5)  # Mer nedbør
    elif category == 'standard_maintenance':
        # Standard vedlikehold - moderate forhold
        temp = base_temp + np.random.normal(0, 1)
        wind = base_wind + np.random.normal(0, 1)
        snow = base_snow + np.random.normal(0, 5)
        precip = base_precip + np.random.exponential(2)
    elif category == 'friday_routine':
        # Fredagsrutiner - kan være planlagt uavhengig av vær
        temp = base_temp + np.random.normal(0, 2)
        wind = base_wind + np.random.normal(0, 1)
        snow = max(0, base_snow + np.random.normal(0, 5))
        precip = base_precip * np.random.uniform(0.5, 1.5)
    else:
        # Inspeksjoner og annet - typisk bedre forhold
        temp = base_temp + np.random.uniform(1, 3)
        wind = max(1, base_wind - np.random.exponential(1))
        snow = max(0, base_snow - np.random.exponential(5))
        precip = base_precip * np.random.uniform(0.2, 0.8)

    # Sikre realistiske grenser
    temp = max(-20, min(15, temp))
    wind = max(0, min(25, wind))
    snow = max(0, min(100, snow))
    precip = max(0, min(50, precip))
    humidity = min(100, max(40, np.random.normal(75, 15)))

    return {
        'temperature': temp,
        'wind_speed': wind,
        'snow_depth': snow,
        'precipitation': precip,
        'humidity': humidity
    }


def test_old_vs_new_criteria():
    """Test gamle vs nye kriterier mot faktiske brøytingsepisoder"""

    print("🧪 TESTING GAMLE VS NYE ML-KRITERIER")
    print("=" * 50)

    # Last brøytingsdata
    try:
        df = pd.read_csv('data/analyzed/Rapport 2022-2025.csv', sep=';')
        print(f"✅ Lastet {len(df)} vedlikeholdsepisoder")
    except Exception as e:
        print(f"❌ Kunne ikke laste data: {e}")
        return

    # Konverter og kategoriser
    df['Varighet_timer'] = df['Varighet'].apply(parse_duration_to_hours)
    df['Dato_parsed'] = pd.to_datetime(df['Dato'], format='%d. %b. %Y', errors='coerce')
    df['Måned'] = df['Dato_parsed'].dt.month
    df['Er_vintersesong'] = df['Måned'].isin([11, 12, 1, 2, 3, 4])

    # Kategorisering (samme som før)
    df['Kategori'] = 'unknown'

    inspection_mask = (df['Varighet_timer'] < 1.0) & (df['Distanse (km)'] < 10.0)
    df.loc[inspection_mask, 'Kategori'] = 'road_inspection'

    friday_mask = (df['Dato_parsed'].dt.day_name() == 'Friday') & ~inspection_mask & (df['Varighet_timer'] >= 1.5)
    df.loc[friday_mask, 'Kategori'] = 'friday_routine'

    heavy_mask = (df['Varighet_timer'] > 5.0) & ~inspection_mask & ~friday_mask
    df.loc[heavy_mask, 'Kategori'] = 'heavy_plowing'

    standard_mask = (df['Varighet_timer'] >= 1.0) & (df['Varighet_timer'] <= 5.0) & ~inspection_mask & ~friday_mask
    df.loc[standard_mask, 'Kategori'] = 'standard_maintenance'

    df.loc[df['Kategori'] == 'unknown', 'Kategori'] = 'unknown_short'

    # Marker væravhengighet
    weather_dependent = ['heavy_plowing', 'standard_maintenance']
    df['Er_væravhengig'] = df['Kategori'].isin(weather_dependent)

    # Test gamle kriterier (last ML-resultater fra tidligere test)
    try:
        old_results = pd.read_csv('data/analyzed/ml_weather_correlation_analysis_20250811_2020.csv')
        print(f"✅ Lastet gamle ML-resultater ({len(old_results)} episoder)")
    except Exception as e:
        print(f"❌ Kunne ikke laste gamle resultater: {e}")
        return

    # Initialiser nye kriterier
    new_criteria = ImprovedMLCriteria()

    # Test nye kriterier på samme datasett
    print(f"\n🔄 Tester nye kriterier på {len(old_results)} episoder...")

    new_results = []

    for idx, row in old_results.iterrows():
        # Bruk samme værdata som før
        weather_data = {
            'temperature': row['temperatur'],
            'wind_speed': row['vind'],
            'snow_depth': row['snødybde'],
            'precipitation': row['nedbør'],
            'humidity': 75  # Standard verdi
        }

        # Test nye snøfokk-kriterier
        new_snowdrift = new_criteria.analyze_snowdrift_risk_improved(weather_data)

        # Test nye glattføre-kriterier
        new_slippery = new_criteria.analyze_slippery_road_risk_improved(weather_data)

        new_results.append({
            'episode_idx': row['episode_idx'],
            'dato': row['dato'],
            'kategori': row['kategori'],
            'er_væravhengig': row['er_væravhengig'],
            'old_snøfokk_risiko': row['snøfokk_risiko'],
            'old_glattføre_risiko': row['glattføre_risiko'],
            'new_snøfokk_risiko': new_snowdrift['risk_level'],
            'new_glattføre_risiko': new_slippery['risk_level'],
            'new_snøfokk_reason': new_snowdrift['reason'],
            'new_glattføre_reason': new_slippery['reason']
        })

    new_results_df = pd.DataFrame(new_results)

    # Sammenlign ytelse
    print("\n📊 SAMMENLIGNING AV GAMLE VS NYE KRITERIER:")
    print("=" * 55)

    # Analyser væravhengige episoder
    weather_dependent_episodes = new_results_df[new_results_df['er_væravhengig'] == True]
    non_weather_episodes = new_results_df[new_results_df['er_væravhengig'] == False]

    print(f"🌤️ VÆRAVHENGIGE EPISODER ({len(weather_dependent_episodes)}):")

    # Gamle kriterier - væravhengige
    old_snowdrift_high = len(weather_dependent_episodes[weather_dependent_episodes['old_snøfokk_risiko'].isin(['medium', 'high'])])
    old_slippery_high = len(weather_dependent_episodes[weather_dependent_episodes['old_glattføre_risiko'].isin(['medium', 'high'])])
    old_correct = len(weather_dependent_episodes[
        (weather_dependent_episodes['old_snøfokk_risiko'].isin(['medium', 'high'])) |
        (weather_dependent_episodes['old_glattføre_risiko'].isin(['medium', 'high']))
    ])
    old_accuracy_weather = old_correct / len(weather_dependent_episodes) * 100

    # Nye kriterier - væravhengige
    new_snowdrift_high = len(weather_dependent_episodes[weather_dependent_episodes['new_snøfokk_risiko'].isin(['medium', 'high'])])
    new_slippery_high = len(weather_dependent_episodes[weather_dependent_episodes['new_glattføre_risiko'].isin(['medium', 'high'])])
    new_correct = len(weather_dependent_episodes[
        (weather_dependent_episodes['new_snøfokk_risiko'].isin(['medium', 'high'])) |
        (weather_dependent_episodes['new_glattføre_risiko'].isin(['medium', 'high']))
    ])
    new_accuracy_weather = new_correct / len(weather_dependent_episodes) * 100

    print("GAMLE KRITERIER:")
    print(f"  Snøfokk medium/high: {old_snowdrift_high}/{len(weather_dependent_episodes)} ({old_snowdrift_high/len(weather_dependent_episodes)*100:.1f}%)")
    print(f"  Glattføre medium/high: {old_slippery_high}/{len(weather_dependent_episodes)} ({old_slippery_high/len(weather_dependent_episodes)*100:.1f}%)")
    print(f"  Total korrekt: {old_correct}/{len(weather_dependent_episodes)} ({old_accuracy_weather:.1f}%)")

    print("NYE KRITERIER:")
    print(f"  Snøfokk medium/high: {new_snowdrift_high}/{len(weather_dependent_episodes)} ({new_snowdrift_high/len(weather_dependent_episodes)*100:.1f}%)")
    print(f"  Glattføre medium/high: {new_slippery_high}/{len(weather_dependent_episodes)} ({new_slippery_high/len(weather_dependent_episodes)*100:.1f}%)")
    print(f"  Total korrekt: {new_correct}/{len(weather_dependent_episodes)} ({new_accuracy_weather:.1f}%)")

    weather_improvement = new_accuracy_weather - old_accuracy_weather
    print(f"🎯 FORBEDRING VÆRAVHENGIGE: {weather_improvement:+.1f} prosentpoeng")

    # Analyser ikke-væravhengige episoder
    print(f"\n📅 IKKE-VÆRAVHENGIGE EPISODER ({len(non_weather_episodes)}):")

    # Gamle kriterier - ikke-væravhengige (bør ha lav risiko)
    old_low = len(non_weather_episodes[
        (non_weather_episodes['old_snøfokk_risiko'] == 'low') &
        (non_weather_episodes['old_glattføre_risiko'] == 'low')
    ])
    old_accuracy_non_weather = old_low / len(non_weather_episodes) * 100

    # Nye kriterier - ikke-væravhengige (bør ha lav risiko)
    new_low = len(non_weather_episodes[
        (non_weather_episodes['new_snøfokk_risiko'] == 'low') &
        (non_weather_episodes['new_glattføre_risiko'] == 'low')
    ])
    new_accuracy_non_weather = new_low / len(non_weather_episodes) * 100

    print("GAMLE KRITERIER:")
    print(f"  Begge lav risiko: {old_low}/{len(non_weather_episodes)} ({old_accuracy_non_weather:.1f}%)")

    print("NYE KRITERIER:")
    print(f"  Begge lav risiko: {new_low}/{len(non_weather_episodes)} ({new_accuracy_non_weather:.1f}%)")

    non_weather_improvement = new_accuracy_non_weather - old_accuracy_non_weather
    print(f"🎯 FORBEDRING IKKE-VÆRAVHENGIGE: {non_weather_improvement:+.1f} prosentpoeng")

    # Total forbedring
    total_old_correct = old_correct + old_low
    total_new_correct = new_correct + new_low
    total_episodes = len(new_results_df)

    total_old_accuracy = total_old_correct / total_episodes * 100
    total_new_accuracy = total_new_correct / total_episodes * 100
    total_improvement = total_new_accuracy - total_old_accuracy

    print("\n🏆 SAMLET RESULTAT:")
    print(f"Gamle kriterier total nøyaktighet: {total_old_accuracy:.1f}%")
    print(f"Nye kriterier total nøyaktighet: {total_new_accuracy:.1f}%")
    print(f"TOTAL FORBEDRING: {total_improvement:+.1f} prosentpoeng")

    if total_improvement > 10:
        print("✅ BETYDELIG FORBEDRING - anbefaler implementering!")
    elif total_improvement > 5:
        print("⚠️ MODERAT FORBEDRING - vurder implementering")
    elif total_improvement > 0:
        print("⚠️ LITEN FORBEDRING - trenger mer justering")
    else:
        print("❌ INGEN/NEGATIV FORBEDRING - ikke implementer")

    # Lagre resultater
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    output_file = f"data/analyzed/old_vs_new_criteria_comparison_{timestamp}.csv"
    new_results_df.to_csv(output_file, index=False)
    print(f"\n💾 Detaljerte sammenligningsresultater lagret: {output_file}")

    # Eksempel på forbedringer
    print("\n💡 EKSEMPLER PÅ FORBEDRINGER:")

    # Finn episoder hvor nye kriterier er bedre
    weather_improved = weather_dependent_episodes[
        ((weather_dependent_episodes['old_snøfokk_risiko'] == 'low') &
         (weather_dependent_episodes['old_glattføre_risiko'] == 'low')) &
        ((weather_dependent_episodes['new_snøfokk_risiko'].isin(['medium', 'high'])) |
         (weather_dependent_episodes['new_glattføre_risiko'].isin(['medium', 'high'])))
    ]

    if len(weather_improved) > 0:
        print("Væravhengige episoder som nå får riktig høy risiko:")
        for _, row in weather_improved.head(3).iterrows():
            print(f"  {row['dato']} ({row['kategori']}): {row['new_snøfokk_reason']} / {row['new_glattføre_reason']}")


def main():
    """Kjør sammenligning av gamle vs nye kriterier"""

    print("🧪 TESTING AV FORBEDREDE ML-KRITERIER")
    print("=" * 50)
    print("Sammenligner gamle vs nye kriterier mot faktiske brøytingsepisoder")
    print()

    test_old_vs_new_criteria()

    print("\n✅ TESTING FULLFØRT")


if __name__ == "__main__":
    main()
