#!/usr/bin/env python3
"""
KRITISK ANALYSE: Hvorfor 420 glatt vei-perioder er tull
======================================================

Undersøker periode-definisjon og snøfall som beskyttende faktor
"""

import pickle

import pandas as pd


def analyze_unrealistic_period_count():
    """Analyser hvorfor vi fikk urealistisk mange perioder."""

    print("🚨 KRITISK ANALYSE: PERIODE-DEFINISJON PROBLEM")
    print("=" * 60)

    # Last cached data
    cache_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/cache/weather_data_2023-11-01_2024-04-30.pkl'

    with open(cache_file, 'rb') as f:
        df = pickle.load(f)

    print("🔍 PROBLEMER MED TIDLIGERE ANALYSE:")
    print("-" * 50)

    problems = [
        "1. 🕐 PERIODE-DEFINISJON ALT FOR LIBERAL",
        "   - Teller hver 1-2 timer som 'periode'",
        "   - Ingen minimumskrav for varighet",
        "   - Ingen gap-toleranse mellom nære hendelser",
        "",
        "2. ❄️ IGNORERER SNØFALL SOM BESKYTTELSE",
        "   - Snøfall fungerer som NATURLIG STRØING",
        "   - Nysnø gir bedre grep enn glatte forhold",
        "   - Kontinuerlig snøfall 'bryter' glatte forhold",
        "",
        "3. 🚗 IGNORERER TRAFIKK-EFFEKT",
        "   - Trafikk varmer opp veibanen",
        "   - Hjulspor 'bryter' opp glatte lag",
        "   - Mindre trafikk = større risiko (natt/helg)",
        "",
        "4. 📏 INGEN PRAKTISK TERSKEL",
        "   - Hva regnes som 'farlig nok' til å være problem?",
        "   - Hvor lenge må det vare for å være relevant?",
        "   - Når opphører en periode å være 'samme hendelse'?"
    ]

    for problem in problems:
        print(problem)

    # Analyser snøfall-data
    print("\n📊 SNØFALL SOM BESKYTTENDE FAKTOR:")
    print("=" * 60)

    if 'sum(precipitation_amount PT1H)' in df.columns:
        precip_data = df['sum(precipitation_amount PT1H)'].dropna()
        snow_hours = (precip_data > 0.1).sum()  # Timer med snøfall >0.1mm
        total_hours = len(df)

        print(f"🌨️ Timer med snøfall (>0.1mm/h): {snow_hours} av {total_hours} ({(snow_hours/total_hours)*100:.1f}%)")
        print(f"🌨️ Timer med moderat snøfall (>0.5mm/h): {(precip_data > 0.5).sum()} ({((precip_data > 0.5).sum()/total_hours)*100:.1f}%)")
        print(f"🌨️ Timer med kraftig snøfall (>2.0mm/h): {(precip_data > 2.0).sum()} ({((precip_data > 2.0).sum()/total_hours)*100:.1f}%)")

    # Analyser temperaturforhold
    temp_data = df['air_temperature'].dropna()
    critical_temp_hours = ((temp_data >= -3) & (temp_data <= 2)).sum()

    print("\n🌡️ TEMPERATURANALYSE:")
    print(f"🌡️ Timer i kritisk område (-3 til +2°C): {critical_temp_hours} av {len(temp_data)} ({(critical_temp_hours/len(temp_data))*100:.1f}%)")

    print("\n💡 REALISTISK PERIODE-DEFINISJON:")
    print("=" * 60)

    realistic_criteria = [
        "1. 🕐 MINIMUM VARIGHET:",
        "   - Minst 3-4 timer sammenhengende for å være 'periode'",
        "   - Korte episoder (1-2t) er ikke operasjonelt relevante",
        "   - Tillat maks 2 timer gap før ny periode",
        "",
        "2. ❄️ SNØFALL EKSKLUDERER GLATT VEI:",
        "   - Snøfall >0.5mm/h = IKKE glatt vei-risiko",
        "   - Nysnø gir bedre grep enn glatte forhold",
        "   - Timer med snøfall teller IKKE som glatt vei",
        "",
        "3. 🎯 OPERASJONELL RELEVANS:",
        "   - Kun perioder som krever HANDLING (strøing/salting)",
        "   - Fokus på når veiene faktisk er FARLIGE",
        "   - Ikke teoretiske 'mulige' forhold",
        "",
        "4. 📊 FORVENTET ANTALL:",
        "   - 10-30 perioder per vintersesong er realistisk",
        "   - 1-2 perioder per måned i gjennomsnitt",
        "   - Ikke hver dag eller annen dag!"
    ]

    for criterion in realistic_criteria:
        print(criterion)

