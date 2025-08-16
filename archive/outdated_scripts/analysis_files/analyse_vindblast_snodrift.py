#!/usr/bin/env python3
"""
ANALYSE AV VINDBLÅST SNØ (SNOW DRIFT)
===================================

Analyserer hvordan vind påvirker snømengde-endringer, spesielt ved minusgrader.
Dette er kritisk for å skille regn fra snø rundt frysepunktet.

HYPOTESE: Sterk vind kan redusere snømengden selv når temperaturen er under null
og nedbøren kommer som snø (vindblåst snø/snow drift).
"""

from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd


def load_maintenance_data():
    """Last vedlikeholdsdata med værinfo"""
    try:
        # Prøv nyeste fil først
        df = pd.read_csv('data/analyzed/maintenance_weather_data_20250810_1138.csv')
        return df
    except FileNotFoundError:
        try:
            # Prøv fallback fil
            df = pd.read_csv('data/analyzed/enhanced_maintenance_analysis_20250810_1138.csv')
            return df
        except FileNotFoundError:
            print("❌ Finner ikke vedlikeholdsdata")
            return None

def analyze_wind_snow_relationship():
    """Analyser sammenhengen mellom vind og snømengde-endringer"""

    print("🌪️ ANALYSE AV VINDBLÅST SNØ (SNOW DRIFT)")
    print("=" * 50)

    df = load_maintenance_data()
    if df is None:
        return

    # Filtrer episoder med nedbør og komplette vinddata
    df_wind = df[
        (df['precip_total'] > 0.5) &
        (df['wind_max'].notna()) &
        (df['temp_mean'].notna()) &
        (df['snow_depth_cm'].notna())
    ].copy()

    # Beregn snømengde-endring (mangler i denne datafilen, bruk snow_depth_cm som proxy)
    df_wind['snow_depth_change'] = df_wind['snow_depth_cm'].diff().fillna(0)

    print(f"📊 Analyserer {len(df_wind)} episoder med nedbør og vinddata")

    # Kategoriser episoder
    df_wind['wind_category'] = pd.cut(df_wind['wind_max'],
                                     bins=[0, 5, 10, 15, 50],
                                     labels=['svak (0-5 m/s)', 'moderat (5-10 m/s)',
                                            'sterk (10-15 m/s)', 'meget_sterk (>15 m/s)'])

    # Kategoriser temperatur
    df_wind['temp_category'] = df_wind['temp_mean'].apply(lambda x:
        'kald (< -2°C)' if x < -2 else
        'rundt frysing (-2 til 0°C)' if x < 0 else
        'lett pluss (0 til 2°C)' if x < 2 else
        'varm (> 2°C)'
    )

    print("\n🌡️ TEMPERATUR vs VIND vs SNØMENGDE-ENDRING:")
    print("=" * 45)

    # Analyser per temperaturkategori
    for temp_cat in df_wind['temp_category'].unique():
        if pd.isna(temp_cat):
            continue

        temp_data = df_wind[df_wind['temp_category'] == temp_cat]
        print(f"\n🌡️ {temp_cat.upper()} ({len(temp_data)} episoder):")
        print("-" * 50)

        # Gruppér etter vindstyrke
        wind_analysis = temp_data.groupby('wind_category').agg({
            'snow_depth_change': ['mean', 'std', 'count'],
            'precip_total': 'mean',
            'temp_mean': 'mean',
            'wind_max': 'mean'
        }).round(1)

        print(wind_analysis)

        # Finn episoder med uventet snømengde-reduksjon ved kalde temperaturer
        if 'kald' in temp_cat or 'rundt frysing' in temp_cat:
            anomalies = temp_data[
                (temp_data['snow_depth_change'] < -5) &  # Betydelig snømengde-reduksjon
                (temp_data['precip_total'] > 1.0) &       # Med nedbør
                (temp_data['wind_max'] > 8)               # Og sterk vind
            ]

            if len(anomalies) > 0:
                print(f"\n⚠️  VINDBLÅST SNØ-KANDIDATER ({len(anomalies)} episoder):")
                for idx, row in anomalies.iterrows():
                    dato = row['maintenance_date']
                    temp = row['temp_mean']
                    precip = row['precip_total']
                    snow_change = row['snow_depth_change']
                    wind_max = row['wind_max']
                    scenarios = row.get('weather_scenarios', 'nan')

                    print(f"  📍 {dato}:")
                    print(f"    🌡️ {temp:.1f}°C, {precip:.1f}mm nedbør")
                    print(f"    ❄️ Snø-endring: {snow_change:.0f}cm")
                    print(f"    🌪️ Vind maks: {wind_max:.1f} m/s")
                    print(f"    📋 Scenarier: {scenarios}")

    # Spesialanalyse: Grenseområdet rundt frysing
    print("\n🎯 KRITISK ANALYSE: GRENSEOMRÅDET (-1°C til +1°C)")
    print("=" * 55)

    boundary_data = df_wind[
        (df_wind['temp_mean'] >= -1) &
        (df_wind['temp_mean'] <= 1) &
        (df_wind['precip_total'] > 2.0)
    ].copy()

    print(f"📊 {len(boundary_data)} episoder i grenseområdet med betydelig nedbør")

    # Analyser vindeffekt i grenseområdet
    for idx, row in boundary_data.iterrows():
        dato = row['maintenance_date']
        temp = row['temp_mean']
        precip = row['precip_total']
        snow_change = row['snow_depth_change']
        wind_max = row['wind_max']
        scenarios = row.get('weather_scenarios', 'nan')
        criteria = row.get('maintenance_criteria', '')

        # Klassifiser basert på snømengde-endring og vind
        if snow_change < -3 and wind_max > 10:
            classification = "🌪️ VINDBLÅST SNØ"
        elif snow_change < -3 and temp > 0:
            classification = "🌧️ SANNSYNLIG REGN"
        elif snow_change > 3:
            classification = "❄️ SNØ-AKKUMULERING"
        else:
            classification = "❓ USIKKER"

        print(f"\n  📍 {dato} ({criteria}):")
        print(f"    🌡️ {temp:.1f}°C, {precip:.1f}mm nedbør")
        print(f"    ❄️ Snø-endring: {snow_change:.0f}cm")
        print(f"    🌪️ Vind maks: {wind_max:.1f} m/s")
        print(f"    🔍 {classification}")
        print(f"    📋 Scenarier: {scenarios}")

    # Statistisk analyse av vindeffekt
    print("\n📊 STATISTISK ANALYSE AV VINDEFFEKT:")
    print("=" * 40)

    # Korrelasjon mellom vind og snømengde-endring per temperaturområde
    for temp_cat in ['kald (< -2°C)', 'rundt frysing (-2 til 0°C)', 'lett pluss (0 til 2°C)']:
        temp_subset = df_wind[df_wind['temp_category'] == temp_cat]
        if len(temp_subset) > 5:
            correlation = temp_subset['wind_max'].corr(temp_subset['snow_depth_change'])
            print(f"{temp_cat}: Korrelasjon vind vs snø-endring = {correlation:.3f}")

    # Vindterskler for snømengde-reduksjon
    print("\n🌪️ VINDTERSKLER FOR SNØMENGDE-REDUKSJON:")
    print("=" * 42)

    # Analyser når snømengden reduseres til tross for kalde temperaturer
    cold_episodes = df_wind[df_wind['temp_mean'] < 0]
    snow_reduction = cold_episodes[cold_episodes['snow_depth_change'] < -2]

    if len(snow_reduction) > 0:
        wind_thresholds = snow_reduction.groupby(
            pd.cut(snow_reduction['wind_max'], bins=[0, 5, 10, 15, 30])
        )['snow_depth_change'].agg(['count', 'mean']).round(1)

        print("Vindstyrke vs snømengde-reduksjon ved minusgrader:")
        print(wind_thresholds)

        # Anbefalt terskler
        median_wind_for_reduction = snow_reduction['wind_max'].median()
        print(f"\n💡 ANBEFALT VINDTERSKEL for snømengde-reduksjon: {median_wind_for_reduction:.1f} m/s")

    # Visualisering
    create_wind_snow_visualization(df_wind)

    return df_wind

