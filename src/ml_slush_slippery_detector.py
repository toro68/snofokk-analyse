#!/usr/bin/env python3
"""
Integrert slush- og glatt vei-detektor basert på ML-kriterier.
Kombinerer domain ekspertise med maskinlæring.
"""

import json
import os

import joblib
import numpy as np


class MLSlushSlipperyDetector:
    """ML-basert detektor for slush og glatt vei med domain ekspertise."""

    def __init__(self, model_file: str = None):
        self.models = None
        self.criteria = None
        self.feature_cols = [
            'temp_mean', 'temp_min', 'temp_max', 'temp_range',
            'precip_total', 'precip_max_hourly',
            'wind_max', 'wind_chill_factor',
            'around_freezing', 'slush_temp_range', 'precip_with_mild_temp',
            'recent_snowfall', 'freeze_thaw_cycle', 'rain_on_snow_risk'
        ]

        if model_file and os.path.exists(model_file):
            self.load_models(model_file)

    def load_models(self, model_file: str):
        """Last trente ML-modeller."""
        try:
            self.models = joblib.load(model_file)
            print(f"Lastet ML-modeller fra: {model_file}")

            # Last tilhørende kriterier
            criteria_file = model_file.replace('models', 'criteria').replace('.joblib', '.json')
            if os.path.exists(criteria_file):
                with open(criteria_file, encoding='utf-8') as f:
                    self.criteria = json.load(f)
                print(f"Lastet kriterier fra: {criteria_file}")
        except Exception as e:
            print(f"Feil ved lasting av modeller: {e}")

    def prepare_features(self, weather_data: dict) -> dict:
        """Forbered features for ML-predikering."""
        # Basis værdata
        temp_mean = weather_data.get('temp_mean', 0)
        temp_min = weather_data.get('temp_min', temp_mean)
        temp_max = weather_data.get('temp_max', temp_mean)
        precip_total = weather_data.get('precip_total', 0)
        precip_max_hourly = weather_data.get('precip_max_hourly', precip_total)
        wind_max = weather_data.get('wind_max', 0)

        # Engineered features
        features = {
            'temp_mean': temp_mean,
            'temp_min': temp_min,
            'temp_max': temp_max,
            'temp_range': temp_max - temp_min,
            'precip_total': precip_total,
            'precip_max_hourly': precip_max_hourly,
            'wind_max': wind_max,
            'wind_chill_factor': temp_mean - (wind_max * 0.2) if wind_max > 5 else temp_mean,
            'around_freezing': 1 if (temp_min <= 2 and temp_max >= -2) else 0,
            'slush_temp_range': 1 if (-1 <= temp_mean <= 4) else 0,
            'precip_with_mild_temp': precip_total if (-1 <= temp_mean <= 4) else 0,
            'recent_snowfall': 1 if (temp_mean < 1 and precip_total > 2) else 0,
            'freeze_thaw_cycle': 1 if (temp_max > 2 and temp_min < -1) else 0,
            'rain_on_snow_risk': 1 if (0 < temp_mean < 3 and precip_total > 1) else 0
        }

        return features

    def predict_slush_risk(self, weather_data: dict) -> dict:
        """Prediker slush-risiko basert på ML og domain rules."""
        features = self.prepare_features(weather_data)

        # Domain-baserte regler først
        domain_risk = self._assess_slush_domain_rules(features)

        # ML-predikering hvis modeller er tilgjengelige
        ml_risk = self._predict_slush_ml(features) if self.models else {}

        # Kombiner resultater
        return self._combine_slush_predictions(domain_risk, ml_risk, features)

    def predict_slippery_risk(self, weather_data: dict) -> dict:
        """Prediker glatt vei-risiko basert på ML og domain rules."""
        features = self.prepare_features(weather_data)

        # Domain-baserte regler først
        domain_risk = self._assess_slippery_domain_rules(features)

        # ML-predikering hvis modeller er tilgjengelige
        ml_risk = self._predict_slippery_ml(features) if self.models else {}

        # Kombiner resultater
        return self._combine_slippery_predictions(domain_risk, ml_risk, features)

    def _assess_slush_domain_rules(self, features: dict) -> dict:
        """Vurder slush-risiko basert på domain ekspertise."""
        temp_mean = features['temp_mean']
        precip_total = features['precip_total']
        recent_snowfall = features['recent_snowfall']

        risk_level = "Lav"
        confidence = 0.0
        reasoning = []

        # Hovedkriterier for slush
        if -1 <= temp_mean <= 4 and precip_total > 0:
            if recent_snowfall == 1:
                risk_level = "Lav"
                confidence = 0.2
                reasoning.append("Nysnø reduserer slush-risiko (naturlig strøing)")
            else:
                if 0 <= temp_mean <= 2 and precip_total > 5:
                    risk_level = "Høy"
                    confidence = 0.9
                    reasoning.append("Ideelle forhold for slush-dannelse")
                elif precip_total > 1:
                    risk_level = "Moderat"
                    confidence = 0.6
                    reasoning.append("Moderat slush-risiko")
                else:
                    risk_level = "Lav"
                    confidence = 0.3
                    reasoning.append("Lav nedbør, begrenset slush-risiko")

        return {
            'risk_level': risk_level,
            'confidence': confidence,
            'reasoning': reasoning,
            'method': 'domain_rules'
        }

    def _assess_slippery_domain_rules(self, features: dict) -> dict:
        """Vurder glatt vei-risiko basert på domain ekspertise."""
        temp_mean = features['temp_mean']
        precip_total = features['precip_total']
        recent_snowfall = features['recent_snowfall']
        freeze_thaw = features['freeze_thaw_cycle']
        rain_on_snow = features['rain_on_snow_risk']

        risk_level = "Lav"
        confidence = 0.0
        reasoning = []

        # VIKTIG: Nysnø beskytter mot glatthet
        if recent_snowfall == 1:
            risk_level = "Lav"
            confidence = 0.8
            reasoning.append("Nysnø fungerer som naturlig strøing")
            return {
                'risk_level': risk_level,
                'confidence': confidence,
                'reasoning': reasoning,
                'method': 'domain_rules',
                'salting_needed': False,
                'salting_reason': 'Nysnø gir naturlig beskyttelse'
            }

        # Høyrisiko scenarioer
        if freeze_thaw == 1:
            risk_level = "Høy"
            confidence = 0.9
            reasoning.append("Tining/frysing-syklus skaper klink is")
        elif rain_on_snow == 1:
            risk_level = "Høy"
            confidence = 0.8
            reasoning.append("Regn på snø skaper glatt underlag")
        elif temp_mean < 0 and precip_total > 0:
            risk_level = "Moderat"
            confidence = 0.6
            reasoning.append("Nedbør ved minusgrader kan skape is")

        # Vurder strøingsbehov
        salting_needed = risk_level in ["Høy", "Moderat"] and recent_snowfall == 0
        salting_reason = "Effektivt på klink is" if salting_needed else "Ikke nødvendig"

        return {
            'risk_level': risk_level,
            'confidence': confidence,
            'reasoning': reasoning,
            'method': 'domain_rules',
            'salting_needed': salting_needed,
            'salting_reason': salting_reason
        }

    def _predict_slush_ml(self, features: dict) -> dict:
        """ML-predikering av slush-risiko."""
        try:
            # Forbered feature array
            feature_array = np.array([[features[col] for col in self.feature_cols]])

            # Standardiser
            feature_scaled = self.models['scaler'].transform(feature_array)

            # Prediker
            slush_prob = self.models['slush_model'].predict_proba(feature_scaled)[0, 1]

            # Anvend optimal terskel
            threshold = self.criteria['optimal_thresholds']['slush_model']['probability_threshold']

            if slush_prob >= threshold:
                risk_level = "Høy" if slush_prob > 0.8 else "Moderat"
            else:
                risk_level = "Lav"

            return {
                'risk_level': risk_level,
                'probability': slush_prob,
                'threshold': threshold,
                'confidence': slush_prob,
                'method': 'ml_model'
            }
        except Exception as e:
            print(f"ML-predikering feilet: {e}")
            return {}

    def _predict_slippery_ml(self, features: dict) -> dict:
        """ML-predikering av glatt vei-risiko."""
        try:
            # Forbered feature array
            feature_array = np.array([[features[col] for col in self.feature_cols]])

            # Standardiser
            feature_scaled = self.models['scaler'].transform(feature_array)

            # Prediker
            slippery_prob = self.models['slippery_model'].predict_proba(feature_scaled)[0, 1]

            # Anvend optimal terskel
            threshold = self.criteria['optimal_thresholds']['slippery_road_model']['probability_threshold']

            if slippery_prob >= threshold:
                risk_level = "Høy" if slippery_prob > 0.8 else "Moderat"
            else:
                risk_level = "Lav"

            return {
                'risk_level': risk_level,
                'probability': slippery_prob,
                'threshold': threshold,
                'confidence': slippery_prob,
                'method': 'ml_model'
            }
        except Exception as e:
            print(f"ML-predikering feilet: {e}")
            return {}

    def _combine_slush_predictions(self, domain_risk: dict, ml_risk: dict, features: dict) -> dict:
        """Kombiner domain rules og ML for slush-predikering."""

        # Start med domain rules
        result = domain_risk.copy()

        # Legg til ML hvis tilgjengelig
        if ml_risk:
            # Bruk høyeste risiko
            domain_score = {'Lav': 1, 'Moderat': 2, 'Høy': 3}.get(domain_risk['risk_level'], 0)
            ml_score = {'Lav': 1, 'Moderat': 2, 'Høy': 3}.get(ml_risk['risk_level'], 0)

            if ml_score > domain_score:
                result['risk_level'] = ml_risk['risk_level']
                result['confidence'] = (domain_risk['confidence'] + ml_risk['confidence']) / 2
                result['method'] = 'combined'
                result['ml_probability'] = ml_risk['probability']
            else:
                result['ml_probability'] = ml_risk.get('probability', 0)

        # Legg til spesifikke råd
        if features['recent_snowfall'] == 1:
            result['recommendation'] = "Ingen handling nødvendig - nysnø beskytter"
        elif result['risk_level'] == "Høy":
            result['recommendation'] = "Vurder slush-fjerning"
        else:
            result['recommendation'] = "Monitorér forhold"

        return result

    def _combine_slippery_predictions(self, domain_risk: dict, ml_risk: dict, features: dict) -> dict:
        """Kombiner domain rules og ML for glatt vei-predikering."""

        # Start med domain rules (prioritert pga nysnø-logikk)
        result = domain_risk.copy()

        # Legg til ML hvis tilgjengelig og ikke nysnø
        if ml_risk and features['recent_snowfall'] == 0:
            domain_score = {'Lav': 1, 'Moderat': 2, 'Høy': 3}.get(domain_risk['risk_level'], 0)
            ml_score = {'Lav': 1, 'Moderat': 2, 'Høy': 3}.get(ml_risk['risk_level'], 0)

            if ml_score > domain_score:
                result['risk_level'] = ml_risk['risk_level']
                result['confidence'] = (domain_risk['confidence'] + ml_risk['confidence']) / 2
                result['method'] = 'combined'
                result['ml_probability'] = ml_risk['probability']
            else:
                result['ml_probability'] = ml_risk.get('probability', 0)
        elif ml_risk:
            result['ml_probability'] = ml_risk.get('probability', 0)

        # Spesifikke anbefalinger basert på nysnø-innsikten
        if features['recent_snowfall'] == 1:
            result['recommendation'] = "Ingen strøing nødvendig - nysnø fungerer som naturlig strøing"
        elif result.get('salting_needed', False):
            result['recommendation'] = f"Strøing anbefalt - {result.get('salting_reason', '')}"
        else:
            result['recommendation'] = "Monitorér forhold"

        return result

    def predict_risk(self, weather_data: dict) -> dict:
        """Hovedmetode for å predikere slush og glatt vei risiko."""

        # Prediker begge risiko-typer
        slush_result = self.predict_slush_risk(weather_data)
        slippery_result = self.predict_slippery_risk(weather_data)

        # Kombiner resultater
        combined_result = {
            'slush_risk': slush_result.get('confidence', 0),
            'slippery_risk': slippery_result.get('confidence', 0),
            'recommendation': self._get_combined_recommendation(slush_result, slippery_result, weather_data),
            'reasoning': self._get_combined_reasoning(slush_result, slippery_result, weather_data),
            'metadata': {
                'slush_details': slush_result,
                'slippery_details': slippery_result,
                'domain_rules_applied': True,
                'ml_models_available': self.models is not None
            }
        }

        return combined_result

    def _get_combined_recommendation(self, slush_result: dict, slippery_result: dict, weather_data: dict) -> str:
        """Generer kombinert anbefaling basert på alle risikofaktorer."""

        # Sjekk for nysnø først (naturlig anti-slip)
        if weather_data.get('recent_snow', False) and weather_data.get('temp_mean', 0) < 0:
            return "Ingen strøing nødvendig - fersk snø fungerer som naturlig anti-slip"

        # Sjekk for svarte veier (snø fjernet av regn/mildvær)
        if (weather_data.get('temp_mean', 0) > 3 and
            weather_data.get('precip_total', 0) > 10 and
            weather_data.get('snow_depth', 0) == 0):
            return "Ingen strøing nødvendig - svarte veier, snøkappe fjernet av regn"

        # Høy slush-risiko
        if slush_result.get('confidence', 0) > 0.7:
            return "Slush-fjerning anbefalt - regn/mildvær på snø skaper farlige forhold"

        # Høy glatt vei-risiko
        if slippery_result.get('confidence', 0) > 0.7:
            return "Strøing anbefalt - høy risiko for glatte veier"

        # Moderat risiko
        if max(slush_result.get('confidence', 0), slippery_result.get('confidence', 0)) > 0.5:
            return "Økt overvåking anbefalt - moderat risiko for vanskelige kjøreforhold"

        return "Normale kjøreforhold - rutinemessig overvåking"

    def _get_combined_reasoning(self, slush_result: dict, slippery_result: dict, weather_data: dict) -> str:
        """Generer begrunnelse for kombinert vurdering."""

        reasons = []

        # Temperatur-analyse
        temp = weather_data.get('temp_mean', 0)
        if temp > 3:
            reasons.append("Mildvær fjerner snøkappe")
        elif -1 <= temp <= 1:
            reasons.append("Temperatur nær frysepunktet øker slush-risiko")
        elif temp < -5:
            reasons.append("Kaldt vær reduserer slush-risiko")

        # Nedbør-analyse
        precip = weather_data.get('precip_total', 0)
        if precip > 15:
            reasons.append("Mye nedbør øker risiko")
        elif precip > 5:
            reasons.append("Moderat nedbør")

        # Snø-analyse
        if weather_data.get('recent_snow', False):
            reasons.append("Fersk snø gir naturlig anti-slip effekt")
        elif weather_data.get('snow_depth', 0) == 0:
            reasons.append("Ingen snøkappe på veiene")

        # ML-tillegg hvis tilgjengelig
        if self.models and len(reasons) == 0:
            reasons.append("ML-basert vurdering anvendt")

        return "; ".join(reasons) if reasons else "Normale værforhold"

