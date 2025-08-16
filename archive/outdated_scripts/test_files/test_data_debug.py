#!/usr/bin/env python3
"""
Diagnostisk test for data-henting i live-appen
"""

import sys

sys.path.append('src')


from dotenv import load_dotenv

from live_conditions_app import LiveConditionsChecker

# Last miljøvariabler
load_dotenv()

def test_data_fetch():
    print("=== DIAGNOSTIC TEST FOR LIVE APP DATA ===")

    # Opprett checker
    checker = LiveConditionsChecker()
    print(f"Station ID: {checker.station_id}")
    print(f"API Key: {checker.frost_client_id[:10] if checker.frost_client_id else 'MISSING'}...")

    # Test data-henting
    print("\n1. Testing data fetch (24 hours)...")
    df = checker.get_current_weather_data(hours_back=24)

    if df is None:
        print("❌ ERROR: No data returned")
        return

    print(f"✅ Data fetched: {len(df)} rows")
    print(f"Columns: {list(df.columns)}")

    # Sjekk kritiske kolonner
    print("\n2. Checking critical columns...")
    critical_cols = ['air_temperature', 'wind_speed', 'surface_snow_thickness']
    for col in critical_cols:
        if col in df.columns:
            non_null = df[col].notna().sum()
            print(f"✅ {col}: {non_null}/{len(df)} valid values")
            if non_null > 0:
                print(f"   Range: {df[col].min():.2f} to {df[col].max():.2f}")
        else:
            print(f"❌ {col}: MISSING")

    # Sjekk tidsserien
    print("\n3. Checking time series...")
    if 'referenceTime' in df.columns:
        latest = df['referenceTime'].max()
        earliest = df['referenceTime'].min()
        print(f"Time range: {earliest} to {latest}")

        # Sjekk for sommersesong
        is_summer = checker.is_summer_season()
        print(f"Is summer season: {is_summer}")

    # Test ML-analyse
    print("\n4. Testing ML analysis...")
    if checker.use_ml:
        print("✅ ML detector available")
        try:
            result = checker.analyze_snowdrift_risk(df)
            print(f"ML analysis result: {result['risk_level']} - {result['message']}")
            if 'ml_details' in result:
                print(f"ML details available: {list(result['ml_details'].keys())}")
        except Exception as e:
            print(f"❌ ML analysis failed: {e}")
    else:
        print("❌ ML detector not available")

    # Test plotting data
    print("\n5. Testing plotting data...")
    try:
        # Test vindkjøling-beregning
        if 'air_temperature' in df.columns and 'wind_speed' in df.columns:
            temp_valid = df['air_temperature'].notna().sum()
            wind_valid = df['wind_speed'].notna().sum()
            print(f"Temp for plotting: {temp_valid} valid values")
            print(f"Wind for plotting: {wind_valid} valid values")

            if temp_valid > 0 and wind_valid > 0 and checker.use_ml:
                # Test vindkjøling-beregning
                test_temp = df['air_temperature'].dropna().iloc[0]
                test_wind = df['wind_speed'].dropna().iloc[0]
                wind_chill = checker.ml_detector.calculate_wind_chill(test_temp, test_wind)
                print(f"Wind chill calculation test: {test_temp}°C + {test_wind}m/s = {wind_chill:.1f}°C")
        else:
            print("❌ Missing temperature or wind data for plotting")
    except Exception as e:
        print(f"❌ Plotting test failed: {e}")

    print("\n=== TEST COMPLETE ===")
    return df

if __name__ == "__main__":
    df = test_data_fetch()

    # Vis første og siste rader
    if df is not None and len(df) > 0:
        print("\nFirst 3 rows:")
        print(df.head(3))
        print("\nLast 3 rows:")
        print(df.tail(3))
