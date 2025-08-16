#!/usr/bin/env python3
"""
ML-basert snøfokk-deteksjon for live conditions app.
Implementerer ML-optimaliserte grenseverdier og kombinasjonsregler.
"""

import json
import logging

import pandas as pd

# Sett opp logging
logger = logging.getLogger(__name__)

class MLSnowdriftDetector:
    """
    ML-basert snøfokk-detektor som implementerer optimaliserte grenseverdier
    identifisert gjennom maskinlæring-analyse av 26,206 værobservasjoner.
    """

    def __init__(self):
        """Initialiserer ML-baserte terskelverdier og regler."""

        # Rekalibrerte ML-grenseverdier (justert til 8-10 dager/sesong 2023-2024)
        # Basert på erfaringsmessig antall snøfokkdager - justert fra tidligere kalibrering
        self.critical_thresholds = {
            'wind_chill': -16.0,     # °C (justert fra -15°C til -16°C)
            'wind_speed': 6.0,       # m/s (justert fra 10.0 til 6.0 m/s)
            'air_temperature': -8.0, # °C (justert fra -10°C til -8°C)
            'surface_snow_thickness': 0.15  # 15cm minimum snødybde (justert fra 20cm)
        }

        # Advarsel-grenser (litt mildere enn kritiske)
        self.warning_thresholds = {
            'wind_chill': -14.0,     # °C (justert fra -12°C)
            'wind_speed': 5.0,       # m/s (justert fra 8.0)
            'air_temperature': -6.0, # °C (justert fra -8°C)
            'surface_snow_thickness': 0.10  # 10cm (justert fra 15cm)
        }

        # Rekalibrerte kombinasjonsregler - hovedkriterier for 8-10 dager/sesong
        self.combination_rules = {
            'high_risk_combo': {
                'wind_chill_threshold': -16.0,      # Vindkjøling < -16°C (justert fra -15°C)
                'wind_speed_threshold': 6.0,        # OG vindstyrke > 6 m/s (justert fra 10 m/s)
                'requires_both': True,               # Begge må oppfylles
                'risk_level': 'HIGH'
            },
            'medium_risk_combo': {
                'wind_chill_threshold': -14.0,      # Vindkjøling < -14°C (justert fra -12°C)
                'wind_speed_threshold': 5.0,        # OG vindstyrke > 5 m/s (justert fra 8 m/s)
                'requires_both': True,
                'risk_level': 'MEDIUM'
            }
        }

        # Ny ML-regel: Snødybde-endringer
        self.snow_change_thresholds = {
            'critical': 0.015,    # ±15mm/time uten nedbør
            'warning': 0.010,     # ±10mm/time uten nedbør
            'precip_limit': 0.002 # 2mm/time nedbør-grense
        }

    def calculate_wind_chill(self, temperature: float, wind_speed: float) -> float:
        """
        Beregner vindkjøling basert på standardformelen.
        Dette er den viktigste enkeltfaktoren (73.1% viktighet).
        """
        if temperature <= 10 and wind_speed >= 1.34:  # 4.8 km/h = 1.34 m/s
            return (13.12 + 0.6215 * temperature -
                   11.37 * (wind_speed * 3.6) ** 0.16 +
                   0.3965 * temperature * (wind_speed * 3.6) ** 0.16)
        return temperature

    def detect_snow_depth_changes(self, df: pd.DataFrame) -> dict:
        """
        Detekterer store endringer i snødybde som indikator på snøfokk.
        Dette er en direkte indikator på pågående snøtransport.
        """
        if df is None or len(df) < 2:
            return {'detected': False, 'reason': 'Ikke nok data'}

        # Beregn snødybde-endringer
        df_copy = df.copy()
        df_copy['snow_change_1h'] = df_copy['surface_snow_thickness'].diff()

        # Siste endring
        latest_change = abs(df_copy['snow_change_1h'].iloc[-1])

        # Sjekk nedbør i samme periode
        latest_precip = df_copy.get('sum(precipitation_amount PT1H)', pd.Series([0])).iloc[-1]
        if pd.isna(latest_precip):
            latest_precip = 0

        # ML-regel: Store endringer uten tilsvarende nedbør
        if latest_change >= self.snow_change_thresholds['critical']:
            if latest_precip < self.snow_change_thresholds['precip_limit']:
                return {
                    'detected': True,
                    'severity': 'CRITICAL',
                    'change_mm': latest_change * 1000,  # Konverter til mm
                    'precip_mm': latest_precip,
                    'reason': f'Stor snødybde-endring ({latest_change*1000:.1f}mm) uten nedbør'
                }

        elif latest_change >= self.snow_change_thresholds['warning']:
            if latest_precip < self.snow_change_thresholds['precip_limit']:
                return {
                    'detected': True,
                    'severity': 'WARNING',
                    'change_mm': latest_change * 1000,
                    'precip_mm': latest_precip,
                    'reason': f'Moderat snødybde-endring ({latest_change*1000:.1f}mm) uten nedbør'
                }

        return {'detected': False, 'reason': 'Normale snødybde-endringer'}

    def evaluate_ml_combination_rules(self, weather_data: dict) -> dict:
        """
        Evaluerer kalibrerte kombinasjonsregler - begge kriterier må oppfylles.
        """
        alerts = []
        wind_chill = weather_data.get('wind_chill', 0)
        wind_speed = weather_data.get('wind_speed', 0)

        # Regel 1: Høy risiko kombinasjon (BEGGE kriterier må oppfylles)
        high_rule = self.combination_rules['high_risk_combo']
        if (wind_chill < high_rule['wind_chill_threshold'] and
            wind_speed > high_rule['wind_speed_threshold']):

            alerts.append({
                'rule': 'Kalibrert høy risiko kombinasjon',
                'risk_level': 'HIGH',
                'confidence': 1.0,
                'description': f"Vindkjøling {wind_chill:.1f}°C + vind {wind_speed:.1f}m/s"
            })

        # Regel 2: Medium risiko kombinasjon
        med_rule = self.combination_rules['medium_risk_combo']
        if (wind_chill < med_rule['wind_chill_threshold'] and
            wind_speed > med_rule['wind_speed_threshold']):

            alerts.append({
                'rule': 'Kalibrert medium risiko kombinasjon',
                'risk_level': 'MEDIUM',
                'confidence': 1.0,
                'description': f"Vindkjøling {wind_chill:.1f}°C + vind {wind_speed:.1f}m/s"
            })

        return {'alerts': alerts, 'total_alerts': len(alerts)}

    def analyze_snowdrift_risk_ml(self, df: pd.DataFrame) -> dict:
        """
        Hovedfunksjon for ML-basert snøfokk-risikoanalyse.
        Implementerer alle ML-optimaliserte terskelverdier og regler.
        """
        if df is None or len(df) == 0:
            return {"risk_level": "unknown", "message": "Ingen data tilgjengelig", "ml_based": True}

        # Hent siste målinger
        latest = df.iloc[-1]
        current_temp = latest.get('air_temperature', None)
        current_wind = latest.get('wind_speed', None)
        current_snow = latest.get('surface_snow_thickness', 0)
        wind_direction = latest.get('wind_from_direction', None)

        if current_temp is None or current_wind is None:
            return {"risk_level": "unknown", "message": "Mangler kritiske målinger", "ml_based": True}

        # Beregn vindkjøling (VIKTIGSTE PARAMETER - 73.1% viktighet)
        wind_chill = self.calculate_wind_chill(current_temp, current_wind)

        # Samle værdata for evaluering
        weather_data = {
            'air_temperature': current_temp,
            'wind_speed': current_wind,
            'surface_snow_thickness': current_snow,
            'wind_chill': wind_chill,
            'wind_from_direction': wind_direction
        }

        # 1. Evaluer snødybde-endringer (direkte indikator)
        snow_change_analysis = self.detect_snow_depth_changes(df)

        # 2. Evaluer ML-kombinasjonsregler
        combination_analysis = self.evaluate_ml_combination_rules(weather_data)

        # 3. Evaluer enkelparameter-terskler (kalibrerte verdier)
        critical_alerts = []
        warning_alerts = []

        # Vindkjøling (viktigste parameter)
        if wind_chill < self.critical_thresholds['wind_chill']:
            critical_alerts.append(f"Kritisk vindkjøling: {wind_chill:.1f}°C (< {self.critical_thresholds['wind_chill']}°C)")
        elif wind_chill < self.warning_thresholds['wind_chill']:
            warning_alerts.append(f"Advarsel vindkjøling: {wind_chill:.1f}°C (< {self.warning_thresholds['wind_chill']}°C)")

        # Vindstyrke
        if current_wind > self.critical_thresholds['wind_speed']:
            critical_alerts.append(f"Kritisk vindstyrke: {current_wind:.1f}m/s (> {self.critical_thresholds['wind_speed']}m/s)")
        elif current_wind > self.warning_thresholds['wind_speed']:
            warning_alerts.append(f"Advarsel vindstyrke: {current_wind:.1f}m/s (> {self.warning_thresholds['wind_speed']}m/s)")

        # Lufttemperatur
        if current_temp < self.critical_thresholds['air_temperature']:
            critical_alerts.append(f"Kritisk lav temperatur: {current_temp:.1f}°C (< {self.critical_thresholds['air_temperature']}°C)")
        elif current_temp < self.warning_thresholds['air_temperature']:
            warning_alerts.append(f"Advarsel lav temperatur: {current_temp:.1f}°C (< {self.warning_thresholds['air_temperature']}°C)")

        # Snødybde (må ha snø for snøfokk)
        if current_snow < self.warning_thresholds['surface_snow_thickness']:
            return {"risk_level": "low", "message": "For lite snø for snøfokk-risiko", "ml_based": True}

        # 4. Bestem samlet risiko-nivå (kalibrert for realistisk frekvens)
        risk_level = "low"
        main_factors = []

        # Høy risiko: Kombinasjonsregel ELLER snøendring + kritiske faktorer
        if (any(alert['risk_level'] == 'HIGH' for alert in combination_analysis['alerts']) or
            (snow_change_analysis['detected'] and snow_change_analysis['severity'] == 'CRITICAL' and len(critical_alerts) >= 1)):
            risk_level = "high"

        # Medium risiko: Medium kombinasjon ELLER moderate endringer + faktorer
        elif (any(alert['risk_level'] == 'MEDIUM' for alert in combination_analysis['alerts']) or
              (snow_change_analysis['detected'] and len(warning_alerts) >= 1) or
              len(critical_alerts) >= 1):
            risk_level = "medium"

        # Bygg hovedfaktorer-liste
        if snow_change_analysis['detected']:
            main_factors.append(snow_change_analysis['reason'])

        for alert in combination_analysis['alerts']:
            main_factors.append(alert['description'])

        main_factors.extend(critical_alerts)
        main_factors.extend(warning_alerts)

        # Generer melding
        if risk_level == "high":
            message = "🔴 HØY SNØFOKK-RISIKO (Kalibrert ML)"
        elif risk_level == "medium":
            message = "🟡 MEDIUM SNØFOKK-RISIKO (Kalibrert ML)"
        else:
            message = "🟢 LAV SNØFOKK-RISIKO (Kalibrert ML)"

        # Legg til vindkjøling i melding (viktigste parameter)
        message += f" | Vindkjøling: {wind_chill:.1f}°C"

        return {
            "risk_level": risk_level,
            "message": message,
            "factors": main_factors,
            "ml_based": True,
            "ml_details": {
                "wind_chill": wind_chill,
                "wind_chill_importance": "73.1%",
                "wind_speed_importance": "21.7%",
                "snow_change_detected": snow_change_analysis['detected'],
                "combination_rules_triggered": combination_analysis['total_alerts'],
                "critical_alerts": len(critical_alerts),
                "warning_alerts": len(warning_alerts)
            },
            "current_conditions": {
                "temperature": current_temp,
                "wind_speed": current_wind,
                "wind_chill": wind_chill,
                "snow_depth_cm": current_snow * 100,
                "wind_direction": wind_direction
            }
        }


