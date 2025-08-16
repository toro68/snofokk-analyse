#!/usr/bin/env python3
"""
REGN-PÅ-SNØ GLATT VEI-ANALYSE
============================

Fokuserer på det EGENTLIGE problemet: Mildvær og regn på snødekte veier
"""

import pickle


def analyze_rain_on_snow_conditions():
    """Analyser regn-på-snø som skaper glatte veier."""

    print("🌧️❄️ REGN-PÅ-SNØ GLATT VEI-ANALYSE")
    print("=" * 60)

    # Last data
    cache_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/cache/weather_data_2023-11-01_2024-04-30.pkl'

    with open(cache_file, 'rb') as f:
        df = pickle.load(f)

    print(f"📊 Totalt {len(df)} timer med data")

    # Definer kritiske kolonner
    PRECIP_COL = 'sum(precipitation_amount PT1H)'
    SNOW_DEPTH_COL = 'surface_snow_thickness'
    TEMP_COL = 'air_temperature'

    # Sjekk tilgjengelige data
    has_precip = PRECIP_COL in df.columns and df[PRECIP_COL].notna().any()
    has_snow_depth = SNOW_DEPTH_COL in df.columns and df[SNOW_DEPTH_COL].notna().any()
    has_temp = TEMP_COL in df.columns and df[TEMP_COL].notna().any()

    print("\n📋 TILGJENGELIGE DATA:")
    print(f"🌧️ Nedbør: {'✅' if has_precip else '❌'}")
    print(f"❄️ Snødybde: {'✅' if has_snow_depth else '❌'}")
    print(f"🌡️ Temperatur: {'✅' if has_temp else '❌'}")

    if not (has_precip and has_snow_depth and has_temp):
        print("❌ Mangler kritiske data for regn-på-snø analyse!")
        return []

    # Analyser snødekke
    snow_depth = df[SNOW_DEPTH_COL].fillna(0)
    snow_covered_hours = (snow_depth > 5).sum()  # >5cm snø
    significant_snow_hours = (snow_depth > 20).sum()  # >20cm snø

    print("\n❄️ SNØDEKKE STATISTIKK:")
    print(f"❄️ Timer med snødekke >5cm: {snow_covered_hours} ({(snow_covered_hours/len(df))*100:.1f}%)")
    print(f"❄️ Timer med betydelig snø >20cm: {significant_snow_hours} ({(significant_snow_hours/len(df))*100:.1f}%)")
    print(f"❄️ Maks snødybde: {snow_depth.max():.0f}cm")
    print(f"❄️ Gjennomsnittlig snødybde (når snø): {snow_depth[snow_depth > 0].mean():.1f}cm")

    # Analyser nedbør
    precip = df[PRECIP_COL].fillna(0)
    rain_hours = (precip > 0.1).sum()
    moderate_rain_hours = (precip > 1.0).sum()
    heavy_rain_hours = (precip > 3.0).sum()

    print("\n🌧️ NEDBØR STATISTIKK:")
    print(f"🌧️ Timer med nedbør >0.1mm: {rain_hours} ({(rain_hours/len(df))*100:.1f}%)")
    print(f"🌧️ Timer med moderat regn >1.0mm: {moderate_rain_hours} ({(moderate_rain_hours/len(df))*100:.1f}%)")
    print(f"🌧️ Timer med kraftig regn >3.0mm: {heavy_rain_hours} ({(heavy_rain_hours/len(df))*100:.1f}%)")

    # KRITISKE FORHOLD: Regn på snødekt vei
    print("\n🚨 KRITISKE FORHOLD - REGN PÅ SNØ:")
    print("=" * 60)

    # 1. Mildvær (0-4°C) - varmt nok til regn, men kaldt nok til å fryse
    mild_weather = (df[TEMP_COL] >= 0) & (df[TEMP_COL] <= 4)

    # 2. Eksisterende snødekke (minst 5cm)
    existing_snow = snow_depth >= 5

    # 3. Regn/nedbør (minst 0.5mm/h, men ikke kraftig snøfall)
    rain_precip = precip >= 0.5

    # 4. Temperaturøkning (fra frost til mildvær) - indikerer smelting
    df['temp_change'] = df[TEMP_COL].diff()
    temp_rising = df['temp_change'] > 1  # Økning >1°C per time

    # Kombiner alle kriterier
    rain_on_snow = mild_weather & existing_snow & rain_precip

    print(f"🌡️ Timer med mildvær (0-4°C): {mild_weather.sum()} ({(mild_weather.sum()/len(df))*100:.1f}%)")
    print(f"❄️ Timer med snødekke (≥5cm): {existing_snow.sum()} ({(existing_snow.sum()/len(df))*100:.1f}%)")
    print(f"🌧️ Timer med regn (≥0.5mm): {rain_precip.sum()} ({(rain_precip.sum()/len(df))*100:.1f}%)")
    print(f"🔥 Timer med temperaturøkning: {temp_rising.sum()} ({(temp_rising.sum()/len(df))*100:.1f}%)")

    print(f"\n🎯 REGN-PÅ-SNØ SITUASJONER: {rain_on_snow.sum()} timer ({(rain_on_snow.sum()/len(df))*100:.1f}%)")

    # Også sjekk temperaturovergang scenarioer
    freeze_after_mild = (
        (df[TEMP_COL] <= 0) &  # Under frost
        (df[TEMP_COL].shift(1) > 0) &  # Forrige time over null
        existing_snow  # Med snødekke
    )

    print(f"🧊 Frysing etter mildvær på snø: {freeze_after_mild.sum()} timer")

    # Kombiner begge scenarioer
    all_dangerous = rain_on_snow | freeze_after_mild

    print(f"⚠️ TOTALT FARLIGE TIMER: {all_dangerous.sum()} ({(all_dangerous.sum()/len(df))*100:.1f}%)")

    # Finn perioder
    print("\n🔧 GRUPPERING TIL REGN-PÅ-SNØ PERIODER:")

    periods = []
    df_dangerous = df[all_dangerous].copy()

    if len(df_dangerous) == 0:
        print("❌ Ingen farlige regn-på-snø timer funnet!")
        return []

    # Grupper sammenhengende timer
    df_dangerous['time_diff'] = df_dangerous['referenceTime'].diff().dt.total_seconds() / 3600

    # Start ny periode hvis gap > 4 timer (regn-på-snø kan ha pauser)
    df_dangerous['new_period'] = (df_dangerous['time_diff'] > 4) | (df_dangerous['time_diff'].isna())
    df_dangerous['period_id'] = df_dangerous['new_period'].cumsum()

    # Analyser hver periode
    for period_id in df_dangerous['period_id'].unique():
        period_data = df_dangerous[df_dangerous['period_id'] == period_id]

        # Krav: Minst 1 time (regn-på-snø kan være kortvarig men farlig)
        if len(period_data) >= 1:

            start_time = period_data['referenceTime'].iloc[0]
            end_time = period_data['referenceTime'].iloc[-1]
            duration_hours = len(period_data)

            # Statistikk for perioden
            avg_temp = period_data[TEMP_COL].mean()
            min_temp = period_data[TEMP_COL].min()
            max_temp = period_data[TEMP_COL].max()

            total_precip = period_data[PRECIP_COL].sum()
            max_precip = period_data[PRECIP_COL].max()

            avg_snow_depth = period_data[SNOW_DEPTH_COL].mean()
            min_snow_depth = period_data[SNOW_DEPTH_COL].min()

            # Klassifiser type farlig situasjon
            rain_hours = (period_data[PRECIP_COL] >= 0.5).sum()
            mild_hours = ((period_data[TEMP_COL] >= 0) & (period_data[TEMP_COL] <= 4)).sum()
            freeze_hours = (period_data[TEMP_COL] <= 0).sum()

            if rain_hours > 0 and mild_hours > 0:
                scenario_type = "Regn på snø (mildvær)"
            elif freeze_hours > 0:
                scenario_type = "Frysing etter mildvær"
            else:
                scenario_type = "Temperaturovergang"

            # Faregrad basert på intensitet
            danger_factors = []
            if total_precip > 3:
                danger_factors.append("Kraftig regn")
            if avg_temp > 2:
                danger_factors.append("Markert mildvær")
            if avg_snow_depth > 15:
                danger_factors.append("Mye snø")
            if duration_hours >= 3:
                danger_factors.append("Lang varighet")
            if max_precip > 2:
                danger_factors.append("Intens nedbør")

            danger_score = len(danger_factors)

            periods.append({
                'start_time': start_time,
                'end_time': end_time,
                'duration_hours': duration_hours,
                'scenario_type': scenario_type,
                'avg_temperature': round(avg_temp, 1),
                'min_temperature': round(min_temp, 1),
                'max_temperature': round(max_temp, 1),
                'total_precipitation': round(total_precip, 2),
                'max_precipitation': round(max_precip, 2),
                'avg_snow_depth': round(avg_snow_depth, 1),
                'min_snow_depth': round(min_snow_depth, 1),
                'danger_factors': danger_factors,
                'danger_score': danger_score
            })

    print(f"✅ Fant {len(periods)} regn-på-snø perioder")

    if periods:
        # Sorter etter faregrad
        periods.sort(key=lambda x: x['danger_score'], reverse=True)

        # Statistikk
        total_hours = sum(p['duration_hours'] for p in periods)
        avg_duration = total_hours / len(periods)

        print("\n📊 REGN-PÅ-SNØ STATISTIKK:")
        print(f"📊 Total varighet: {total_hours} timer ({total_hours/24:.1f} døgn)")
        print(f"📊 Gjennomsnittlig varighet: {avg_duration:.1f} timer")
        print(f"📊 Andel av vinteren: {(total_hours/len(df))*100:.1f}%")

        # Scenario-fordeling
        scenario_counts = {}
        for period in periods:
            scenario = period['scenario_type']
            scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1

        print("\n🎭 SCENARIO-FORDELING:")
        for scenario, count in scenario_counts.items():
            print(f"  • {scenario}: {count} perioder")

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

        print("\n🚨 TOPP 10 FARLIGSTE REGN-PÅ-SNØ EPISODER:")
        for i, period in enumerate(periods[:10], 1):
            factors_str = ", ".join(period['danger_factors']) if period['danger_factors'] else "Grunnleggende risiko"
            print(f"{i:2d}. {period['start_time'].strftime('%d.%m %H:%M')} - {period['end_time'].strftime('%d.%m %H:%M')}")
            print(f"    {period['scenario_type']} | {period['duration_hours']}t")
            print(f"    Temp: {period['min_temperature']:.1f}°C til {period['max_temperature']:.1f}°C")
            print(f"    Regn: {period['total_precipitation']:.1f}mm | Snødybde: {period['avg_snow_depth']:.0f}cm")
            print(f"    Faktorer: {factors_str}")
            print()

    return periods

def main():
    """Hovedfunksjon."""
    try:
        periods = analyze_rain_on_snow_conditions()

        # Lagre resultat
        output_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/rain_on_snow_slippery_periods.json'

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
