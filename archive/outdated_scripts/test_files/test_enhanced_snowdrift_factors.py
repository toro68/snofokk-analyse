#!/usr/bin/env python3
"""
Test av utvidede snøfokk-faktorer:
1. Nysnø/løs snø tilgjengelighet (fersk nedbør)
2. Snødybde-endringer fra vind (uten tilsvarende nedbør)
"""


import pandas as pd


def analyze_snow_conditions(df):
    """Analyser snøforhold for realistisk snøfokk-deteksjon"""

    print("=== ANALYSE AV SNØFOKK-BETINGELSER ===\n")

    # 1. Analyser nedbørsdata (nysnø tilgjengelighet)
    print("📊 NEDBØRSANALYSE (Nysnø/løs snø):")

    precip_col = 'sum(precipitation_amount PT1H)'
    if precip_col in df.columns:
        df['precip'] = df[precip_col].fillna(0)

        # Definer "fersk snø" - nedbør siste 6-24 timer
        df['precip_6h'] = df['precip'].rolling(window=6, min_periods=1).sum()
        df['precip_24h'] = df['precip'].rolling(window=24, min_periods=1).sum()

        print(f"- Gjennomsnittlig nedbør/time: {df['precip'].mean():.2f}mm")
        print(f"- Timer med nedbør > 0: {(df['precip'] > 0).sum()}")
        print(f"- Timer med nedbør > 1mm: {(df['precip'] > 1).sum()}")
        print(f"- Maks nedbør/time: {df['precip'].max():.1f}mm")

        # Identifiser perioder med fersk snø (siste 24h)
        fresh_snow_threshold = 2.0  # mm siste 24h
        df['has_fresh_snow'] = df['precip_24h'] > fresh_snow_threshold
        print(f"- Timer med fersk snø (>{fresh_snow_threshold}mm/24h): {df['has_fresh_snow'].sum()}")
    else:
        print("- ADVARSEL: Ingen nedbørsdata funnet!")
        df['has_fresh_snow'] = True  # Anta tilgjengelig hvis ikke data

    # 2. Analyser snødybde-endringer
    print("\n🌨️ SNØDYBDE-ENDRINGER (Vindtransport):")

    if 'surface_snow_thickness' in df.columns:
        # Beregn endringer over ulike tidsperioder
        df['snow_change_1h'] = df['surface_snow_thickness'].diff()
        df['snow_change_3h'] = df['surface_snow_thickness'].diff(periods=3)
        df['snow_change_6h'] = df['surface_snow_thickness'].diff(periods=6)

        # Konverter til mm for lettere forståelse
        df['snow_change_1h_mm'] = df['snow_change_1h'] * 1000
        df['snow_change_3h_mm'] = df['snow_change_3h'] * 1000
        df['snow_change_6h_mm'] = df['snow_change_6h'] * 1000

        print(f"- Gjennomsnittlig endring/time: {df['snow_change_1h_mm'].mean():.1f}mm")
        print(f"- Standardavvik endring/time: {df['snow_change_1h_mm'].std():.1f}mm")
        print(f"- Maks økning/time: {df['snow_change_1h_mm'].max():.1f}mm")
        print(f"- Maks reduksjon/time: {df['snow_change_1h_mm'].min():.1f}mm")

        # Definer betydelige endringer (potensielt vindtransport)
        significant_change_threshold = 5.0  # mm/time
        df['significant_snow_change'] = abs(df['snow_change_1h_mm']) > significant_change_threshold
        print(f"- Timer med betydelig endring (>{significant_change_threshold}mm): {df['significant_snow_change'].sum()}")

        # Sjekk endringer uten tilsvarende nedbør (indikerer vindtransport)
        if 'precip' in df.columns:
            # Endring uten nedbør = vindtransport
            df['wind_transport'] = (abs(df['snow_change_1h_mm']) > significant_change_threshold) & (df['precip'] < 1.0)
            print(f"- Timer med vindtransport (endring uten nedbør): {df['wind_transport'].sum()}")
        else:
            df['wind_transport'] = df['significant_snow_change']
    else:
        print("- ADVARSEL: Ingen snødybde-data funnet!")
        df['wind_transport'] = False

    return df

