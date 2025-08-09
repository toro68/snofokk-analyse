#!/usr/bin/env python3
"""
KRITISK ANALYSE AV GLATT VEI-KRITERIER
=====================================

Evaluerer eksisterende kriterier for glatte veier og identifiserer mangler
"""

import pandas as pd
import numpy as np
import pickle
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from typing import Dict, List

def critical_slippery_road_analysis():
    """Kritisk analyse av eksisterende glatt vei-kriterier."""
    
    print("🚨 KRITISK ANALYSE AV GLATT VEI-KRITERIER")
    print("=" * 60)
    print("📋 Evaluerer fysisk realisme og kompletthet")
    print("=" * 60)
    
    # Last cached værdata for sammenligning
    cache_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/cache/weather_data_2023-11-01_2024-04-30.pkl'
    
    with open(cache_file, 'rb') as f:
        df = pickle.load(f)
    
    print("\n🔍 EKSISTERENDE KRITERIER ANALYSE:")
    print("-" * 50)
    
    # Analyser eksisterende kriterier fra alert_config.json
    existing_criteria = {
        'temperature': {'min': 0.0, 'max': 5.0},
        'humidity': {'min': 85.0},
        'precipitation_3h': {'min': 2.0},
        'snow_depth': {'min': 10.0},
        'snow_change': {'max': -0.3},
        'fresh_snow': {'max': 1.0}
    }
    
    print("📊 NÅVÆRENDE KRITERIER:")
    for criterion, values in existing_criteria.items():
        print(f"  • {criterion}: {values}")
    
    print("\n❌ KRITISKE PROBLEMER IDENTIFISERT:")
    print("-" * 50)
    
    problems = [
        "1. 🌡️ TEMPERATUROMRÅDE (0-5°C) - ALT FOR BREDT!",
        "   - Glatte veier oppstår hovedsakelig nær 0°C (-2°C til +2°C)",
        "   - 5°C er for høyt - snø/is smelter raskt ved denne temperaturen",
        "   - Mangler skille mellom is, rim og våt is",
        "",
        "2. 💧 NEDBØRSKRAV (2.0mm/3h) - OVERESTIMERER!",
        "   - Glatte veier kan oppstå uten nedbør (rimfrost, underkjøling)",
        "   - Kan oppstå med minimal nedbør + riktige forhold",
        "   - Fokuserer for mye på smelting, ikke nok på frysing",
        "",
        "3. ❄️ SNØDYBDEKRAV (≥10cm) - MISFORSTÅTT!",
        "   - Glatte veier kan oppstå på bar mark (rimfrost, underkjølt regn)",
        "   - Tynne lag is/rim er ofte farligere enn tykk snø",
        "   - Ignorerer 'svart is' - mest farlige type",
        "",
        "4. 💨 MANGLER VINDDATA!",
        "   - Vind påvirker både fordampning og nedkjøling",
        "   - Vindstille forhold fremmer rimfrost",
        "   - Vindeksponerte områder kjøles ned raskere",
        "",
        "5. 🌙 MANGLER TIDSPUNKT/SOLINFALL!",
        "   - Glatte veier oppstår oftere om natten (utstrålingsavkjøling)",
        "   - Tidlig morgen er mest kritisk (laveste temperatur)",
        "   - Skyggelagt vs. soleksponerte områder",
        "",
        "6. 📉 MANGLER TEMPERATURGRADIENTER!",
        "   - Rask temperaturfall er kritisk faktor",
        "   - Duggpunkt vs. lufttemperatur",
        "   - Temperaturinversjon (kaldere ved bakken)",
        "",
        "7. 🛣️ MANGLER VEISPESIFIKKE FAKTORER!",
        "   - Veimateriale (asfalt vs. betong)",
        "   - Drenering og topografi", 
        "   - Trafikktetthet (varme fra trafikk)",
        "",
        "8. ⏰ MANGLER HISTORISK KONTEKST!",
        "   - Hvor lenge siden siste frostperiode?",
        "   - Akkumulering av fuktighet i vegdekke",
        "   - Sesongavhengige faktorer"
    ]
    
    for problem in problems:
        print(problem)
    
    print("\n🎯 FORESLÅTTE FYSISK REALISTISKE KRITERIER:")
    print("=" * 60)
    
    realistic_criteria = {
        "1. TEMPERATURKRITERIER": [
            "• Kritisk område: -3°C til +2°C (ikke 0-5°C!)",
            "• Is-fare: < -1°C + fuktighet",
            "• Rimfrost-fare: -2°C til 0°C + høy fuktighet + vindstille",
            "• Våt is-fare: 0°C til +1°C + nedbør + rask avkjøling"
        ],
        
        "2. FUKTIGHETSKRITERIER": [
            "• Rimfrost: ≥90% + vindstille forhold",
            "• Is-dannelse: ≥80% + temperatur < 0°C",
            "• Duggpunkt nær lufttemperatur (≤2°C forskjell)"
        ],
        
        "3. NEDBØRSKRITERIER": [
            "• Kan oppstå UTEN nedbør (rimfrost!)",
            "• Underkjølt regn: >0.1mm/h + temp ≤ 0°C",
            "• Smelting + refryzing: snø/is + temp-svingninger"
        ],
        
        "4. VINDKRITERIER (NYE!)": [
            "• Vindstille (≤2 m/s): Øker rimfrost-risiko",
            "• Moderat vind (2-5 m/s): Øker avkjøling",
            "• Sterk vind (>5 m/s): Kan hindre is-dannelse"
        ],
        
        "5. TIDSAVHENGIGE FAKTORER (NYE!)": [
            "• Nattetid (22-08): Høyest risiko",
            "• Temperaturfall >2°C/time: Kritisk",
            "• Timer siden solnedgang: Utstrålingsavkjøling"
        ],
        
        "6. SNØSTATUS": [
            "• Kan oppstå på BAR MARK (viktig!)",
            "• Tynt islag: 0-2cm er farligst",
            "• Eksisterende snø: bidrar til fuktighet ved smelting"
        ]
    }
    
    for category, criteria in realistic_criteria.items():
        print(f"\n{category}:")
        for criterion in criteria:
            print(f"  {criterion}")
    
    # Analyser faktiske data for å validere kriterier
    print(f"\n📊 DATAVALIDERING:")
    print("=" * 60)
    
    # Temperaturanalyse
    temp_data = df['air_temperature'].dropna()
    print(f"🌡️ TEMPERATURFORDELING:")
    print(f"  • Kvartiler: Q1={temp_data.quantile(0.25):.1f}°C, Median={temp_data.median():.1f}°C, Q3={temp_data.quantile(0.75):.1f}°C")
    print(f"  • Kritisk område (-3 til +2°C): {((temp_data >= -3) & (temp_data <= 2)).sum()} av {len(temp_data)} timer ({((temp_data >= -3) & (temp_data <= 2)).mean()*100:.1f}%)")
    print(f"  • Eksisterende område (0 til +5°C): {((temp_data >= 0) & (temp_data <= 5)).sum()} av {len(temp_data)} timer ({((temp_data >= 0) & (temp_data <= 5)).mean()*100:.1f}%)")
    
    # Fuktighetanalyse
    if 'relative_humidity' in df.columns:
        humidity_data = df['relative_humidity'].dropna()
        print(f"\n💧 FUKTIGHETFORDELING:")
        print(f"  • Høy fuktighet (≥85%): {(humidity_data >= 85).sum()} av {len(humidity_data)} timer ({(humidity_data >= 85).mean()*100:.1f}%)")
        print(f"  • Meget høy fuktighet (≥90%): {(humidity_data >= 90).sum()} av {len(humidity_data)} timer ({(humidity_data >= 90).mean()*100:.1f}%)")
    
    # Vindanalyse
    if 'wind_speed' in df.columns:
        wind_data = df['wind_speed'].dropna()
        print(f"\n💨 VINDFORDELING:")
        print(f"  • Vindstille (≤2 m/s): {(wind_data <= 2).sum()} av {len(wind_data)} timer ({(wind_data <= 2).mean()*100:.1f}%)")
        print(f"  • Moderat vind (2-5 m/s): {((wind_data > 2) & (wind_data <= 5)).sum()} av {len(wind_data)} timer ({((wind_data > 2) & (wind_data <= 5)).mean()*100:.1f}%)")
        print(f"  • Sterk vind (>5 m/s): {(wind_data > 5).sum()} av {len(wind_data)} timer ({(wind_data > 5).mean()*100:.1f}%)")
    
    print(f"\n🚨 HOVEDKONKLUSJON:")
    print("=" * 60)
    print("De eksisterende glatt vei-kriteriene har ALVORLIGE mangler:")
    print("1. 🎯 Temperaturområdet er ALT FOR BREDT")
    print("2. 🚫 Mangler vinddata - kritisk faktor!")
    print("3. 🌙 Ignorerer tidspunkt og utstrålingsavkjøling")
    print("4. 🛣️ Forutsetter snø på bakken - farlig antagelse!")
    print("5. 📉 Ignorerer temperaturgradienter og duggpunkt")
    print("6. ⏰ Mangler historisk kontekst")
    print("")
    print("RESULTAT: Eksisterende system kan MISSE farlige situasjoner")
    print("og gi FALSKE alarmer. Trenger fysisk realistisk redesign!")

