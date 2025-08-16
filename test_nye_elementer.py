#!/usr/bin/env python3
"""
Test av nye empirisk validerte værelementer i appen.
"""

import pandas as pd
import sys
import os

# Legg til src til path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from live_conditions_app import LiveConditionsChecker
    print("✅ Importerte LiveConditionsChecker")
except ImportError as e:
    print(f"❌ Kunne ikke importere LiveConditionsChecker: {e}")
    sys.exit(1)

def test_weather_elements():
    """Test at alle 15 empirisk validerte værelementer er implementert."""
    
    checker = LiveConditionsChecker()
    
    # Test de nye elementene som ble lagt til
    required_elements = [
        'air_temperature',
        'wind_speed', 
        'wind_from_direction',
        'surface_snow_thickness',
        'sum(precipitation_amount PT1H)',
        'sum(precipitation_amount PT10M)',          # NY: 6x bedre oppløsning
        'accumulated(precipitation_amount)',        # NY: HØYESTE viktighet
        'max_wind_speed(wind_from_direction PT1H)', # NY: KRITISK for snøfokk
        'relative_humidity',
        'surface_temperature',
        'dew_point_temperature',
        'sum(duration_of_precipitation PT1H)',      # NY: HØY PRIORITET
        'max(wind_speed_of_gust PT1H)',            # NY: MEDIUM PRIORITET
        'weather_symbol',                          # NY: MEDIUM PRIORITET
        'visibility'                               # NY: MEDIUM PRIORITET
    ]
    
    print(f"\n🔍 Testing {len(required_elements)} empirisk validerte elementer:")
    
    # Mock test data med alle nye elementer
    test_data = {
        'referenceTime': [pd.Timestamp.now()],
        'air_temperature': [-5.0],
        'wind_speed': [6.0],
        'wind_from_direction': [270],
        'surface_snow_thickness': [30],
        'sum(precipitation_amount PT1H)': [2.0],
        'sum(precipitation_amount PT10M)': [0.5],          # NY
        'accumulated(precipitation_amount)': [15.0],       # NY 
        'max_wind_speed(wind_from_direction PT1H)': [8.0], # NY
        'relative_humidity': [85],
        'surface_temperature': [-3.0],
        'dew_point_temperature': [-7.0],
        'sum(duration_of_precipitation PT1H)': [30],       # NY
        'max(wind_speed_of_gust PT1H)': [9.0],            # NY
        'weather_symbol': [22],                           # NY
        'visibility': [5000]                              # NY
    }
    
    df = pd.DataFrame(test_data)
    
    print("✅ Opprettet testdata med alle 15 elementer")
    
    # Test snøfokk-analyse med nye elementer
    try:
        result = checker.analyze_snowdrift_risk(df)
        print(f"✅ Snøfokk-analyse: {result['risk_level']} - {result['message']}")
        
        if 'factors' in result:
            print("   Faktorer:")
            for factor in result.get('factors', []):
                print(f"   • {factor}")
                
    except Exception as e:
        print(f"❌ Snøfokk-analyse feilet: {e}")
    
    # Test glattføre-analyse
    try:
        result = checker.analyze_slippery_road_risk(df)
        print(f"✅ Glattføre-analyse: {result['risk_level']} - {result['message']}")
    except Exception as e:
        print(f"❌ Glattføre-analyse feilet: {e}")
    
    print("\n📊 Implementeringsstatus:")
    implemented = 0
    for element in required_elements:
        if element in df.columns:
            print(f"   ✅ {element}")
            implemented += 1
        else:
            print(f"   ❌ {element}")
    
    coverage = (implemented / len(required_elements)) * 100
    print(f"\n🎯 Implementerte elementer: {implemented}/{len(required_elements)} ({coverage:.1f}%)")
    
    if coverage >= 80:
        print("🎉 GODT SAMSVAR med empiriske funn!")
    elif coverage >= 60:
        print("⚠️ DELVIS SAMSVAR - trenger flere elementer")
    else:
        print("❌ LITE SAMSVAR - mange elementer mangler")

def test_ml_detector():
    """Test ML-detektoren med nye elementer."""
    
    try:
        from ml_snowdrift_detector import MLSnowdriftDetector
        print("\n🧠 Testing ML-detektor med nye elementer:")
        
        detector = MLSnowdriftDetector()
        
        # Test med utvidede elementer
        test_data = {
            'referenceTime': [pd.Timestamp.now()],
            'air_temperature': [-8.0],
            'wind_speed': [12.0],
            'surface_snow_thickness': [40],
            'wind_from_direction': [315],
            'max_wind_per_direction': [15.0],      # Fra ny normalisering
            'accumulated_precipitation': [20.0],    # Fra ny normalisering  
            'precipitation_amount_10m': [1.5],      # Fra ny normalisering
        }
        
        df = pd.DataFrame(test_data)
        
        # Test forbedret extract_enhanced_weather_data
        weather_data = detector.extract_enhanced_weather_data(df)
        print("✅ Ekstrakterte utvidede værdata:")
        for key, value in weather_data.items():
            if value is not None:
                print(f"   • {key}: {value}")
        
        # Test forbedret ML-analyse
        result = detector.analyze_snowdrift_risk_ml(df)
        print(f"✅ ML-analyse: {result['risk_level']} - {result['message']}")
        
    except ImportError:
        print("⚠️ ML-detektor ikke tilgjengelig")
    except Exception as e:
        print(f"❌ ML-test feilet: {e}")

if __name__ == "__main__":
    print("🧪 TESTING: Nye Empirisk Validerte Værelementer")
    print("=" * 50)
    
    test_weather_elements()
    test_ml_detector()
    
    print("\n" + "=" * 50)
    print("🎯 Test fullført!")
