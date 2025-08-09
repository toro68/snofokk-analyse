import json
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import smtplib
from pathlib import Path
import time
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import AutoMinorLocator


# Sett opp basismappe
BASE_DIR = Path(__file__).parent.parent
LOG_DIR = BASE_DIR / 'logs'
CONFIG_FILE = BASE_DIR / 'config' / 'test_config.json'

# Opprett nødvendige mapper
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Sett opp logging
log_file = LOG_DIR / 'weekly_report.log'
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


def get_weather_data(config, max_retries=3, retry_delay=5):
    """Henter værdata for siste uke fra Frost API med retry-mekanisme."""
    try:
        endpoint = 'https://frost.met.no/observations/v0.jsonld'
        
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        
        # Formater datoene i ISO format
        from_time = week_ago.strftime('%Y-%m-%dT%H:%M:%S')
        to_time = now.strftime('%Y-%m-%dT%H:%M:%S')
        
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
            
            df = pd.json_normalize(
                data['data'],
                ['observations'],
                ['referenceTime']
            )
            
            df = df.pivot_table(
                index='referenceTime',
                columns='elementId',
                values='value',
                aggfunc='first'
            ).reset_index()
            
            df['referenceTime'] = pd.to_datetime(df['referenceTime'])
            df = df.sort_values('referenceTime')
            df['snow_change'] = df['surface_snow_thickness'].diff()
            
            return df
            
        logger.error(f"API-feil: {response.status_code} - {response.text}")
        return None
        
    except Exception as e:
        logger.error(f"Feil ved henting av værdata: {str(e)}")
        return None


def analyze_weather_data(df):
    """Analyser værdata for ukesrapporten."""
    try:
        if df is None or df.empty:
            return None
            
        # Konverter referenceTime til dato for gruppering
        df['date'] = pd.to_datetime(df['referenceTime']).dt.date
        
        # Grupper nedbør per dag og tell dager med nedbør
        precip_col = 'sum(precipitation_amount PT1H)'
        daily_precip = df.groupby('date')[precip_col].sum()
        
        # Debug: Skriv ut unike datoer og deres nedbørsmengder
        logger.info("\nNedbør per dag:")
        for date, precip in daily_precip.items():
            logger.info(f"{date}: {precip:.1f} mm")
        
        # Tell dager med mer enn 0.1mm nedbør
        days_with_precip = len(daily_precip[daily_precip > 0.1])
        days_with_precip = min(days_with_precip, 7)
        
        # Analyser siste 24 timer
        last_24h = df[
            df['referenceTime'] >= (
                df['referenceTime'].max() - timedelta(hours=24)
            )
        ]
        
        last_24h_analysis = {
            'nedbør': last_24h[precip_col].sum(),
            'temp_min': last_24h['air_temperature'].min(),
            'temp_max': last_24h['air_temperature'].max(),
            'temp_snitt': last_24h['air_temperature'].mean(),
            'vind_snitt': last_24h['wind_speed'].mean()
        }
            
        analysis = {
            'periode_start': df['referenceTime'].min(),
            'periode_slutt': df['referenceTime'].max(),
            'temperatur': {
                'min': df['air_temperature'].min(),
                'max': df['air_temperature'].max(),
                'snitt': df['air_temperature'].mean()
            },
            'nedbør': {
                'total': df[precip_col].sum(),
                'dager_med_nedbør': days_with_precip
            },
            'vind': {
                'max': df['wind_speed'].max(),
                'snitt': df['wind_speed'].mean()
            },
            'snødybde': {
                'start': df['surface_snow_thickness'].iloc[0],
                'slutt': df['surface_snow_thickness'].iloc[-1],
                'endring': (
                    df['surface_snow_thickness'].iloc[-1] -
                    df['surface_snow_thickness'].iloc[0]
                )
            },
            'siste_døgn': last_24h_analysis
        }
        
        return analysis
        
    except Exception as e:
        logger.error(f"Feil ved analyse av værdata: {str(e)}")
        return None


