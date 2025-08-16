#!/usr/bin/env python3
"""
ANALYSER TEMPERATUR VS SNØMENGDE-ENDRINGER
Sjekker hva som skjer med snømålinger ved ulike temperaturer
"""

from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd


def analyze_temp_snow_relationship():
    """Analyser sammenheng mellom temperatur og snømengde-endringer"""

    print("🔍 ANALYSER TEMPERATUR VS SNØMENGDE-ENDRINGER")
    print("=" * 52)

    # Les brøytingsdata
    df = pd.read_csv("/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/maintenance_weather_data_20250810_1303.csv")

    print(f"✅ Analyserer {len(df)} episoder")

    # Filtrer ut episoder med nedbør
    df_precip = df[(df['precip_total'] > 0) & (df['temp_mean'].notna()) & (df['snow_depth_cm'].notna())]

    print(f"📊 {len(df_precip)} episoder med nedbør og temperatur/snødata")

    # Kategoriser temperatur
    df_precip['temp_category'] = 'unknown'
    df_precip.loc[df_precip['temp_mean'] < -2, 'temp_category'] = 'kald (< -2°C)'
    df_precip.loc[(df_precip['temp_mean'] >= -2) & (df_precip['temp_mean'] < 0), 'temp_category'] = 'rundt frysing (-2 til 0°C)'
    df_precip.loc[(df_precip['temp_mean'] >= 0) & (df_precip['temp_mean'] < 2), 'temp_category'] = 'lett pluss (0 til 2°C)'
    df_precip.loc[df_precip['temp_mean'] >= 2, 'temp_category'] = 'varm (> 2°C)'

    print("\n🌡️ TEMPERATUR-KATEGORIER:")
    print("-" * 30)
    for cat in df_precip['temp_category'].value_counts().index:
        count = df_precip['temp_category'].value_counts()[cat]
        print(f"  {cat}: {count} episoder")

    # Analyser snømengde-endringer per temperatur-kategori
    print("\n📊 SNØMENGDE-ENDRINGER PER TEMPERATUR-KATEGORI:")
    print("=" * 55)

    for temp_cat in df_precip['temp_category'].unique():
        if temp_cat == 'unknown':
            continue

        subset = df_precip[df_precip['temp_category'] == temp_cat]

        print(f"\n🌡️ {temp_cat.upper()} ({len(subset)} episoder):")
        print("-" * 40)

        # Gjennomsnitt
        avg_temp = subset['temp_mean'].mean()
        avg_precip = subset['precip_total'].mean()
        avg_snow_before = subset['snow_depth_cm'].mean()

        print(f"  Gjennomsnitt temp: {avg_temp:.1f}°C")
        print(f"  Gjennomsnitt nedbør: {avg_precip:.1f}mm")
        print(f"  Gjennomsnitt snødybde: {avg_snow_before:.0f}cm")

        # Analyser hva som skjer med snømengdene
        # Vi kan ikke se endring direkte, men kan se nivåer
        print("\n  EKSEMPLER FRA DENNE KATEGORIEN:")
        sample_episodes = subset.head(5)
        for idx, episode in sample_episodes.iterrows():
            dato = episode['maintenance_date']
            temp = episode['temp_mean']
            precip = episode['precip_total']
            snow = episode['snow_depth_cm']
            scenarios = episode['weather_scenarios']

            print(f"    {dato}: {temp:.1f}°C, {precip:.1f}mm nedbør, {snow:.0f}cm snø")
            print(f"      Scenarier: {scenarios}")

    # Analyser spesielt grenseområdene
    print("\n🎯 GRENSEOMRÅDE-ANALYSE (0°C ± 2°C):")
    print("=" * 45)

    boundary_cases = df_precip[
        (df_precip['temp_mean'] >= -2) &
        (df_precip['temp_mean'] <= 2) &
        (df_precip['precip_total'] > 0.5)  # Betydelig nedbør
    ].copy()

    print(f"📊 {len(boundary_cases)} episoder med betydelig nedbør rundt 0°C:")

    # Sorter etter temperatur
    boundary_cases = boundary_cases.sort_values('temp_mean')

    for idx, episode in boundary_cases.iterrows():
        dato = episode['maintenance_date']
        temp = episode['temp_mean']
        precip = episode['precip_total']
        snow = episode['snow_depth_cm']
        scenarios = episode['weather_scenarios']
        criteria = episode['maintenance_criteria']

        # Gjett nedbørtype basert på scenarier
        nedbor_type = "ukjent"
        if pd.isna(scenarios):
            nedbor_type = "sannsynligvis snø"
        else:
            scenarios_str = str(scenarios)
            if 'rain_on_snow' in scenarios_str:
                nedbor_type = "regn"
            elif 'slush' in scenarios_str:
                nedbor_type = "sludd/regn"
            elif scenarios_str == 'freeze_thaw_cycle':
                nedbor_type = "snø/regn"

        print(f"\n  📍 {dato} ({criteria}):")
        print(f"    🌡️ {temp:.1f}°C, {precip:.1f}mm nedbør, {snow:.0f}cm snø")
        print(f"    🌧️ Sannsynlig type: {nedbor_type}")
        print(f"    📋 Scenarier: {scenarios}")

    # Konklusjon basert på analyse
    print("\n🎯 KONKLUSJONER:")
    print("=" * 15)

    print("1. TEMPERATUR-GRENSER:")
    print("   - Under -2°C: Sannsynligvis snø")
    print("   - -2°C til 0°C: Kan være både snø og regn (sjekk snømengde-endring)")
    print("   - 0°C til 2°C: Kan være regn, men også snø (sjekk snømengde-endring)")
    print("   - Over 2°C: Sannsynligvis regn")

    print("\n2. ANBEFALT LOGIKK FOR GLATTFØRE:")
    print("   - Bruk BÅDE temperatur OG snømengde-endring")
    print("   - Regn = temp > 0°C + nedbør + snømengde minkende")
    print("   - Snø = temp < 0°C + nedbør + snømengde økende")
    print("   - Grensesone = 0°C ± 1°C, sjekk snømengde-endring")

    return boundary_cases

