#!/usr/bin/env python3
"""
Rekalibrering av ML-grenseverdier til 8-10 dager for 2023-2024 sesongen
Basert på erfaringsmessig antall snøfokkdager
"""

import sys
from datetime import datetime

import pandas as pd

# Legg til src-mappe til path
sys.path.append('src')
sys.path.append('.')

try:
    from ml_snowdrift_detector import MLSnowdriftDetector
    ML_AVAILABLE = True
except ImportError:
    print("❌ Kan ikke importere ML-detektor")
    ML_AVAILABLE = False

def load_weather_data():
    """Last værdata for 2023-2024 sesongen"""
    try:
        # Last historiske data og filtrer for 2023-2024 sesongen
        df = pd.read_csv('data/raw/historical_data.csv')
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Omdøp for konsistens
        df = df.rename(columns={'timestamp': 'referenceTime'})

        # Filtrer for sesongen 2023-2024 (november til april)
        season_start = pd.to_datetime('2023-11-01')
        season_end = pd.to_datetime('2024-04-30')

        df_season = df[(df['referenceTime'] >= season_start) &
                      (df['referenceTime'] <= season_end)]

        print(f"✅ Lastet {len(df_season)} observasjoner for sesongen 2023-2024")
        print(f"   Periode: {df_season['referenceTime'].min()} til {df_season['referenceTime'].max()}")

        # Sjekk datatilgjengelighet
        temp_valid = df_season['air_temperature'].notna().sum()
        wind_valid = df_season['wind_speed'].notna().sum()
        snow_valid = df_season['surface_snow_thickness'].notna().sum()

        print(f"   Temperatur: {temp_valid} gyldige verdier")
        print(f"   Vindstyrke: {wind_valid} gyldige verdier")
        print(f"   Snødybde: {snow_valid} gyldige verdier")

        return df_season

    except FileNotFoundError:
        print("❌ Finner ikke historical_data.csv")
        return None
    except Exception as e:
        print(f"❌ Feil ved lasting av data: {e}")
        return None

def test_thresholds(df, wind_chill_thresh, wind_speed_thresh, temp_thresh=None, snow_thresh=None):
    """Test et sett med grenseverdier og tell antall alarmdager"""

    alerts = []

    for idx, row in df.iterrows():
        # Hent verdier
        temp = row.get('air_temperature', None)
        wind = row.get('wind_speed', None)
        snow = row.get('surface_snow_thickness', 0)

        if pd.isna(temp) or pd.isna(wind):
            continue

        # Beregn vindkjøling
        if temp <= 10 and wind >= 1.34:
            wind_chill = (13.12 + 0.6215 * temp -
                         11.37 * (wind * 3.6) ** 0.16 +
                         0.3965 * temp * (wind * 3.6) ** 0.16)
        else:
            wind_chill = temp

        # Test grenseverdier
        wind_chill_ok = wind_chill < wind_chill_thresh
        wind_speed_ok = wind > wind_speed_thresh
        temp_ok = temp < temp_thresh if temp_thresh else True
        snow_ok = snow > snow_thresh if snow_thresh else True

        # Kombiner kriterier
        if wind_chill_ok and wind_speed_ok and temp_ok and snow_ok:
            date = pd.to_datetime(row['referenceTime']).date()
            if date not in [alert['date'] for alert in alerts]:
                alerts.append({
                    'date': date,
                    'wind_chill': wind_chill,
                    'wind_speed': wind,
                    'temperature': temp,
                    'snow': snow
                })

    return alerts

def find_optimal_thresholds():
    """Finn grenseverdier som gir 8-10 alarmdager for 2023-2024"""

    print("=== REKALIBRERING TIL 8-10 ALARMDAGER ===")

    # Last data
    df = load_weather_data()
    if df is None:
        return

    print(f"Analyserer {len(df)} observasjoner (nov 2023 - apr 2024)")

    # Test ulike kombinasjoner av grenseverdier
    wind_chill_options = [-18, -16, -14, -12, -10, -8]
    wind_speed_options = [12, 10, 8, 6, 5]

    results = []

    print("\nTester ulike grenseverdier...")

    for wc_thresh in wind_chill_options:
        for ws_thresh in wind_speed_options:
            alerts = test_thresholds(df, wc_thresh, ws_thresh)
            num_days = len(alerts)

            # Kun vis resultater nær målet (8-10 dager)
            if 6 <= num_days <= 12:
                results.append({
                    'wind_chill_thresh': wc_thresh,
                    'wind_speed_thresh': ws_thresh,
                    'num_days': num_days,
                    'alerts': alerts
                })
                print(f"  Vindkjøling < {wc_thresh}°C + Vind > {ws_thresh} m/s = {num_days} dager")

    # Sorter etter hvor nær vi er målet (8-10 dager)
    results.sort(key=lambda x: abs(x['num_days'] - 9))  # 9 er midten av 8-10

    print("\n=== BESTE KOMBINASJONER ===")
    for i, result in enumerate(results[:5]):
        wc = result['wind_chill_thresh']
        ws = result['wind_speed_thresh']
        days = result['num_days']
        target_diff = abs(days - 9)

        print(f"\n{i+1}. Vindkjøling < {wc}°C + Vind > {ws} m/s")
        print(f"   Resultat: {days} alarmdager (avvik fra mål: {target_diff})")

        # Vis datoer for beste resultat
        if i == 0:
            print("   Alarmdatoene:")
            for alert in sorted(result['alerts'], key=lambda x: x['date']):
                date = alert['date']
                wc_val = alert['wind_chill']
                ws_val = alert['wind_speed']
                print(f"   • {date}: Vindkjøling {wc_val:.1f}°C, Vind {ws_val:.1f} m/s")

    # Returner beste resultat
    if results:
        best = results[0]
        print("\n🎯 ANBEFALT KALIBRERING:")
        print(f"   Vindkjøling-terskel: {best['wind_chill_thresh']}°C")
        print(f"   Vindstyrke-terskel: {best['wind_speed_thresh']} m/s")
        print(f"   Forventet alarmdager: {best['num_days']} (mål: 8-10)")

        return best
    else:
        print("❌ Fant ingen gode kombinasjoner")
        return None

if __name__ == "__main__":
    result = find_optimal_thresholds()

    if result:
        print("\n💾 Lagrer nye grenseverdier...")

        # Lagre resultatet
        import json
        calibration_result = {
            'target_season': '2023-2024',
            'target_days': '8-10',
            'actual_days': result['num_days'],
            'wind_chill_threshold': result['wind_chill_thresh'],
            'wind_speed_threshold': result['wind_speed_thresh'],
            'alert_dates': [alert['date'].isoformat() for alert in result['alerts']],
            'calibration_date': datetime.now().isoformat()
        }

        with open('data/analyzed/recalibrated_thresholds_8_10_days.json', 'w') as f:
            json.dump(calibration_result, f, indent=2)

        print("✅ Resultater lagret i data/analyzed/recalibrated_thresholds_8_10_days.json")
        print("\nKjør neste: Oppdater ml_snowdrift_detector.py med nye grenseverdier")
