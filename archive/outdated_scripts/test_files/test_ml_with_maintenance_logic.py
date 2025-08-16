"""
Forbedret test for ML-kriterier basert på faktiske brøytingslogikk fra MD-filene.
Tar hensyn til:
- Tunbrøyting fredager (ukentlig snøakkumulering)
- Veiinspeksjoner (ikke værbetingede)
- Slush-skraping vs. vanlig brøyting
- Rutinemessige kjøringer
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

# Legg til src-mappen til Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from live_conditions_app import LiveConditionsChecker
    print("✅ Importerte Live Conditions moduler")
except ImportError as e:
    print(f"❌ Feil ved import: {e}")
    sys.exit(1)


def load_maintenance_data():
    """Last vedlikeholdsdata fra CSV"""
    try:
        df = pd.read_csv('data/analyzed/Rapport 2022-2025.csv')
        print(f"✅ Lastet {len(df)} vedlikeholdsepisoder fra CSV")
        return df
    except Exception as e:
        print(f"❌ Kunne ikke laste CSV: {e}")
        return None


def classify_maintenance_purpose(row):
    """Klassifiser vedlikeholdsformål basert på MD-filenes logikk"""
    
    # Konverter dato til datetime hvis nødvendig
    date_str = row.get('Dato', '')
    try:
        date = pd.to_datetime(date_str)
        is_friday = date.weekday() == 4  # Fredag = 4
    except:
        is_friday = False
    
    # Varighet og distanse (proxy for inspeksjon vs. faktisk arbeid)
    duration_hours = float(row.get('Varighet_timer', 0))
    distance_km = float(row.get('Distanse_km', 0))
    
    # Temperatur og nedbør
    temp = float(row.get('Temperatur', 999))  # 999 = mangler data
    precip = float(row.get('Nedbør_mm', 0))
    
    # Klassifiser basert på MD-filenes kategorier
    
    # 1. VEIINSPEKSJON (korte kjøringer, lav distanse)
    if duration_hours < 1.0 and distance_km < 10:
        return {
            'category': 'road_inspection',
            'weather_dependent': False,
            'expected_risk': 'any',
            'reason': 'Kort varighet og lav distanse indikerer inspeksjon'
        }
    
    # 2. TUNBRØYTING FREDAGER
    if is_friday and duration_hours > 2.0:
        return {
            'category': 'weekly_heavy_plowing',  
            'weather_dependent': False,  # Planlagt, ikke værreaktiv
            'expected_risk': 'low_to_medium',
            'reason': 'Ukentlig tunbrøyting på fredag'
        }
    
    # 3. SLUSH-SKRAPING (mildvær, mye nedbør)
    if temp != 999 and 0 <= temp <= 3 and precip > 20:
        return {
            'category': 'slush_scraping',
            'weather_dependent': True,
            'expected_risk': 'high',
            'reason': 'Mildvær med mye nedbør - slush-forhold'
        }
    
    # 4. REGN-PÅ-SNØ STRØING (kalt regn)
    if temp != 999 and -1 <= temp <= 1 and precip > 5:
        return {
            'category': 'rain_on_snow_salting',
            'weather_dependent': True,
            'expected_risk': 'high',
            'reason': 'Regn på snø - kritisk for glatte veier'
        }
    
    # 5. FRYSING/TINING SYKLER
    # (Trenger temperaturtidsserie for å detektere dette)
    
    # 6. STANDARD BRØYTING (fallback)
    if duration_hours > 1.0:
        return {
            'category': 'standard_plowing',
            'weather_dependent': True,
            'expected_risk': 'medium',
            'reason': 'Standard brøyting basert på værforhold'
        }
    
    # 7. UNØDVENDIG BEHANDLING (få, korte episoder uten værgrunn)
    return {
        'category': 'unnecessary_or_unknown',
        'weather_dependent': False,
        'expected_risk': 'low',
        'reason': 'Ukjent formål eller unødvendig behandling'
    }


def test_ml_against_maintenance_logic():
    """Test ML-kriterier mot realistisk vedlikeholdslogikk"""
    
    print("\n🧪 TESTING ML-KRITERIER MOT FAKTISK BRØYTINGSLOGIKK")
    print("=" * 60)
    
    # Last data
    maintenance_df = load_maintenance_data()
    if maintenance_df is None:
        return
    
    checker = LiveConditionsChecker()
    results = []
    
    # Statistikk
    categories = {}
    weather_dependent_episodes = 0
    ml_correct_predictions = 0
    total_weather_tests = 0
    
    print(f\"\\n📊 Analyserer {len(maintenance_df)} vedlikeholdsepisoder...\")
    
    for idx, row in maintenance_df.iterrows():
        if idx >= 20:  # Begrens for testing
            break
            
        print(f\"\\n--- Episode {idx+1}: {row.get('Dato', 'Ukjent dato')} ---\")
        
        # Klassifiser episode
        classification = classify_maintenance_purpose(row)
        category = classification['category']
        weather_dependent = classification['weather_dependent']
        expected_risk = classification['expected_risk']
        reason = classification['reason']
        
        print(f\"📋 Kategori: {category}\")
        print(f\"📝 Grunn: {reason}\")
        print(f\"🌤️  Væravhengig: {'Ja' if weather_dependent else 'Nei'}\")
        
        # Oppdater statistikk
        categories[category] = categories.get(category, 0) + 1
        
        # Test kun væravhengige episoder
        if weather_dependent:
            weather_dependent_episodes += 1
            total_weather_tests += 1
            
            # Simuler værdata (siden API kanskje ikke har historiske data)
            temp = float(row.get('Temperatur', 0))
            precip = float(row.get('Nedbør_mm', 0))
            
            # Lag minimal værdata for testing
            if temp != 999:  # Har temperaturdata
                test_df = pd.DataFrame({
                    'referenceTime': [pd.Timestamp.now()],
                    'air_temperature': [temp],
                    'wind_speed': [5.0],  # Standard vind
                    'surface_snow_thickness': [20.0 if temp < 0 else 5.0],
                    'hourly_precipitation_1h': [precip],
                    'surface_temperature': [temp - 1],
                    'dew_point_temperature': [temp - 3],
                    'relative_humidity': [80],
                    'wind_from_direction': [270]
                })
                
                try:
                    # Test snøfokk-risiko
                    snowdrift_result = checker.analyze_snowdrift_risk(test_df)
                    slippery_result = checker.analyze_slippery_road_risk(test_df)
                    
                    snowdrift_risk = snowdrift_result['risk_level']
                    slippery_risk = slippery_result['risk_level']
                    
                    print(f\"🌨️  Snøfokk ML: {snowdrift_risk}\")
                    print(f\"🧊 Glatt føre ML: {slippery_risk}\")
                    
                    # Evaluer om ML stemmer med forventet risiko
                    ml_prediction_correct = False
                    
                    if category == 'slush_scraping':
                        # Forventer høy slippery/slush-risiko
                        if slippery_risk in ['high', 'medium']:
                            ml_prediction_correct = True
                    elif category == 'rain_on_snow_salting':
                        # Forventer høy slippery-risiko
                        if slippery_risk in ['high', 'medium']:
                            ml_prediction_correct = True
                    elif category == 'standard_plowing':
                        # Forventer snøfokk eller slippery risiko
                        if snowdrift_risk in ['high', 'medium'] or slippery_risk in ['medium', 'high']:
                            ml_prediction_correct = True
                    
                    if ml_prediction_correct:
                        ml_correct_predictions += 1
                        print(f\"✅ ML-prediksjon KORREKT for {category}\")
                    else:
                        print(f\"❌ ML-prediksjon FEIL for {category}\")
                    
                    results.append({
                        'episode': idx + 1,
                        'date': row.get('Dato', ''),
                        'category': category,
                        'weather_dependent': weather_dependent,
                        'temperature': temp,
                        'precipitation': precip,
                        'snowdrift_risk': snowdrift_risk,
                        'slippery_risk': slippery_risk,
                        'ml_correct': ml_prediction_correct,
                        'reason': reason
                    })
                    
                except Exception as e:
                    print(f\"⚠️  Feil ved ML-analyse: {e}\")
            else:
                print(f\"⚠️  Ingen temperaturdata - kan ikke teste ML\")
        else:
            print(f\"⏭️  Hopper over - ikke væravhengig\")
    
    # Sammendrag
    print(f\"\\n📈 SAMMENDRAG AV TESTRESULTATER\")
    print(f\"=\" * 50)
    
    print(f\"\\n📊 EPISODEKATEGORIER:\")
    for category, count in categories.items():
        print(f\"  {category}: {count} episoder\")
    
    print(f\"\\n🌤️  VÆRAVHENGIGE EPISODER: {weather_dependent_episodes}/{len(maintenance_df)} ({weather_dependent_episodes/len(maintenance_df)*100:.1f}%)\")
    
    if total_weather_tests > 0:
        ml_accuracy = ml_correct_predictions / total_weather_tests * 100
        print(f\"🤖 ML-NØYAKTIGHET: {ml_correct_predictions}/{total_weather_tests} ({ml_accuracy:.1f}%)\")
        
        if ml_accuracy >= 75:
            print(f\"✅ UTMERKET ML-ytelse!\")
        elif ml_accuracy >= 50:
            print(f\"⚠️  AKSEPTABEL ML-ytelse - kan forbedres\")
        else:
            print(f\"❌ DÅRLIG ML-ytelse - trenger betydelig forbedring\")
    else:
        print(f\"⚠️  Ingen væravhengige episoder testet\")
    
    print(f\"\\n💡 VIKTIGE INNSIKTER:\")
    print(f\"1. Mange brøytinger er IKKE væravhengige (fredagsrutiner, inspeksjoner)\")
    print(f\"2. ML bør kun evalueres mot væravhengige episoder\")
    print(f\"3. Kategorisering av vedlikeholdsformål er kritisk for riktig evaluering\")
    
    # Lagre resultater
    output_file = f\"data/analyzed/ml_validation_realistic_{datetime.now().strftime('%Y%m%d_%H%M')}.json\"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'summary': {
                'total_episodes': len(maintenance_df),
                'weather_dependent': weather_dependent_episodes,
                'ml_tests': total_weather_tests,
                'ml_correct': ml_correct_predictions,
                'ml_accuracy': ml_correct_predictions / total_weather_tests * 100 if total_weather_tests > 0 else 0,
                'categories': categories
            },
            'detailed_results': results
        }, f, indent=2, ensure_ascii=False)
    
    print(f\"\\n💾 Resultater lagret: {output_file}\")


def main():
    \"\"\"Kjør realistisk testing av ML-kriterier\"\"\"
    print(\"🚀 REALISTISK ML-VALIDERING MOT FAKTISK BRØYTINGSLOGIKK\")
    print(\"=\" * 65)
    print(\"Mål: Teste ML kun mot væravhengige episoder, ikke rutiner/inspeksjoner\")
    print()
    
    test_ml_against_maintenance_logic()
    
    print(f\"\\n✅ TESTING FULLFØRT\")
    print(\"=\" * 50)
    print(\"\\n🎯 KONKLUSJON:\")
    print(\"Ved å skille væravhengige fra rutine-episoder får vi\")
    print(\"en mye mer realistisk evaluering av ML-kriteriene!\")


if __name__ == \"__main__\":
    main()
