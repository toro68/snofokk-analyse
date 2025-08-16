#!/usr/bin/env python3
"""
BALANSERT GLATT VEI-ANALYSE
===========================

Finner den riktige balansen mellom realisme og faktiske forhold
"""

import pickle

import pandas as pd


def create_balanced_slippery_analysis():
    """Lag en balansert glatt vei-analyse."""

    print("🎯 BALANSERT GLATT VEI-ANALYSE")
    print("=" * 60)

    # Last data
    cache_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/cache/weather_data_2023-11-01_2024-04-30.pkl'

    with open(cache_file, 'rb') as f:
        df = pickle.load(f)

    print(f"📊 Totalt {len(df)} timer med data")

    # La oss utforske tilgjengelige data først
    print("\n📋 TILGJENGELIGE KOLONNER:")
    for col in df.columns:
        non_null = df[col].notna().sum()
        print(f"  • {col}: {non_null} av {len(df)} ({(non_null/len(df))*100:.1f}%)")

    # Basis kriterier - mer moderate
    critical_temp = (df['air_temperature'] >= -3) & (df['air_temperature'] <= 2)

    # Snøfall som beskyttelse (moderat terskel)
    PRECIP_COL = 'sum(precipitation_amount PT1H)'
    if PRECIP_COL in df.columns:
        snow_protection = df[PRECIP_COL] > 0.3  # Redusert fra 0.5mm/h
        total_precip = df[PRECIP_COL].notna().sum()
        snow_hours = snow_protection.sum()
        print(f"\n❄️ Snøfall-beskyttelse (>0.3mm/h): {snow_hours} timer ({(snow_hours/total_precip)*100:.1f}% av målinger)")
    else:
        snow_protection = pd.Series([False] * len(df))
        print("\n❄️ Ingen nedbørsdata tilgjengelig")

    # Nattetid/tidlig morgen (økt risiko)
    df['hour'] = df['referenceTime'].dt.hour
    high_risk_hours = (df['hour'] >= 22) | (df['hour'] <= 8)

    # Fuktighetskrav (der tilgjengelig)
    if 'relative_humidity' in df.columns:
        high_humidity = df['relative_humidity'] >= 80  # Redusert fra 85%
        humidity_available = df['relative_humidity'].notna()
        print(f"💧 Fuktighetsmålinger: {humidity_available.sum()} timer")
    else:
        high_humidity = pd.Series([True] * len(df))
        humidity_available = pd.Series([False] * len(df))
        print("💧 Ingen fuktighetsmålinger tilgjengelig")

    # Vindkrav (der tilgjengelig)
    if 'wind_speed' in df.columns:
        low_wind = df['wind_speed'] <= 4  # Økt fra 3 m/s
        wind_available = df['wind_speed'].notna()
        print(f"💨 Vindmålinger: {wind_available.sum()} timer")
    else:
        low_wind = pd.Series([True] * len(df))
        wind_available = pd.Series([False] * len(df))
        print("💨 Ingen vindmålinger tilgjengelig")

    # Fleksible kriterier basert på tilgjengelig data
    print("\n🎯 KRITERIER FOR GLATT VEI-RISIKO:")

    if humidity_available.any() and wind_available.any():
        # Full datasett
        risky_conditions = (
            critical_temp &
            high_humidity &
            low_wind &
            high_risk_hours &
            ~snow_protection &
            humidity_available &
            wind_available
        )
        print("✅ Bruker FULL analyse (temp + fuktighet + vind + tid - snøfall)")

    elif humidity_available.any():
        # Kun temperatur og fuktighet
        risky_conditions = (
            critical_temp &
            high_humidity &
            high_risk_hours &
            ~snow_protection &
            humidity_available
        )
        print("✅ Bruker REDUSERT analyse (temp + fuktighet + tid - snøfall)")

    else:
        # Kun temperatur og tid
        risky_conditions = (
            critical_temp &
            high_risk_hours &
            ~snow_protection
        )
        print("✅ Bruker MINIMAL analyse (temp + tid - snøfall)")

    risky_hours = risky_conditions.sum()
    print(f"🎯 Timer med risiko-forhold: {risky_hours} av {len(df)} ({(risky_hours/len(df))*100:.1f}%)")

    # Finn perioder med smartere gruppering
    print("\n🔧 GRUPPERING TIL PERIODER:")

    periods = []
    df_risky = df[risky_conditions].copy()

    if len(df_risky) == 0:
        print("❌ Ingen risiko-timer funnet!")
        return []

    # Grupper sammenhengende timer
    df_risky['time_diff'] = df_risky['referenceTime'].diff().dt.total_seconds() / 3600

    # Start ny periode hvis gap > 3 timer
    df_risky['new_period'] = (df_risky['time_diff'] > 3) | (df_risky['time_diff'].isna())
    df_risky['period_id'] = df_risky['new_period'].cumsum()

    # Analyser hver periode
    for period_id in df_risky['period_id'].unique():
        period_data = df_risky[df_risky['period_id'] == period_id]

        # Krav: Minst 2 timer (redusert fra 3)
        if len(period_data) >= 2:

            start_time = period_data['referenceTime'].iloc[0]
            end_time = period_data['referenceTime'].iloc[-1]
            duration_hours = len(period_data)

            # Temperaturstatistikk
            avg_temp = period_data['air_temperature'].mean()
            min_temp = period_data['air_temperature'].min()
            max_temp = period_data['air_temperature'].max()

            # Fuktighetstatistikk
            if 'relative_humidity' in period_data.columns:
                avg_humidity = period_data['relative_humidity'].mean()
                max_humidity = period_data['relative_humidity'].max()
            else:
                avg_humidity = None
                max_humidity = None

            # Vindstatistikk
            if 'wind_speed' in period_data.columns:
                avg_wind = period_data['wind_speed'].mean()
                max_wind = period_data['wind_speed'].max()
            else:
                avg_wind = None
                max_wind = None

            # Nedbørstatistikk
            if PRECIP_COL in period_data.columns:
                total_precip = period_data[PRECIP_COL].sum()
                max_precip = period_data[PRECIP_COL].max()
            else:
                total_precip = 0
                max_precip = 0

            # Risikovurdering
            risk_factors = []
            if avg_temp < 0:
                risk_factors.append("Frost")
            if avg_temp > -1 and avg_temp < 1:
                risk_factors.append("Kritisk temp")
            if avg_humidity and avg_humidity > 90:
                risk_factors.append("Høy fuktighet")
            if avg_wind and avg_wind < 2:
                risk_factors.append("Vindstille")
            if duration_hours >= 6:
                risk_factors.append("Lang varighet")

            risk_score = len(risk_factors)

            periods.append({
                'start_time': start_time,
                'end_time': end_time,
                'duration_hours': duration_hours,
                'avg_temperature': round(avg_temp, 1),
                'min_temperature': round(min_temp, 1),
                'max_temperature': round(max_temp, 1),
                'avg_humidity': round(avg_humidity, 1) if avg_humidity else None,
                'max_humidity': round(max_humidity, 1) if max_humidity else None,
                'avg_wind_speed': round(avg_wind, 1) if avg_wind else None,
                'max_wind_speed': round(max_wind, 1) if max_wind else None,
                'total_precipitation': round(total_precip, 2),
                'max_precipitation': round(max_precip, 2),
                'risk_factors': risk_factors,
                'risk_score': risk_score
            })

    print(f"✅ Fant {len(periods)} perioder (≥2t, med gap-toleranse)")

    if periods:
        # Sorter etter risikoscore
        periods.sort(key=lambda x: x['risk_score'], reverse=True)

        # Statistikk
        total_hours = sum(p['duration_hours'] for p in periods)
        avg_duration = total_hours / len(periods)

        print("\n📊 STATISTIKK:")
        print(f"📊 Total varighet: {total_hours} timer ({total_hours/24:.1f} døgn)")
        print(f"📊 Gjennomsnittlig varighet: {avg_duration:.1f} timer")
        print(f"📊 Andel av vinteren: {(total_hours/len(df))*100:.1f}%")

        # Månedlig fordeling
        monthly_counts = {}
        for period in periods:
            month = period['start_time'].month
            month_name = {11: 'Nov', 12: 'Des', 1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr'}[month]
            monthly_counts[month_name] = monthly_counts.get(month_name, 0) + 1

        print("\n📅 MÅNEDLIG FORDELING:")
        for month in ['Nov', 'Des', 'Jan', 'Feb', 'Mar', 'Apr']:
            count = monthly_counts.get(month, 0)
            print(f"  • {month}: {count} perioder")

        # Risikoscore fordeling
        risk_distribution = {}
        for period in periods:
            score = period['risk_score']
            risk_distribution[score] = risk_distribution.get(score, 0) + 1

        print("\n🎯 RISIKOSCORE FORDELING:")
        for score in sorted(risk_distribution.keys(), reverse=True):
            count = risk_distribution[score]
            print(f"  • Høy risiko ({score} faktorer): {count} perioder")

        print("\n🏆 TOPP 10 HØYEST RISIKO:")
        for i, period in enumerate(periods[:10], 1):
            factors_str = ", ".join(period['risk_factors'])
            print(f"{i:2d}. {period['start_time'].strftime('%d.%m %H:%M')} - {period['end_time'].strftime('%d.%m %H:%M')}")
            print(f"    {period['duration_hours']}t | {period['min_temperature']:.1f}°C til {period['max_temperature']:.1f}°C | Faktorer: {factors_str}")
            if period['avg_humidity']:
                print(f"    Fuktighet: {period['avg_humidity']:.1f}% | Vind: {period['avg_wind_speed']:.1f} m/s")

        # Sammenligning
        print("\n📊 SAMMENLIGNING MED TIDLIGERE:")
        print("❌ Første (urealistisk): 420 perioder")
        print("❌ Andre (for streng): 0 perioder")
        print(f"✅ Balansert: {len(periods)} perioder")

        if len(periods) >= 10 and len(periods) <= 50:
            print(f"🎯 Dette ser REALISTISK ut! ({len(periods)} perioder på 6 måneder)")
        elif len(periods) < 10:
            print(f"⚠️ Kanskje litt for få? ({len(periods)} perioder)")
        else:
            print(f"⚠️ Fortsatt litt mange? ({len(periods)} perioder)")

    return periods

def main():
    """Hovedfunksjon."""
    try:
        periods = create_balanced_slippery_analysis()

        # Lagre resultat
        output_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/balanced_slippery_road_periods.json'

        import json
        with open(output_file, 'w', encoding='utf-8') as f:
            # Konverter datetime objekter til strenger for JSON
            periods_json = []
            for period in periods:
                period_json = period.copy()
                period_json['start_time'] = period['start_time'].isoformat()
                period_json['end_time'] = period['end_time'].isoformat()
                periods_json.append(period_json)

            json.dump(periods_json, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Resultat lagret i: {output_file}")

    except Exception as e:
        print(f"❌ Feil: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
