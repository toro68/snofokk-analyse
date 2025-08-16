"""
Test for å validere kategoriseringen i MD-filene mot faktiske data fra CSV.
Sjekker om statistikken stemmer med virkeligheten.
"""

import json
from datetime import datetime

import pandas as pd


def parse_duration_to_hours(duration_str):
    """Konverter varighet fra format 'H:MM:SS' til desimaltimer"""
    try:
        if pd.isna(duration_str) or duration_str == '':
            return 0.0

        # Split på : for å få timer, minutter, sekunder
        parts = str(duration_str).split(':')
        if len(parts) != 3:
            return 0.0

        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])

        # Konverter til desimaltimer
        total_hours = hours + minutes/60.0 + seconds/3600.0
        return total_hours

    except (ValueError, IndexError):
        return 0.0

def load_and_analyze_maintenance_data():
    """Last og analyser vedlikeholdsdata for å validere MD-kategorisering"""

    print("🔍 VALIDERING AV MD-FILENES KATEGORISERING")
    print("=" * 55)

    try:
        # Last CSV-data med korrekt separator
        df = pd.read_csv('data/analyzed/Rapport 2022-2025.csv', sep=';')
        print(f"✅ Lastet {len(df)} vedlikeholdsepisoder fra CSV")

        # Vis første rader for å forstå strukturen
        print("\n📊 DATASTRUKTUR:")
        print(f"Kolonner: {list(df.columns)}")
        print("\nFørste 3 rader:")
        for i in range(min(3, len(df))):
            row = df.iloc[i]
            print(f"  Rad {i+1}: {row.get('Dato', 'N/A')} - Varighet: {row.get('Varighet', 'N/A')} - Distanse: {row.get('Distanse (km)', 'N/A')}km")

        return df

    except Exception as e:
        print(f"❌ Feil ved lasting av CSV: {e}")
        return None


def analyze_actual_categories(df):
    """Analyser faktiske kategorier i dataene"""

    print("\n📈 FAKTISK FORDELING AV KATEGORIER I DATA:")
    print("-" * 50)

    # Konverter varighet fra timer:min:sek til desimaltimer
    if 'Varighet' in df.columns:
        df['Varighet_timer'] = df['Varighet'].apply(parse_duration_to_hours)
        duration_stats = df['Varighet_timer'].describe()
        print(f"Varighet (timer) - Min: {duration_stats['min']:.1f}, Median: {duration_stats['50%']:.1f}, Maks: {duration_stats['max']:.1f}")

    # Analyser distanse
    if 'Distanse (km)' in df.columns:
        distance_stats = df['Distanse (km)'].describe()
        print(f"Distanse (km) - Min: {distance_stats['min']:.1f}, Median: {distance_stats['50%']:.1f}, Maks: {distance_stats['max']:.1f}")

    # Analyser fredagsmønster
    if 'Dato' in df.columns:
        print("\n📅 FREDAGSMØNSTER:")
        df['Dato_parsed'] = pd.to_datetime(df['Dato'], format='%d. %b. %Y', errors='coerce')
        df['Ukedag'] = df['Dato_parsed'].dt.day_name()

        friday_episodes = df[df['Ukedag'] == 'Friday']
        friday_count = len(friday_episodes)
        friday_percentage = friday_count / len(df) * 100

        print(f"Fredagsepisoder: {friday_count}/{len(df)} ({friday_percentage:.1f}%)")

        # Sjekk varighet på fredager vs andre dager
        if 'Varighet_timer' in df.columns:
            friday_durations = friday_episodes['Varighet_timer'].dropna()
            other_durations = df[df['Ukedag'] != 'Friday']['Varighet_timer'].dropna()

            if len(friday_durations) > 0:
                avg_friday_duration = friday_durations.mean()
                print(f"Gjennomsnittlig varighet fredager: {avg_friday_duration:.1f} timer")

            if len(other_durations) > 0:
                avg_other_duration = other_durations.mean()
                print(f"Gjennomsnittlig varighet andre dager: {avg_other_duration:.1f} timer")

    # Analyser varighet og distanse (for å identifisere inspeksjoner)
    print("\n🔍 VARIGHET OG DISTANSE ANALYSE:")
    if 'Varighet_timer' in df.columns and 'Distanse (km)' in df.columns:
        duration_data = df['Varighet_timer'].dropna()
        distance_data = df['Distanse (km)'].dropna()

        print(f"Varighet - Median: {duration_data.median():.1f}t, Gjennomsnitt: {duration_data.mean():.1f}t")
        print(f"Distanse - Median: {distance_data.median():.1f}km, Gjennomsnitt: {distance_data.mean():.1f}km")

        # Finn potensielle inspeksjoner (kort varighet OG lav distanse)
        short_duration = df['Varighet_timer'] < 1.0
        low_distance = df['Distanse (km)'] < 10.0
        potential_inspections = df[short_duration & low_distance]

        inspection_count = len(potential_inspections)
        inspection_percentage = inspection_count / len(df) * 100

        print(f"Potensielle inspeksjoner (<1t og <10km): {inspection_count}/{len(df)} ({inspection_percentage:.1f}%)")


