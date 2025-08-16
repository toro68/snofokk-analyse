"""
ANALYSE AV NÅVÆRENDE ML-KRITERIER OG FORSLAG TIL NYE KRITERIER
Basert på faktiske brøyting vs værdata analysen
"""

def analyze_current_criteria():
    """Analyser nåværende kriterier som brukes i ML"""

    print("🔍 NÅVÆRENDE ML-KRITERIER SOM ANALYSERES:")
    print("=" * 55)

    print("📊 SNØFOKK-KRITERIER (ml_snowdrift_detector.py):")
    print("1. HØYRISIKO KOMBINASJON:")
    print("   - Vindkjøling < -15°C OG vind > 5 m/s")
    print("   - Snødybde > 20cm")

    print("2. MEDIUM-RISIKO KOMBINASJON:")
    print("   - Vindkjøling < -12°C OG vind > 4 m/s")
    print("   - Snødybde > 20cm")

    print("3. ENKELTPARAMETER-TERSKLER:")
    print("   - Vindstyrke > 7.5 m/s (kritisk)")
    print("   - Temperatur < -8°C (kritisk)")
    print("   - Snødybde > 26cm (kritisk)")

    print("\n🧊 GLATTFØRE-KRITERIER (live_conditions_app.py):")
    print("1. HØYRISIKO:")
    print("   - Regn på snø: 0-4°C + snø ≥5cm + nedbør ≥0.3mm/h")
    print("   - Is-risiko: Bakketemperatur ≤0°C + lufttemp >-1°C")

    print("2. MEDIUM-RISIKO:")
    print("   - Rimfrost: Bakketemperatur ≤0°C + temp nær duggpunkt")
    print("   - Temperaturovergang: Mildvær + snø + temperaturøkning")

    print("3. LAV RISIKO:")
    print("   - Snøfall (økende snødybde)")
    print("   - Stabilt kaldt (<-5°C)")

    print("\n❌ IDENTIFISERTE PROBLEMER:")
    print("1. SNØFOKK: For strenge kriterier")
    print("   - Vindkjøling-terskler for lave (-15°C/-12°C)")
    print("   - Vindterskler for høye (4-5 m/s)")
    print("   - Snødybde-krav for høyt (20-26cm)")

    print("2. GLATTFØRE: ALT for strenge kriterier")
    print("   - Regn-på-snø krever for mye nedbør (≥0.3mm/h)")
    print("   - Temperaturområde for smalt (0-4°C)")
    print("   - Snødybde-krav for høyt (≥5cm)")
    print("   - Is-risiko sjelden utløst")


def propose_new_criteria():
    """Foreslå nye kriterier basert på faktiske brøytingsdata"""

    print("\n💡 FORESLÅTTE NYE KRITERIER:")
    print("=" * 40)

    print("📈 BASERT PÅ FAKTISKE VÆRFORHOLD VED BRØYTING:")
    print("- Tunbrøyting: -2.1°C, 8.5 m/s, 22.1 cm snø, 11.3 mm nedbør")
    print("- Standard vedlikehold: 0.3°C, 4.8 m/s, 12.3 cm snø, 4.7 mm nedbør")
    print("- Disse BØR utløse medium/high risiko!")

    print("\n🌨️ NYE SNØFOKK-KRITERIER:")
    print("HØYRISIKO (skal fange tunbrøyting):")
    print("   - Vindkjøling < -8°C OG vind > 3 m/s  (i stedet for -15°C + 5 m/s)")
    print("   - ELLER vind > 6 m/s + snø > 15cm")
    print("   - ELLER snødybde > 20cm + vind > 3 m/s")

    print("MEDIUM-RISIKO (skal fange standard vedlikehold):")
    print("   - Vindkjøling < -5°C OG vind > 2.5 m/s  (i stedet for -12°C + 4 m/s)")
    print("   - ELLER vind > 4 m/s + snø > 10cm")
    print("   - ELLER temp < 2°C + vind > 3 m/s + snø > 5cm")

    print("\n🧊 NYE GLATTFØRE-KRITERIER:")
    print("HØYRISIKO (skal fange mer situasjoner):")
    print("   - Regn på snø: -2°C til 6°C + snø ≥1cm + nedbør ≥0.1mm/h  (mye mildere)")
    print("   - Temperaturovergang: Temp krysser 0°C + snø tilstede")
    print("   - Fuktighet >85% + temp -2°C til 2°C")

    print("MEDIUM-RISIKO:")
    print("   - Mildvær med snø: 0°C til 4°C + snø ≥1cm (uten nedbør-krav)")
    print("   - Rimfrost: Temp < 2°C + fuktighet >80%")
    print("   - Lettere nedbør: nedbør 0.05-0.1mm/h + snø tilstede")

    print("\n🎯 FORVENTET EFFEKT AV NYE KRITERIER:")
    print("- Snøfokk high-risiko: 6% → 15-20%")
    print("- Glattføre high-risiko: 0% → 10-15%")
    print("- Total ML-nøyaktighet: 56% → 75-80%")


