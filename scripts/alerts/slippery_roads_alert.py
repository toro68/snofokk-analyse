import os
import json
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from pathlib import Path

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
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Kunne ikke laste konfigurasjonsfil: {str(e)}")
        raise

def get_last_alert_time():
    """Hent tidspunkt for siste varsel fra fil."""
    try:
        if os.path.exists('last_slippery_alert.txt'):
            with open('last_slippery_alert.txt', 'r') as f:
                timestamp = f.read().strip()
                return datetime.fromisoformat(timestamp)
    except Exception as e:
        logger.error(f"Feil ved lesing av siste varseltidspunkt: {str(e)}")
    return None

def save_last_alert_time(timestamp):
    """Lagre tidspunkt for siste varsel til fil."""
    try:
        with open('last_slippery_alert.txt', 'w') as f:
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
                'air_temperature', 'relative_humidity',
                'surface_snow_thickness', 'sum(precipitation_amount PT1H)'
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
            
            # Sorter etter tid og beregn endringer
            pivot_df = pivot_df.sort_values('referenceTime')
            pivot_df['snow_change'] = pivot_df['surface_snow_thickness'].diff()
            pivot_df['precip_3h'] = pivot_df['sum(precipitation_amount PT1H)'].rolling(
                window=3, min_periods=1).sum()
            
            # Konverter til dictionary for enklere håndtering
            latest_data = {
                'air_temperature': float(pivot_df['air_temperature'].iloc[-1]),
                'surface_snow_thickness': float(pivot_df['surface_snow_thickness'].iloc[-1]),
                'relative_humidity': float(pivot_df['relative_humidity'].iloc[-1]),
                'snow_change': float(pivot_df['snow_change'].fillna(0).iloc[-1]),
                'precip_3h': float(pivot_df['precip_3h'].fillna(0).iloc[-1])
            }
            
            logger.info("\n=== VÆRDATA ===")
            logger.info(f"Temperatur: {latest_data['air_temperature']:.1f}°C")
            logger.info(f"Luftfuktighet: {latest_data['relative_humidity']:.1f}%")
            logger.info(f"Snødybde: {latest_data['surface_snow_thickness']:.1f} cm")
            logger.info(f"Endring i snødybde: {latest_data['snow_change']:.1f} cm")
            logger.info(f"Nedbør siste 3 timer: {latest_data['precip_3h']:.1f} mm")
            
            return latest_data
            
        logger.error(f"API-feil: {response.status_code} - {response.text}")
        return None
        
    except Exception as e:
        logger.error(f"Feil ved henting av værdata: {str(e)}")
        return None

def assess_slippery_conditions(weather_data, config):
    """Vurderer om forholdene tilsier glatte veier."""
    try:
        conditions = {
            'temp_ok': 0 <= weather_data['air_temperature'] <= 6,
            'humidity_ok': weather_data['relative_humidity'] >= 80,
            'precip_ok': weather_data['precip_3h'] >= 1.5,
            'snow_ok': weather_data['surface_snow_thickness'] >= 10,
            'melting_ok': weather_data['snow_change'] < 0
        }
        
        risk_present = all(conditions.values())
        
        logger.info("\n=== RISIKOVURDERING ===")
        logger.info("Kriterier for glatte veier:")
        logger.info(f"- Temperatur mellom 0°C og +6°C: {conditions['temp_ok']}")
        logger.info(f"- Høy luftfuktighet (>80%): {conditions['humidity_ok']}")
        logger.info(f"- Tilstrekkelig nedbør (>1.5mm/3t): {conditions['precip_ok']}")
        logger.info(f"- Nok snø på bakken (>10cm): {conditions['snow_ok']}")
        logger.info(f"- Minkende snødybde: {conditions['melting_ok']}")
        
        if risk_present:
            logger.info("\nAlle kriterier oppfylt - risiko for glatte veier")
        else:
            logger.info("\nIngen varsel nødvendig - ikke alle kriterier oppfylt")
        
        return {
            'risk_present': risk_present,
            'conditions': conditions,
            'weather_data': weather_data
        }
        
    except Exception as e:
        logger.error(f"Feil ved risikovurdering: {str(e)}")
        return None

def send_alert(config, assessment):
    """Send e-postvarsel."""
    try:
        msg = MIMEMultipart()
        msg['From'] = config['email_from']
        msg['To'] = config['email_to']
        msg['Subject'] = 'VARSEL: Risiko for glatte veier i Fjellbergsskardet'
        
        body = f"""VARSEL: Risiko for glatte veier i Fjellbergsskardet

Tid: {datetime.now().strftime('%Y-%m-%d %H:%M')}

VÆRFORHOLD:
- Temperatur: {assessment['weather_data']['air_temperature']:.1f}°C
- Luftfuktighet: {assessment['weather_data']['relative_humidity']:.1f}%
- Snødybde: {assessment['weather_data']['surface_snow_thickness']:.1f} cm
- Endring i snødybde: {assessment['weather_data']['snow_change']:.1f} cm
- Nedbør siste 3 timer: {assessment['weather_data']['precip_3h']:.1f} mm

KRITERIER OPPFYLT:
✓ Temperatur mellom 0°C og +6°C
✓ Høy luftfuktighet (over 80%)
✓ Tilstrekkelig nedbør (over 1.5mm/3t)
✓ Nok snø på bakken (over 10cm)
✓ Minkende snødybde (smelting)

-------------------
Dette er et automatisk varsel med værdata fra Gullingen værstasjon.

Vi jobber kontinuerlig med å forbedre varslingssystemet. Gi gjerne 
tilbakemelding dersom du opplever glatte veier som ikke ble varslet, 
eller varsler som ikke samsvarer med faktiske forhold. Dette hjelper 
oss å justere parameterne for mer presise varsler."""
        
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
        assessment = assess_slippery_conditions(weather_data, config)
        if assessment and assessment['risk_present']:
            send_alert(config, assessment)
        else:
            logger.info("Ingen varsel nødvendig")
            
    except Exception as e:
        logger.error(f"Feil i hovedfunksjon: {str(e)}")

if __name__ == '__main__':
    main() 