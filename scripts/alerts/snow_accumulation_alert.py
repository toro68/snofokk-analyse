import json
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from pathlib import Path


# Sett opp basismappe
BASE_DIR = Path(__file__).parent.parent
LOG_DIR = BASE_DIR / 'logs'
DATA_DIR = BASE_DIR / 'data'
CONFIG_FILE = BASE_DIR / 'config' / 'test_config.json'

# Opprett nødvendige mapper
LOG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Sett opp logging
log_file = LOG_DIR / 'snow_alert.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_config():
    """Last inn konfigurasjon fra JSON-fil."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Kunne ikke laste konfigurasjonsfil: {str(e)}")
        raise


def get_last_alert_time():
    """Hent tidspunkt for siste varsel fra fil."""
    try:
        alert_file = DATA_DIR / 'last_snow_alert.txt'
        if alert_file.exists():
            with open(alert_file, 'r') as f:
                timestamp = f.read().strip()
                return datetime.fromisoformat(timestamp)
    except Exception as e:
        logger.error(f"Feil ved lesing av siste varseltidspunkt: {str(e)}")
    return None


def save_last_alert_time(timestamp):
    """Lagre tidspunkt for siste varsel til fil."""
    try:
        alert_file = DATA_DIR / 'last_snow_alert.txt'
        with open(alert_file, 'w') as f:
            f.write(timestamp.isoformat())
    except Exception as e:
        logger.error(f"Feil ved lagring av varseltidspunkt: {str(e)}")


def get_weather_data(config, test_date=None):
    """Henter ferske værdata fra Frost API."""
    try:
        endpoint = 'https://frost.met.no/observations/v0.jsonld'
        
        if test_date:
            now = test_date
        else:
            now = datetime.now()
            
        check_hours = config['snow_alert']['check_hours']
        hours_ago = now - timedelta(hours=check_hours)
        
        # Formater datoene i ISO format som Frost API forventer
        from_time = hours_ago.strftime('%Y-%m-%dT%H:%M:%S')
        to_time = now.strftime('%Y-%m-%dT%H:%M:%S')
        
        params = {
            'sources': config['weather_station'],
            'elements': ','.join([
                'air_temperature',
                'surface_snow_thickness',
                'sum(precipitation_amount PT1H)'
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
            
            # Pivot dataene for å få riktig format
            pivot_df = df.pivot_table(
                index='referenceTime',
                columns='elementId',
                values='value',
                aggfunc='first'
            ).reset_index()
            
            # Konverter referenceTime til datetime
            pivot_df['referenceTime'] = pd.to_datetime(
                pivot_df['referenceTime']
            )
            pivot_df = pivot_df.sort_values('referenceTime')
            
            # Beregn endring i snødybde
            pivot_df['snow_change'] = pivot_df['surface_snow_thickness'].diff()
            
            return pivot_df
            
        logger.error(f"API-feil: {response.status_code} - {response.text}")
        return None
        
    except Exception as e:
        logger.error(f"Feil ved henting av værdata: {str(e)}")
        return None


def get_last_plowing():
    """Hent tidspunkt for siste brøyting."""
    try:
        url = (
            "https://plowman-new.xn--snbryting-m8ac.net/nb/share/"
            "Y3VzdG9tZXItMTM="
        )
        response = requests.get(url, timeout=10)
        
        if not response.ok:
            logger.error(
                "Feil ved henting av brøytedata. "
                f"Status: {response.status_code}"
            )
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        scripts = soup.find_all('script')
        
        if len(scripts) >= 29:
            script = scripts[28]
            if script.string:
                content = script.string.strip()
                
                if 'self.__next_f.push' in content:
                    content = content.replace('self.__next_f.push([1,"', '')
                    content = content.replace('"])', '')
                    content = content.replace('\\"', '"')
                    
                    if '{"dictionary"' in content:
                        start = content.find('{"dictionary"')
                        end = content.rfind('}') + 1
                        json_str = content[start:end]
                        data = json.loads(json_str)
                        
                        # Finn alle tidspunkt
                        timestamps = []
                        for f in data.get('geojson', {}).get("features", []):
                            ts = f.get("properties", {}).get("lastUpdated")
                            if ts:
                                clean_ts = ts.replace('$D', '')
                                try:
                                    dt_utc = datetime.strptime(
                                        clean_ts, 
                                        '%Y-%m-%dT%H:%M:%S.%fZ'
                                    ).replace(tzinfo=timezone.utc)
                                    timestamps.append(dt_utc)
                                except ValueError:
                                    continue
                        
                        if timestamps:
                            # Sorter etter UTC tid
                            timestamps.sort()
                            # Konverter til Oslo tid
                            oslo_time = timestamps[-1].astimezone(
                                ZoneInfo('Europe/Oslo')
                            )
                            return oslo_time - timedelta(hours=1)
        
        return None
        
    except Exception as e:
        logger.error(f"Feil ved henting av brøytedata: {str(e)}")
        return None


def analyze_snow_conditions(df, last_plowing, config):
    """Analyser snøforhold og sjekk for varslingsbehov."""
    try:
        if df is None or df.empty:
            return None
            
        # Beregn total endring i snødybde
        initial_snow = df['surface_snow_thickness'].iloc[0]
        current_snow = df['surface_snow_thickness'].iloc[-1]
        total_snow_change = current_snow - initial_snow
        
        # Beregn total nedbør
        total_precip = df['sum(precipitation_amount PT1H)'].sum()
        
        # Sjekk temperatur for å vurdere om nedbør kommer som snø
        avg_temp = df['air_temperature'].mean()
        
        # Sjekk om det har vært brøyting i perioden
        now = datetime.now(timezone.utc)
        recent_plowing = False
        if last_plowing:
            hours_since_plowing = (now - last_plowing).total_seconds() / 3600
            recent_plowing = (
                hours_since_plowing <= config['snow_alert']['plowing_hours']
            )
        
        logger.info("\n=== SNØFORHOLD ANALYSE ===")
        start_time = df['referenceTime'].iloc[0]
        end_time = df['referenceTime'].iloc[-1]
        logger.info(f"Periode: {start_time} til {end_time}")
        logger.info(f"Snødybde endring: {total_snow_change:.1f} cm")
        logger.info(f"Total nedbør: {total_precip:.1f} mm")
        logger.info(f"Gjennomsnittstemperatur: {avg_temp:.1f}°C")
        if last_plowing:
            logger.info(
                f"Siste brøyting: {last_plowing.strftime('%Y-%m-%d %H:%M')}"
            )
        
        # Vurder om det er behov for varsel - snødybde og ingen brøyting
        needs_alert = (
            total_snow_change >= 7.0
            and not recent_plowing
        )
        
        return {
            'needs_alert': needs_alert,
            'snow_change': total_snow_change,
            'total_precip': total_precip,
            'avg_temp': avg_temp,
            'last_plowing': last_plowing,
            'start_time': start_time,
            'end_time': end_time
        }
        
    except Exception as e:
        logger.error(f"Feil ved analyse av snøforhold: {str(e)}")
        return None


def send_alert(config, analysis):
    """Send e-postvarsel om snøakkumulering."""
    try:
        msg = MIMEMultipart()
        msg['From'] = config['email_from']
        msg['To'] = config['email_to']
        msg['Subject'] = (
            f"VARSEL: Betydelig snøfall i Fjellbergsskardet "
            f"{analysis['end_time'].strftime('%d.%m.%Y')}"
        )
        
        # Formater tidspunkt for siste brøyting
        plowing_info = "Ingen brøytedata tilgjengelig"
        if analysis['last_plowing']:
            plowing_info = analysis['last_plowing'].strftime(
                '%d.%m.%Y kl. %H:%M'
            )
        
        # Formater start og slutt-tid
        time_period = (
            f"{analysis['start_time'].strftime('%d.%m.%Y kl. %H:%M')} - "
            f"{analysis['end_time'].strftime('%H:%M')}"
        )
        
        body = f"""VARSEL OM BETYDELIG SNØFALL I FJELLBERGSSKARDET
{analysis['end_time'].strftime('%d.%m.%Y kl. %H:%M')}