# Test-implementasjon av nye kriterier
class ImprovedMLCriteria:
    """Forbedrede ML-kriterier basert på faktiske brøytingsdata"""

    def __init__(self):
        # Nye snøfokk-kriterier (mildere terskler)
        self.snowdrift_criteria = {
            'high_risk': {
                'wind_chill_temp_and_wind': {'wind_chill': -8.0, 'wind_speed': 3.0},
                'high_wind_and_snow': {'wind_speed': 6.0, 'snow_depth': 15.0},
                'snow_and_moderate_wind': {'snow_depth': 20.0, 'wind_speed': 3.0}
            },
            'medium_risk': {
                'moderate_wind_chill': {'wind_chill': -5.0, 'wind_speed': 2.5},
                'wind_and_snow': {'wind_speed': 4.0, 'snow_depth': 10.0},
                'cold_windy_snow': {'temperature': 2.0, 'wind_speed': 3.0, 'snow_depth': 5.0}
            }
        }

        # Nye glattføre-kriterier (mye mildere terskler)
        self.slippery_criteria = {
            'high_risk': {
                'rain_on_snow_mild': {'temp_min': -2.0, 'temp_max': 6.0, 'snow_min': 1.0, 'precip_min': 0.1},
                'temp_transition': {'temp_cross_zero': True, 'snow_present': True},
                'high_humidity_critical': {'humidity_min': 85.0, 'temp_min': -2.0, 'temp_max': 2.0}
            },
            'medium_risk': {
                'mild_with_snow': {'temp_min': 0.0, 'temp_max': 4.0, 'snow_min': 1.0},
                'frost_conditions': {'temperature': 2.0, 'humidity_min': 80.0},
                'light_precip_snow': {'precip_min': 0.05, 'precip_max': 0.1, 'snow_present': True}
            }
        }

    def calculate_wind_chill(self, temperature: float, wind_speed: float) -> float:
        """Beregn vindkjøling"""
        if temperature <= 10 and wind_speed >= 1.34:
            return (13.12 + 0.6215 * temperature -
                   11.37 * (wind_speed * 3.6) ** 0.16 +
                   0.3965 * temperature * (wind_speed * 3.6) ** 0.16)
        return temperature

    def analyze_snowdrift_risk_improved(self, weather_data: dict) -> dict:
        """Test nye snøfokk-kriterier"""

        temp = weather_data.get('temperature', 0)
        wind = weather_data.get('wind_speed', 0)
        snow = weather_data.get('snow_depth', 0)
        wind_chill = self.calculate_wind_chill(temp, wind)

        # Test høyrisiko-kriterier
        high_criteria = self.snowdrift_criteria['high_risk']

        # Kriterie 1: Vindkjøling + vind
        if (wind_chill < high_criteria['wind_chill_temp_and_wind']['wind_chill'] and
            wind > high_criteria['wind_chill_temp_and_wind']['wind_speed']):
            return {
                'risk_level': 'high',
                'reason': f'Vindkjøling {wind_chill:.1f}°C + vind {wind:.1f}m/s',
                'criteria_met': 'wind_chill_and_wind'
            }

        # Kriterie 2: Høy vind + snø
        if (wind > high_criteria['high_wind_and_snow']['wind_speed'] and
            snow > high_criteria['high_wind_and_snow']['snow_depth']):
            return {
                'risk_level': 'high',
                'reason': f'Høy vind {wind:.1f}m/s + snø {snow:.1f}cm',
                'criteria_met': 'high_wind_and_snow'
            }

        # Kriterie 3: Mye snø + moderat vind
        if (snow > high_criteria['snow_and_moderate_wind']['snow_depth'] and
            wind > high_criteria['snow_and_moderate_wind']['wind_speed']):
            return {
                'risk_level': 'high',
                'reason': f'Mye snø {snow:.1f}cm + vind {wind:.1f}m/s',
                'criteria_met': 'snow_and_moderate_wind'
            }

        # Test medium-risiko kriterier
        medium_criteria = self.snowdrift_criteria['medium_risk']

        # Moderat vindkjøling
        if (wind_chill < medium_criteria['moderate_wind_chill']['wind_chill'] and
            wind > medium_criteria['moderate_wind_chill']['wind_speed']):
            return {
                'risk_level': 'medium',
                'reason': f'Moderat vindkjøling {wind_chill:.1f}°C + vind {wind:.1f}m/s',
                'criteria_met': 'moderate_wind_chill'
            }

        # Vind og snø
        if (wind > medium_criteria['wind_and_snow']['wind_speed'] and
            snow > medium_criteria['wind_and_snow']['snow_depth']):
            return {
                'risk_level': 'medium',
                'reason': f'Vind {wind:.1f}m/s + snø {snow:.1f}cm',
                'criteria_met': 'wind_and_snow'
            }

        # Kaldt, vind og snø
        if (temp < medium_criteria['cold_windy_snow']['temperature'] and
            wind > medium_criteria['cold_windy_snow']['wind_speed'] and
            snow > medium_criteria['cold_windy_snow']['snow_depth']):
            return {
                'risk_level': 'medium',
                'reason': f'Kaldt {temp:.1f}°C + vind {wind:.1f}m/s + snø {snow:.1f}cm',
                'criteria_met': 'cold_windy_snow'
            }

        return {
            'risk_level': 'low',
            'reason': 'Ingen kriterier oppfylt for snøfokk-risiko',
            'criteria_met': 'none'
        }

    def analyze_slippery_road_risk_improved(self, weather_data: dict) -> dict:
        """Test nye glattføre-kriterier"""

        temp = weather_data.get('temperature', 0)
        snow = weather_data.get('snow_depth', 0)
        precip = weather_data.get('precipitation', 0)
        humidity = weather_data.get('humidity', 70)

        # Test høyrisiko-kriterier
        high_criteria = self.slippery_criteria['high_risk']

        # Kriterie 1: Regn på snø (mildere kriterier)
        rain_snow = high_criteria['rain_on_snow_mild']
        if (rain_snow['temp_min'] <= temp <= rain_snow['temp_max'] and
            snow >= rain_snow['snow_min'] and
            precip >= rain_snow['precip_min']):
            return {
                'risk_level': 'high',
                'reason': f'Regn på snø: {temp:.1f}°C, {snow:.1f}cm snø, {precip:.1f}mm nedbør',
                'criteria_met': 'rain_on_snow_mild'
            }

        # Kriterie 2: Høy fuktighet i kritisk temperaturområde
        humidity_crit = high_criteria['high_humidity_critical']
        if (humidity >= humidity_crit['humidity_min'] and
            humidity_crit['temp_min'] <= temp <= humidity_crit['temp_max']):
            return {
                'risk_level': 'high',
                'reason': f'Høy fuktighet {humidity:.0f}% ved kritisk temp {temp:.1f}°C',
                'criteria_met': 'high_humidity_critical'
            }

        # Test medium-risiko kriterier
        medium_criteria = self.slippery_criteria['medium_risk']

        # Mildvær med snø (uten nedbør-krav)
        mild_snow = medium_criteria['mild_with_snow']
        if (mild_snow['temp_min'] <= temp <= mild_snow['temp_max'] and
            snow >= mild_snow['snow_min']):
            return {
                'risk_level': 'medium',
                'reason': f'Mildvær med snø: {temp:.1f}°C, {snow:.1f}cm snø',
                'criteria_met': 'mild_with_snow'
            }

        # Rimfrost-forhold
        if (temp < medium_criteria['frost_conditions']['temperature'] and
            humidity >= medium_criteria['frost_conditions']['humidity_min']):
            return {
                'risk_level': 'medium',
                'reason': f'Rimfrost-forhold: {temp:.1f}°C, {humidity:.0f}% fuktighet',
                'criteria_met': 'frost_conditions'
            }

        # Lett nedbør med snø
        light_precip = medium_criteria['light_precip_snow']
        if (light_precip['precip_min'] <= precip <= light_precip['precip_max'] and
            snow > 0):
            return {
                'risk_level': 'medium',
                'reason': f'Lett nedbør med snø: {precip:.2f}mm, {snow:.1f}cm snø',
                'criteria_met': 'light_precip_snow'
            }

        return {
            'risk_level': 'low',
            'reason': 'Ingen kriterier oppfylt for glattføre-risiko',
            'criteria_met': 'none'
        }


def main():
    """Vis analyse av nåværende kriterier og forslag til nye"""

    print("🔍 ANALYSE AV ML-KRITERIER OG FORBEDRINGSFORSLAG")
    print("=" * 60)
    print("Basert på faktisk brøyting vs værdata analyse")
    print()

    analyze_current_criteria()
    propose_new_criteria()

    print("\n📋 NESTE STEG:")
    print("1. Lag testscript som sammenligner gamle vs nye kriterier")
    print("2. Test mot de 50 faktiske brøytingsepisodene")
    print("3. Mål forbedring i nøyaktighet")
    print("4. Implementer de nye kriteriene hvis bedre ytelse")


if __name__ == "__main__":
    main()
