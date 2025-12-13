import logging
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd
import requests

from src.config import get_secret, settings

# Sett opp logging
logging.basicConfig(level=logging.INFO,
                   format='%(message)s')
logger = logging.getLogger(__name__)

# Logg tidspunkt ved start
logger.info(f"\n=== KJØRING STARTET {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

def load_config():
    """Bygg runtime-konfigurasjon.

    Terskler hentes fra `src/config.py` (settings.*) for å unngå drift.
    Secrets hentes fra Streamlit secrets eller miljøvariabler.
    """
    cooldown_hours = int(get_secret("ALERT_COOLDOWN_HOURS", os.getenv("ALERT_COOLDOWN_HOURS", "12")) or "12")
    return {
        "frost_client_id": settings.api.client_id,
        "weather_station": settings.station.station_id,
        "cooldown_hours": cooldown_hours,
        "email_from": get_secret("ALERT_EMAIL_FROM", ""),
        "email_to": get_secret("ALERT_EMAIL_TO", ""),
        "smtp_server": get_secret("ALERT_SMTP_SERVER", "smtp.gmail.com"),
        "smtp_username": get_secret("ALERT_SMTP_USERNAME", ""),
        "smtp_password": get_secret("ALERT_SMTP_PASSWORD", ""),
    }

def get_last_alert_time():
    """Hent tidspunkt for siste varsel fra fil."""
    try:
        if os.path.exists('last_alert.txt'):
            with open('last_alert.txt') as f:
                timestamp = f.read().strip()
                return datetime.fromisoformat(timestamp)
    except Exception as e:
        logger.error(f"Feil ved lesing av siste varseltidspunkt: {str(e)}")
    return None

def save_last_alert_time(timestamp):
    """Lagre tidspunkt for siste varsel til fil."""
    try:
        with open('last_alert.txt', 'w') as f:
            f.write(timestamp.isoformat())
    except Exception as e:
        logger.error(f"Feil ved lagring av varseltidspunkt: {str(e)}")

def get_weather_data(config):
    """Henter ferske værdata fra Frost API."""
    try:
        endpoint = 'https://frost.met.no/observations/v0.jsonld'

        now = datetime.now()
        three_hours_ago = now - timedelta(hours=3)

        # Formater datoene i ISO format som Frost API forventer
        from_time = three_hours_ago.strftime('%Y-%m-%dT%H:%M:%S')
        to_time = now.strftime('%Y-%m-%dT%H:%M:%S')

        params = {
            'sources': config['weather_station'],
            'elements': ','.join([
                'air_temperature', 'wind_speed', 'relative_humidity',
                'surface_snow_thickness', 'max_wind_speed_3h',
                'wind_from_direction'
            ]),
            'referencetime': f"{from_time}/{to_time}"
        }

        response = requests.get(
            endpoint,
            params=params,
            auth=(config['frost_client_id'], '')
        )

        if response.status_code == 200:
            data = response.json()

            if not data.get('data'):
                logger.error("Ingen data mottatt fra API-en")
                return None

            # Konverter data til DataFrame
            df = pd.json_normalize(
                data['data'],
                ['observations'],
                ['referenceTime']
            )

            # Filtrer bare timesdata
            df = df[df['timeResolution'] == 'PT1H']

            # Pivot dataene for å få riktig format
            pivot_df = df.pivot_table(
                index='referenceTime',
                columns='elementId',
                values='value',
                aggfunc='first'
            ).reset_index()

            # Konverter referenceTime til datetime
            pivot_df['referenceTime'] = pd.to_datetime(pivot_df['referenceTime'])

            # Sorter etter tid og beregn endring i snødybde per time
            pivot_df = pivot_df.sort_values('referenceTime')
            pivot_df['time_diff'] = pivot_df['referenceTime'].diff().dt.total_seconds() / 3600  # Timer
            pivot_df['snow_change'] = abs(pivot_df['surface_snow_thickness'].diff() / pivot_df['time_diff'])
            pivot_df['snow_change'] = pivot_df['snow_change'].fillna(0)

            # Konverter til dictionary for enklere håndtering
            latest_data = {
                'wind_speed': float(pivot_df['wind_speed'].max()),
                'air_temperature': float(pivot_df['air_temperature'].mean()),
                'surface_snow_thickness': float(pivot_df['surface_snow_thickness'].max()),
                'relative_humidity': float(pivot_df['relative_humidity'].mean()),
                'snow_change': float(pivot_df['snow_change'].fillna(0).max()),
            }

            # Legg til vindkast hvis tilgjengelig
            if 'max_wind_speed_3h' in pivot_df.columns:
                latest_data['max_wind_speed_3h'] = float(pivot_df['max_wind_speed_3h'].max())

            logger.info("\n=== VÆRDATA ===")
            sd = settings.snowdrift
            logger.info(
                f"Vind: {latest_data['wind_speed']:.1f} m/s (Sterk: {latest_data['wind_speed'] >= sd.wind_speed_critical}, "
                f"Moderat: {latest_data['wind_speed'] >= sd.wind_speed_warning})"
            )

            if 'max_wind_speed_3h' in latest_data:
                logger.info(f"Vindkast: {latest_data['max_wind_speed_3h']:.1f} m/s")

            if 'wind_from_direction' in latest_data:
                logger.info(f"Vindretning: {latest_data['wind_from_direction']}° ({get_wind_direction_text(latest_data['wind_from_direction'])})")

            logger.info(
                f"\nTemperatur: {latest_data['air_temperature']:.1f}°C (Gate: ≤ {sd.temperature_max:.1f}°C)"
            )

            logger.info("\nSnøforhold:")
            logger.info(f"- Dybde: {latest_data['surface_snow_thickness']:.1f} cm")
            logger.info(f"- Endring: {latest_data['snow_change']:.2f} cm/t")
            snow_rate_low = sd.fresh_snow_threshold
            snow_rate_med = 2 * sd.fresh_snow_threshold
            snow_rate_high = 4 * sd.fresh_snow_threshold
            logger.info(
                f"- Kategorier (cm/t): Høy: {latest_data['snow_change'] >= snow_rate_high}, "
                f"Moderat: {latest_data['snow_change'] >= snow_rate_med}, "
                f"Lav: {latest_data['snow_change'] >= snow_rate_low}"
            )

            return latest_data

        logger.error(f"API-feil: {response.status_code} - {response.text}")
        return None

    except Exception as e:
        logger.error(f"Feil ved henting av værdata: {str(e)}")
        return None

def assess_snowdrift_risk(data, config):
    """Vurderer risiko for snøfokk basert på værdata."""
    try:
        sd = settings.snowdrift

        # Vindkriterier
        wind_speed = data['wind_speed']
        wind_strong = wind_speed >= sd.wind_speed_critical
        wind_moderate = wind_speed >= sd.wind_speed_warning

        # Håndter vindkast og vindretning
        max_gust = data.get('max_wind_speed_3h', wind_speed)  # Bruk vindhastighet hvis vindkast mangler
        wind_gust_warning = max_gust >= sd.wind_gust_warning
        wind_gust_critical = max_gust >= sd.wind_gust_critical

        # Sjekk kritisk vindsektor hvis tilgjengelig
        wind_dir_in_critical_sector = False
        wind_dir = None
        if 'wind_from_direction' in data and data['wind_from_direction'] is not None:
            wind_dir = float(data['wind_from_direction'])
            wind_dir_in_critical_sector = sd.critical_wind_dir_min <= wind_dir <= sd.critical_wind_dir_max

        # Beregn risikoscore med vekting
        risk_score = 0

        # Vindrisiko (40%)
        wind_factor = (
            1.0 if wind_strong or wind_gust_critical or (wind_moderate and wind_dir_in_critical_sector) else
            0.8 if wind_gust_warning else
            0.7 if wind_moderate else
            0.0
        )
        wind_score = wind_factor * 0.4

        # Temperaturrisiko (30%)
        temp_factor = 1.0 if data['air_temperature'] <= sd.temperature_max else 0.0
        temp_score = temp_factor * 0.3

        # Snørisiko (30%)
        snow_rate_low = sd.fresh_snow_threshold
        snow_rate_med = 2 * sd.fresh_snow_threshold
        snow_rate_high = 4 * sd.fresh_snow_threshold
        snow_factor = (
            1.0 if data['snow_change'] >= snow_rate_high else
            0.7 if data['snow_change'] >= snow_rate_med else
            0.3 if data['snow_change'] >= snow_rate_low else
            0.0
        )
        snow_score = snow_factor * 0.3

        # Total risikoscore
        risk_score = wind_score + temp_score + snow_score

        logger.info("\n=== RISIKOVURDERING ===")
        logger.info(f"Vind score: {wind_score:.2f} (faktor: {wind_factor})")
        if 'max_wind_speed_3h' in data:
            logger.info(f"Vindkast: {max_gust:.1f} m/s (Kritisk: {wind_gust_critical}, Advarsel: {wind_gust_warning})")
        logger.info(f"Temperatur score: {temp_score:.2f} (faktor: {temp_factor})")
        logger.info(f"Snø score: {snow_score:.2f} (faktor: {snow_factor})")
        logger.info(f"\nTotal risikoscore: {risk_score:.2f} av 1.00")

        # Sjekk grunnkriterier (uten egen fukt-gating i gjeldende config)
        wind_criteria_met = wind_moderate or wind_strong or wind_gust_warning
        temp_criteria_met = data['air_temperature'] <= sd.temperature_max
        snow_criteria_met = data['snow_change'] >= sd.fresh_snow_threshold

        should_alert = wind_criteria_met and temp_criteria_met and snow_criteria_met

        if should_alert:
            logger.info("Alle grunnkriterier oppfylt")
        else:
            logger.info("\nIngen varsel nødvendig - grunnkriterier ikke oppfylt:")
            if not wind_criteria_met:
                logger.info("- Vind/vindkast for svak")
            if not temp_criteria_met:
                logger.info(f"- Temperatur for høy (må være ≤ {sd.temperature_max:.1f}°C)")
            if not snow_criteria_met:
                logger.info(f"- For lite snøendring (må være ≥ {sd.fresh_snow_threshold:.2f} cm/t)")

        return {
            'should_alert': should_alert,
            'risk_score': risk_score,
            'conditions': {
                'wind_speed': wind_speed,
                'wind_gust': max_gust,
                'wind_from_direction': wind_dir,
                'temperature': data['air_temperature'],
                'snow_depth': data['surface_snow_thickness'],
                'snow_change': data['snow_change'],
                'humidity': data.get('relative_humidity')
            },
            'factors': {
                'wind': {
                    'strong': wind_strong,
                    'moderate': wind_moderate,
                    'gust_warning': wind_gust_warning,
                    'gust_critical': wind_gust_critical,
                    'critical_sector': wind_dir_in_critical_sector,
                    'score': wind_score if 'wind_score' in locals() else 0
                },
                'temp': {
                    'cool': data['air_temperature'] <= sd.temperature_max,
                    'score': temp_score if 'temp_score' in locals() else 0
                },
                'snow': {
                    'high': data['snow_change'] >= snow_rate_high,
                    'moderate': data['snow_change'] >= snow_rate_med,
                    'low': data['snow_change'] >= snow_rate_low,
                    'score': snow_score if 'snow_score' in locals() else 0
                }
            }
        }

    except Exception as e:
        logger.error(f"Feil ved risikovurdering: {str(e)}")
        return None

def send_alert(config, risk_assessment):
    """Send e-postvarsel."""
    try:
        msg = MIMEMultipart()
        msg['From'] = config['email_from']
        msg['To'] = config['email_to']
        msg['Subject'] = (
            'VARSEL: Risiko for snøfokk i Fjellbergsskardet Hyttegrend'
        )

        # Konverter vindretning til kompassretning
        wind_dir = risk_assessment['conditions'].get('wind_from_direction')
        compass_dir = get_wind_direction_text(wind_dir) if wind_dir else "Ukjent"

        sd = settings.snowdrift
        body = f"""VARSEL: Risiko for snøfokk i Fjellbergsskardet Hyttegrend

Tid: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Risikoscore: {risk_assessment['risk_score']:.2f} av 1.00

VÆRFORHOLD:
- Vindstyrke: {risk_assessment['conditions']['wind_speed']:.1f} m/s
- Vindkast: {risk_assessment['conditions']['wind_gust']:.1f} m/s
- Vindretning: {wind_dir if wind_dir else "Ukjent"}° ({compass_dir})
- Temperatur: {risk_assessment['conditions']['temperature']:.1f}°C
- Snøendring: {risk_assessment['conditions']['snow_change']:.2f} cm/t

VURDERING:
- Varselet er trigget av vind/vindkast, frost-gate og snøtilgjengelighet.
- Gjeldende terskler hentes fra `src/config.py` (settings.snowdrift.*).

NØKKELTERSKLER (fra konfigurasjon):
- Vindkast: advarsel ≥ {sd.wind_gust_warning:.0f} m/s, kritisk ≥ {sd.wind_gust_critical:.0f} m/s
- Vind (snitt): advarsel ≥ {sd.wind_speed_warning:.0f} m/s, kritisk ≥ {sd.wind_speed_critical:.0f} m/s
- Temperatur gate: ≤ {sd.temperature_max:.1f}°C
- Minimum snødekke: ≥ {sd.snow_depth_min_cm:.0f} cm
Dette er et automatisk varsel med værdata fra Gullingen værstasjon.

Vi jobber kontinuerlig med å forbedre varslingssystemet. Gi gjerne
tilbakemelding dersom du opplever situasjoner med snøfokk som ikke ble
varslet, eller varsler som ikke samsvarer med faktiske forhold. Dette
hjelper oss å justere parameterne for mer presise varsler."""

        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(config['smtp_server'], 587) as server:
            server.starttls()
            server.login(config['smtp_username'], config['smtp_password'])
            server.send_message(msg)

        logger.info("Varsel sendt på e-post")

        # Lagre varseltidspunkt
        save_last_alert_time(datetime.now())

    except Exception as e:
        logger.error(f"Feil ved sending av varsel: {str(e)}")

def get_wind_direction_text(degrees):
    """Konverterer vindretning i grader til kompassretning."""
    directions = ['Nord', 'Nordøst', 'Øst', 'Sørøst', 'Sør',
                 'Sørvest', 'Vest', 'Nordvest']
    index = round(degrees / 45) % 8
    return directions[index]

def main():
    """Hovedfunksjon for værovervåking og varsling."""
    try:
        config = load_config()

        # Sjekk siste varsel
        last_alert = get_last_alert_time()
        if last_alert:
            hours_since_last = (datetime.now() - last_alert).total_seconds() / 3600
            if hours_since_last < config['cooldown_hours']:
                logger.info(f"For kort tid siden siste varsel ({hours_since_last:.1f} timer)")
                return

        # Hent værdata
        weather_data = get_weather_data(config)
        if not weather_data:
            return

        # Vurder risiko og send varsel
        risk_assessment = assess_snowdrift_risk(weather_data, config)
        if risk_assessment and risk_assessment.get('should_alert'):
            send_alert(config, risk_assessment)
        else:
            logger.info("Ingen varsel nødvendig")

    except Exception as e:
        logger.error(f"Feil i hovedfunksjon: {str(e)}")

if __name__ == '__main__':
    main()
