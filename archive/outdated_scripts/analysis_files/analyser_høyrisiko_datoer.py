#!/usr/bin/env python3
"""
ANALYSE AV HØYRISIKO-DATOER DE SISTE VINTRENE
Finner alle datoer med høy risiko for snøfokk og glattføre 2022-2025
"""

from datetime import datetime

import pandas as pd


def detect_snowdrift_risk_balanced(weather_data):
    """Balanserte snøfokk-kriterier"""

    temp = weather_data.get('temperatur', 0)
    wind_speed = weather_data.get('vindstyrke', 0)
    snow_depth = weather_data.get('snødybde', 0)
    snow_change = weather_data.get('snødybdeendring', 0)

    # Vindkjøling (justert terskel)
    wind_chill = temp - (wind_speed * 2)

    # Høy risiko (strenge kriterier fra gamle systemet)
    if wind_chill <= -15 and wind_speed >= 7:
        return 'high', f"Ekstrem vindkjøling {wind_chill:.1f}°C + høy vind {wind_speed:.1f}m/s"

    if snow_depth >= 30 and wind_speed >= 8:
        return 'high', f"Mye snø {snow_depth:.1f}cm + høy vind {wind_speed:.1f}m/s"

    # Medium risiko (justerte terskler)
    if wind_chill <= -6 and wind_speed >= 3:
        return 'medium', f"Vindkjøling {wind_chill:.1f}°C + vind {wind_speed:.1f}m/s"

    if snow_depth >= 15 and wind_speed >= 5:
        return 'medium', f"Moderat snø {snow_depth:.1f}cm + vind {wind_speed:.1f}m/s"

    if abs(snow_change) >= 3 and wind_speed >= 4:
        return 'medium', f"Snøendring {snow_change:.1f}cm + vind {wind_speed:.1f}m/s"

    return 'low', "Ingen kriterier oppfylt for snøfokk-risiko"

def detect_slippery_risk_balanced(weather_data):
    """Balanserte glattføre-kriterier"""

    temp = weather_data.get('temperatur', 0)
    precipitation = weather_data.get('nedbør', 0)
    snow_depth = weather_data.get('snødybde', 0)
    snow_change = weather_data.get('snødybdeendring', 0)

    # Regn på snø (justerte terskler)
    if (temp > -2 and precipitation >= 0.2 and snow_depth >= 1 and
        snow_change <= 0):
        return 'high', f"Regn på snø: {temp:.1f}°C, {snow_depth:.1f}cm snø, {precipitation:.1f}mm nedbør"

    # Mildvær etter frost
    if temp > 2 and snow_depth >= 5:
        return 'medium', f"Mildvær {temp:.1f}°C etter frost, {snow_depth:.1f}cm snø"

    return 'low', "Ingen kriterier oppfylt for glattføre-risiko"

