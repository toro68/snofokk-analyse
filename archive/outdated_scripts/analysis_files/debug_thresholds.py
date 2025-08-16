#!/usr/bin/env python3
"""
Test av ML-optimaliserte grenseverdier med debug-informasjon
"""

import sys

sys.path.append('src')


from ml_snowdrift_detector import MLSnowdriftDetector


def debug_ml_thresholds():
    print("=== DEBUG ML-OPTIMALISERTE GRENSEVERDIER ===")

    # Opprett ML-detektor
    detector = MLSnowdriftDetector()

    print("📊 FAKTISKE GRENSEVERDIER I OBJEKT:")
    print(f"- Vindkjøling: < {detector.critical_thresholds['wind_chill']}°C")
    print(f"- Vindstyrke: > {detector.critical_thresholds['wind_speed']} m/s")
    print(f"- Temperatur: < {detector.critical_thresholds['air_temperature']}°C")
    print(f"- Snødybde: > {detector.critical_thresholds['surface_snow_thickness']:.2f}m")

    print("\n📊 ADVARSEL-GRENSEVERDIER:")
    print(f"- Vindkjøling: < {detector.warning_thresholds['wind_chill']}°C")
    print(f"- Vindstyrke: > {detector.warning_thresholds['wind_speed']} m/s")
    print(f"- Temperatur: < {detector.warning_thresholds['air_temperature']}°C")
    print(f"- Snødybde: > {detector.warning_thresholds['surface_snow_thickness']:.2f}m")

    print("\n📊 KOMBINASJONSREGLER:")
    print(f"- Høy risiko: Vindkjøling < {detector.combination_rules['high_risk_combo']['wind_chill_threshold']}°C og vind > {detector.combination_rules['high_risk_combo']['wind_speed_threshold']} m/s")
    print(f"- Medium risiko: Vindkjøling < {detector.combination_rules['medium_risk_combo']['wind_chill_threshold']}°C og vind > {detector.combination_rules['medium_risk_combo']['wind_speed_threshold']} m/s")

if __name__ == "__main__":
    debug_ml_thresholds()
