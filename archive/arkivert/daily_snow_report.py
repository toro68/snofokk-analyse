import json
import logging
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import requests

# Sett opp logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Logg tidspunkt ved start
logger.info(f"\n=== DAGLIG RAPPORT STARTET {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

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

def is_snow_season():
    """Sjekk om vi er i brøytesesongen."""
    now = datetime.now()
    year = now.year

    # Konverter datoer til datetime
    season_start = datetime.strptime(f"{year}-11-01", "%Y-%m-%d")
    season_end = datetime.strptime(f"{year+1}-05-01", "%Y-%m-%d")

    # Juster hvis vi er i første del av året
    if now.month < 6:
        season_start = datetime.strptime(f"{year-1}-11-01", "%Y-%m-%d")
        season_end = datetime.strptime(f"{year}-05-01", "%Y-%m-%d")

    return season_start <= now <= season_end

def get_weather_data():
    """Hent værdata for siste 24 timer."""
    try:
        config = load_config()
        endpoint = 'https://frost.met.no/observations/v0.jsonld'

        now = datetime.now()
        yesterday = now - timedelta(hours=24)

        params = {
            'sources': config['weather_station'],
            'elements': ','.join([
                'air_temperature',
                'relative_humidity',
                'wind_speed',
                'wind_from_direction',
                'surface_snow_thickness',
                'sum(precipitation_amount PT1H)',
                'max(wind_speed PT1H)',
                'min(air_temperature PT1H)',
                'max(air_temperature PT1H)'
            ]),
            'referencetime': f"{yesterday.strftime('%Y-%m-%dT%H:%M:%S')}/{now.strftime('%Y-%m-%dT%H:%M:%S')}"
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

            # Konverter til DataFrame
            df = pd.json_normalize(
                data['data'],
                ['observations'],
                ['referenceTime']
            )

            # Pivot dataene
            df = df.pivot_table(
                index='referenceTime',
                columns='elementId',
                values='value',
                aggfunc='first'
            ).reset_index()

            # Konverter tid og sorter
            df['referenceTime'] = pd.to_datetime(df['referenceTime'])
            df = df.sort_values('referenceTime')

            # Beregn endringer
            df['snow_change'] = df['surface_snow_thickness'].diff()

            return df

    except Exception as e:
        logger.error(f"Feil ved henting av værdata: {str(e)}")
        return None

def create_graphs(df):
    """Lag grafer for værutviklingen."""
    try:
        # Opprett output-mappe
        output_dir = Path('data/graphs')
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. Temperatur og snødybde
        plt.figure(figsize=(12, 6))
        ax1 = plt.gca()
        ax2 = ax1.twinx()

        ax1.plot(df['referenceTime'], df['air_temperature'], 'b-', label='Temperatur')
        ax2.plot(df['referenceTime'], df['surface_snow_thickness'], 'g-', label='Snødybde')

        ax1.set_xlabel('Tid')
        ax1.set_ylabel('Temperatur (°C)', color='b')
        ax2.set_ylabel('Snødybde (cm)', color='g')

        plt.title('Temperatur og snødybde siste 24 timer')
        plt.savefig(output_dir / 'temp_snow.png')
        plt.close()

        # 2. Nedbør og vind
        plt.figure(figsize=(12, 6))
        ax1 = plt.gca()
        ax2 = ax1.twinx()

        ax1.bar(df['referenceTime'], df['sum(precipitation_amount PT1H)'],
                color='b', alpha=0.3, label='Nedbør')
        ax2.plot(df['referenceTime'], df['wind_speed'], 'r-', label='Vindstyrke')

        ax1.set_xlabel('Tid')
        ax1.set_ylabel('Nedbør (mm)', color='b')
        ax2.set_ylabel('Vindstyrke (m/s)', color='r')

        plt.title('Nedbør og vind siste 24 timer')
        plt.savefig(output_dir / 'precip_wind.png')
        plt.close()

        return [
            str(output_dir / 'temp_snow.png'),
            str(output_dir / 'precip_wind.png')
        ]

    except Exception as e:
        logger.error(f"Feil ved oppretting av grafer: {str(e)}")
        return []

def analyze_conditions(df):
    """Analyser værforholdene."""
    try:
        analysis = {
            'total_precip': df['sum(precipitation_amount PT1H)'].sum(),
            'snow_change': df['snow_change'].sum(),
            'current_snow': df['surface_snow_thickness'].iloc[-1],
            'prev_snow': df['surface_snow_thickness'].iloc[0],
            'avg_temp': df['air_temperature'].mean(),
            'min_temp': df['air_temperature'].min(),
            'max_temp': df['air_temperature'].max(),
            'avg_wind': df['wind_speed'].mean(),
            'max_wind': df['wind_speed'].max(),
            'current_temp': df['air_temperature'].iloc[-1]
        }

        if analysis['avg_temp'] < 0:
            analysis['precip_type'] = 'snø'
        elif analysis['avg_temp'] < 2:
            analysis['precip_type'] = 'sludd'
        else:
            analysis['precip_type'] = 'regn'

        return analysis

    except Exception as e:
        logger.error(f"Feil ved analyse av forhold: {str(e)}")
        return None

def send_report(config, analysis, graph_paths):
    """Send daglig rapport på e-post."""
    try:
        msg = MIMEMultipart()
        msg['From'] = config['email_from']
        msg['To'] = config['email_to']
        msg['Subject'] = f"Værrapport Fjellbergsskardet {datetime.now().strftime('%d.%m.%Y')}"

        now = datetime.now()
        yesterday = now - timedelta(hours=24)

        body = f"""VÆRRAPPORT FRA GULLINGEN VÆRSTASJON
{yesterday.strftime('%d.%m.%Y %H:00')} - {now.strftime('%d.%m.%Y %H:00')}

Nedbør:
- Snø: {analysis['snow_change']:.1f} cm
- Regn: {analysis['total_precip']:.1f} mm

Temperatur:
- Snitt: {analysis['avg_temp']:.1f}°C
- Maks: {analysis['max_temp']:.1f}°C
- Min: {analysis['min_temp']:.1f}°C

Vind:
- Gjennomsnitt: {analysis['avg_wind']:.1f} m/s
- Sterkeste vindkast: {analysis['max_wind']:.1f} m/s
- Tid: {now.strftime('%d.%m.%Y %H:00')}

Snødybde:
- Endring: {analysis['snow_change']:.1f} cm
- Fra {analysis['prev_snow']:.1f} cm til {analysis['current_snow']:.1f} cm

-------------------
Dette er en automatisk rapport med værdata fra Gullingen værstasjon.
Se vedlagte grafer for detaljert værutvikling siste 24 timer."""

        msg.attach(MIMEText(body, 'plain'))

        for graph_path in graph_paths:
            with open(graph_path, 'rb') as f:
                img = MIMEImage(f.read())
                img.add_header('Content-Disposition', 'attachment',
                             filename=os.path.basename(graph_path))
                msg.attach(img)

        with smtplib.SMTP(config['smtp_server'], 587) as server:
            server.starttls()
            server.login(config['smtp_username'], config['smtp_password'])
            server.send_message(msg)

        logger.info("Rapport sendt på e-post")

    except Exception as e:
        logger.error(f"Feil ved sending av rapport: {str(e)}")

def main():
    """Hovedfunksjon for daglig rapport."""
    try:
        # Sjekk om vi er i brøytesesongen
        if not is_snow_season():
            logger.info("Utenfor brøytesesong - ingen rapport genereres")
            return

        # Last konfigurasjon
        config = load_config()

        # Hent værdata
        df = get_weather_data()
        if df is None:
            return

        # Lag grafer
        graph_paths = create_graphs(df)

        # Analyser forhold
        analysis = analyze_conditions(df)
        if analysis:
            # Send rapport
            send_report(config, analysis, graph_paths)

    except Exception as e:
        logger.error(f"Feil i hovedfunksjon: {str(e)}")

if __name__ == '__main__':
    main()