def compare_with_md_claims(df):
    """Sammenlign faktiske data med påstander i MD-filene"""

    print("\n🔍 SAMMENLIGNING MED MD-FILENES PÅSTANDER:")
    print("=" * 55)

    # MD-fil påstand: "77 episoder (46.4%) snow_plowing"
    total_episodes = len(df)
    expected_snow_plowing = int(total_episodes * 0.464)

    print("MD-fil påstand: 77 episoder (46.4%) snow_plowing")
    print(f"Faktisk total episoder: {total_episodes}")
    print(f"Forventet snow_plowing basert på prosent: {expected_snow_plowing}")

    # MD-fil påstand: "38 episoder: Fredager med >10mm snø siste uke"
    # Vi kan ikke sjekke snø siste uke, men kan sjekke fredager generelt
    if 'Ukedag' in df.columns:
        friday_count = len(df[df['Ukedag'] == 'Friday'])
    else:
        friday_count = 0
    print("\nMD-fil påstand: 38 episoder fredager med >10mm snø")
    print(f"Faktiske fredagsepisoder: {friday_count}")

    # MD-fil påstand: "6 episoder (3.6%) road_inspection"
    expected_inspections = int(total_episodes * 0.036)

    # Estimer inspeksjoner basert på varighet/distanse
    if 'Varighet_timer' in df.columns and 'Distanse_km' in df.columns:
        short_duration = df['Varighet_timer'] < 1.0
        low_distance = df['Distanse_km'] < 10.0
        estimated_inspections = len(df[short_duration & low_distance])

        print("\nMD-fil påstand: 6 episoder (3.6%) road_inspection")
        print(f"Forventet basert på prosent: {expected_inspections}")
        print(f"Estimert basert på varighet/distanse: {estimated_inspections}")

        if abs(estimated_inspections - expected_inspections) <= 2:
            print("✅ INSPEKSJONSESTIMATET STEMMER RIMELIG")
        else:
            print("❌ INSPEKSJONSESTIMATET STEMMER IKKE")

    # Sammendrag av validering
    print("\n📊 VALIDERINGSSAMMENDRAG:")
    validation_score = 0
    total_checks = 0

    # Sjekk total episoder (innenfor 10%)
    if 140 <= total_episodes <= 180:  # Ca 166 episoder fra MD
        print(f"✅ Total episoder rimelig ({total_episodes})")
        validation_score += 1
    else:
        print(f"❌ Total episoder uventet ({total_episodes})")
    total_checks += 1

    # Sjekk fredager (innenfor 50%)
    if 19 <= friday_count <= 57:  # 38 ± 50%
        print(f"✅ Fredagsepisoder rimelig ({friday_count})")
        validation_score += 1
    else:
        print(f"❌ Fredagsepisoder uventet ({friday_count})")
    total_checks += 1

    validation_percentage = validation_score / total_checks * 100
    print(f"\n🎯 VALIDERINGSRESULTAT: {validation_score}/{total_checks} ({validation_percentage:.0f}%)")

    if validation_percentage >= 75:
        print("✅ MD-KATEGORISERINGEN STEMMER GODT!")
    elif validation_percentage >= 50:
        print("⚠️  MD-KATEGORISERINGEN STEMMER DELVIS - trenger justering")
    else:
        print("❌ MD-KATEGORISERINGEN STEMMER IKKE - trenger stor revisjon")


def main():
    """Kjør validering av MD-kategorisering"""

    print("🧪 VALIDERING AV MD-FILENES KATEGORISERING MOT FAKTISKE DATA")
    print("=" * 70)
    print("Mål: Sjekk om statistikken i MD-filene stemmer med CSV-dataene")
    print()

    # Last data
    df = load_and_analyze_maintenance_data()
    if df is None:
        return

    # Analyser faktiske kategorier
    analyze_actual_categories(df)

    # Sammenlign med MD-påstander
    compare_with_md_claims(df)

    # Lagre resultat
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    output_file = f"data/analyzed/md_validation_{timestamp}.json"

    validation_results = {
        'timestamp': timestamp,
        'total_episodes': len(df),
        'validation_summary': 'Se konsollutskrift for detaljer',
        'data_columns': list(df.columns),
        'sample_data': df.head(3).to_dict('records') if len(df) > 0 else []
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(validation_results, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n💾 Valideringsresultater lagret: {output_file}")
    print("\n✅ VALIDERING FULLFØRT")


if __name__ == "__main__":
    main()
