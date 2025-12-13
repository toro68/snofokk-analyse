#!/usr/bin/env python3
"""
Enkel sammenligning av optimaliserte parametere
"""
import json
from pathlib import Path

from src.config import settings


def compare_parameters():
    """Sammenlign original vs optimaliserte parametere"""

    config_file = Path(__file__).parent.parent.parent / 'archive' / 'legacy_config' / 'optimized_snowdrift_config.json'

    try:
        with open(config_file, encoding='utf-8') as f:
            optimized = json.load(f)
    except FileNotFoundError:
        print("Optimalisert konfigurasjon ikke funnet")
        return

    # Nåværende standardverdier (hentet fra src/config.py)
    sd = settings.snowdrift
    current = {
        'min_wind_speed': float(sd.wind_speed_warning),
        'max_temperature': float(sd.temperature_max),
        'min_snow_depth': float(sd.snow_depth_min_cm),
        'min_duration': int(sd.interval_hours)
    }

    # Optimaliserte verdier
    opt_config = optimized['snowdrift_detection']
    opt_values = {
        'min_wind_speed': opt_config['wind']['min_speed_ms'],
        'max_temperature': opt_config['temperature']['max_temp_c'],
        'min_snow_depth': opt_config['snow']['min_depth_cm'],
        'min_duration': optimized['detection_rules']['min_duration_hours']
    }

    print("PARAMETER-OPTIMALISERING SAMMENDRAG")
    print("=" * 60)
    print("Basert på 246 historiske snøfokk-hendelser fra 3 vintre")
    print()

    print("PARAMETERE:")
    print()

    # Vind
    wind_change = ((opt_values['min_wind_speed'] - current['min_wind_speed']) / current['min_wind_speed']) * 100
    print("MINIMUM VINDSTYRKE:")
    print(f"   Original:     {current['min_wind_speed']} m/s")
    print(f"   Optimalisert: {opt_values['min_wind_speed']} m/s")
    print(f"   Endring:      {wind_change:+.1f}% (strengere krav)")
    print()

    # Temperatur
    temp_change = opt_values['max_temperature'] - current['max_temperature']
    print("MAKSIMAL TEMPERATUR:")
    print(f"   Original:     {current['max_temperature']}°C")
    print(f"   Optimalisert: {opt_values['max_temperature']}°C")
    print(f"   Endring:      {temp_change:+.1f}°C (kaldere krav)")
    print()

    # Snødybde
    snow_change = ((opt_values['min_snow_depth'] - current['min_snow_depth']) / current['min_snow_depth']) * 100
    print("MINIMUM SNØDYBDE:")
    print(f"   Original:     {current['min_snow_depth']} cm")
    print(f"   Optimalisert: {opt_values['min_snow_depth']:.1f} cm")
    print(f"   Endring:      {snow_change:+.1f}% (krever mer snø)")
    print()

    # Varighet
    duration_change = opt_values['min_duration'] - current['min_duration']
    print("MINIMUM VARIGHET:")
    print(f"   Original:     {current['min_duration']} timer")
    print(f"   Optimalisert: {opt_values['min_duration']} timer")
    print(f"   Endring:      {duration_change:+d} timer")
    print()

    print("HOVEDFUNN:")
    print("   - Snøfokk krever sterkere vind enn antatt")
    print("   - Snøfokk krever kaldere temperaturer enn antatt")
    print("   - Snøfokk krever mer snø enn antatt")
    print("   • Kortere hendelser (1 time) kan være relevante")
    print()

    print("ANBEFALING:")
    print("   - Implementer optimaliserte parametere gradvis")
    print("   - Overvåk resultater og juster etter behov")
    print("   - Oppdater årlig basert på ny historisk data")
    print()

    # Seasonjusteringer
    seasonal = optimized['seasonal_adjustments']
    print("SESONGMESSIGE JUSTERINGER:")
    for season, config in seasonal.items():
        months = ', '.join(str(m) for m in config['months'])
        print(f"   {season}: Måneder {months} (faktor: {config['snow_depth_multiplier']})")

    print()
    print(f"Full konfigurasjon: {config_file}")

if __name__ == '__main__':
    compare_parameters()
