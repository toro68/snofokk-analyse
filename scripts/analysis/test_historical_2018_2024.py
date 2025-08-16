#!/usr/bin/env python3
"""
Test finalkalibrerte grenseverdier på historiske data fra 2018-2024.
Konverterer historical_data.csv til riktig format og analyserer.
"""

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd


def calculate_wind_chill(temp, wind):
    """Beregn vindkjøling."""
    if pd.isna(temp) or pd.isna(wind):
        return np.nan
    if temp <= 10 and wind >= 1.34:
        return (13.12 + 0.6215 * temp - 11.37 * (wind * 3.6) ** 0.16 + 0.3965 * temp * (wind * 3.6) ** 0.16)
    return temp

def load_and_prepare_historical_data():
    """Last og forbered historiske data fra 2018-2024."""

    print("📊 LASTER HISTORISKE DATA FRA 2018-2024")
    print("=" * 60)

    # Last historiske data
    df = pd.read_csv('data/raw/historical_data.csv')
    print(f"Lastet {len(df)} observasjoner")

    # Konverter timestamp og filtrer
    df['referenceTime'] = pd.to_datetime(df['timestamp'])
    df = df.dropna(subset=['referenceTime'])

    print(f"Periode: {df['referenceTime'].min()} til {df['referenceTime'].max()}")

    # Konverter snødybde fra cm til meter (hvis nødvendig)
    if 'surface_snow_thickness' in df.columns:
        # Sjekk om verdiene ser ut til å være i cm (typisk > 10 for snødybde)
        sample_values = df['surface_snow_thickness'].dropna().head(100)
        if sample_values.mean() > 5:  # Trolig i cm
            print("Konverterer snødybde fra cm til meter")
            df['surface_snow_thickness'] = df['surface_snow_thickness'] / 100

    # Sett manglende verdier til 0 for snødybde hvis det gir mening
    df['surface_snow_thickness'] = df['surface_snow_thickness'].fillna(0)

    print("\nData-kvalitet etter forberedelse:")
    print(f"  Lufttemperatur: {df['air_temperature'].notna().sum()} av {len(df)} ({df['air_temperature'].notna().sum()/len(df)*100:.1f}%)")
    print(f"  Vindstyrke: {df['wind_speed'].notna().sum()} av {len(df)} ({df['wind_speed'].notna().sum()/len(df)*100:.1f}%)")
    print(f"  Snødybde: {df['surface_snow_thickness'].notna().sum()} av {len(df)} ({df['surface_snow_thickness'].notna().sum()/len(df)*100:.1f}%)")

    return df

