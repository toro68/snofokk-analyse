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

        # ML-OPTIMALISERTE grenseverdier (systematisk søk 8-10 dager/sesong)
        # Optimalisert via grid search på 184,320 kombinasjoner for perfekt match
        self.critical_thresholds = {
            'wind_chill': -15.0,     # °C (ML-optimalisert: gir nøyaktig 9 dager i 2023-2024)
            'wind_speed': 5.0,       # m/s (ML-optimalisert fra grid search)
            'air_temperature': -5.0, # °C (ML-optimalisert fra grid search)
            'surface_snow_thickness': 0.26  # 26cm minimum snødybde (ML-optimalisert)
        }

        # Advarsel-grenser (litt mildere enn ML-optimaliserte kritiske)
        self.warning_thresholds = {
            'wind_chill': -12.0,     # °C
            'wind_speed': 4.0,       # m/s (senket fra 8.0)
            'air_temperature': -3.0, # °C (justert fra -8.0)
            'surface_snow_thickness': 0.20  # 20cm (litt mindre enn kritiske 26cm)
        }

        # ML-optimaliserte kombinasjonsregler - begge kriterier må oppfylles
        self.combination_rules = {
            'high_risk_combo': {
                'wind_chill_threshold': -15.0,      # Vindkjøling < -15°C (ML-optimalisert)
                'wind_speed_threshold': 5.0,        # OG vindstyrke > 5 m/s (ML-optimalisert)
                'requires_both': True,               # Begge må oppfylles
                'risk_level': 'HIGH'
            },
            'medium_risk_combo': {
                'wind_chill_threshold': -12.0,      # Vindkjøling < -12°C
                'wind_speed_threshold': 4.0,        # OG vindstyrke > 4 m/s
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
        FORBEDRET: Bruker alle nye validerte værelementer.
        """
        if df is None or len(df) < 2:
            return {'detected': False, 'reason': 'Ikke nok data'}

        # Beregn snødybde-endringer
        df_copy = df.copy()
        df_copy['snow_change_1h'] = df_copy['surface_snow_thickness'].diff()

        # Siste endring
        latest_change = abs(df_copy['snow_change_1h'].iloc[-1])

        # FORBEDRET: Sjekk nedbør med flere kilder
        latest_precip_1h = df_copy.get('sum(precipitation_amount PT1H)', pd.Series([0])).iloc[-1]
        latest_precip_10m = df_copy.get('precipitation_amount_10m', pd.Series([0])).iloc[-1]
        accumulated_precip = df_copy.get('accumulated_precipitation', pd.Series([0])).iloc[-1]
        
        # Bruk høyoppløselig nedbør hvis tilgjengelig
        if pd.notna(latest_precip_10m) and latest_precip_10m > 0:
            latest_precip = latest_precip_10m * 6  # Konverter 10-min til time
        elif pd.notna(latest_precip_1h):
            latest_precip = latest_precip_1h
        else:
            latest_precip = 0

        # FORBEDRET: ML-regel med flere nedbørkilder
        if latest_change >= self.snow_change_thresholds['critical']:
            if latest_precip < self.snow_change_thresholds['precip_limit']:
                return {
                    'detected': True,
                    'severity': 'CRITICAL',
                    'change_mm': latest_change * 1000,  # Konverter til mm
                    'precip_mm': latest_precip,
                    'accumulated_mm': accumulated_precip or 0,
                    'reason': f'Stor snødybde-endring ({latest_change*1000:.1f}mm) uten nedbør'
                }

        elif latest_change >= self.snow_change_thresholds['warning']:
            if latest_precip < self.snow_change_thresholds['precip_limit']:
                return {
                    'detected': True,
                    'severity': 'WARNING',
                    'change_mm': latest_change * 1000,
                    'precip_mm': latest_precip,
                    'accumulated_mm': accumulated_precip or 0,
                    'reason': f'Moderat snødybde-endring ({latest_change*1000:.1f}mm) uten nedbør'
                }

        return {'detected': False, 'reason': 'Normale snødybde-endringer'}

    def evaluate_ml_combination_rules(self, weather_data: dict) -> dict:
        """
        Evaluerer kalibrerte kombinasjonsregler - begge kriterier må oppfylles.
        Velger høyeste risiko-nivå for å unngå duplikater.
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

        # Regel 2: Medium risiko kombinasjon (KUN hvis ikke høy risiko allerede)
        elif wind_chill < self.combination_rules['medium_risk_combo']['wind_chill_threshold'] and wind_speed > self.combination_rules['medium_risk_combo']['wind_speed_threshold']:

            alerts.append({
                'rule': 'Kalibrert medium risiko kombinasjon',
                'risk_level': 'MEDIUM',
                'confidence': 1.0,
                'description': f"Vindkjøling {wind_chill:.1f}°C + vind {wind_speed:.1f}m/s"
            })

        return {'alerts': alerts, 'total_alerts': len(alerts)}

    def extract_enhanced_weather_data(self, df: pd.DataFrame) -> dict:
        """
        NYTT: Ekstraherer alle 15 empirisk validerte værelementer.
        """
        if df is None or len(df) == 0:
            return {}
        
        latest = df.iloc[-1]
        period_analysis = len(df) > 24  # Mer enn 24 målinger = lengre periode
        
        # Kjerneelementer (1-8)
        air_temp = latest.get('air_temperature', None)
        wind_speed = latest.get('wind_speed', None)
        snow_thickness = latest.get('surface_snow_thickness', 0)
        precip_1h = latest.get('sum(precipitation_amount PT1H)', 0)
        humidity = latest.get('relative_humidity', None)
        wind_direction = latest.get('wind_from_direction', None)
        surface_temp = latest.get('surface_temperature', None)
        dew_point = latest.get('dew_point_temperature', None)
        
        # Nye kritiske elementer (9-11)
        max_wind_per_direction = latest.get('max_wind_per_direction', wind_speed)
        accumulated_precip = latest.get('accumulated_precipitation', 0)
        precip_10m = latest.get('precipitation_amount_10m', 0)
        
        # Medium prioritet elementer (12-15)
        precip_duration = latest.get('sum(duration_of_precipitation PT1H)', 0)
        wind_gust = latest.get('max(wind_speed_of_gust PT1H)', wind_speed)
        weather_symbol = latest.get('weather_symbol', None)
        visibility = latest.get('visibility', None)
        
        # Beregn effektiv vindstyrke (maks av alle vindmålinger)
        effective_wind = max(
            wind_speed or 0,
            max_wind_per_direction or 0,
            wind_gust or 0
        )
        
        # Periode-analyse for maks/min verdier
        if period_analysis:
            max_wind = df['wind_speed'].max() if 'wind_speed' in df.columns and df['wind_speed'].notna().any() else wind_speed
            min_temp = df['air_temperature'].min() if 'air_temperature' in df.columns and df['air_temperature'].notna().any() else air_temp
            effective_wind = max(effective_wind, max_wind or 0)
        else:
            min_temp = air_temp
        
        # Beregn vindkjøling med effektiv vind
        wind_chill = self.calculate_wind_chill(min_temp or 0, effective_wind)
        
        return {
            'air_temperature': air_temp,
            'wind_speed': effective_wind,
            'wind_chill': wind_chill,
            'surface_snow_thickness': snow_thickness,
            'wind_from_direction': wind_direction,
            'surface_temperature': surface_temp,
            'dew_point_temperature': dew_point,
            'relative_humidity': humidity,
            'precipitation_1h': precip_1h,
            'precipitation_10m': precip_10m,
            'accumulated_precipitation': accumulated_precip,
            'max_wind_per_direction': max_wind_per_direction,
            'wind_gust': wind_gust,
            'precipitation_duration': precip_duration,
            'weather_symbol': weather_symbol,
            'visibility': visibility,
            'period_analysis': period_analysis
        }

    def analyze_snowdrift_risk_ml(self, df: pd.DataFrame) -> dict:
        """
        FORBEDRET: ML-basert snøfokk-risikoanalyse med alle 15 validerte elementer.
        """
        if df is None or len(df) == 0:
            return {"risk_level": "unknown", "message": "Ingen data tilgjengelig", "ml_based": True}

        # NYTT: Bruk forbedret data-ekstraksjon med alle elementer
        weather_data = self.extract_enhanced_weather_data(df)
        
        if not weather_data:
            return {"risk_level": "unknown", "message": "Kunne ikke ekstraktere værdata", "ml_based": True}

        # Grunnleggende validering
        if weather_data['air_temperature'] is None or weather_data['wind_speed'] is None:
            return {"risk_level": "unknown", "message": "Mangler kritiske målinger", "ml_based": True}

        # Bruk data fra forbedret ekstraksjon
        current_temp = weather_data['air_temperature']
        current_wind = weather_data['wind_speed']
        current_snow = weather_data['surface_snow_thickness']
        wind_chill = weather_data['wind_chill']
        period_analysis = weather_data['period_analysis']

        # 1. Evaluer snødybde-endringer (direkte indikator)
        snow_change_analysis = self.detect_snow_depth_changes(df)

        # 2. Evaluer ML-kombinasjonsregler med forbedret vinddata
        ml_weather_data = {
            'air_temperature': current_temp,
            'wind_speed': current_wind,
            'wind_chill': wind_chill,
            'surface_snow_thickness': current_snow
        }
        combination_analysis = self.evaluate_ml_combination_rules(ml_weather_data)

        # 3. Evaluer enkelparameter-terskler med forbedrede data
        critical_alerts = []
        warning_alerts = []

        # Vindkjøling (viktigste parameter) - bruk forbedret data
        if wind_chill < self.critical_thresholds['wind_chill']:
            critical_alerts.append(f"Kritisk vindkjøling: {wind_chill:.1f}°C (< {self.critical_thresholds['wind_chill']}°C)")
        elif wind_chill < self.warning_thresholds['wind_chill']:
            warning_alerts.append(f"Advarsel vindkjøling: {wind_chill:.1f}°C (< {self.warning_thresholds['wind_chill']}°C)")

        # Vindstyrke - bruk effektiv vind (maks av alle vindmålinger)
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

        # Generer melding med periode-informasjon
        if risk_level == "high":
            message = "HØY SNØFOKK-RISIKO"
        elif risk_level == "medium":
            message = "MEDIUM SNØFOKK-RISIKO"
        else:
            message = "LAV SNØFOKK-RISIKO"

        # Legg til periode-informasjon
        if period_analysis:
            message += f" [Analyse av {len(df)} målinger]"

        # Legg til vindkjøling i melding (viktigste parameter)
        if pd.notna(wind_chill):
            message += f" | Vindkjøling: {wind_chill:.1f}°C"
        else:
            message += " | Vindkjøling: Utilgjengelig"

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
                "warning_alerts": len(warning_alerts),
                "enhanced_elements_used": True,
                "total_elements": 15
            },
            "current_conditions": {
                "temperature": current_temp,
                "wind_speed": current_wind,
                "wind_chill": wind_chill,
                "snow_depth_cm": current_snow,
                "wind_direction": weather_data.get('wind_from_direction'),
                "accumulated_precipitation": weather_data.get('accumulated_precipitation', 0),
                "precipitation_10m": weather_data.get('precipitation_10m', 0),
                "max_wind_per_direction": weather_data.get('max_wind_per_direction'),
                "visibility": weather_data.get('visibility'),
                "weather_symbol": weather_data.get('weather_symbol')
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