{plowing_info}

VÆRFORHOLD SISTE {config['snow_alert']['check_hours']} TIMER:
- Total nedbør: {analysis['total_precip']:.1f} mm
- Endring i snødybde: {analysis['snow_change']:.1f} cm
- Gjennomsnittstemperatur: {analysis['avg_temp']:.1f}°C

ANALYSEPERIODE:
{time_period}

-------------------
Dette er et automatisk varsel basert på værdata fra Gullingen værstasjon.
Varselet sendes når snødybden på værstasjonen øker med mer enn 7.0 cm 
og det ikke er registrert GPS-aktivitet i området."""

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


def main(test_date=None):
    """Hovedfunksjon for snøovervåking."""
    try:
        if test_date:
            test_date = datetime.strptime(
                test_date, 
                '%Y-%m-%d %H:%M'
            )
            
        start_msg = (
            f"\n=== SNØOVERVÅKING STARTET "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ==="
        )
        if test_date:
            start_msg += (
                f"\nTester for dato: "
                f"{test_date.strftime('%Y-%m-%d %H:%M')}"
            )
        start_msg += "\n"
        logger.info(start_msg)
        
        config = load_config()
        
        # Sjekk siste varsel
        last_alert = get_last_alert_time()
        if last_alert and not test_date:  # Skip cooldown check for test dates
            hours_since_last = (
                datetime.now() - last_alert
            ).total_seconds() / 3600
            if hours_since_last < config['snow_alert']['cooldown_hours']:
                logger.info(
                    f"For kort tid siden siste varsel "
                    f"({hours_since_last:.1f} timer)"
                )
                return
        
        # Hent værdata og siste brøytetidspunkt
        weather_data = get_weather_data(config, test_date)
        last_plowing = get_last_plowing()
        
        if weather_data is None:
            return
            
        # Analyser snøforhold
        analysis = analyze_snow_conditions(weather_data, last_plowing, config)
        
        if analysis and analysis['needs_alert']:
            send_alert(config, analysis)
        else:
            logger.info("Ingen varsel nødvendig")
            
    except Exception as e:
        logger.error(f"Feil i hovedfunksjon: {str(e)}")


if __name__ == '__main__':
    import sys
    test_date = None
    if len(sys.argv) > 1:
        test_date = sys.argv[1]
    main(test_date) 