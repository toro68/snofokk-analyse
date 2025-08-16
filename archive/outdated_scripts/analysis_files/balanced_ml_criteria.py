
def detect_snowdrift_risk_balanced(weather_data):
    """Balanserte snøfokk-kriterier"""

    temp = weather_data.get('temperatur', 0)
    wind_speed = weather_data.get('vindstyrke', 0)
    snow_depth = weather_data.get('snødybde', 0)
    snow_change = weather_data.get('snødybdeendring', 0)

    # Vindkjøling (justert terskel)
    wind_chill = temp - (wind_speed * 2)

    # Høy risiko (strenge kriterier fra gamle systemet)
    if wind_chill <= -15 and wind_speed >= 7:
        return 'high', f"Ekstrem vindkjøling {wind_chill:.1f}°C + høy vind {wind_speed:.1f}m/s"

    if snow_depth >= 30 and wind_speed >= 8:
        return 'high', f"Mye snø {snow_depth:.1f}cm + høy vind {wind_speed:.1f}m/s"

    # Medium risiko (justerte terskler)
    if wind_chill <= -6 and wind_speed >= 3:  # Justert fra -8 til -6
        return 'medium', f"Vindkjøling {wind_chill:.1f}°C + vind {wind_speed:.1f}m/s"

    if snow_depth >= 15 and wind_speed >= 5:
        return 'medium', f"Moderat snø {snow_depth:.1f}cm + vind {wind_speed:.1f}m/s"

    if abs(snow_change) >= 3 and wind_speed >= 4:
        return 'medium', f"Snøendring {snow_change:.1f}cm + vind {wind_speed:.1f}m/s"

    return 'low', "Ingen kriterier oppfylt for snøfokk-risiko"

def detect_slippery_risk_balanced(weather_data):
    """Balanserte glattføre-kriterier"""

    temp = weather_data.get('temperatur', 0)
    precipitation = weather_data.get('nedbør', 0)
    snow_depth = weather_data.get('snødybde', 0)
    snow_change = weather_data.get('snødybdeendring', 0)

    # Regn på snø (justerte terskler)
    if (temp > -2 and precipitation >= 0.2 and snow_depth >= 1 and  # Justert fra 0.5 til 0.2
        snow_change <= 0):  # Negativ eller null endring = regn
        return 'high', f"Regn på snø: {temp:.1f}°C, {snow_depth:.1f}cm snø, {precipitation:.1f}mm nedbør"

    # Mildvær etter frost
    if temp > 2 and snow_depth >= 5:
        return 'medium', f"Mildvær {temp:.1f}°C etter frost, {snow_depth:.1f}cm snø"

    return 'low', "Ingen kriterier oppfylt for glattføre-risiko"
