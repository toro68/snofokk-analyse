"""
Fallback og utility funksjoner for mobil weather app
"""
from typing import Any

import pandas as pd


def simple_snowdrift_analysis(temp: float, wind: float, snow_depth: float | None = None) -> dict[str, Any]:
    """Enkel snøfokk-analyse uten ML"""

    # Validering
    if pd.isna(temp) or pd.isna(wind):
        return {
            'risk_level': 'unknown',
            'message': 'Mangler værdata',
            'confidence': 0.0,
            'factors': ['Mangler temperatur eller vinddata']
        }

    factors = []
    risk_level = 'low'
    confidence = 0.5

    # Temperatur-vurdering
    if temp <= -10:
        factors.append(f"Meget kald luft ({temp:.1f}°C)")
        temp_score = 3
    elif temp <= -5:
        factors.append(f"Kald luft ({temp:.1f}°C)")
        temp_score = 2
    elif temp <= -1:
        factors.append(f"Under frysepunktet ({temp:.1f}°C)")
        temp_score = 1
    else:
        factors.append(f"For varmt for snøfokk ({temp:.1f}°C)")
        temp_score = 0

    # Vind-vurdering
    if wind >= 15:
        factors.append(f"Sterk vind ({wind:.1f} m/s)")
        wind_score = 3
    elif wind >= 10:
        factors.append(f"Moderat vind ({wind:.1f} m/s)")
        wind_score = 2
    elif wind >= 6:
        factors.append(f"Lett vind ({wind:.1f} m/s)")
        wind_score = 1
    else:
        factors.append(f"For lite vind ({wind:.1f} m/s)")
        wind_score = 0

    # Snødybde-vurdering
    snow_score = 1  # Default
    if pd.notna(snow_depth) and snow_depth is not None:
        # Filter out negative sentinel values
        if snow_depth < 0:
            factors.append("Snødybde ukjent")
        else:
            snow_cm = snow_depth * 100 if snow_depth < 10 else snow_depth
            if snow_cm >= 20:
                factors.append(f"Mye snø ({snow_cm:.0f} cm)")
                snow_score = 2
            elif snow_cm >= 5:
                factors.append(f"Noe snø ({snow_cm:.0f} cm)")
                snow_score = 1
            else:
                factors.append(f"Lite snø ({snow_cm:.0f} cm)")
                snow_score = 0
    else:
        factors.append("Snødybde ukjent")

    # Kombinert vurdering
    total_score = temp_score + wind_score + snow_score

    if total_score >= 6 and temp <= -3 and wind >= 12:
        risk_level = 'high'
        message = 'Høy snøfokk-risiko'
        confidence = 0.8
    elif total_score >= 4 and temp <= -1 and wind >= 8:
        risk_level = 'medium'
        message = 'Moderat snøfokk-risiko'
        confidence = 0.7
    elif total_score >= 2:
        risk_level = 'low'
        message = 'Lav snøfokk-risiko'
        confidence = 0.6
    else:
        risk_level = 'low'
        message = 'Meget lav snøfokk-risiko'
        confidence = 0.8

    return {
        'risk_level': risk_level,
        'message': message,
        'confidence': confidence,
        'factors': factors,
        'scores': {
            'temperature': temp_score,
            'wind': wind_score,
            'snow': snow_score,
            'total': total_score
        }
    }


def simple_slippery_analysis(temp: float, surface_temp: float | None = None,
                           humidity: float | None = None) -> dict[str, Any]:
    """Enkel glattføre-analyse"""

    # Bruk overflatetemperatur hvis tilgjengelig
    analysis_temp = surface_temp if pd.notna(surface_temp) else temp

    if pd.isna(analysis_temp):
        return {
            'risk_level': 'unknown',
            'message': 'Mangler temperaturdata',
            'confidence': 0.0,
            'factors': ['Ingen temperaturdata tilgjengelig']
        }

    factors = []

    # Temperatur-analyse
    if -3 <= analysis_temp <= 3:
        if pd.notna(humidity):
            if humidity > 90:
                risk_level = 'high'
                message = 'Høy glattføre-risiko'
                confidence = 0.9
                factors.append(f"Kritisk temperatur ({analysis_temp:.1f}°C)")
                factors.append(f"Meget høy fuktighet ({humidity:.0f}%)")
            elif humidity > 80:
                risk_level = 'medium'
                message = 'Moderat glattføre-risiko'
                confidence = 0.7
                factors.append(f"Risiko-temperatur ({analysis_temp:.1f}°C)")
                factors.append(f"Høy fuktighet ({humidity:.0f}%)")
            else:
                risk_level = 'low'
                message = 'Lav glattføre-risiko'
                confidence = 0.6
                factors.append(f"Grensetemperatur ({analysis_temp:.1f}°C)")
                factors.append(f"Moderat fuktighet ({humidity:.0f}%)")
        else:
            # Ingen fuktighetsmåling
            if -1 <= analysis_temp <= 1:
                risk_level = 'medium'
                message = 'Moderat glattføre-risiko'
                confidence = 0.6
                factors.append(f"Kritisk temperatur ({analysis_temp:.1f}°C)")
                factors.append("Fuktighet ukjent")
            else:
                risk_level = 'low'
                message = 'Lav glattføre-risiko'
                confidence = 0.5
                factors.append(f"Grensetemperatur ({analysis_temp:.1f}°C)")
                factors.append("Fuktighet ukjent")

    elif analysis_temp < -10:
        risk_level = 'low'
        message = 'Stabilt kaldt - godt førføre'
        confidence = 0.8
        factors.append(f"Stabilt kaldt ({analysis_temp:.1f}°C)")
        factors.append("Optimale kjøreforhold på snø")

    elif analysis_temp > 8:
        risk_level = 'low'
        message = 'For varmt for glattføre'
        confidence = 0.8
        factors.append(f"Varmt ({analysis_temp:.1f}°C)")
        factors.append("Ingen is-fare")

    else:
        risk_level = 'low'
        message = 'Lav glattføre-risiko'
        confidence = 0.6
        factors.append(f"Moderat temperatur ({analysis_temp:.1f}°C)")

    # Legg til temperaturtype-info
    if pd.notna(surface_temp) and pd.notna(temp):
        if abs(surface_temp - temp) > 2:
            factors.append(f"Forskjell luft/overflate: {abs(surface_temp - temp):.1f}°C")

    return {
        'risk_level': risk_level,
        'message': message,
        'confidence': confidence,
        'factors': factors
    }


