#!/usr/bin/env python3
"""
Detaljert sammenligning av snøfokk-deteksjon:
Original ML-kriterier vs Utvidede kriterier med vindtransport
"""

import pandas as pd


def detailed_comparison_analysis():
    """Sammenlign deteksjonsmetoder detaljert"""

    print("=== DETALJERT SAMMENLIGNING: ML vs ML+VINDTRANSPORT ===\n")

    # Last data og beregn kriterier
    df = pd.read_csv('data/raw/historical_data.csv')
    season_df = df[(df['timestamp'] >= '2023-11-01') & (df['timestamp'] <= '2024-04-30')].copy()

    # Beregn vindkjøling
    def calc_wind_chill(temp, wind):
        if temp <= 10 and wind >= 1.34:
            return (13.12 + 0.6215 * temp - 11.37 * (wind * 3.6) ** 0.16 +
                   0.3965 * temp * (wind * 3.6) ** 0.16)
        return temp

    season_df['wind_chill'] = season_df.apply(lambda row: calc_wind_chill(row['air_temperature'], row['wind_speed']), axis=1)

    # Snødybde-endringer
    season_df['snow_change_1h'] = season_df['surface_snow_thickness'].diff()
    season_df['snow_change_1h_mm'] = season_df['snow_change_1h'] * 1000
    season_df['significant_snow_change'] = abs(season_df['snow_change_1h_mm']) > 5.0

    # Original ML-kriterier
    ml_criteria = (
        (season_df['air_temperature'] < -5.0) &
        (season_df['wind_speed'] > 5.0) &
        (season_df['surface_snow_thickness'] > 0.26) &
        (season_df['wind_chill'] < -15.0)
    )

    # Utvidede kriterier (ML + vindtransport)
    enhanced_criteria = ml_criteria & season_df['significant_snow_change']

    # Finn unike dager
    ml_dates = set(season_df[ml_criteria]['timestamp'].str[:10])
    enhanced_dates = set(season_df[enhanced_criteria]['timestamp'].str[:10])

    print("📊 SAMMENLIGNING 2023-2024 SESONG:")
    print(f"- Original ML-kriterier: {len(ml_dates)} dager")
    print(f"- ML + Vindtransport: {len(enhanced_dates)} dager")
    print(f"- Reduksjon: {len(ml_dates) - len(enhanced_dates)} dager ({(1-len(enhanced_dates)/len(ml_dates))*100:.1f}%)")

    # Hvilke dager forsvant?
    removed_dates = ml_dates - enhanced_dates
    print("\n❌ DAGER SOM FALT BORT (mangler vindtransport-tegn):")
    for date in sorted(removed_dates):
        day_data = season_df[(season_df['timestamp'].str[:10] == date) & ml_criteria]
        if len(day_data) > 0:
            avg_temp = day_data['air_temperature'].mean()
            avg_wind = day_data['wind_speed'].mean()
            avg_chill = day_data['wind_chill'].mean()
            max_change = day_data['snow_change_1h_mm'].abs().max()
            print(f"  📅 {date}: Temp {avg_temp:.1f}°C, Vind {avg_wind:.1f}m/s, Vindkjøling {avg_chill:.1f}°C, Maks snøendring {max_change:.1f}mm")

    # Hvilke dager ble beholdt?
    print("\n✅ DAGER SOM OPPFYLLER ALLE KRITERIER (med vindtransport):")
    for date in sorted(enhanced_dates):
        day_data = season_df[(season_df['timestamp'].str[:10] == date) & enhanced_criteria]
        if len(day_data) > 0:
            avg_temp = day_data['air_temperature'].mean()
            avg_wind = day_data['wind_speed'].mean()
            avg_chill = day_data['wind_chill'].mean()
            avg_change = day_data['snow_change_1h_mm'].mean()
            max_change = day_data['snow_change_1h_mm'].abs().max()
            print(f"  📅 {date}: Temp {avg_temp:.1f}°C, Vind {avg_wind:.1f}m/s, Vindkjøling {avg_chill:.1f}°C, "
                  f"Snøendring {avg_change:.1f}mm (maks {max_change:.1f}mm)")

    # Analyse av snøendringer per dag
    print("\n📈 SNØENDRING-ANALYSE:")
    ml_days_detailed = []
    for date in sorted(ml_dates):
        day_data = season_df[season_df['timestamp'].str[:10] == date]
        if len(day_data) > 0:
            max_abs_change = day_data['snow_change_1h_mm'].abs().max()
            has_significant = (day_data['snow_change_1h_mm'].abs() > 5.0).any()
            ml_days_detailed.append({
                'date': date,
                'max_change': max_abs_change,
                'has_significant': has_significant,
                'in_enhanced': date in enhanced_dates
            })

    print("\nDager uten betydelig snøendring (>5mm):")
    no_change_days = [d for d in ml_days_detailed if not d['has_significant']]
    for day in no_change_days:
        print(f"  📅 {day['date']}: Maks endring {day['max_change']:.1f}mm")

    return {
        'ml_days': len(ml_dates),
        'enhanced_days': len(enhanced_dates),
        'reduction': len(ml_dates) - len(enhanced_dates),
        'reduction_percent': (1-len(enhanced_dates)/len(ml_dates))*100 if len(ml_dates) > 0 else 0,
        'removed_dates': removed_dates,
        'enhanced_dates': enhanced_dates
    }

def test_different_thresholds():
    """Test ulike terskler for snøendring"""

    print("\n🔬 SENSITIVITETS-ANALYSE: Ulike snøendring-terskler")

    df = pd.read_csv('data/raw/historical_data.csv')
    season_df = df[(df['timestamp'] >= '2023-11-01') & (df['timestamp'] <= '2024-04-30')].copy()

    # Beregn grunndata
    season_df['wind_chill'] = season_df.apply(
        lambda row: (13.12 + 0.6215 * row['air_temperature'] -
                    11.37 * (row['wind_speed'] * 3.6) ** 0.16 +
                    0.3965 * row['air_temperature'] * (row['wind_speed'] * 3.6) ** 0.16)
        if row['air_temperature'] <= 10 and row['wind_speed'] >= 1.34
        else row['air_temperature'], axis=1)

    season_df['snow_change_1h_mm'] = season_df['surface_snow_thickness'].diff() * 1000

    # Base ML-kriterier
    base_ml = (
        (season_df['air_temperature'] < -5.0) &
        (season_df['wind_speed'] > 5.0) &
        (season_df['surface_snow_thickness'] > 0.26) &
        (season_df['wind_chill'] < -15.0)
    )

    # Test ulike terskler
    thresholds = [1.0, 2.0, 5.0, 10.0, 15.0, 20.0]

    base_days = len(set(season_df[base_ml]['timestamp'].str[:10]))
    print(f"Original ML (uten snøendring): {base_days} dager")

    for threshold in thresholds:
        significant_change = abs(season_df['snow_change_1h_mm']) > threshold
        combined = base_ml & significant_change
        enhanced_days = len(set(season_df[combined]['timestamp'].str[:10]))
        reduction = base_days - enhanced_days
        reduction_pct = (reduction / base_days * 100) if base_days > 0 else 0

        print(f"ML + snøendring >{threshold:.0f}mm: {enhanced_days} dager (-{reduction}, -{reduction_pct:.1f}%)")

if __name__ == "__main__":
    detailed_comparison_analysis()
    test_different_thresholds()