def create_wind_snow_visualization(df_wind):
    """Lag visualiseringer av vind vs snømengde-endring"""

    fig, axes = plt.subplots(2, 2, figsize=(15, 12))

    # 1. Scatter plot: Vind vs snømengde-endring, farget etter temperatur
    scatter = axes[0,0].scatter(df_wind['wind_max'], df_wind['snow_depth_change'],
                               c=df_wind['temp_mean'], cmap='coolwarm', alpha=0.7)
    axes[0,0].set_xlabel('Vindstyrke (m/s)')
    axes[0,0].set_ylabel('Snømengde-endring (cm)')
    axes[0,0].set_title('Vind vs Snømengde-endring (farget etter temperatur)')
    axes[0,0].grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=axes[0,0], label='Temperatur (°C)')

    # 2. Box plot: Snømengde-endring per vindkategori
    df_wind.boxplot(column='snow_depth_change', by='wind_category', ax=axes[0,1])
    axes[0,1].set_title('Snømengde-endring per vindkategori')
    axes[0,1].set_xlabel('Vindkategori')
    axes[0,1].set_ylabel('Snømengde-endring (cm)')

    # 3. Histogram: Vindstyrke ved snømengde-reduksjon
    snow_reduction = df_wind[df_wind['snow_depth_change'] < -5]
    axes[1,0].hist(snow_reduction['wind_max'], bins=15, alpha=0.7, color='red',
                   label=f'Snømengde-reduksjon < -5cm (n={len(snow_reduction)})')
    axes[1,0].set_xlabel('Vindstyrke (m/s)')
    axes[1,0].set_ylabel('Antall episoder')
    axes[1,0].set_title('Vindstyrke ved betydelig snømengde-reduksjon')
    axes[1,0].legend()
    axes[1,0].grid(True, alpha=0.3)

    # 4. Temperatur vs vind, størrelse = snømengde-endring
    abs_snow_change = abs(df_wind['snow_depth_change'])
    scatter2 = axes[1,1].scatter(df_wind['temp_mean'], df_wind['wind_max'],
                                s=abs_snow_change*2, alpha=0.6,
                                c=df_wind['snow_depth_change'], cmap='RdBu_r')
    axes[1,1].set_xlabel('Temperatur (°C)')
    axes[1,1].set_ylabel('Vindstyrke (m/s)')
    axes[1,1].set_title('Temp vs Vind (størrelse = abs snøendring)')
    axes[1,1].grid(True, alpha=0.3)
    plt.colorbar(scatter2, ax=axes[1,1], label='Snømengde-endring (cm)')

    plt.tight_layout()

    # Lagre figur
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filepath = f"data/analyzed/vindblast_snodrift_analyse_{timestamp}.png"
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    print(f"\n📊 Visualisering lagret: {filepath}")

    plt.show()