def create_weather_plot(df, target_file):
    """Lag graf med værdata for siste uke."""
    try:
        # Opprett figur med fire subplot-akser
        fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(12, 12), height_ratios=[2, 2, 1, 1.5])
        fig.suptitle('Værdata siste 7 dager - Fjellbergsskardet', fontsize=14, y=0.95)
        
        # Formater x-akse med dato
        for ax in [ax1, ax2, ax3, ax4]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            ax.xaxis.set_major_locator(mdates.DayLocator())
            ax.xaxis.set_minor_locator(AutoMinorLocator())
            ax.grid(True, linestyle='--', alpha=0.7)
            
        # Plot 1: Temperatur
        ax1.plot(df['referenceTime'], df['air_temperature'], 
                color='red', label='Temperatur')
        ax1.fill_between(df['referenceTime'], df['air_temperature'], 0, 
                        where=df['air_temperature'] > 0, 
                        color='red', alpha=0.1)
        ax1.fill_between(df['referenceTime'], df['air_temperature'], 0, 
                        where=df['air_temperature'] < 0, 
                        color='blue', alpha=0.1)
        ax1.set_ylabel('Temperatur (°C)')
        ax1.legend(loc='upper right')
        
        # Plot 2: Snødybde
        ax2.plot(df['referenceTime'], df['surface_snow_thickness'], 
                color='blue', label='Snødybde')
        ax2.fill_between(df['referenceTime'], df['surface_snow_thickness'], 
                        color='lightblue', alpha=0.3)
        ax2.set_ylabel('Snødybde (cm)')
        ax2.legend(loc='upper right')
        
        # Plot 3: Nedbør
        precip_col = 'sum(precipitation_amount PT1H)'
        daily_precip = df.groupby(df['referenceTime'].dt.date)[precip_col].sum()
        bar_positions = [datetime.combine(date, datetime.min.time()) 
                        for date in daily_precip.index]
        ax3.bar(bar_positions, daily_precip.values, 
               width=0.8, color='darkblue', alpha=0.6, label='Nedbør')
        ax3.set_ylabel('Nedbør (mm)')
        ax3.legend(loc='upper right')
        
        # Plot 4: Vindstyrke med markering av snøfokkfare
        ax4.plot(df['referenceTime'], df['wind_speed'], 
                color='green', label='Vindstyrke', linewidth=2)
                
        # Legg til vindkast som prikker
        ax4.scatter(df['referenceTime'], df['max(wind_speed PT1H)'], 
                   color='darkgreen', alpha=0.5, s=20,
                   label='Vindkast')
        
        # Marker områder med snøfokkfare (vind > 6 m/s og temp < -1°C)
        snofokk_mask = (df['wind_speed'] > 6) & (df['air_temperature'] < -1)
        if snofokk_mask.any():
            # Fyll området over 6 m/s med rød farge
            ax4.fill_between(df['referenceTime'], 
                           df['wind_speed'].where(snofokk_mask), 
                           y2=6,
                           color='red', alpha=0.3, label='Snøfokkfare')
            
        # Legg til referanselinjer for vindstyrke
        vindstyrker = [
            (6, 'Snøfokkgrense', '--', 'gray'),
            (8, 'Frisk bris', ':', 'darkgray'),
            (10, 'Liten kuling', ':', 'darkgray'),
            (15, 'Stiv kuling', ':', 'darkgray')
        ]
        
        for styrke, navn, stil, farge in vindstyrker:
            ax4.axhline(y=styrke, color=farge, linestyle=stil, alpha=0.5)
            ax4.text(df['referenceTime'].iloc[0], styrke + 0.2, 
                    f'{navn} ({styrke} m/s)', 
                    color=farge, alpha=0.7)
        
        # Juster y-akse for bedre lesbarhet
        max_vind = max(df['wind_speed'].max(), df['max(wind_speed PT1H)'].max())
        ax4.set_ylim(0, max(15, max_vind * 1.1))
        ax4.set_ylabel('Vindstyrke (m/s)')
        ax4.legend(loc='upper right')
        
        # Juster layout og lagre
        plt.tight_layout()
        plt.savefig(target_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        return True
        
    except Exception as e:
        logger.error(f"Feil ved oppretting av værgraf: {str(e)}")
        return False


def send_weekly_report(config, analysis):
    """Send ukentlig værrapport på e-post."""
    try:
        msg = MIMEMultipart()
        msg['From'] = config['email_from']
        msg['To'] = config['email_to']
        
        subject = (
            f"Ukentlig værrapport for Fjellbergsskardet "
            f"{analysis['periode_slutt'].strftime('%d.%m.%Y')}"
        )
        msg['Subject'] = subject
        
        periode = (
            f"{analysis['periode_start'].strftime('%d.%m')} - "
            f"{analysis['periode_slutt'].strftime('%d.%m.%Y')}"
        )
        
        temp_range = (
            f"{analysis['siste_døgn']['temp_min']:.1f}°C til "
            f"{analysis['siste_døgn']['temp_max']:.1f}°C"
        )
        
        body = f"""UKENTLIG VÆRRAPPORT FOR FJELLBERGSSKARDET
{periode}

SISTE 24 TIMER
- Temperatur: {temp_range}
- Gjennomsnittstemperatur: {analysis['siste_døgn']['temp_snitt']:.1f}°C
- Nedbør: {analysis['siste_døgn']['nedbør']:.1f} mm
- Gjennomsnittlig vind: {analysis['siste_døgn']['vind_snitt']:.1f} m/s

SNØFORHOLD (UKE)
- Snødybde start: {analysis['snødybde']['start']:.1f} cm
- Snødybde slutt: {analysis['snødybde']['slutt']:.1f} cm
- Endring: {analysis['snødybde']['endring']:.1f} cm

TEMPERATUR (UKE)
- Høyeste: {analysis['temperatur']['max']:.1f}°C
- Laveste: {analysis['temperatur']['min']:.1f}°C
- Gjennomsnitt: {analysis['temperatur']['snitt']:.1f}°C

NEDBØR (UKE)
- Total nedbør: {analysis['nedbør']['total']:.1f} mm
- Dager med nedbør: {analysis['nedbør']['dager_med_nedbør']} dager

VIND (UKE)
- Høyeste vindstyrke: {analysis['vind']['max']:.1f} m/s
- Gjennomsnittlig vind: {analysis['vind']['snitt']:.1f} m/s

-------------------
Dette er en automatisk generert rapport basert på værdata fra 
Gullingen værstasjon. Rapporten sendes hver fredag.

Se vedlagt graf for visuell fremstilling av værdata."""

        msg.attach(MIMEText(body, 'plain'))
        
        # Legg ved værgraf
        plot_file = BASE_DIR / 'data' / 'weather_plot.png'
        if plot_file.exists():
            with open(plot_file, 'rb') as f:
                img = MIMEImage(f.read())
                img.add_header('Content-Disposition', 
                             'attachment', 
                             filename='vaerdata_siste_uke.png')
                msg.attach(img)
        
        with smtplib.SMTP(config['smtp_server'], 587) as server:
            server.starttls()
            server.login(config['smtp_username'], config['smtp_password'])
            server.send_message(msg)
            
        logger.info("Ukesrapport sendt på e-post")
        
    except Exception as e:
        logger.error(f"Feil ved sending av rapport: {str(e)}")


def main(test_mode=False):
    """Hovedfunksjon for ukentlig værrapport."""
    try:
        # Sjekk om det er fredag, med mindre vi er i test-modus
        if not test_mode and datetime.now().weekday() != 4:  # 4 = fredag
            logger.info("Ikke fredag - ingen rapport sendes")
            return
            
        start_msg = (
            f"\n=== UKENTLIG VÆRRAPPORT STARTER "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ==="
        )
        if test_mode:
            start_msg += " (TEST-MODUS)"
        start_msg += "\n"
        logger.info(start_msg)
        
        config = load_config()
        weather_data = get_weather_data(config)
        
        if weather_data is None:
            return
            
        analysis = analyze_weather_data(weather_data)
        
        if analysis:
            # Opprett graf
            plot_file = BASE_DIR / 'data' / 'weather_plot.png'
            if create_weather_plot(weather_data, plot_file):
                logger.info(f"Værgraf lagret til {plot_file}")
            
            send_weekly_report(config, analysis)
        else:
            logger.info("Kunne ikke generere rapport")
            
    except Exception as e:
        logger.error(f"Feil i hovedfunksjon: {str(e)}")


if __name__ == '__main__':
    import sys
    test_mode = '--test' in sys.argv
    main(test_mode) 