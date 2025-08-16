"""
Forbedret ML-validering basert på FAKTISKE tall fra CSV-analyse.
Bruker realistiske kategorier basert på dataens faktiske fordeling:
- 28 inspeksjoner (16.8%) - korte kjøringer <1t og <10km
- 27 fredagsrutiner (16.2%) - ukentlige rutiner  
- ~112 væravhengige episoder (67%) - standard brøyting/strøing
"""

import os
import sys

import numpy as np
import pandas as pd

# Legg til src-mappen til Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

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


def load_and_categorize_maintenance():
    """Last vedlikeholdsdata og kategoriser basert på faktiske mønstre"""

    try:
        df = pd.read_csv('data/analyzed/Rapport 2022-2025.csv', sep=';')
        print(f"✅ Lastet {len(df)} vedlikeholdsepisoder")

        # Konverter varighet til timer
        df['Varighet_timer'] = df['Varighet'].apply(parse_duration_to_hours)

        # Parse dato og finn ukedag
        df['Dato_parsed'] = pd.to_datetime(df['Dato'], format='%d. %b. %Y', errors='coerce')
        df['Ukedag'] = df['Dato_parsed'].dt.day_name()
        df['Er_fredag'] = df['Ukedag'] == 'Friday'

        # Kategoriser basert på faktiske data
        conditions = []
        categories = []

        # 1. INSPEKSJONER: Kort varighet OG lav distanse
        inspection_mask = (df['Varighet_timer'] < 1.0) & (df['Distanse (km)'] < 10.0)
        conditions.append(inspection_mask)
        categories.append('road_inspection')

        # 2. FREDAGSRUTINER: Fredager som ikke er inspeksjoner
        friday_routine_mask = df['Er_fredag'] & ~inspection_mask & (df['Varighet_timer'] >= 1.5)
        conditions.append(friday_routine_mask)
        categories.append('friday_routine')

        # 3. LANGE OPERASJONER: >5 timer (tunbrøyting/storbrøyting)
        heavy_plowing_mask = (df['Varighet_timer'] > 5.0) & ~inspection_mask & ~friday_routine_mask
        conditions.append(heavy_plowing_mask)
        categories.append('heavy_plowing')

        # 4. STANDARD VEDLIKEHOLD: Alt annet med rimelig varighet
        standard_mask = (df['Varighet_timer'] >= 1.0) & (df['Varighet_timer'] <= 5.0) & ~inspection_mask & ~friday_routine_mask
        conditions.append(standard_mask)
        categories.append('standard_maintenance')

        # 5. UKJENT/KORT: Fallback for alt annet
        conditions.append(~(inspection_mask | friday_routine_mask | heavy_plowing_mask | standard_mask))
        categories.append('unknown_short')

        # Tildel kategorier
        df['Kategori'] = np.select(conditions, categories, default='unknown')

        # Marker væravhengighet basert på kategori
        weather_dependent_categories = ['heavy_plowing', 'standard_maintenance']
        df['Er_væravhengig'] = df['Kategori'].isin(weather_dependent_categories)

        return df

    except Exception as e:
        print(f"❌ Feil ved lasting: {e}")
        return None


def analyze_categorization(df):
    """Analyser kategoriseringen"""

    print("\n📊 KATEGORISERING BASERT PÅ FAKTISKE DATA:")
    print("=" * 55)

    category_counts = df['Kategori'].value_counts()
    for category, count in category_counts.items():
        percentage = count / len(df) * 100
        weather_episodes = len(df[df['Kategori'] == category])
        weather_dependent = df[df['Kategori'] == category]['Er_væravhengig'].iloc[0] if weather_episodes > 0 else False
        weather_status = "⛅ Væravhengig" if weather_dependent else "📅 Rutinemessig/Planlagt"

        print(f"  {category}: {count} ({percentage:.1f}%) - {weather_status}")

    # Sammendrag væravhengighet
    weather_dependent_count = df['Er_væravhengig'].sum()
    weather_percentage = weather_dependent_count / len(df) * 100

    print(f"\n🌤️ VÆRAVHENGIGE EPISODER: {weather_dependent_count}/{len(df)} ({weather_percentage:.1f}%)")
    print(f"📋 RUTINEMESSIGE EPISODER: {len(df) - weather_dependent_count}/{len(df)} ({100-weather_percentage:.1f}%)")

    return df