def analyze_high_risk_dates():
    """Analyser høyrisiko-datoer fra brøytingsdata"""

    print("🔍 ANALYSE AV HØYRISIKO-DATOER DE SISTE VINTRENE")
    print("=" * 52)

    # Les brøytingsdata
    df = pd.read_csv("/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/maintenance_weather_data_20250810_1303.csv")

    print(f"✅ Analyserer {len(df)} episoder fra 2022-2025")

    # Konverter datoer
    df['date'] = pd.to_datetime(df['maintenance_date'], format='%d. %b. %Y', errors='coerce')
    df = df.dropna(subset=['date'])

    # Analyser hver episode
    high_risk_episodes = []
    medium_risk_episodes = []

    for idx, row in df.iterrows():
        # Håndter missing values
        temp = row['temp_mean'] if pd.notna(row['temp_mean']) else 0
        wind = row['wind_max'] if pd.notna(row['wind_max']) else 0
        snow_depth = row['snow_depth_cm'] if pd.notna(row['snow_depth_cm']) else 0
        precip = row['precip_total'] if pd.notna(row['precip_total']) else 0

        weather_data = {
            'temperatur': temp,
            'vindstyrke': wind,
            'snødybde': snow_depth,
            'snødybdeendring': 0,  # Ikke tilgjengelig
            'nedbør': precip
        }

        # Test balanserte kriterier
        snow_risk, snow_reason = detect_snowdrift_risk_balanced(weather_data)
        slip_risk, slip_reason = detect_slippery_risk_balanced(weather_data)

        episode_data = {
            'dato': row['maintenance_date'],
            'date': row['date'],
            'år': row['date'].year,
            'måned': row['date'].month,
            'kategori': row['maintenance_criteria'],
            'temp': temp,
            'vind': wind,
            'snø': snow_depth,
            'nedbør': precip,
            'snøfokk_risiko': snow_risk,
            'glattføre_risiko': slip_risk,
            'snøfokk_årsak': snow_reason,
            'glattføre_årsak': slip_reason
        }

        # Kategoriser basert på høyeste risiko
        if snow_risk == 'high' or slip_risk == 'high':
            high_risk_episodes.append(episode_data)
        elif snow_risk == 'medium' or slip_risk == 'medium':
            medium_risk_episodes.append(episode_data)

    # Analyser høyrisiko-episoder
    print(f"\n🚨 HØYRISIKO-EPISODER ({len(high_risk_episodes)}):")
    print("=" * 45)

    if high_risk_episodes:
        high_df = pd.DataFrame(high_risk_episodes)

        # Sorter etter dato
        high_df = high_df.sort_values('date')

        # Gruppe per vinter
        print("\n📅 HØYRISIKO-DATOER PER VINTER:")
        print("-" * 35)

        for year in sorted(high_df['år'].unique()):
            year_episodes = high_df[high_df['år'] == year]
            vinter = f"{year-1}/{year}" if year <= 2024 else f"{year}/{year+1}"

            print(f"\n🌨️ VINTER {vinter} ({len(year_episodes)} episoder):")

            for idx, episode in year_episodes.iterrows():
                dato = episode['dato']
                temp = episode['temp']
                vind = episode['vind']
                snø = episode['snø']
                nedbør = episode['nedbør']

                risks = []
                if episode['snøfokk_risiko'] == 'high':
                    risks.append(f"SNØFOKK: {episode['snøfokk_årsak']}")
                if episode['glattføre_risiko'] == 'high':
                    risks.append(f"GLATTFØRE: {episode['glattføre_årsak']}")

                print(f"  📍 {dato}")
                print(f"    Vær: {temp:.1f}°C, {vind:.1f}m/s vind, {snø:.1f}cm snø, {nedbør:.1f}mm nedbør")
                for risk in risks:
                    print(f"    🚨 {risk}")
                print()

        # Månedlig fordeling
        print("\n📊 MÅNEDLIG FORDELING AV HØYRISIKO:")
        print("-" * 40)

        monthly_counts = high_df.groupby('måned').size().sort_index()
        month_names = {1: 'Januar', 2: 'Februar', 3: 'Mars', 4: 'April',
                      10: 'Oktober', 11: 'November', 12: 'Desember'}

        for month, count in monthly_counts.items():
            month_name = month_names.get(month, f"Måned {month}")
            print(f"  {month_name}: {count} episoder")

        # Type-fordeling
        print("\n🎯 TYPE-FORDELING AV HØYRISIKO:")
        print("-" * 35)

        snøfokk_high = len(high_df[high_df['snøfokk_risiko'] == 'high'])
        glattføre_high = len(high_df[high_df['glattføre_risiko'] == 'high'])
        begge_high = len(high_df[(high_df['snøfokk_risiko'] == 'high') &
                                (high_df['glattføre_risiko'] == 'high')])

        print(f"  Kun snøfokk høy: {snøfokk_high - begge_high} episoder")
        print(f"  Kun glattføre høy: {glattføre_high - begge_high} episoder")
        print(f"  Begge høy: {begge_high} episoder")
        print(f"  Total høyrisiko: {len(high_risk_episodes)} episoder")

    # Analyser medium-risiko episoder
    print(f"\n⚠️ MEDIUM-RISIKO EPISODER ({len(medium_risk_episodes)}):")
    print("=" * 48)

    if medium_risk_episodes:
        medium_df = pd.DataFrame(medium_risk_episodes)

        # Månedlig fordeling for medium risiko
        monthly_medium = medium_df.groupby('måned').size().sort_index()

        print("\n📊 MÅNEDLIG FORDELING AV MEDIUM-RISIKO:")
        print("-" * 44)

        for month, count in monthly_medium.items():
            month_name = month_names.get(month, f"Måned {month}")
            print(f"  {month_name}: {count} episoder")

    # Lagre resultater
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    # Lagre høyrisiko-episoder
    if high_risk_episodes:
        high_df = pd.DataFrame(high_risk_episodes)
        high_output = f"/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/høyrisiko_episoder_{timestamp}.csv"
        high_df.to_csv(high_output, index=False)
        print(f"\n💾 Høyrisiko-episoder lagret: {high_output}")

    # Lagre medium-risiko episoder
    if medium_risk_episodes:
        medium_df = pd.DataFrame(medium_risk_episodes)
        medium_output = f"/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/medium_risiko_episoder_{timestamp}.csv"
        medium_df.to_csv(medium_output, index=False)
        print(f"💾 Medium-risiko episoder lagret: {medium_output}")

    # Oppsummering
    print("\n📋 OPPSUMMERING HØYRISIKO 2022-2025:")
    print("=" * 40)
    print(f"🚨 Høyrisiko-episoder: {len(high_risk_episodes)}")
    print(f"⚠️ Medium-risiko episoder: {len(medium_risk_episodes)}")
    print(f"📊 Total analyserte episoder: {len(df)}")

    if high_risk_episodes:
        høyrisiko_andel = len(high_risk_episodes) / len(df) * 100
        print(f"📈 Høyrisiko-andel: {høyrisiko_andel:.1f}%")

    return high_risk_episodes, medium_risk_episodes

if __name__ == "__main__":
    high_risk, medium_risk = analyze_high_risk_dates()
