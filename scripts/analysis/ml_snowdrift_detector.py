#!/usr/bin/env python3
"""
Automatisk snøfokk-varslingssystem basert på ML-optimaliserte grenseverdier.
Implementerer ML-identifiserte terskelverdier og kombinasjonsregler.
"""

import json
import logging
from datetime import datetime

# Logging oppsett
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MLBasedSnowDriftDetector:
    """
    ML-basert snøfokk-detektor som bruker optimaliserte grenseverdier
    og kombinasjonsregler identifisert gjennom maskinlæring.
    """

    def __init__(self, threshold_file: str = "data/analyzed/ml_threshold_optimization_results.json"):
        """Initialiserer detektor med ML-optimaliserte parametere."""
        self.load_ml_thresholds(threshold_file)
        self.setup_detection_rules()

    def load_ml_thresholds(self, threshold_file: str):
        """Laster ML-optimaliserte terskelverdier."""
        try:
            with open(threshold_file, encoding='utf-8') as f:
                self.ml_results = json.load(f)

            # Ekstrahér kritiske terskelverdier
            self.critical_thresholds = self.ml_results['recommendations']['critical_thresholds']
            self.warning_thresholds = self.ml_results['recommendations']['warning_thresholds']
            self.combination_rules = self.ml_results['recommendations']['combination_rules']

            logger.info(f"Lastet ML-terskelverdier fra {threshold_file}")

        except Exception as e:
            logger.error(f"Feil ved lasting av ML-terskelverdier: {e}")
            self._use_fallback_thresholds()

    def _use_fallback_thresholds(self):
        """Fallback-terskelverdier hvis ML-resultater ikke er tilgjengelige."""
        self.critical_thresholds = {
            'wind_chill': {'value': 3.9, 'importance': 0.731},
            'wind_speed': {'value': 2.0, 'importance': 0.217},
            'air_temperature': {'value': 4.1, 'importance': 0.038}
        }
        self.warning_thresholds = {
            'wind_chill': {'value': 1.9},
            'wind_speed': {'value': 0.0},
            'air_temperature': {'value': 2.2}
        }
        self.combination_rules = {}

    def setup_detection_rules(self):
        """Setter opp deteksjonsregler basert på ML-analysen."""

        # ML-optimaliserte enkeltparameter-regler
        self.parameter_rules = {
            'wind_chill_critical': {
                'parameter': 'wind_chill',
                'threshold': self.critical_thresholds.get('wind_chill', {}).get('value', 3.9),
                'operator': '<',
                'risk_level': 'HIGH',
                'importance': 0.731,
                'description': 'Kritisk vindkjøling (ML-optimalisert)'
            },
            'wind_speed_critical': {
                'parameter': 'wind_speed',
                'threshold': self.critical_thresholds.get('wind_speed', {}).get('value', 2.0),
                'operator': '>',
                'risk_level': 'HIGH',
                'importance': 0.217,
                'description': 'Kritisk vindstyrke (ML-optimalisert)'
            },
            'wind_chill_warning': {
                'parameter': 'wind_chill',
                'threshold': self.warning_thresholds.get('wind_chill', {}).get('value', 1.9),
                'operator': '<',
                'risk_level': 'MEDIUM',
                'importance': 0.731,
                'description': 'Advarsel vindkjøling (ML-optimalisert)'
            }
        }

        # ML-identifiserte kombinasjonsregler
        self.multi_parameter_rules = {
            'high_wind_frost_snow': {
                'conditions': [
                    ('wind_speed', '>', 8.3),
                    ('air_temperature', '<', -1.6),
                    ('surface_snow_thickness', '>', 0.0295)  # 29.5mm i meter
                ],
                'risk_level': 'HIGH',
                'confidence': 1.0,
                'description': 'ML-regel: Høy vind + frost + snø'
            },
            'medium_wind_cold': {
                'conditions': [
                    ('wind_speed', 'between', 2.1, 6.7),
                    ('air_temperature', '<', -5.3)
                ],
                'risk_level': 'MEDIUM',
                'confidence': 1.0,
                'description': 'ML-regel: Medium vind + kulde'
            }
        }

    def calculate_wind_chill(self, temperature: float, wind_speed: float) -> float:
        """Beregner vindkjøling."""
        if temperature <= 10 and wind_speed >= 1.34:  # 4.8 km/h = 1.34 m/s
            return (13.12 + 0.6215 * temperature -
                   11.37 * (wind_speed * 3.6) ** 0.16 +
                   0.3965 * temperature * (wind_speed * 3.6) ** 0.16)
        return temperature

    def evaluate_single_parameters(self, weather_data: dict) -> list[dict]:
        """Evaluerer enkeltparameter-regler."""
        alerts = []

        # Beregn vindkjøling hvis ikke allerede tilstede
        if 'wind_chill' not in weather_data and 'air_temperature' in weather_data and 'wind_speed' in weather_data:
            weather_data['wind_chill'] = self.calculate_wind_chill(
                weather_data['air_temperature'],
                weather_data['wind_speed']
            )

        for rule_name, rule in self.parameter_rules.items():
            param_value = weather_data.get(rule['parameter'])

            if param_value is not None:
                threshold = rule['threshold']
                operator = rule['operator']

                triggered = False
                if operator == '>' and param_value > threshold:
                    triggered = True
                elif operator == '<' and param_value < threshold:
                    triggered = True
                elif operator == '>=' and param_value >= threshold:
                    triggered = True
                elif operator == '<=' and param_value <= threshold:
                    triggered = True

                if triggered:
                    alerts.append({
                        'rule_name': rule_name,
                        'parameter': rule['parameter'],
                        'value': param_value,
                        'threshold': threshold,
                        'risk_level': rule['risk_level'],
                        'importance': rule['importance'],
                        'description': rule['description'],
                        'type': 'single_parameter'
                    })

        return alerts

    def evaluate_combination_rules(self, weather_data: dict) -> list[dict]:
        """Evaluerer kombinasjonsregler."""
        alerts = []

        for rule_name, rule in self.multi_parameter_rules.items():
            all_conditions_met = True
            condition_details = []

            for condition in rule['conditions']:
                param, operator, threshold = condition[:3]
                param_value = weather_data.get(param)

                if param_value is None:
                    all_conditions_met = False
                    break

                condition_met = False
                if operator == '>' and param_value > threshold:
                    condition_met = True
                elif operator == '<' and param_value < threshold:
                    condition_met = True
                elif operator == 'between' and len(condition) == 4:
                    min_val, max_val = threshold, condition[3]
                    condition_met = min_val <= param_value <= max_val

                condition_details.append({
                    'parameter': param,
                    'value': param_value,
                    'operator': operator,
                    'threshold': threshold,
                    'met': condition_met
                })

                if not condition_met:
                    all_conditions_met = False

            if all_conditions_met:
                alerts.append({
                    'rule_name': rule_name,
                    'risk_level': rule['risk_level'],
                    'confidence': rule['confidence'],
                    'description': rule['description'],
                    'conditions': condition_details,
                    'type': 'combination_rule'
                })

        return alerts

    def detect_snowdrift_risk(self, weather_data: dict) -> dict:
        """
        Hovedfunksjon for å detektere snøfokk-risiko basert på ML-optimaliserte regler.
        
        Args:
            weather_data: Dictionary med værdata
            
        Returns:
            Dictionary med deteksjonsresultater
        """

        # Evaluer enkeltparameter-regler
        single_param_alerts = self.evaluate_single_parameters(weather_data)

        # Evaluer kombinasjonsregler
        combination_alerts = self.evaluate_combination_rules(weather_data)

        # Kombiner alle alerts
        all_alerts = single_param_alerts + combination_alerts

        # Bestem samlet risiko-nivå
        risk_levels = [alert['risk_level'] for alert in all_alerts]

        if 'HIGH' in risk_levels:
            overall_risk = 'HIGH'
        elif 'MEDIUM' in risk_levels:
            overall_risk = 'MEDIUM'
        else:
            overall_risk = 'LOW'

        # Beregn confidence score basert på viktighet av triggered regler
        confidence_score = 0.0
        for alert in single_param_alerts:
            confidence_score += alert.get('importance', 0.1)

        for alert in combination_alerts:
            confidence_score += alert.get('confidence', 0.5)

        confidence_score = min(confidence_score, 1.0)  # Cap at 1.0

        return {
            'timestamp': datetime.now().isoformat(),
            'overall_risk': overall_risk,
            'confidence_score': confidence_score,
            'triggered_alerts': len(all_alerts),
            'single_parameter_alerts': single_param_alerts,
            'combination_alerts': combination_alerts,
            'weather_data': weather_data,
            'ml_based': True
        }

    def generate_alert_message(self, detection_result: dict) -> str:
        """Genererer menneskelesbart alert-message."""

        risk = detection_result['overall_risk']
        confidence = detection_result['confidence_score']
        alerts = detection_result['triggered_alerts']

        message = "🌨️ SNØFOKK-VARSLING (ML-basert)\n"
        message += f"Risk-nivå: {risk}\n"
        message += f"Confidence: {confidence:.1%}\n"
        message += f"Aktive alerts: {alerts}\n\n"

        # Detaljer om enkeltparameter-alerts
        single_alerts = detection_result['single_parameter_alerts']
        if single_alerts:
            message += "📊 KRITISKE PARAMETERE:\n"
            for alert in single_alerts:
                param = alert['parameter']
                value = alert['value']
                threshold = alert['threshold']
                message += f"• {param}: {value:.1f} (grense: {threshold:.1f})\n"

        # Detaljer om kombinasjonsregler
        combo_alerts = detection_result['combination_alerts']
        if combo_alerts:
            message += "\n🔗 AKTIVE KOMBINASJONSREGLER:\n"
            for alert in combo_alerts:
                message += f"• {alert['description']}\n"
                message += f"  Confidence: {alert['confidence']:.1%}\n"

        return message