def calculate_wind_chill(temp: float, wind_speed: float) -> float:
    """Beregn vindkjøling"""
    if pd.isna(temp) or pd.isna(wind_speed) or wind_speed <= 0:
        return temp if pd.notna(temp) else float('nan')

    # Standard vindkjøling-formel
    wind_chill = 13.12 + 0.6215 * temp - 11.37 * (wind_speed ** 0.16) + 0.3965 * temp * (wind_speed ** 0.16)
    return wind_chill


def format_time_ago(timestamp: pd.Timestamp) -> str:
    """Format hvor lenge siden en tidsstempel"""
    if pd.isna(timestamp):
        return "Ukjent tid"

    now = pd.Timestamp.now(tz=timestamp.tz)
    diff = now - timestamp

    if diff.total_seconds() < 3600:  # Under 1 time
        minutes = int(diff.total_seconds() / 60)
        return f"{minutes} min siden"
    elif diff.total_seconds() < 86400:  # Under 1 dag
        hours = int(diff.total_seconds() / 3600)
        return f"{hours} timer siden"
    else:
        days = int(diff.total_seconds() / 86400)
        return f"{days} dager siden"


def get_risk_color(risk_level: str) -> str:
    """Få CSS-farge for risikonivå"""
    colors = {
        'high': '#ff4757',
        'medium': '#ffa502',
        'low': '#26de81',
        'unknown': '#747d8c'
    }
    return colors.get(risk_level, '#747d8c')


def get_risk_emoji(risk_level: str) -> str:
    """Returner tom streng.

    Appen bruker ikke emojis i UI.
    """
    return ""


def validate_weather_data(df: pd.DataFrame) -> dict[str, Any]:
    """Valider kvaliteten på værdata"""
    if df.empty:
        return {
            'valid': False,
            'score': 0,
            'issues': ['Ingen data mottatt'],
            'recommendations': ['Sjekk internettforbindelse', 'Verifiser API-nøkkel']
        }

    issues = []
    score = 100

    # Sjekk kritiske kolonner
    critical_columns = ['air_temperature', 'wind_speed']
    for col in critical_columns:
        if col not in df.columns:
            issues.append(f"Mangler {col}")
            score -= 30
        else:
            missing_pct = (df[col].isna().sum() / len(df)) * 100
            if missing_pct > 50:
                issues.append(f"{col}: {missing_pct:.0f}% mangler")
                score -= 20
            elif missing_pct > 20:
                issues.append(f"{col}: {missing_pct:.0f}% mangler")
                score -= 10

    # Sjekk dataalder
    if 'time' in df.columns and not df['time'].empty:
        latest_time = df['time'].max()
        now = pd.Timestamp.now(tz=latest_time.tz if latest_time.tz else None)
        hours_old = (now - latest_time).total_seconds() / 3600

        if hours_old > 6:
            issues.append(f"Data er {hours_old:.1f} timer gammel")
            score -= 15
        elif hours_old > 3:
            issues.append(f"Data er {hours_old:.1f} timer gammel")
            score -= 5

    # Sjekk datamengde
    if len(df) < 10:
        issues.append(f"Lite data ({len(df)} målinger)")
        score -= 10

    recommendations = []
    if score < 70:
        recommendations.append("Vurder å bruke backup-datakilder")
    if score < 50:
        recommendations.append("Begrens analyser til grunnleggende vurderinger")
    if score < 30:
        recommendations.append("Vent og prøv igjen senere")

    return {
        'valid': score >= 30,
        'score': max(0, score),
        'issues': issues,
        'recommendations': recommendations
    }
