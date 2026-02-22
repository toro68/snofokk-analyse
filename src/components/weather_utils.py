"""
Fallback og utility funksjoner for mobil weather app
"""
from datetime import timedelta
from typing import Any

import pandas as pd

from src.config import settings


def simple_snowdrift_analysis(temp: float, wind: float, snow_depth: float | None = None) -> dict[str, Any]:
    """Enkel snøfokk-analyse uten ML"""

    th = settings.fallback

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
    confidence = th.snowdrift_confidence_base

    # Temperatur-vurdering
    if temp <= th.snowdrift_temp_very_cold_max_c:
        factors.append(f"Meget kald luft ({temp:.1f}°C)")
        temp_score = 3
    elif temp <= th.snowdrift_temp_cold_max_c:
        factors.append(f"Kald luft ({temp:.1f}°C)")
        temp_score = 2
    elif temp <= th.snowdrift_temp_freezing_max_c:
        factors.append(f"Under frysepunktet ({temp:.1f}°C)")
        temp_score = 1
    else:
        factors.append(f"For varmt for snøfokk ({temp:.1f}°C)")
        temp_score = 0

    # Vind-vurdering
    if wind >= th.snowdrift_wind_strong_min_ms:
        factors.append(f"Sterk vind ({wind:.1f} m/s)")
        wind_score = 3
    elif wind >= th.snowdrift_wind_moderate_min_ms:
        factors.append(f"Moderat vind ({wind:.1f} m/s)")
        wind_score = 2
    elif wind >= th.snowdrift_wind_light_min_ms:
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
            snow_cm = snow_depth * 100 if snow_depth < settings.historical.snow_depth_conversion_cutoff_cm else snow_depth
            if snow_cm >= th.snowdrift_snow_cm_high_min:
                factors.append(f"Mye snø ({snow_cm:.0f} cm)")
                snow_score = 2
            elif snow_cm >= th.snowdrift_snow_cm_medium_min:
                factors.append(f"Noe snø ({snow_cm:.0f} cm)")
                snow_score = 1
            else:
                factors.append(f"Lite snø ({snow_cm:.0f} cm)")
                snow_score = 0
    else:
        factors.append("Snødybde ukjent")

    # Kombinert vurdering
    total_score = temp_score + wind_score + snow_score

    if (
        total_score >= th.snowdrift_high_total_score_min
        and temp <= th.snowdrift_high_temp_max_c
        and wind >= th.snowdrift_high_wind_min_ms
    ):
        risk_level = 'high'
        message = 'Høy snøfokk-risiko'
        confidence = th.snowdrift_confidence_high
    elif (
        total_score >= th.snowdrift_medium_total_score_min
        and temp <= th.snowdrift_medium_temp_max_c
        and wind >= th.snowdrift_medium_wind_min_ms
    ):
        risk_level = 'medium'
        message = 'Moderat snøfokk-risiko'
        confidence = th.snowdrift_confidence_medium
    elif total_score >= th.snowdrift_low_total_score_min:
        risk_level = 'low'
        message = 'Lav snøfokk-risiko'
        confidence = th.snowdrift_confidence_low
    else:
        risk_level = 'low'
        message = 'Meget lav snøfokk-risiko'
        confidence = th.snowdrift_confidence_very_low

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

    th = settings.fallback

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
    if th.slippery_temp_band_min_c <= analysis_temp <= th.slippery_temp_band_max_c:
        if pd.notna(humidity):
            if humidity > th.slippery_humidity_high_pct:
                risk_level = 'high'
                message = 'Høy glattføre-risiko'
                confidence = th.slippery_confidence_high
                factors.append(f"Kritisk temperatur ({analysis_temp:.1f}°C)")
                factors.append(f"Meget høy fuktighet ({humidity:.0f}%)")
            elif humidity > th.slippery_humidity_medium_pct:
                risk_level = 'medium'
                message = 'Moderat glattføre-risiko'
                confidence = th.slippery_confidence_medium
                factors.append(f"Risiko-temperatur ({analysis_temp:.1f}°C)")
                factors.append(f"Høy fuktighet ({humidity:.0f}%)")
            else:
                risk_level = 'low'
                message = 'Lav glattføre-risiko'
                confidence = th.slippery_confidence_low
                factors.append(f"Grensetemperatur ({analysis_temp:.1f}°C)")
                factors.append(f"Moderat fuktighet ({humidity:.0f}%)")
        else:
            # Ingen fuktighetsmåling
            if th.slippery_temp_near_freezing_min_c <= analysis_temp <= th.slippery_temp_near_freezing_max_c:
                risk_level = 'medium'
                message = 'Moderat glattføre-risiko'
                confidence = th.slippery_confidence_medium_no_humidity
                factors.append(f"Kritisk temperatur ({analysis_temp:.1f}°C)")
                factors.append("Fuktighet ukjent")
            else:
                risk_level = 'low'
                message = 'Lav glattføre-risiko'
                confidence = th.slippery_confidence_low_no_humidity
                factors.append(f"Grensetemperatur ({analysis_temp:.1f}°C)")
                factors.append("Fuktighet ukjent")

    elif analysis_temp < th.slippery_stable_cold_max_c:
        risk_level = 'low'
        message = 'Stabilt kaldt - godt førføre'
        confidence = th.slippery_confidence_stable_cold
        factors.append(f"Stabilt kaldt ({analysis_temp:.1f}°C)")
        factors.append("Optimale kjøreforhold på snø")

    elif analysis_temp > th.slippery_too_warm_min_c:
        risk_level = 'low'
        message = 'For varmt for glattføre'
        confidence = th.slippery_confidence_too_warm
        factors.append(f"Varmt ({analysis_temp:.1f}°C)")
        factors.append("Ingen is-fare")

    else:
        risk_level = 'low'
        message = 'Lav glattføre-risiko'
        confidence = th.slippery_confidence_low
        factors.append(f"Moderat temperatur ({analysis_temp:.1f}°C)")

    # Legg til temperaturtype-info
    if pd.notna(surface_temp) and pd.notna(temp):
        if abs(surface_temp - temp) > settings.slippery.surface_air_diff_notice_min_c:
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

    if diff < timedelta(hours=1):
        minutes = int(diff.total_seconds() / 60)
        return f"{minutes} min siden"
    elif diff < timedelta(days=1):
        hours = int(diff.total_seconds() / 3600)
        return f"{hours} timer siden"
    else:
        days = int(diff / timedelta(days=1))
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


