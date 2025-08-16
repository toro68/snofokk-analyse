#!/usr/bin/env python3
"""
Test av ML slush/glatt vei-detektor med eksempeldata.
"""

import sys

sys.path.append('src')

from ml_slush_slippery_detector import MLSlushSlipperyDetector


def test_ml_detector():
    """Test ML-detektoren med forskjellige scenarioer."""

    # Last modeller
    model_file = 'data/models/slush_slippery_models.joblib'
    detector = MLSlushSlipperyDetector(model_file)

    if not detector.models:
        print("ML-modeller ikke tilgjengelig - tester kun domain rules")

    # Test scenarioer
    scenarios = [
        {
            'name': 'Slush-scenario (0°C + regn)',
            'data': {
                'temp_mean': 0.5,
                'temp_min': -0.5,
                'temp_max': 1.5,
                'precip_total': 15.0,
                'precip_max_hourly': 3.0,
                'wind_max': 8.0,
                'snow_depth': 10.0,
                'recent_snow': True
            }
        },
        {
            'name': 'Glatt vei (underkjølt regn)',
            'data': {
                'temp_mean': -2.0,
                'temp_min': -3.0,
                'temp_max': -0.5,
                'precip_total': 5.0,
                'precip_max_hourly': 2.0,
                'wind_max': 12.0,
                'snow_depth': 0.0,
                'recent_snow': False
            }
        },
        {
            'name': 'Svarte veier (regn fjerner snø)',
            'data': {
                'temp_mean': 5.0,
                'temp_min': 3.0,
                'temp_max': 7.0,
                'precip_total': 25.0,
                'precip_max_hourly': 8.0,
                'wind_max': 15.0,
                'snow_depth': 0.0,  # Snø er fjernet
                'recent_snow': False
            }
        },
        {
            'name': 'Fersk snø (naturlig anti-slip)',
            'data': {
                'temp_mean': -5.0,
                'temp_min': -7.0,
                'temp_max': -3.0,
                'precip_total': 0.0,
                'precip_max_hourly': 0.0,
                'wind_max': 5.0,
                'snow_depth': 15.0,
                'recent_snow': True
            }
        }
    ]

    print("=== TEST AV ML SLUSH/GLATT VEI DETEKTOR ===\n")

    for scenario in scenarios:
        print(f"SCENARIO: {scenario['name']}")
        print(f"Værdata: {scenario['data']}")

        try:
            result = detector.predict_risk(scenario['data'])

            print("RESULTAT:")
            print(f"  Slush risiko: {result['slush_risk']:.3f}")
            print(f"  Glatt vei risiko: {result['slippery_risk']:.3f}")
            print(f"  Anbefaling: {result['recommendation']}")
            print(f"  Begrunnelse: {result['reasoning']}")
            print(f"  Metadata: {result['metadata']}")

        except Exception as e:
            print(f"  FEIL: {e}")

        print("-" * 60)

if __name__ == "__main__":
    test_ml_detector()
