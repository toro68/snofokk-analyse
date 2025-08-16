#!/usr/bin/env python3
"""
JUSTERTE ML-KRITERIER ANALYSE
Finjusterer kriteriene basert på faktiske testresultater
"""


import pandas as pd


def analyze_test_results():
    """Analyser testresultatene og foreslå justeringer"""

    print("🔍 ANALYSE AV ML-KRITERIER TESTRESULTATER")
    print("=" * 55)

    # Les sammenligning
    comparison_file = "/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/analyzed/old_vs_new_criteria_comparison_20250811_2027.csv"
    df = pd.read_csv(comparison_file)

    # Analyser hvor de nye kriteriene feiler
    weather_episodes = df[df['er_væravhengig'] == True]

    print(f"📊 ANALYSER {len(weather_episodes)} VÆRAVHENGIGE EPISODER:")
    print("-" * 50)

    # Finn episoder der gamle kriterier var riktige, men nye feiler
    old_correct_new_wrong = weather_episodes[
        ((weather_episodes['old_snøfokk_risiko'].isin(['medium', 'high'])) |
         (weather_episodes['old_glattføre_risiko'].isin(['medium', 'high']))) &
        ((weather_episodes['new_snøfokk_risiko'] == 'low') &
         (weather_episodes['new_glattføre_risiko'] == 'low'))
    ]

    print(f"❌ EPISODER DER GAMLE VAR RIKTIGE, NYE FEILER: {len(old_correct_new_wrong)}")
    for idx, episode in old_correct_new_wrong.iterrows():
        print(f"  {episode['dato']}: Gamle ga {episode['old_snøfokk_risiko']}/{episode['old_glattføre_risiko']}, nye ga low/low")

    # Finn episoder der nye kriterier forbedret
    new_improvements = weather_episodes[
        ((weather_episodes['old_snøfokk_risiko'] == 'low') &
         (weather_episodes['old_glattføre_risiko'] == 'low')) &
        ((weather_episodes['new_snøfokk_risiko'].isin(['medium', 'high'])) |
         (weather_episodes['new_glattføre_risiko'].isin(['medium', 'high'])))
    ]

    print(f"\n✅ EPISODER DER NYE KRITERIER FORBEDRET: {len(new_improvements)}")
    for idx, episode in new_improvements.iterrows():
        old_risk = f"{episode['old_snøfokk_risiko']}/{episode['old_glattføre_risiko']}"
        new_risk = f"{episode['new_snøfokk_risiko']}/{episode['new_glattføre_risiko']}"
        print(f"  {episode['dato']}: {old_risk} → {new_risk}")
        if episode['new_snøfokk_reason'] != "Ingen kriterier oppfylt for snøfokk-risiko":
            print(f"    Snøfokk: {episode['new_snøfokk_reason']}")
        if episode['new_glattføre_reason'] != "Ingen kriterier oppfylt for glattføre-risiko":
            print(f"    Glattføre: {episode['new_glattføre_reason']}")

    print("\n🎯 FORESLÅTTE JUSTERINGER:")
    print("=" * 30)

    # Analyser problemområder
    print("1. SNØFOKK-KRITERIER:")
    print("   Problem: Nye kriterier for strenge på vindkjøling")
    print("   Anbefaling: Øk vindkjøling-terskel fra -8°C til -6°C")
    print("   Begrunnelse: Mange væravhengige episoder har vindkjøling -6 til -8°C")

    print("\n2. GLATTFØRE-KRITERIER:")
    print("   Problem: Regn-på-snø kriterier for strenge")
    print("   Anbefaling: Reduser nedbørsmengde fra 0.5mm til 0.2mm")
    print("   Begrunnelse: Små nedbørsmengder kan gi glatte forhold")

    print("\n3. KOMBINERT STRATEGI:")
    print("   - Behold de gamle kriteriene som baseline")
    print("   - Legg til spesifikke forbedringer for glattføre")
    print("   - Juster vindkjøling-terskel moderat")

    return df

def create_balanced_criteria():
    """Lag balanserte kriterier som kombinerer det beste fra begge"""

    print("\n🔧 LAGER BALANSERTE KRITERIER")
    print("=" * 35)

    criteria_code = '''
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
'''

    # Lagre kriteriene
    with open('/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/balanced_ml_criteria.py', 'w') as f:
        f.write(criteria_code)

    print("✅ Balanserte kriterier lagret i: balanced_ml_criteria.py")

    print("\n📋 BALANSERTE KRITERIER - HOVEDENDRINGER:")
    print("-" * 45)
    print("1. Vindkjøling snøfokk: -8°C → -6°C (mer sensitiv)")
    print("2. Regn-på-snø nedbør: 0.5mm → 0.2mm (mer sensitiv)")
    print("3. Beholder høye terskler for høy risiko")
    print("4. Fokuserer på værrelaterte forbedringer")

if __name__ == "__main__":
    # Analyser testresultater
    df = analyze_test_results()

    # Lag balanserte kriterier
    create_balanced_criteria()

    print("\n🎯 ANBEFALING:")
    print("=" * 15)
    print("- Test de balanserte kriteriene på samme datasett")
    print("- Sammenlign med både gamle og nye kriterier")
    print("- Fokuser på å beholde god ytelse på væravhengige episoder")
    print("- Implementer kun hvis balanserte kriterier viser forbedring")
