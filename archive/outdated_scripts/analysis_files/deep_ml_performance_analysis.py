"""
Dybdeanalyse av ML-værdata korrelasjoner for å identifisere 
styrker og svakheter i ML-kriteriene.
"""

from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd


def analyze_ml_performance():
    """Analyser ML-ytelse i detalj"""

    print("🔍 DYBDEANALYSE AV ML-YTELSE")
    print("=" * 40)

    # Last resultatene
    try:
        df = pd.read_csv('data/analyzed/ml_weather_correlation_analysis_20250811_2020.csv')
        print(f"✅ Lastet {len(df)} episoder med ML-resultater")
    except Exception as e:
        print(f"❌ Kunne ikke laste ML-resultater: {e}")
        return

    # Grunnleggende statistikk
    print("\n📊 GRUNNLEGGENDE FUNN:")

    # Temperaturfordeling
    temp_stats = df['temperatur'].describe()
    print(f"Temperatur: {temp_stats['min']:.1f}°C til {temp_stats['max']:.1f}°C, median {temp_stats['50%']:.1f}°C")

    # Vindfordeling
    vind_stats = df['vind'].describe()
    print(f"Vind: {vind_stats['min']:.1f} til {vind_stats['max']:.1f} m/s, median {vind_stats['50%']:.1f} m/s")

    # Snødybdefordeling
    snø_stats = df['snødybde'].describe()
    print(f"Snødybde: {snø_stats['min']:.1f} til {snø_stats['max']:.1f} cm, median {snø_stats['50%']:.1f} cm")

    # Nedbørfordeling
    nedbør_stats = df['nedbør'].describe()
    print(f"Nedbør: {nedbør_stats['min']:.1f} til {nedbør_stats['max']:.1f} mm, median {nedbør_stats['50%']:.1f} mm")

    # Analyser ML-ytelse per kategori
    print("\n🎯 ML-YTELSE PER KATEGORI:")

    kategorier = ['heavy_plowing', 'standard_maintenance', 'road_inspection', 'friday_routine']

    for kategori in kategorier:
        kategori_data = df[df['kategori'] == kategori]
        if len(kategori_data) == 0:
            continue

        print(f"\n--- {kategori.upper()} ({len(kategori_data)} episoder) ---")

        # Værforhold for denne kategorien
        print("Gjennomsnittlige værforhold:")
        print(f"  Temperatur: {kategori_data['temperatur'].mean():.1f}°C")
        print(f"  Vind: {kategori_data['vind'].mean():.1f} m/s")
        print(f"  Snødybde: {kategori_data['snødybde'].mean():.1f} cm")
        print(f"  Nedbør: {kategori_data['nedbør'].mean():.1f} mm")

        # ML-risikonivåer
        snøfokk_fordeling = kategori_data['snøfokk_risiko'].value_counts()
        glattføre_fordeling = kategori_data['glattføre_risiko'].value_counts()

        print("ML-prediksjoner:")
        print(f"  Snøfokk: {dict(snøfokk_fordeling)}")
        print(f"  Glattføre: {dict(glattføre_fordeling)}")

        # Evaluer om ML-prediksjonen er rimelig
        if kategori in ['heavy_plowing', 'standard_maintenance']:
            # Væravhengige - bør ha medium/high risiko
            høy_snøfokk = len(kategori_data[kategori_data['snøfokk_risiko'].isin(['medium', 'high'])])
            høy_glattføre = len(kategori_data[kategori_data['glattføre_risiko'].isin(['medium', 'high'])])

            snøfokk_andel = høy_snøfokk / len(kategori_data) * 100
            glattføre_andel = høy_glattføre / len(kategori_data) * 100

            print(f"  Høy snøfokk-risiko: {høy_snøfokk}/{len(kategori_data)} ({snøfokk_andel:.1f}%)")
            print(f"  Høy glattføre-risiko: {høy_glattføre}/{len(kategori_data)} ({glattføre_andel:.1f}%)")

            if snøfokk_andel >= 50 or glattføre_andel >= 50:
                print("  ✅ ML predikerer rimelig høy risiko")
            else:
                print("  ❌ ML predikerer for lav risiko")
        else:
            # Ikke-væravhengige - bør ha low risiko
            lav_snøfokk = len(kategori_data[kategori_data['snøfokk_risiko'] == 'low'])
            lav_glattføre = len(kategori_data[kategori_data['glattføre_risiko'] == 'low'])

            snøfokk_andel = lav_snøfokk / len(kategori_data) * 100
            glattføre_andel = lav_glattføre / len(kategori_data) * 100

            print(f"  Lav snøfokk-risiko: {lav_snøfokk}/{len(kategori_data)} ({snøfokk_andel:.1f}%)")
            print(f"  Lav glattføre-risiko: {lav_glattføre}/{len(kategori_data)} ({glattføre_andel:.1f}%)")

            if snøfokk_andel >= 70 and glattføre_andel >= 70:
                print("  ✅ ML predikerer rimelig lav risiko")
            else:
                print("  ⚠️ ML predikerer for høy risiko")

    # Identifiser problemer med ML-kriteriene
    print("\n🔍 IDENTIFISERTE PROBLEMER:")

    # Problem 1: Glattføre-risiko alltid lav
    høy_glattføre = len(df[df['glattføre_risiko'].isin(['medium', 'high'])])
    if høy_glattføre == 0:
        print("❌ PROBLEM: Glattføre-risiko er ALLTID 'low' - kriteriene er for strenge!")

    # Problem 2: Snøfokk-risiko sjelden høy
    høy_snøfokk = len(df[df['snøfokk_risiko'] == 'high'])
    snøfokk_prosent = høy_snøfokk / len(df) * 100
    if snøfokk_prosent < 10:
        print(f"⚠️ PROBLEM: Snøfokk 'high' risiko sjelden ({snøfokk_prosent:.1f}%) - kanskje for strenge kriterier?")

    # Problem 3: Væravhengige episoder med lav risiko
    væravhengige = df[df['er_væravhengig'] == True]
    lav_risiko_væravhengige = væravhengige[
        (væravhengige['snøfokk_risiko'] == 'low') &
        (væravhengige['glattføre_risiko'] == 'low')
    ]

    if len(lav_risiko_væravhengige) > len(væravhengige) * 0.3:
        prosent = len(lav_risiko_væravhengige) / len(væravhengige) * 100
        print(f"⚠️ PROBLEM: {prosent:.1f}% av væravhengige episoder har lav risiko - ML er for forsiktig!")

    # Forslag til forbedringer
    print("\n💡 FORSLAG TIL FORBEDRINGER:")

    if høy_glattføre == 0:
        print("1. GLATTFØRE: Senk tersklene for glattføre-risiko")
        print("   - Nåværende terskler er for strenge")
        print("   - Vurder å inkludere flere faktorer (fuktighet, temperaturgradienter)")

    if snøfokk_prosent < 10:
        print("2. SNØFOKK: Juster snøfokk-kriteriene")
        print("   - Vurder lavere vindterskler")
        print("   - Ta hensyn til snøkvalitet og temperatur")

    # Spesifikke forbedringsforslag basert på data
    print("3. KALIBRERING: Basert på faktiske værforhold")

    # Analyser værforhold for væravhengige episoder som får lav risiko
    if len(lav_risiko_væravhengige) > 0:
        print("   Væravhengige episoder med lav ML-risiko har:")
        print(f"   - Snitt temperatur: {lav_risiko_væravhengige['temperatur'].mean():.1f}°C")
        print(f"   - Snitt vind: {lav_risiko_væravhengige['vind'].mean():.1f} m/s")
        print(f"   - Snitt snødybde: {lav_risiko_væravhengige['snødybde'].mean():.1f} cm")
        print(f"   - Snitt nedbør: {lav_risiko_væravhengige['nedbør'].mean():.1f} mm")
        print("   → Disse forholdene BØR utløse høyere risiko!")