def test_ml_detector():
    """Test ML-basert snøfokk-detektor med eksempeldata."""

    print("🧪 TESTING ML-BASERT SNØFOKK-DETEKTOR")
    print("=" * 50)

    detector = MLBasedSnowDriftDetector()

    # Test-scenarier
    test_scenarios = [
        {
            'name': 'Høy risiko scenario',
            'data': {
                'wind_speed': 9.0,
                'air_temperature': -2.0,
                'surface_snow_thickness': 0.05,
                'relative_humidity': 80.0
            }
        },
        {
            'name': 'Medium risiko scenario',
            'data': {
                'wind_speed': 4.0,
                'air_temperature': -6.0,
                'surface_snow_thickness': 0.02,
                'relative_humidity': 70.0
            }
        },
        {
            'name': 'Lav risiko scenario',
            'data': {
                'wind_speed': 1.0,
                'air_temperature': 2.0,
                'surface_snow_thickness': 0.0,
                'relative_humidity': 60.0
            }
        }
    ]

    for scenario in test_scenarios:
        print(f"\n🔬 {scenario['name'].upper()}")
        print("-" * 30)

        result = detector.detect_snowdrift_risk(scenario['data'])
        message = detector.generate_alert_message(result)

        print(message)


def main():
    """Hovedfunksjon."""
    test_ml_detector()


if __name__ == "__main__":
    main()