def test_detector():
    """Test ML-basert detektor med eksempeldata."""
    print("=== TEST AV ML-BASERT SLUSH/GLATT VEI DETEKTOR ===\n")

    # Last siste modell
    model_files = [f for f in os.listdir('data/analyzed') if f.startswith('ml_slush_slippery_models')]
    if not model_files:
        print("Ingen ML-modeller funnet. Kjør først: python scripts/analysis/ml_slush_slippery_classifier.py")
        return

    latest_model = f"data/analyzed/{sorted(model_files)[-1]}"
    detector = MLSlushSlipperyDetector(latest_model)

    # Test scenarioer
    test_scenarios = [
        {
            'name': 'Slush-risiko (mildvær + regn)',
            'weather': {'temp_mean': 1.5, 'temp_min': 0, 'temp_max': 3, 'precip_total': 8, 'wind_max': 3}
        },
        {
            'name': 'Nysnø beskyttelse',
            'weather': {'temp_mean': -1, 'temp_min': -3, 'temp_max': 0, 'precip_total': 5, 'wind_max': 2}
        },
        {
            'name': 'Freeze-thaw risiko',
            'weather': {'temp_mean': 0.5, 'temp_min': -2, 'temp_max': 4, 'precip_total': 1, 'wind_max': 5}
        },
        {
            'name': 'Stabilt kaldt vær',
            'weather': {'temp_mean': -8, 'temp_min': -12, 'temp_max': -5, 'precip_total': 0, 'wind_max': 8}
        }
    ]

    for scenario in test_scenarios:
        print(f"SCENARIO: {scenario['name']}")
        print(f"Vær: {scenario['weather']}")

        slush_result = detector.predict_slush_risk(scenario['weather'])
        slippery_result = detector.predict_slippery_risk(scenario['weather'])

        print(f"SLUSH-RISIKO: {slush_result['risk_level']} (tillit: {slush_result['confidence']:.2f})")
        print(f"GLATT VEI-RISIKO: {slippery_result['risk_level']} (tillit: {slippery_result['confidence']:.2f})")
        print(f"ANBEFALING: {slippery_result.get('recommendation', 'N/A')}")
        print("-" * 60)

if __name__ == "__main__":
    test_detector()