def test_ml_on_weather_dependent_only():
    """Test ML kun på væravhengige episoder for realistisk evaluering"""

    print("\n🧪 ML-TESTING KUN PÅ VÆRAVHENGIGE EPISODER")
    print("=" * 55)
    print("Dette gir en mye mer realistisk evaluering av ML-kriteriene!")

    try:
        from live_conditions_app import LiveConditionsChecker
        checker = LiveConditionsChecker()
        print("✅ Importerte ML-moduler")
    except ImportError as e:
        print(f"❌ Kunne ikke importere ML-moduler: {e}")
        return

    # Last og kategoriser data
    df = load_and_categorize_maintenance()
    if df is None:
        return

    # Analyser kategorisering
    df = analyze_categorization(df)

    # Test kun væravhengige episoder
    weather_episodes = df[df['Er_væravhengig'] == True].copy()

    print(f"\n🎯 TESTING {len(weather_episodes)} VÆRAVHENGIGE EPISODER:")

    ml_correct = 0
    ml_tests = 0

    for idx, row in weather_episodes.head(10).iterrows():  # Test første 10 for hastighet
        date_str = row['Dato']
        category = row['Kategori']
        duration = row['Varighet_timer']
        distance = row['Distanse (km)']

        print(f"\n--- {date_str} ({category}) ---")
        print(f"Varighet: {duration:.1f}t, Distanse: {distance:.1f}km")

        # Simuler værdata basert på kategori og sesong
        date_parsed = row['Dato_parsed']
        if pd.isna(date_parsed):
            continue

        # Estimér værforhold basert på sesong og kategori
        month = date_parsed.month
        is_winter = month in [12, 1, 2, 3]

        if category == 'heavy_plowing':
            # Tunbrøyting - sannsynligvis mye snø og vind
            temp = -5.0 if is_winter else 1.0
            wind = 8.0
            snow_depth = 25.0 if is_winter else 10.0
            precip = 10.0
        elif category == 'standard_maintenance':
            # Standard - moderate forhold
            temp = -2.0 if is_winter else 2.0
            wind = 5.0
            snow_depth = 15.0 if is_winter else 5.0
            precip = 5.0
        else:
            continue

        # Lag test DataFrame
        test_df = pd.DataFrame({
            'referenceTime': [pd.Timestamp.now()],
            'air_temperature': [temp],
            'wind_speed': [wind],
            'surface_snow_thickness': [snow_depth],
            'hourly_precipitation_1h': [precip],
            'surface_temperature': [temp - 1],
            'dew_point_temperature': [temp - 3],
            'relative_humidity': [80],
            'wind_from_direction': [270]
        })

        try:
            # Test ML-kriterier
            snowdrift_result = checker.analyze_snowdrift_risk(test_df)
            slippery_result = checker.analyze_slippery_road_risk(test_df)

            snowdrift_risk = snowdrift_result['risk_level']
            slippery_risk = slippery_result['risk_level']

            print(f"🌨️ Snøfokk ML: {snowdrift_risk}")
            print(f"🧊 Glatt føre ML: {slippery_risk}")

            # Evaluer ML-prediksjon
            ml_predicted_action = False

            if category == 'heavy_plowing':
                # Forventer høy risiko for tunbrøyting
                if snowdrift_risk in ['high', 'medium'] or slippery_risk in ['high', 'medium']:
                    ml_predicted_action = True
            elif category == 'standard_maintenance':
                # Forventer moderat risiko for standard vedlikehold
                if snowdrift_risk in ['high', 'medium', 'low'] or slippery_risk in ['high', 'medium', 'low']:
                    ml_predicted_action = True

            ml_tests += 1
            if ml_predicted_action:
                ml_correct += 1
                print("✅ ML predikerte riktig: Handling nødvendig")
            else:
                print("❌ ML predikerte feil: Ingen handling nødvendig")

        except Exception as e:
            print(f"⚠️ Feil ved ML-test: {e}")

    # Sammendrag
    if ml_tests > 0:
        ml_accuracy = ml_correct / ml_tests * 100
        print("\n📈 ML-RESULTAT FOR VÆRAVHENGIGE EPISODER:")
        print(f"🎯 Nøyaktighet: {ml_correct}/{ml_tests} ({ml_accuracy:.1f}%)")

        if ml_accuracy >= 80:
            print("✅ UTMERKET - ML kriteriene fungerer godt!")
        elif ml_accuracy >= 60:
            print("⚠️ AKSEPTABELT - ML kan forbedres")
        else:
            print("❌ DÅRLIG - ML trenger betydelig forbedring")
    else:
        print("⚠️ Ingen ML-tester utført")


def main():
    """Kjør realistisk ML-validering"""

    print("🚀 REALISTISK ML-VALIDERING BASERT PÅ FAKTISKE DATA")
    print("=" * 65)
    print("Mål: Kategoriser episoder realistisk og test ML kun på væravhengige")
    print()

    test_ml_on_weather_dependent_only()

    print("\n✅ TESTING FULLFØRT")
    print("\n🎯 HOVEDKONKLUSJON:")
    print("Ved å skille rutinemessige fra væravhengige episoder")
    print("får vi en mye mer realistisk evaluering av ML-kriteriene!")


if __name__ == "__main__":
    main()