def create_realistic_slippery_periods():
    """Lag realistisk glatt vei-analyse med korrekt periode-definisjon."""

    print("\n🔧 REVIDERT GLATT VEI-ANALYSE")
    print("=" * 60)

    # Last data
    cache_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/cache/weather_data_2023-11-01_2024-04-30.pkl'

    with open(cache_file, 'rb') as f:
        df = pickle.load(f)

    # Forbedrede kriterier med snøfall-ekskludering
    df_clean = df.copy()

    # Ekskluder timer med snøfall
    if 'sum(precipitation_amount PT1H)' in df_clean.columns:
        snow_protection = df_clean['sum(precipitation_amount PT1H)'] > 0.5  # mm/h
        print(f"❄️ Ekskluderer {snow_protection.sum()} timer med snøfall >0.5mm/h")
    else:
        snow_protection = pd.Series([False] * len(df_clean))

    # Identifiser kritiske forhold (MED snøfall-ekskludering)
    critical_temp = (df_clean['air_temperature'] >= -2) & (df_clean['air_temperature'] <= 1)

    # Høy fuktighet (der tilgjengelig)
    if 'relative_humidity' in df_clean.columns:
        high_humidity = df_clean['relative_humidity'] >= 85
        valid_humidity = df_clean['relative_humidity'].notna()
    else:
        high_humidity = pd.Series([True] * len(df_clean))
        valid_humidity = pd.Series([False] * len(df_clean))

    # Vindstille forhold (der tilgjengelig)
    if 'wind_speed' in df_clean.columns:
        low_wind = df_clean['wind_speed'] <= 3  # m/s
        valid_wind = df_clean['wind_speed'].notna()
    else:
        low_wind = pd.Series([True] * len(df_clean))
        valid_wind = pd.Series([False] * len(df_clean))

    # Nattetid (22-08)
    df_clean['hour'] = df_clean['referenceTime'].dt.hour
    night_time = (df_clean['hour'] >= 22) | (df_clean['hour'] <= 8)

    # Kombinerte kriterier (EKSKLUDERER snøfall)
    risky_conditions = (
        critical_temp &
        high_humidity &
        low_wind &
        night_time &
        ~snow_protection &  # IKKE under snøfall
        valid_humidity &    # Kun når vi har fuktighetsmålinger
        valid_wind         # Kun når vi har vindmålinger
    )

    print(f"🎯 Timer med kritiske forhold (uten snøfall): {risky_conditions.sum()}")

    # Gruppe til realistiske perioder
    realistic_periods = []

    # Finn start og slutt av risikoperioder
    risk_changes = risky_conditions.astype(int).diff()
    starts = df_clean[risk_changes == 1].index
    ends = df_clean[risk_changes == -1].index

    # Håndter edge cases
    if risky_conditions.iloc[0]:
        starts = [df_clean.index[0]] + list(starts)
    if risky_conditions.iloc[-1]:
        ends = list(ends) + [df_clean.index[-1]]

    # Match starts og ends og filtrer på varighet
    for start_idx in starts:
        matching_ends = [e for e in ends if e > start_idx]
        if matching_ends:
            end_idx = matching_ends[0]

            period_data = df_clean.loc[start_idx:end_idx]
            duration_hours = len(period_data)

            # KRAV: Minst 3 timer for å være relevant periode
            if duration_hours >= 3:

                start_time = period_data['referenceTime'].iloc[0]
                end_time = period_data['referenceTime'].iloc[-1]

                # Beregn statistikk
                avg_temp = period_data['air_temperature'].mean()
                min_temp = period_data['air_temperature'].min()
                max_temp = period_data['air_temperature'].max()

                avg_humidity = period_data['relative_humidity'].mean() if 'relative_humidity' in period_data.columns else None
                avg_wind = period_data['wind_speed'].mean() if 'wind_speed' in period_data.columns else None

                # Sjekk om det var snøfall i perioden (skal ikke være det)
                if 'sum(precipitation_amount PT1H)' in period_data.columns:
                    snow_in_period = (period_data['sum(precipitation_amount PT1H)'] > 0.5).any()
                    total_precip = period_data['sum(precipitation_amount PT1H)'].sum()
                else:
                    snow_in_period = False
                    total_precip = 0

                # Kun legg til hvis INGEN snøfall i perioden
                if not snow_in_period:
                    realistic_periods.append({
                        'start_time': start_time,
                        'end_time': end_time,
                        'duration_hours': duration_hours,
                        'avg_temperature': round(avg_temp, 1),
                        'min_temperature': round(min_temp, 1),
                        'max_temperature': round(max_temp, 1),
                        'avg_humidity': round(avg_humidity, 1) if avg_humidity is not None else None,
                        'avg_wind_speed': round(avg_wind, 1) if avg_wind is not None else None,
                        'total_precipitation': round(total_precip, 2),
                        'measurement_count': len(period_data)
                    })

    print(f"✅ Realistiske glatt vei-perioder (≥3t, uten snøfall): {len(realistic_periods)}")

    if realistic_periods:
        total_hours = sum(p['duration_hours'] for p in realistic_periods)
        avg_duration = total_hours / len(realistic_periods)
        longest_period = max(p['duration_hours'] for p in realistic_periods)

        print(f"📊 Total varighet: {total_hours:.1f} timer ({total_hours/24:.1f} døgn)")
        print(f"📊 Gjennomsnittlig varighet: {avg_duration:.1f} timer")
        print(f"📊 Lengste periode: {longest_period:.1f} timer")

        # Månedlig fordeling
        monthly_counts = {}
        for period in realistic_periods:
            month = period['start_time'].month
            month_name = {11: 'Nov', 12: 'Des', 1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr'}[month]
            monthly_counts[month_name] = monthly_counts.get(month_name, 0) + 1

        print("\n📅 MÅNEDLIG FORDELING:")
        for month in ['Nov', 'Des', 'Jan', 'Feb', 'Mar', 'Apr']:
            count = monthly_counts.get(month, 0)
            print(f"  • {month}: {count} perioder")

        print("\n🎯 TOPP 5 LENGSTE PERIODER:")
        sorted_periods = sorted(realistic_periods, key=lambda x: x['duration_hours'], reverse=True)
        for i, period in enumerate(sorted_periods[:5], 1):
            print(f"{i}. {period['start_time'].strftime('%d.%m.%Y %H:%M')} - {period['end_time'].strftime('%d.%m.%Y %H:%M')}")
            print(f"   Varighet: {period['duration_hours']:.1f}t | Temp: {period['min_temp']:.1f}°C til {period['max_temp']:.1f}°C")
            if period['avg_humidity']:
                print(f"   Fuktighet: {period['avg_humidity']:.1f}% | Vind: {period['avg_wind_speed']:.1f} m/s")

    # Sammenligning
    print("\n📊 SAMMENLIGNING:")
    print("❌ Tidligere (urealistisk): 420 perioder")
    print(f"✅ Revidert (realistisk): {len(realistic_periods)} perioder")
    print(f"📉 Reduksjon: {((420 - len(realistic_periods))/420)*100:.1f}%")

    return realistic_periods

def main():
    """Hovedfunksjon."""
    try:
        analyze_unrealistic_period_count()
        create_realistic_slippery_periods()

    except Exception as e:
        print(f"❌ Feil: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