def get_risk_emoji(_risk_level: str) -> str:
    """Returner tom streng.

    Appen bruker ikke emojis i UI.
    """
    return ""


def validate_weather_data(df: pd.DataFrame) -> dict[str, Any]:
    """Valider kvaliteten på værdata"""
    th = settings.fallback

    if df.empty:
        return {
            'valid': False,
            'score': 0,
            'issues': ['Ingen data mottatt'],
            'recommendations': ['Sjekk internettforbindelse', 'Verifiser API-nøkkel']
        }

    issues = []
    score = th.data_quality_score_start

    # Sjekk kritiske kolonner
    critical_columns = ['air_temperature', 'wind_speed']
    for col in critical_columns:
        if col not in df.columns:
            issues.append(f"Mangler {col}")
            score -= th.data_quality_missing_col_penalty
        else:
            missing_pct = (df[col].isna().sum() / len(df)) * 100
            if missing_pct > th.data_quality_missing_pct_high:
                issues.append(f"{col}: {missing_pct:.0f}% mangler")
                score -= th.data_quality_missing_pct_high_penalty
            elif missing_pct > th.data_quality_missing_pct_medium:
                issues.append(f"{col}: {missing_pct:.0f}% mangler")
                score -= th.data_quality_missing_pct_medium_penalty

    # Sjekk dataalder
    if 'time' in df.columns and not df['time'].empty:
        latest_time = df['time'].max()
        now = pd.Timestamp.now(tz=latest_time.tz if latest_time.tz else None)
        hours_old = (now - latest_time).total_seconds() / 3600

        if hours_old > th.data_quality_hours_old_critical:
            issues.append(f"Data er {hours_old:.1f} timer gammel")
            score -= th.data_quality_hours_old_critical_penalty
        elif hours_old > th.data_quality_hours_old_warning:
            issues.append(f"Data er {hours_old:.1f} timer gammel")
            score -= th.data_quality_hours_old_warning_penalty

    # Sjekk datamengde
    if len(df) < th.data_quality_min_rows:
        issues.append(f"Lite data ({len(df)} målinger)")
        score -= th.data_quality_min_rows_penalty

    recommendations = []
    if score < th.data_quality_reco_backup_below_score:
        recommendations.append("Vurder å bruke backup-datakilder")
    if score < th.data_quality_reco_basic_only_below_score:
        recommendations.append("Begrens analyser til grunnleggende vurderinger")
    if score < th.data_quality_reco_wait_below_score:
        recommendations.append("Vent og prøv igjen senere")

    return {
        'valid': score >= th.data_quality_valid_min_score,
        'score': max(0, score),
        'issues': issues,
        'recommendations': recommendations
    }