def propose_improved_slippery_criteria():
    """Foreslår forbedrede, fysisk realistiske kriterier."""
    
    print(f"\n💡 FORBEDREDE GLATT VEI-KRITERIER:")
    print("=" * 60)
    
    improved_system = {
        "TYPE 1: RIMFROST": {
            "kriterier": [
                "• Temperatur: -2°C til 0°C",
                "• Luftfuktighet: ≥90%",
                "• Vindstyrke: ≤2 m/s (vindstille)",
                "• Klarvær eller lett overskyet",
                "• Nattetid eller tidlig morgen"
            ],
            "risiko": "HØY - 'Usynlig' fare, vanskeligt å oppdage"
        },
        
        "TYPE 2: IS-DANNELSE": {
            "kriterier": [
                "• Temperatur: ≤ -1°C",
                "• Luftfuktighet: ≥80%",
                "• Fuktighet på veibanen (snøsmelting, regn)",
                "• Rask temperaturfall (>1°C/time)"
            ],
            "risiko": "EKSTREM - Kompakt is, meget glatt"
        },
        
        "TYPE 3: UNDERKJØLT REGN/SLUDD": {
            "kriterier": [
                "• Temperatur: -1°C til +1°C",
                "• Nedbør: >0.1mm/h",
                "• Lufttemperatur nær frysepunktet",
                "• Kald veibane"
            ],
            "risiko": "EKSTREM - Øyeblikkelig is-dannelse"
        },
        
        "TYPE 4: REFRYZING": {
            "kriterier": [
                "• Tidligere smelting (temp >2°C)",
                "• Nå: temperatur ≤0°C",
                "• Fuktighet fra tidligere smelting",
                "• Utstrålingsavkjøling (natt)"
            ],
            "risiko": "HØY - Forutsigbar, men farlig"
        }
    }
    
    for ice_type, details in improved_system.items():
        print(f"\n{ice_type}:")
        for criterion in details["kriterier"]:
            print(f"  {criterion}")
        print(f"  → {details['risiko']}")
    
    print(f"\n🔧 IMPLEMENTERINGSSTRATEGI:")
    print("=" * 60)
    print("1. 📊 Samle manglende data (vind, duggpunkt, soldata)")
    print("2. 🧪 Test nye kriterier mot historiske hendelser")
    print("3. 🎯 Kalibrering per geografisk område")
    print("4. ⚡ Real-time overvåking av alle faktorer")
    print("5. 🚨 Trinnvise varselnivåer basert på type og intensitet")

def main():
    """Hovedfunksjon."""
    try:
        critical_slippery_road_analysis()
        propose_improved_slippery_criteria()
        
    except Exception as e:
        print(f"❌ Feil: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
