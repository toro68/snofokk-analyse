#!/usr/bin/env python3
"""
Test de finalkalibrerte grenseverdiene mot historiske data.
Verifiserer at vi får 8 dager med varsling som forventet.
"""

import json
from datetime import datetime

import pandas as pd


def calculate_wind_chill(temp, wind):
    """Beregn vindkjøling."""
    if temp <= 10 and wind >= 1.34:
        return (13.12 + 0.6215 * temp - 11.37 * (wind * 3.6) ** 0.16 + 0.3965 * temp * (wind * 3.6) ** 0.16)
    return temp

def test_final_calibration():
    """Test finalkalibrerte grenseverdier."""

    print("🎯 TESTING FINALKALIBRERTE GRENSEVERDIER")
    print("=" * 60)

    # Last data
    cache_file = 'data/cache/weather_data_2023-11-01_2024-04-30.pkl'
    df = pd.read_pickle(cache_file)

    print(f"📊 Lastet {len(df)} værobservasjoner")
    print(f"📅 Periode: {df['referenceTime'].min()} til {df['referenceTime'].max()}")

    # Beregn vindkjøling
    df['wind_chill'] = df.apply(lambda row: calculate_wind_chill(
        row['air_temperature'], row['wind_speed']), axis=1)

    # Finalkalibrerte grenseverdier
    WIND_CHILL_CRITICAL = -15.0  # °C
    WIND_SPEED_CRITICAL = 10.0   # m/s
    SNOW_DEPTH_MIN = 0.2         # m (20cm)

    print("\n🎯 FINALKALIBRERTE GRENSEVERDIER:")
    print(f"• Vindkjøling < {WIND_CHILL_CRITICAL}°C")
    print(f"• Vindstyrke > {WIND_SPEED_CRITICAL} m/s")
    print(f"• Snødybde > {SNOW_DEPTH_MIN*100}cm")
    print("• ALLE kriterier må oppfylles")

    # Anvend finalkalibrerte regler
    conditions = (
        (df['wind_chill'] < WIND_CHILL_CRITICAL) &
        (df['wind_speed'] > WIND_SPEED_CRITICAL) &
        (df['surface_snow_thickness'] > SNOW_DEPTH_MIN)
    )

    # Analyser resultater
    filtered_df = df[conditions].copy()

    if len(filtered_df) > 0:
        filtered_df['date'] = pd.to_datetime(filtered_df['referenceTime']).dt.date
        days_with_alerts = filtered_df['date'].nunique()

        print("\n📊 RESULTATER:")
        print(f"🔴 Totale observasjoner med høy risiko: {len(filtered_df)}")
        print(f"📅 Unike dager med varsling: {days_with_alerts}")
        print(f"📈 Prosentandel av sesongen: {days_with_alerts/180*100:.1f}%")

        # Daglig sammendrag
        daily_summary = filtered_df.groupby('date').agg({
            'wind_chill': 'min',
            'wind_speed': 'max',
            'air_temperature': 'min',
            'surface_snow_thickness': 'max'
        }).sort_values('wind_chill')

        print(f"\n🗓️ DAGER MED VARSLING ({days_with_alerts} dager):")
        print("-" * 80)

        for i, (date, row) in enumerate(daily_summary.iterrows(), 1):
            print(f"{i:2d}. {date}: "
                  f"Vindkjøling {row['wind_chill']:5.1f}°C, "
                  f"Vind {row['wind_speed']:4.1f}m/s, "
                  f"Temp {row['air_temperature']:5.1f}°C, "
                  f"Snø {row['surface_snow_thickness']*100:4.0f}cm")

        # Lagre resultater
        results = {
            "calibration_summary": {
                "total_observations": len(df),
                "high_risk_observations": len(filtered_df),
                "days_with_alerts": int(days_with_alerts),
                "percentage_of_season": round(days_with_alerts/180*100, 1),
                "calibration_successful": days_with_alerts <= 10
            },
            "thresholds_used": {
                "wind_chill_critical": WIND_CHILL_CRITICAL,
                "wind_speed_critical": WIND_SPEED_CRITICAL,
                "snow_depth_minimum_cm": SNOW_DEPTH_MIN * 100
            },
            "alert_dates": [str(date) for date in daily_summary.index],
            "validation_timestamp": datetime.now().isoformat()
        }

        output_file = 'data/analyzed/final_calibration_validation.json'
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Resultater lagret i: {output_file}")

        if days_with_alerts <= 10:
            print(f"\n✅ KALIBRERING VELLYKKET: {days_with_alerts} dager ≤ 10 dager målsetting")
        else:
            print(f"\n❌ KALIBRERING IKKE OPTIMAL: {days_with_alerts} dager > 10 dager målsetting")

    else:
        print("\n❌ Ingen observasjoner oppfyller de finalkalibrerte kriteriene")

if __name__ == "__main__":
    test_final_calibration()
