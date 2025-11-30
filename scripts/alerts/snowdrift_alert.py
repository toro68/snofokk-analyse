import json
import logging
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd
import requests

# Sett opp logging
logging.basicConfig(level=logging.INFO,
                   format='%(message)s')
logger = logging.getLogger(__name__)

# Logg tidspunkt ved start
logger.info(f"\n=== KJØRING STARTET {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

def load_config():
    """Last inn konfigurasjon fra JSON-fil."""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(script_dir)
        config_path = os.path.join(base_dir, 'config', 'alert_config.json')
        with open(config_path) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Kunne ikke laste konfigurasjonsfil: {str(e)}")
        raise

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
            logger.info(f"Vind: {latest_data['wind_speed']:.1f} m/s (Sterk: {latest_data['wind_speed'] >= config.get('wind_strong', 10.61)}, Moderat: {latest_data['wind_speed'] >= config.get('wind_moderate', 7.77)})")

            if 'max_wind_speed_3h' in latest_data:
                logger.info(f"Vindkast: {latest_data['max_wind_speed_3h']:.1f} m/s")

            if 'wind_from_direction' in latest_data:
                logger.info(f"Vindretning: {latest_data['wind_from_direction']}° ({get_wind_direction_text(latest_data['wind_from_direction'])})")

            logger.info(f"\nTemperatur: {latest_data['air_temperature']:.1f}°C (Kald: {latest_data['air_temperature'] <= config.get('temp_cold', -2.2)}, Kjølig: {latest_data['air_temperature'] <= config.get('temp_cool', 0.0)})")

            logger.info("\nSnøforhold:")
            logger.info(f"- Dybde: {latest_data['surface_snow_thickness']:.1f} cm")
            logger.info(f"- Endring: {latest_data['snow_change']:.2f} cm/t")
            logger.info(f"- Kategorier: Høy: {latest_data['snow_change'] >= config.get('snow_high', 1.61)}, Moderat: {latest_data['snow_change'] >= config.get('snow_moderate', 0.84)}, Lav: {latest_data['snow_change'] >= config.get('snow_low', 0.31)}")

            logger.info(f"\nLuftfuktighet: {latest_data['relative_humidity']:.1f}% (Tørr nok for snøfokk: {latest_data['relative_humidity'] < config.get('humidity_max', 85.0)})")

            return latest_data

        logger.error(f"API-feil: {response.status_code} - {response.text}")
        return None

    except Exception as e:
        logger.error(f"Feil ved henting av værdata: {str(e)}")
        return None

def assess_snowdrift_risk(data, config):
    """Vurderer risiko for snøfokk basert på værdata."""
    try:
        # Vindkriterier
        wind_speed = data['wind_speed']
        wind_strong = wind_speed >= config.get('wind_strong', 10.61)
        wind_moderate = wind_speed >= config.get('wind_moderate', 7.77)

        # Håndter vindkast og vindretning
        max_gust = data.get('max_wind_speed_3h', wind_speed)  # Bruk vindhastighet hvis vindkast mangler
        wind_gust = max_gust >= config.get('wind_gust', 16.96)
        wind_gust_moderate = max_gust >= 10.0  # Moderat vindkast over 10 m/s
        wind_gust_strong = max_gust >= 12.0    # Sterk vindkast over 12 m/s

        # Sjekk vindretningsendring hvis tilgjengelig
        wind_dir_significant = False
        if 'wind_from_direction' in data:
            wind_dir = data['wind_from_direction']
            wind_dir_significant = wind_dir >= config.get('wind_dir_change', 37.83)

        # Beregn risikoscore med vekting
        risk_score = 0

        # Vindrisiko (40%)
        wind_factor = (
            1.0 if wind_strong or wind_gust_strong or (wind_moderate and wind_dir_significant) else
            0.8 if wind_gust_moderate else  # Økt vekt for moderate vindkast
            0.7 if wind_moderate else
            0.3 if wind_gust else
            0.0
        )
        wind_score = wind_factor * config.get('wind_weight', 0.4)

        # Temperaturrisiko (30%)
        temp_factor = (
            1.0 if data['air_temperature'] <= config.get('temp_cold', -2.2) else
            0.7 if data['air_temperature'] <= config.get('temp_cool', 0.0) else
            0.0
        )
        temp_score = temp_factor * config.get('temp_weight', 0.3)

        # Snørisiko (30%)
        snow_factor = (
            1.0 if data['snow_change'] >= config.get('snow_high', 1.61) else
            0.7 if data['snow_change'] >= config.get('snow_moderate', 0.84) else
            0.3 if data['snow_change'] >= config.get('snow_low', 0.31) else
            0.0
        )
        snow_score = snow_factor * config.get('snow_weight', 0.3)

        # Total risikoscore
        risk_score = wind_score + temp_score + snow_score

        logger.info("\n=== RISIKOVURDERING ===")
        logger.info(f"Vind score: {wind_score:.2f} (faktor: {wind_factor})")
        if 'max_wind_speed_3h' in data:
            logger.info(f"Vindkast: {max_gust:.1f} m/s (Sterk: {wind_gust_strong}, Moderat: {wind_gust_moderate})")
        logger.info(f"Temperatur score: {temp_score:.2f} (faktor: {temp_factor})")
        logger.info(f"Snø score: {snow_score:.2f} (faktor: {snow_factor})")
        logger.info(f"\nTotal risikoscore: {risk_score:.2f} av 1.00")

        # Sjekk grunnkriterier - inkluder vindkast i vurderingen
        wind_criteria_met = wind_moderate or wind_strong or wind_gust_moderate
        temp_criteria_met = data['air_temperature'] <= config.get('temp_cool', 0.0)
        snow_criteria_met = data['snow_change'] >= config.get('snow_low', 0.31)
        humidity_criteria_met = data['relative_humidity'] < config.get('humidity_max', 85.0)

        if wind_criteria_met and temp_criteria_met and snow_criteria_met and humidity_criteria_met:
            logger.info("Alle grunnkriterier oppfylt")
        else:
            logger.info("\nIngen varsel nødvendig - grunnkriterier ikke oppfylt:")
            if not wind_criteria_met:
                logger.info("- Vind for svak (må være over 7.77 m/s eller vindkast over 10 m/s)")
            if not temp_criteria_met:
                logger.info("- Temperatur for høy (må være under 0.0°C)")
            if not snow_criteria_met:
                logger.info("- For lite snøendring (må være over 0.31 cm/t)")
            if not humidity_criteria_met:
                logger.info("- For høy luftfuktighet (må være under 85%)")

        return {
            'risk_score': risk_score,
            'conditions': {
                'wind_speed': wind_speed,
                'wind_gust': max_gust,
                'wind_from_direction': wind_dir if 'wind_dir' in locals() else None,
                'temperature': data['air_temperature'],
                'snow_depth': data['surface_snow_thickness'],
                'snow_change': data['snow_change'],
                'humidity': data['relative_humidity']
            },
            'factors': {
                'wind': {
                    'strong': wind_strong,
                    'moderate': wind_moderate,
                    'gust': wind_gust,
                    'gust_moderate': wind_gust_moderate,
                    'gust_strong': wind_gust_strong,
                    'dir_change': wind_dir_significant if 'wind_dir_significant' in locals() else False,
                    'score': wind_score if 'wind_score' in locals() else 0
                },
                'temp': {
                    'cold': data['air_temperature'] <= config.get('temp_cold', -2.2),
                    'cool': data['air_temperature'] <= config.get('temp_cool', 0.0),
                    'score': temp_score if 'temp_score' in locals() else 0
                },
                'snow': {
                    'high': data['snow_change'] >= config.get('snow_high', 1.61),
                    'moderate': data['snow_change'] >= config.get('snow_moderate', 0.84),
                    'low': data['snow_change'] >= config.get('snow_low', 0.31),
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

        body = f"""VARSEL: Risiko for snøfokk i Fjellbergsskardet Hyttegrend

Tid: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Risikoscore: {risk_assessment['risk_score']:.2f} av 1.00

VÆRFORHOLD:
- Vindstyrke: {risk_assessment['conditions']['wind_speed']:.1f} m/s
- Vindkast: {risk_assessment['conditions']['wind_gust']:.1f} m/s
- Vindretning: {wind_dir if wind_dir else "Ukjent"}° ({compass_dir})
- Temperatur: {risk_assessment['conditions']['temperature']:.1f}°C
- Snøendring: {risk_assessment['conditions']['snow_change']:.2f} cm/t
- Luftfuktighet: {risk_assessment['conditions']['humidity']:.1f}%

RISIKOVURDERING:
⚠️ Sterk vind over {config.get('wind_strong', 10.61)} m/s
⚡ Kraftige vindkast over {config.get('wind_gust', 16.96)} m/s
❄️ Temperatur under {config.get('temp_cold', -2.2)}°C
🌨️ Moderat til høy snøendring
💧 Luftfuktighet under {config.get('humidity_max', 85.0)}%

-------------------

OM RISIKOVURDERINGEN:
Varselet er basert på en automatisk analyse av følgende faktorer:

1. VIND (40% vekt)
   - Sterk: Over {config.get('wind_strong', 10.61)} m/s
   - Moderat: Over {config.get('wind_moderate', 7.77)} m/s
   - Vindkast: Moderate over 10 m/s, sterke over 12 m/s
   - Vindretningsendringer over {config.get('wind_dir_change', 37.83)}° følges

2. TEMPERATUR (30% vekt)
   - Kald: Under {config.get('temp_cold', -2.2)}°C
   - Kjølig: Under {config.get('temp_cool', 0.0)}°C

3. SNØFORHOLD (30% vekt)
   - Høy endring: Over {config.get('snow_high', 1.61)} cm/t
   - Moderat endring: Over {config.get('snow_moderate', 0.84)} cm/t
   - Lav endring: Over {config.get('snow_low', 0.31)} cm/t

4. ANDRE FAKTORER
   - Luftfuktighet under {config.get('humidity_max', 85.0)}% øker risiko for fokk
   - Minimum varighet: {config.get('min_duration', 2)} timer
   - Nedkjølingstid: {config.get('cooldown_hours', 12)} timer (minimum tid mellom varsler for samme værsituasjon for å unngå for hyppige varsler)

Risikoscoren går fra 0 til 1, der:
- Over 0.90: Svært høy risiko
- 0.80-0.89: Høy risiko
- 0.70-0.79: Moderat risiko
- Under 0.70: Lav risiko

Dette varselet sendes automatisk når risikoscoren overstiger {config['risk_threshold']}.

-------------------
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
            if hours_since_last < config.get('cooldown_hours', 12):
                logger.info(f"For kort tid siden siste varsel ({hours_since_last:.1f} timer)")
                return

        # Hent værdata
        weather_data = get_weather_data(config)
        if not weather_data:
            return

        # Vurder risiko og send varsel
        risk_assessment = assess_snowdrift_risk(weather_data, config)
        if risk_assessment and risk_assessment['risk_score'] >= config['risk_threshold']:
            send_alert(config, risk_assessment)
        else:
            logger.info("Ingen varsel nødvendig")

    except Exception as e:
        logger.error(f"Feil i hovedfunksjon: {str(e)}")

if __name__ == '__main__':
    main()