def integrate_ml_detector_with_app():
    """
    Integrasjonsfunksjon for å koble ML-detektoren til hovedappen.
    Returnerer en funksjon som kan brukes som erstatning for analyze_snowdrift_risk.
    """

    ml_detector = MLSnowdriftDetector()

    def enhanced_analyze_snowdrift_risk(df: pd.DataFrame, checker_instance=None) -> dict:
        """
        Forbedret snøfokk-analyse som kombinerer ML-baserte metoder
        med eksisterende logikk for bakoverkompatibilitet.
        """

        # Kjør ML-basert analyse
        ml_result = ml_detector.analyze_snowdrift_risk_ml(df)

        # Legg til sesong-informasjon hvis checker_instance er tilgjengelig
        if checker_instance and hasattr(checker_instance, 'is_summer_season'):
            if checker_instance.is_summer_season():
                ml_result['seasonal_note'] = "Sommersesong: ML-analyse med forsiktighet"

        return ml_result

    return enhanced_analyze_snowdrift_risk


# For direkte testing
if __name__ == "__main__":
    # Test ML-detektoren
    detector = MLSnowdriftDetector()

    # Simuler testdata
    test_data = pd.DataFrame({
        'referenceTime': pd.date_range(start='2024-01-01', periods=10, freq='H'),
        'air_temperature': [-2.0, -3.0, -4.0, -3.5, -2.8, -4.2, -5.0, -4.8, -3.9, -4.1],
        'wind_speed': [3.5, 4.2, 8.5, 9.1, 7.8, 8.9, 9.5, 9.2, 8.7, 9.0],
        'surface_snow_thickness': [0.05, 0.052, 0.048, 0.045, 0.042, 0.040, 0.038, 0.036, 0.034, 0.032],
        'sum(precipitation_amount PT1H)': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    })

    result = detector.analyze_snowdrift_risk_ml(test_data)
    print("ML Snøfokk-analyse resultat:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
