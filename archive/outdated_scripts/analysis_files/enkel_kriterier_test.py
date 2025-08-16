#!/usr/bin/env python3
"""
ENKEL TEST AV BALANSERTE KRITERIER
Tester de justerte kriteriene på faktiske brøytingsepisoder
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
    if wind_chill <= -6 and wind_speed >= 3:  # Justert fra -8 til -6
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
    if (temp > -2 and precipitation >= 0.2 and snow_depth >= 1 and  # Justert fra 0.5 til 0.2
        snow_change <= 0):  # Negativ eller null endring = regn
        return 'high', f"Regn på snø: {temp:.1f}°C, {snow_depth:.1f}cm snø, {precipitation:.1f}mm nedbør"

    # Mildvær etter frost
    if temp > 2 and snow_depth >= 5:
        return 'medium', f"Mildvær {temp:.1f}°C etter frost, {snow_depth:.1f}cm snø"

    return 'low', "Ingen kriterier oppfylt for glattføre-risiko"

def detect_snowdrift_risk_old(weather_data):
    """Gamle snøfokk-kriterier (strenge)"""

    temp = weather_data.get('temperatur', 0)
    wind_speed = weather_data.get('vindstyrke', 0)
    snow_depth = weather_data.get('snødybde', 0)
    snow_change = weather_data.get('snødybdeendring', 0)

    wind_chill = temp - (wind_speed * 2)

    # Høy risiko
    if wind_chill <= -15 and wind_speed >= 8:
        return 'high', f"Ekstrem vindkjøling {wind_chill:.1f}°C + høy vind {wind_speed:.1f}m/s"

    if snow_depth >= 30 and wind_speed >= 10:
        return 'high', f"Mye snø {snow_depth:.1f}cm + høy vind {wind_speed:.1f}m/s"

    # Medium risiko (gamle strenge terskler)
    if wind_chill <= -10 and wind_speed >= 5:
        return 'medium', f"Vindkjøling {wind_chill:.1f}°C + vind {wind_speed:.1f}m/s"

    if snow_depth >= 20 and wind_speed >= 6:
        return 'medium', f"Moderat snø {snow_depth:.1f}cm + vind {wind_speed:.1f}m/s"

    if abs(snow_change) >= 5 and wind_speed >= 6:
        return 'medium', f"Snøendring {snow_change:.1f}cm + vind {wind_speed:.1f}m/s"

    return 'low', "Ingen kriterier oppfylt for snøfokk-risiko"

def detect_slippery_risk_old(weather_data):
    """Gamle glattføre-kriterier (strenge)"""

    temp = weather_data.get('temperatur', 0)
    precipitation = weather_data.get('nedbør', 0)
    snow_depth = weather_data.get('snødybde', 0)
    snow_change = weather_data.get('snødybdeendring', 0)

    # Regn på snø (gamle strenge terskler)
    if (temp > -1 and precipitation >= 1.0 and snow_depth >= 5 and
        snow_change <= 0):
        return 'high', f"Regn på snø: {temp:.1f}°C, {snow_depth:.1f}cm snø, {precipitation:.1f}mm nedbør"

    # Mildvær etter frost
    if temp > 3 and snow_depth >= 10:
        return 'medium', f"Mildvær {temp:.1f}°C etter frost, {snow_depth:.1f}cm snø"

    return 'low', "Ingen kriterier oppfylt for glattføre-risiko"

def test_on_real_data():
    """Test på faktiske brøytingsepisoder"""

    print("🧪 TEST AV BALANSERTE VS GAMLE KRITERIER")
    print("=" * 45)

    # Les brøytingsdata
    df = pd.read_csv("/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/maintenance_weather_data_20250810_1303.csv")

    print(f"✅ Lastet {len(df)} brøytingsepisoder")

    # Filter væravhengige episoder basert på maintenance_criteria
    weather_related = ['snow_plowing', 'slush_scraping', 'freeze_thaw_salting', 'rain_on_snow_salting']
    weather_episodes = df[df['maintenance_criteria'].isin(weather_related)]
    other_episodes = df[~df['maintenance_criteria'].isin(weather_related)]

    print(f"🌤️ {len(weather_episodes)} væravhengige episoder")
    print(f"📅 {len(other_episodes)} andre episoder (inspeksjoner/unødvendig)")

    # Test begge kriterier
    results = []

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

        # Test gamle kriterier
        old_snow_risk, old_snow_reason = detect_snowdrift_risk_old(weather_data)
        old_slip_risk, old_slip_reason = detect_slippery_risk_old(weather_data)

        # Test balanserte kriterier
        bal_snow_risk, bal_snow_reason = detect_snowdrift_risk_balanced(weather_data)
        bal_slip_risk, bal_slip_reason = detect_slippery_risk_balanced(weather_data)

        is_weather_related = row['maintenance_criteria'] in weather_related

        results.append({
            'dato': row['maintenance_date'],
            'kategori': row['maintenance_criteria'],
            'væravhengig': is_weather_related,
            'temp': temp,
            'vind': wind,
            'snø': snow_depth,
            'nedbør': precip,
            'old_snøfokk': old_snow_risk,
            'old_glatt': old_slip_risk,
            'bal_snøfokk': bal_snow_risk,
            'bal_glatt': bal_slip_risk,
            'old_snow_reason': old_snow_reason,
            'bal_snow_reason': bal_snow_reason,
            'old_slip_reason': old_slip_reason,
            'bal_slip_reason': bal_slip_reason
        })

    results_df = pd.DataFrame(results)

    # Analyser væravhengige episoder
    weather_df = results_df[results_df['væravhengig'] == True]
    other_df = results_df[results_df['væravhengig'] == False]

    print(f"\n🌤️ VÆRAVHENGIGE EPISODER ANALYSE ({len(weather_df)}):")
    print("-" * 50)

    # Gamle kriterier - væravhengige
    old_weather_detected = len(weather_df[
        (weather_df['old_snøfokk'].isin(['medium', 'high'])) |
        (weather_df['old_glatt'].isin(['medium', 'high']))
    ])
    old_weather_accuracy = old_weather_detected / len(weather_df) * 100

    # Balanserte kriterier - væravhengige
    bal_weather_detected = len(weather_df[
        (weather_df['bal_snøfokk'].isin(['medium', 'high'])) |
        (weather_df['bal_glatt'].isin(['medium', 'high']))
    ])
    bal_weather_accuracy = bal_weather_detected / len(weather_df) * 100

    print(f"GAMLE KRITERIER: {old_weather_detected}/{len(weather_df)} ({old_weather_accuracy:.1f}%)")
    print(f"BALANSERTE KRITERIER: {bal_weather_detected}/{len(weather_df)} ({bal_weather_accuracy:.1f}%)")
    print(f"FORBEDRING: {bal_weather_accuracy - old_weather_accuracy:+.1f} prosentpoeng")

    # Ikke-væravhengige episoder
    print(f"\n📅 IKKE-VÆRAVHENGIGE EPISODER ANALYSE ({len(other_df)}):")
    print("-" * 55)

    # Gamle kriterier - ikke-væravhengige (begge lav er riktig)
    old_other_correct = len(other_df[
        (other_df['old_snøfokk'] == 'low') &
        (other_df['old_glatt'] == 'low')
    ])
    old_other_accuracy = old_other_correct / len(other_df) * 100

    # Balanserte kriterier - ikke-væravhengige
    bal_other_correct = len(other_df[
        (other_df['bal_snøfokk'] == 'low') &
        (other_df['bal_glatt'] == 'low')
    ])
    bal_other_accuracy = bal_other_correct / len(other_df) * 100

    print(f"GAMLE KRITERIER (begge lav): {old_other_correct}/{len(other_df)} ({old_other_accuracy:.1f}%)")
    print(f"BALANSERTE KRITERIER (begge lav): {bal_other_correct}/{len(other_df)} ({bal_other_accuracy:.1f}%)")
    print(f"ENDRING: {bal_other_accuracy - old_other_accuracy:+.1f} prosentpoeng")

    # Samlet resultat
    print("\n🏆 SAMLET RESULTAT:")
    print("-" * 20)

    old_total_correct = old_weather_detected + old_other_correct
    bal_total_correct = bal_weather_detected + bal_other_correct
    total_episodes = len(weather_df) + len(other_df)

    old_total_accuracy = old_total_correct / total_episodes * 100
    bal_total_accuracy = bal_total_correct / total_episodes * 100

    print(f"GAMLE KRITERIER: {old_total_accuracy:.1f}%")
    print(f"BALANSERTE KRITERIER: {bal_total_accuracy:.1f}%")
    print(f"TOTAL FORBEDRING: {bal_total_accuracy - old_total_accuracy:+.1f} prosentpoeng")

    # Spesifikke forbedringer
    print("\n💡 SPESIFIKKE FORBEDRINGER:")
    print("-" * 30)

    # Episoder der balanserte er bedre
    improved = weather_df[
        ((weather_df['old_snøfokk'] == 'low') & (weather_df['old_glatt'] == 'low')) &
        ((weather_df['bal_snøfokk'].isin(['medium', 'high'])) | (weather_df['bal_glatt'].isin(['medium', 'high'])))
    ]

    print(f"Forbedret {len(improved)} væravhengige episoder:")
    for idx, row in improved.head(10).iterrows():  # Vis max 10 eksempler
        old_risk = f"{row['old_snøfokk']}/{row['old_glatt']}"
        bal_risk = f"{row['bal_snøfokk']}/{row['bal_glatt']}"
        print(f"  {row['dato']}: {old_risk} → {bal_risk}")
        print(f"    Vær: {row['temp']:.1f}°C, {row['vind']:.1f}m/s, {row['snø']:.1f}cm, {row['nedbør']:.1f}mm")
        if row['bal_snow_reason'] != "Ingen kriterier oppfylt for snøfokk-risiko":
            print(f"    Snøfokk: {row['bal_snow_reason']}")
        if row['bal_slip_reason'] != "Ingen kriterier oppfylt for glattføre-risiko":
            print(f"    Glattføre: {row['bal_slip_reason']}")

    # Vurdering
    if bal_total_accuracy > old_total_accuracy:
        print("\n✅ ANBEFALING: IMPLEMENTER BALANSERTE KRITERIER")
        print(f"Gir {bal_total_accuracy - old_total_accuracy:+.1f}pp forbedring i samlet nøyaktighet")
    else:
        print("\n❌ ANBEFALING: BEHOLD GAMLE KRITERIER")
        print("Balanserte kriterier gir ikke forbedring")

    # Lagre resultater
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = f"/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/simple_criteria_test_{timestamp}.csv"
    results_df.to_csv(output_file, index=False)
    print(f"\n💾 Detaljerte resultater lagret: {output_file}")

    return results_df

if __name__ == "__main__":
    test_on_real_data()