def test_enhanced_snowdrift_detection(df):
    """Test utvidet snøfokk-deteksjon med nye faktorer"""

    print("\n⚡ UTVIDET SNØFOKK-DETEKSJON TEST:")
    print(f"Total datapunkter: {len(df)}")

    # Grunnleggende værkriterier (fra tidligere ML-optimalisering)
    base_criteria = (
        (df['air_temperature'] < -5.0) &  # ML-optimalisert
        (df['wind_speed'] > 5.0) &        # ML-optimalisert
        (df['surface_snow_thickness'] > 0.26)  # ML-optimalisert (26cm)
    )

    # Beregn vindkjøling
    df['wind_chill'] = df.apply(lambda row: calculate_wind_chill(row['air_temperature'], row['wind_speed']), axis=1)
    wind_chill_criteria = df['wind_chill'] < -15.0  # ML-optimalisert

    print("\n📊 KRITERIER-ANALYSE:")
    print(f"- Grunnleggende værkriterier: {base_criteria.sum()} timer")
    print(f"- Vindkjøling < -15°C: {wind_chill_criteria.sum()} timer")

    if 'has_fresh_snow' in df.columns:
        print(f"- Med fersk snø tilgjengelig: {df['has_fresh_snow'].sum()} timer")

    if 'wind_transport' in df.columns:
        print(f"- Med vindtransport-tegn: {df['wind_transport'].sum()} timer")

    # Kombinasjoner av kriterier
    print("\n🎯 KOMBINERTE DETEKSJONER:")

    # Original ML-kriterier
    original_detection = base_criteria & wind_chill_criteria
    print(f"1. Original ML-kriterier: {original_detection.sum()} timer")

    # Med fersk snø-krav
    if 'has_fresh_snow' in df.columns:
        with_fresh_snow = original_detection & df['has_fresh_snow']
        print(f"2. ML + fersk snø krav: {with_fresh_snow.sum()} timer")

    # Med vindtransport-krav
    if 'wind_transport' in df.columns:
        with_wind_transport = original_detection & df['wind_transport']
        print(f"3. ML + vindtransport krav: {with_wind_transport.sum()} timer")

    # Alle kriterier kombinert
    if 'has_fresh_snow' in df.columns and 'wind_transport' in df.columns:
        all_criteria = original_detection & df['has_fresh_snow'] & df['wind_transport']
        print(f"4. Alle kriterier (ML + fersk snø + vindtransport): {all_criteria.sum()} timer")

        # Analyser disse dagene detaljert
        if all_criteria.sum() > 0:
            enhanced_days = df[all_criteria].copy()
            unique_dates = enhanced_days['timestamp'].str[:10].unique()
            print(f"\n✅ IDENTIFISERTE SNØFOKK-DAGER (alle kriterier): {len(unique_dates)} dager")

            for date in sorted(unique_dates)[:10]:  # Vis første 10
                day_data = enhanced_days[enhanced_days['timestamp'].str.startswith(date)]
                if len(day_data) > 0:
                    avg_temp = day_data['air_temperature'].mean()
                    avg_wind = day_data['wind_speed'].mean()
                    avg_chill = day_data['wind_chill'].mean()
                    snow_change = day_data['snow_change_1h_mm'].mean()
                    precip_24h = day_data['precip_24h'].mean() if 'precip_24h' in day_data.columns else 0

                    print(f"📅 {date}: Temp {avg_temp:.1f}°C, Vind {avg_wind:.1f}m/s, "
                          f"Vindkjøling {avg_chill:.1f}°C, Snøendring {snow_change:.1f}mm/h, "
                          f"Nedbør 24h {precip_24h:.1f}mm")

    return df

def calculate_wind_chill(temperature, wind_speed):
    """Beregn vindkjøling"""
    if temperature <= 10 and wind_speed >= 1.34:
        return (13.12 + 0.6215 * temperature -
               11.37 * (wind_speed * 3.6) ** 0.16 +
               0.3965 * temperature * (wind_speed * 3.6) ** 0.16)
    return temperature

def test_seasonal_analysis(df):
    """Analyser sesongdata med utvidede kriterier"""

    print("\n🗓️ SESONG-ANALYSE (2023-2024):")

    # Filter for vintersesong
    season_df = df[
        ((df['timestamp'] >= '2023-11-01') & (df['timestamp'] <= '2024-04-30'))
    ].copy()

    print(f"Sesongdata: {len(season_df)} timer (Nov 2023 - Apr 2024)")

    # Kjør analyse på sesongdata
    season_df = analyze_snow_conditions(season_df)
    season_df = test_enhanced_snowdrift_detection(season_df)

    return season_df

def main():
    """Hovedfunksjon for testing"""

    print("=== TEST AV UTVIDEDE SNØFOKK-FAKTORER ===")
    print("Faktorer: Nysnø/løs snø + Snødybde-endringer fra vind\n")

    # Last historiske data
    try:
        df = pd.read_csv('data/raw/historical_data.csv')
        print(f"✅ Data lastet: {len(df)} rader, {len(df.columns)} kolonner")
        print(f"Tidsperiode: {df['timestamp'].min()} til {df['timestamp'].max()}")

        # Vis tilgjengelige kolonner
        print("\n📋 Tilgjengelige kolonner:")
        for col in sorted(df.columns):
            print(f"  - {col}")

        # Kjør analyse
        df = analyze_snow_conditions(df)
        df = test_enhanced_snowdrift_detection(df)

        # Sesonganalyse
        season_df = test_seasonal_analysis(df)

        print("\n✅ ANALYSE FULLFØRT!")
        print("Se resultater ovenfor for hvordan nysnø og vindtransport")
        print("påvirker antall detekterte snøfokk-hendelser.")

    except FileNotFoundError:
        print("❌ FEIL: Finner ikke data/raw/historical_data.csv")
    except Exception as e:
        print(f"❌ FEIL ved analyse: {e}")

if __name__ == "__main__":
    main()