def test_calibrated_thresholds_historical(df):
    """Test kalibrerte grenseverdier på historiske data."""

    print("\n🎯 TESTING FINALKALIBRERTE GRENSEVERDIER PÅ HISTORISKE DATA")
    print("=" * 60)

    # Beregn vindkjøling
    df['wind_chill'] = df.apply(lambda row: calculate_wind_chill(
        row['air_temperature'], row['wind_speed']), axis=1)

    # Finalkalibrerte grenseverdier
    WIND_CHILL_CRITICAL = -15.0  # °C
    WIND_SPEED_CRITICAL = 10.0   # m/s
    SNOW_DEPTH_MIN = 0.2         # m (20cm)

    print("Grenseverdier:")
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

    # Filtrer ut sommermåneder (mai-oktober) for mer realistisk analyse
    df['month'] = df['referenceTime'].dt.month
    winter_months = df['month'].isin([11, 12, 1, 2, 3, 4])  # Nov-Apr
    winter_df = df[winter_months].copy()
    winter_conditions = conditions[winter_months]

    # Analyser resultater
    filtered_df = winter_df[winter_conditions].copy()

    print("\n📊 RESULTATER (kun vintermåneder nov-apr):")
    print(f"🔵 Totale vinterobservasjoner: {len(winter_df)}")
    print(f"🔴 Observasjoner med høy risiko: {len(filtered_df)}")
    print(f"📈 Prosentandel: {len(filtered_df)/len(winter_df)*100:.2f}%")

    if len(filtered_df) > 0:
        filtered_df['date'] = filtered_df['referenceTime'].dt.date
        filtered_df['year'] = filtered_df['referenceTime'].dt.year

        # Årsvis analyse
        yearly_analysis = {}

        print("\n📅 ÅRSVIS ANALYSE:")
        print("-" * 50)

        for year in sorted(filtered_df['year'].unique()):
            year_data = filtered_df[filtered_df['year'] == year]
            unique_days = year_data['date'].nunique()
            yearly_analysis[year] = unique_days

            print(f"{year}: {unique_days} dager med varsling")

            # Vis de mest ekstreme dagene for dette året
            if unique_days > 0:
                daily_summary = year_data.groupby('date').agg({
                    'wind_chill': 'min',
                    'wind_speed': 'max',
                    'air_temperature': 'min'
                }).sort_values('wind_chill').head(3)

                print("    Mest ekstreme dager:")
                for date, row in daily_summary.iterrows():
                    print(f"      {date}: Vindkjøling {row['wind_chill']:.1f}°C, Vind {row['wind_speed']:.1f}m/s")

        # Samlet analyse over alle år
        total_days = filtered_df['date'].nunique()
        years_analyzed = len(yearly_analysis)
        avg_days_per_year = total_days / years_analyzed if years_analyzed > 0 else 0

        print(f"\n📊 SAMMENDRAG OVER ALLE ÅR ({min(yearly_analysis.keys())}-{max(yearly_analysis.keys())}):")
        print(f"• Totalt dager med varsling: {total_days}")
        print(f"• Antall sesonger analysert: {years_analyzed}")
        print(f"• Gjennomsnitt per sesong: {avg_days_per_year:.1f} dager")

        # Månedlig fordeling
        monthly_analysis = filtered_df.groupby(filtered_df['referenceTime'].dt.month)['date'].nunique()
        month_names = {11: 'Nov', 12: 'Des', 1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr'}

        print("\n📈 MÅNEDLIG FORDELING (totalt over alle år):")
        for month, days in monthly_analysis.items():
            if month in month_names:
                print(f"  {month_names[month]}: {days} dager")

        # Lagre resultater
        results = {
            "analysis_period": f"{df['referenceTime'].min().isoformat()} - {df['referenceTime'].max().isoformat()}",
            "total_winter_observations": len(winter_df),
            "high_risk_observations": len(filtered_df),
            "percentage": round(len(filtered_df)/len(winter_df)*100, 2),
            "yearly_analysis": {str(k): v for k, v in yearly_analysis.items()},
            "total_alert_days": int(total_days),
            "average_days_per_season": round(avg_days_per_year, 1),
            "monthly_distribution": {month_names.get(k, str(k)): int(v) for k, v in monthly_analysis.items()},
            "thresholds_used": {
                "wind_chill_critical": WIND_CHILL_CRITICAL,
                "wind_speed_critical": WIND_SPEED_CRITICAL,
                "snow_depth_minimum_cm": SNOW_DEPTH_MIN * 100
            },
            "validation_timestamp": datetime.now().isoformat()
        }

        output_file = 'data/analyzed/historical_calibration_2018_2024.json'
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Detaljerte resultater lagret i: {output_file}")

        # Vurdering av kalibrering
        if avg_days_per_year <= 10:
            print(f"\n✅ KALIBRERING VELLYKKET: {avg_days_per_year:.1f} dager/år ≤ 10 dager målsetting")
        else:
            print(f"\n⚠️ KALIBRERING BEGRENSER: {avg_days_per_year:.1f} dager/år > 10 dager målsetting")
            print("    Kan trenge enda strengere grenseverdier")

    else:
        print("\n❌ Ingen observasjoner oppfyller de finalkalibrerte kriteriene")

def main():
    # Last og forbered data
    df = load_and_prepare_historical_data()

    # Test kalibrerte grenseverdier
    test_calibrated_thresholds_historical(df)

if __name__ == "__main__":
    main()