def propose_updated_logic():
    """Foreslå oppdatert logikk som tar hensyn til vindblåst snø"""

    print("\n💡 FORESLÅTT OPPDATERT LOGIKK:")
    print("=" * 35)

    print("🌪️ VINDBLÅST SNØ-DETEKSJON:")
    print("   - Temp < 0°C + nedbør + snø-reduksjon + vind > 7 m/s")
    print("   - Spesielt kritisk i området -2°C til 0°C")
    print("   - Vindkast > 15 m/s øker sannsynlighet for vindblåst snø")

    print("\n🎯 FORBEDRET REGN/SNØ-KLASSIFISERING:")
    print("   1. Temp > 2°C: Regn (uavhengig av vind)")
    print("   2. Temp < -3°C + vind < 5 m/s: Snø")
    print("   3. Temp < -1°C + vind > 8 m/s + snø-reduksjon: Vindblåst snø")
    print("   4. -1°C < temp < 1°C: Krever både snø-endring OG vindanalyse")
    print("   5. Temp > 0°C + snø-reduksjon + vind < 5 m/s: Regn")

    print("\n⚠️  GLATTFØRE-RISIKO (kun ved regn):")
    print("   - Temp > 0°C + nedbør + snø-reduksjon + vind < 8 m/s = REGN")
    print("   - Temp < 0°C + nedbør + snø-reduksjon + vind > 8 m/s = VINDBLÅST SNØ (ikke glattføre)")
    print("   - Grenseområde (-1°C til +1°C): Bruk alle faktorer for beslutning")

if __name__ == "__main__":
    df_analysis = analyze_wind_snow_relationship()

    if df_analysis is not None:
        propose_updated_logic()

        print("\n✅ VINDBLÅST SNØ-ANALYSE FULLFØRT")
        print("   - Identifiserte vindeffekt på snømengde-endringer")
        print("   - Analyserte grenseområdet rundt frysing")
        print("   - Foreslått forbedret logikk for rain/snow-klassifisering")
        print("   - Tatt hensyn til snow drift ved vindsterke forhold")