def plot_temp_precip_analysis():
    """Lag visualisering av temperatur vs nedbør"""

    # Les data
    df = pd.read_csv("/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/maintenance_weather_data_20250810_1303.csv")

    # Filtrer episoder med nedbør
    df_precip = df[(df['precip_total'] > 0) & (df['temp_mean'].notna())].copy()

    # Lag scatter plot
    plt.figure(figsize=(12, 8))

    # Fargekoding basert på weather scenarios
    colors = []
    labels = []
    for idx, row in df_precip.iterrows():
        scenarios = str(row['weather_scenarios'])
        if 'rain_on_snow' in scenarios:
            colors.append('red')
            labels.append('Regn-situasjon')
        elif 'slush' in scenarios:
            colors.append('orange')
            labels.append('Sludd-situasjon')
        elif 'freeze_thaw' in scenarios:
            colors.append('blue')
            labels.append('Frysing/tining')
        else:
            colors.append('gray')
            labels.append('Ukjent')

    scatter = plt.scatter(df_precip['temp_mean'], df_precip['precip_total'],
                         c=colors, alpha=0.6, s=50)

    # Legg til vertikale linjer for viktige temperaturer
    plt.axvline(x=0, color='black', linestyle='--', alpha=0.5, label='0°C (frysegrense)')
    plt.axvline(x=2, color='green', linestyle='--', alpha=0.5, label='2°C (sikker regn-grense)')
    plt.axvline(x=-2, color='blue', linestyle='--', alpha=0.5, label='-2°C (sikker snø-grense)')

    plt.xlabel('Temperatur (°C)')
    plt.ylabel('Nedbør (mm)')
    plt.title('Temperatur vs Nedbør - Analyse av nedbørtype')
    plt.legend()
    plt.grid(True, alpha=0.3)

    # Lagre plot
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = f"/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/temperatur_nedbor_analyse_{timestamp}.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\n📊 Visualisering lagret: {output_file}")

    plt.show()

if __name__ == "__main__":
    boundary_cases = analyze_temp_snow_relationship()
    plot_temp_precip_analysis()