def create_visualization():
    """Lag visualiseringer av ML-ytelse"""

    try:
        df = pd.read_csv('data/analyzed/ml_weather_correlation_analysis_20250811_2020.csv')
    except Exception as e:
        print(f"❌ Kunne ikke lage visualisering: {e}")
        return

    plt.style.use('default')
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('ML-Ytelse Analyse: Brøyting vs Værdata', fontsize=16, fontweight='bold')

    # 1. Temperatur vs ML-risiko
    ax1 = axes[0, 0]
    for risiko in ['low', 'medium', 'high']:
        subset = df[df['snøfokk_risiko'] == risiko]
        if len(subset) > 0:
            ax1.scatter(subset['temperatur'], subset['vind'],
                       label=f'Snøfokk {risiko}', alpha=0.7)
    ax1.set_xlabel('Temperatur (°C)')
    ax1.set_ylabel('Vind (m/s)')
    ax1.set_title('Snøfokk-risiko vs Temperatur/Vind')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. Kategorier vs risiko
    ax2 = axes[0, 1]
    kategori_risiko = df.groupby(['kategori', 'snøfokk_risiko']).size().unstack(fill_value=0)
    kategori_risiko.plot(kind='bar', ax=ax2, stacked=True)
    ax2.set_title('Snøfokk-risiko per Kategori')
    ax2.set_xlabel('Kategori')
    ax2.set_ylabel('Antall episoder')
    ax2.tick_params(axis='x', rotation=45)

    # 3. Væravhengighet vs ytelse
    ax3 = axes[1, 0]
    væravhengig_data = df.groupby(['er_væravhengig', 'snøfokk_risiko']).size().unstack(fill_value=0)
    væravhengig_data.plot(kind='bar', ax=ax3)
    ax3.set_title('Snøfokk-risiko: Væravhengig vs Ikke-væravhengig')
    ax3.set_xlabel('Væravhengig')
    ax3.set_ylabel('Antall episoder')
    ax3.tick_params(axis='x', rotation=0)

    # 4. Værparametre fordeling
    ax4 = axes[1, 1]
    df_weather = df[['temperatur', 'vind', 'snødybde', 'nedbør']].copy()
    # Normaliser for sammenligning
    df_weather['temperatur_norm'] = (df_weather['temperatur'] + 10) / 30  # Skaler til 0-1
    df_weather['vind_norm'] = df_weather['vind'] / 15  # Skaler til 0-1
    df_weather['snødybde_norm'] = df_weather['snødybde'] / 100  # Skaler til 0-1
    df_weather['nedbør_norm'] = df_weather['nedbør'] / 20  # Skaler til 0-1

    ax4.boxplot([df_weather['temperatur_norm'], df_weather['vind_norm'],
                 df_weather['snødybde_norm'], df_weather['nedbør_norm']])
    ax4.set_xticklabels(['Temp', 'Vind', 'Snødybde', 'Nedbør'])
    ax4.set_title('Normaliserte Værparametre Fordeling')
    ax4.set_ylabel('Normalisert verdi (0-1)')
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()

    # Lagre plot
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    plot_file = f"data/graphs/ml_ytelse_analyse_{timestamp}.png"
    plt.savefig(plot_file, dpi=300, bbox_inches='tight')
    print(f"📊 Visualisering lagret: {plot_file}")
    plt.close()


def main():
    """Kjør dybdeanalyse av ML-ytelse"""

    print("🔍 DYBDEANALYSE AV ML-VÆRDATA KORRELASJONER")
    print("=" * 55)

    analyze_ml_performance()

    print("\n📊 Lager visualiseringer...")
    create_visualization()

    print("\n✅ DYBDEANALYSE FULLFØRT")
    print("\n🎯 SAMMENDRAG:")
    print("Analysen identifiserer spesifikke problemer og forbedringsmuligheter")
    print("for ML-kriteriene basert på faktiske brøytingsbeslutninger!")


if __name__ == "__main__":
    main()
