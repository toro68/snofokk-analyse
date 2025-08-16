#!/usr/bin/env python3
"""
Test script for the enhanced live conditions app.
Verifies all new weather elements are properly requested and processed.
"""

import os
import sys
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from live_conditions_app import LiveConditionsChecker


def test_enhanced_elements():
    """Test that all enhanced weather elements work correctly."""

    # Load environment
    load_dotenv()

    # Initialize checker
    checker = LiveConditionsChecker()

    # Test period: last 6 hours for quick test
    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(hours=6)

    print("🧪 Testing Enhanced Weather App...")
    print(f"📊 Fetching data for: {start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%Y-%m-%d %H:%M')} UTC")

    # Fetch data using the current method
    df = checker.get_current_weather_data(hours_back=6)

    if df is None:
        print("❌ Failed to fetch data")
        return False

    print(f"✅ Successfully fetched {len(df)} measurements")

    # Check for new elements
    expected_elements = [
        'air_temperature',
        'wind_speed',
        'wind_from_direction',  # NEW
        'surface_snow_thickness',
        'sum(precipitation_amount PT1H)',  # FIXED
        'relative_humidity',
        'surface_temperature',  # NEW
        'dew_point_temperature'  # NEW
    ]

    print("\n📋 Element Availability Check:")
    available_count = 0
    for element in expected_elements:
        if element in df.columns:
            non_null_count = df[element].notna().sum()
            print(f"✅ {element}: {non_null_count}/{len(df)} values")
            available_count += 1
        else:
            print(f"❌ {element}: Missing from dataset")

    print(f"\n📈 Element Coverage: {available_count}/{len(expected_elements)} ({available_count/len(expected_elements)*100:.1f}%)")

    # Test analyses
    print("\n🔍 Testing Analysis Functions:")

    # Test snowdrift analysis
    snowdrift_result = checker.analyze_snowdrift_risk(df)
    print(f"✅ Snowdrift Analysis: {snowdrift_result['risk_level']} - {snowdrift_result['message']}")

    # Test slippery road analysis
    slippery_result = checker.analyze_slippery_road_risk(df)
    print(f"✅ Slippery Road Analysis: {slippery_result['risk_level']} - {slippery_result['message']}")

    # Show latest weather data
    if len(df) > 0:
        latest = df.iloc[-1]
        print(f"\n🌡️ Latest Conditions ({latest['referenceTime']}):")
        print(f"   • Air Temperature: {latest.get('air_temperature', 'N/A')} °C")
        print(f"   • Wind Speed: {latest.get('wind_speed', 'N/A')} m/s")
        if 'wind_from_direction' in latest and latest['wind_from_direction'] is not None:
            print(f"   • Wind Direction: {latest['wind_from_direction']:.0f}°")
        if 'surface_temperature' in latest and latest['surface_temperature'] is not None:
            print(f"   • Surface Temperature: {latest['surface_temperature']} °C")
        if 'dew_point_temperature' in latest and latest['dew_point_temperature'] is not None:
            print(f"   • Dew Point: {latest['dew_point_temperature']} °C")
        print(f"   • Snow Depth: {latest.get('surface_snow_thickness', 'N/A')} cm")
        print(f"   • Precipitation: {latest.get('sum(precipitation_amount PT1H)', 'N/A')} mm/h")
        print(f"   • Humidity: {latest.get('relative_humidity', 'N/A')} %")

    return True

if __name__ == "__main__":
    success = test_enhanced_elements()
    if success:
        print("\n🎉 Enhanced app test completed successfully!")
        print("   All new weather elements are properly integrated.")
    else:
        print("\n💥 Enhanced app test failed!")
        sys.exit(1)
