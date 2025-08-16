import json
import logging
import smtplib
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import lru_cache
from logging.handlers import RotatingFileHandler
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import pytz
import requests
from matplotlib.ticker import AutoMinorLocator

# Ignorer matplotlib warnings
warnings.filterwarnings('ignore', category=UserWarning)

# Type definitions
WeatherData = pd.DataFrame
WeatherAnalysis = dict[str, datetime | dict[str, float]]

@dataclass
class SnowAnalysis:
    """Dataklasse for snøanalyse."""
    raw_depth: float
    normalized_depth: float
    confidence: float
    is_valid: bool
    change_type: str  # 'steady', 'increase', 'decrease'

@dataclass
class WeatherConfig:
    """Dataklasse for værkonfigurasjon."""
    frost_client_id: str
    weather_station: str
    email_from: str
    email_to: str
    smtp_server: str
    smtp_username: str
    smtp_password: str
    snow_alert: dict = None  # Legg til støtte for snow_alert konfigurasjon

# Konstanter
OSLO_TZ = pytz.timezone('Europe/Oslo')
SNOW_CHANGE_THRESHOLD = 0.5  # cm
TEMPERATURE_SNOW_THRESHOLD = 2.0  # °C
WIND_IMPACT_THRESHOLD = 8.0  # m/s
ROLLING_WINDOW = 3  # Timer for rullende gjennomsnitt
CACHE_MINUTES = 15

# Sett opp basismappe
BASE_DIR = Path(__file__).parent.parent
LOG_DIR = BASE_DIR / 'logs'
DATA_DIR = BASE_DIR / 'data'
CONFIG_FILE = BASE_DIR / 'config' / 'test_config.json'

# Opprett nødvendige mapper
LOG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Sett opp logging med rotasjon
log_file = LOG_DIR / 'weekly_report_v2.log'
max_bytes = 10 * 1024 * 1024  # 10MB
backup_count = 5

file_handler = RotatingFileHandler(
    log_file,
    maxBytes=max_bytes,
    backupCount=backup_count
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        file_handler,
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_config() -> WeatherConfig:
    """Last inn konfigurasjon fra JSON-fil."""
    try:
        with open(CONFIG_FILE) as f:
            config_data = json.load(f)
        return WeatherConfig(**config_data)
    except Exception as e:
        logger.error(f"Kunne ikke laste konfigurasjonsfil: {str(e)}")
        raise

@lru_cache(maxsize=1)
def get_cached_weather_data(
    station: str,
    from_time: str,
    to_time: str,
    client_id: str
) -> WeatherData | None:
    """Hent værdata fra Frost API med caching."""
    try:
        endpoint = 'https://frost.met.no/observations/v0.jsonld'

        params = {
            'sources': station,
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
            auth=(client_id, '')
        )

        response.raise_for_status()  # Raise an exception for HTTP errors

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

        # Konverter til Oslo tidssone
        df['referenceTime'] = pd.to_datetime(df['referenceTime'])
        df['referenceTime'] = df['referenceTime'].dt.tz_convert('Europe/Oslo')

        return df

    except requests.exceptions.HTTPError as e:
        logger.error(f"API-feil: {e}")
        return None
    except Exception as e:
        logger.error(f"Feil ved henting av værdata: {str(e)}")
        return None

def normalize_snow_data(df: WeatherData) -> WeatherData:
    """
    Normaliser snødata ved å:
    1. Fjerne korte pulser
    2. Validere mot temperatur og nedbør
    3. Bruke glidende gjennomsnitt
    """
    df = df.copy()

    # Konverter kolonnenavn for enklere referering
    snow_col = 'surface_snow_thickness'
    temp_col = 'air_temperature'
    precip_col = 'sum(precipitation_amount PT1H)'
    wind_col = 'wind_speed'

    # Beregn glidende gjennomsnitt for snødybde med større vindu for å fjerne pulser
    df[f'{snow_col}_smooth'] = df[snow_col].rolling(
        window=ROLLING_WINDOW * 2,  # Doble vindusstørrelsen for bedre utjevning
        center=True,
        min_periods=1
    ).mean()

    # Beregn endring i snødybde
    df['snow_change'] = df[snow_col].diff()

    # Valider endringer
    df['valid_snow'] = True

    # Marker ugyldige endringer basert på strengere kriterier
    invalid_conditions = [
        # For små endringer - øk terskelen
        (abs(df['snow_change']) < SNOW_CHANGE_THRESHOLD * 1.5),
        # Temperatur for høy for snø - strengere krav
        (df[temp_col] > TEMPERATURE_SNOW_THRESHOLD - 0.5) &
        (df['snow_change'] > 0),
        # Store endringer uten nedbør
        (abs(df['snow_change']) > 3) &
        (df[precip_col] < 0.2),
        # Sterk vind kan påvirke målinger - senk terskelen
        (df[wind_col] > WIND_IMPACT_THRESHOLD - 1) &
        (abs(df['snow_change']) > 1.5)
    ]

    for condition in invalid_conditions:
        df.loc[condition, 'valid_snow'] = False

    # Bruk validert glidende gjennomsnitt der endringer er ugyldige
    df[f'{snow_col}_normalized'] = df[snow_col].copy()
    df.loc[~df['valid_snow'], f'{snow_col}_normalized'] = \
        df.loc[~df['valid_snow'], f'{snow_col}_smooth']

    # Ekstra utjevning for å fjerne gjenværende pulser
    df[f'{snow_col}_normalized'] = df[f'{snow_col}_normalized'].rolling(
        window=3,
        center=True,
        min_periods=1
    ).mean()

    return df

def analyze_snow_conditions(
    df: WeatherData,
    window: str = '3H'
) -> list[SnowAnalysis]:
    """Analyser snøforhold med konfidensberegning."""
    analyses = []

    for idx in df.index:
        row = df.iloc[idx]

        # Beregn konfidensverdi basert på flere faktorer
        confidence_factors = [
            # Temperatur nær 0°C gir lavere konfidens
            1 - min(abs(-2 - row['air_temperature']), 4) / 4,
            # Sterk vind gir lavere konfidens
            1 - min(row['wind_speed'] / 15, 1),
            # Stor forskjell mellom rå og normalisert gir lavere konfidens
            1 - min(
                abs(
                    row['surface_snow_thickness'] -
                    row['surface_snow_thickness_normalized']
                ) / 5,
                1
            )
        ]

        confidence = sum(confidence_factors) / len(confidence_factors)

        # Bestem endringstype
        if abs(row['snow_change']) < SNOW_CHANGE_THRESHOLD:
            change_type = 'steady'
        else:
            change_type = 'increase' if row['snow_change'] > 0 else 'decrease'

        analysis = SnowAnalysis(
            raw_depth=row['surface_snow_thickness'],
            normalized_depth=row['surface_snow_thickness_normalized'],
            confidence=confidence,
            is_valid=row['valid_snow'],
            change_type=change_type
        )

        analyses.append(analysis)

    return analyses

def create_enhanced_weather_plot(
    df: WeatherData,
    snow_analyses: list[SnowAnalysis],
    target_file: Path
) -> bool:
    """Lag forbedret værgraf med snøanalyse."""
    try:
        # Opprett figur med fem subplot-akser (lagt til en for vindretning)
        fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(
            5, 1,
            figsize=(12, 15),
            height_ratios=[2, 2, 1, 1.5, 1.5]
        )

        fig.suptitle(
            'Værdata siste 7 dager - Fjellbergsskardet',
            fontsize=16,
            y=0.95
        )

        # Forbedret formatering for alle akser
        for ax in [ax1, ax2, ax3, ax4, ax5]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            ax.xaxis.set_major_locator(mdates.DayLocator())
            ax.xaxis.set_minor_locator(AutoMinorLocator())
            ax.grid(True, linestyle='--', alpha=0.7)
            # Øk fontstørrelsen for bedre lesbarhet
            ax.tick_params(axis='both', labelsize=10)
            for label in ax.get_xticklabels():
                label.set_rotation(45)
                label.set_ha('right')

        # Plot 1: Temperatur (forbedret)
        ax1.plot(
            df['referenceTime'],
            df['air_temperature'],
            color='red',
            label='Temperatur',
            linewidth=2.5
        )

        # Legg til min/max temperatur
        if 'min(air_temperature PT1H)' in df.columns and 'max(air_temperature PT1H)' in df.columns:
            ax1.fill_between(
                df['referenceTime'],
                df['min(air_temperature PT1H)'],
                df['max(air_temperature PT1H)'],
                color='red',
                alpha=0.2,
                label='Min/Max temperatur'
            )

        ax1.fill_between(
            df['referenceTime'],
            df['air_temperature'],
            0,
            where=df['air_temperature'] > 0,
            color='red',
            alpha=0.1
        )

        ax1.fill_between(
            df['referenceTime'],
            df['air_temperature'],
            0,
            where=df['air_temperature'] < 0,
            color='blue',
            alpha=0.1
        )

        # Legg til frysepunktlinje
        ax1.axhline(y=0, color='blue', linestyle='-', alpha=0.3, linewidth=1)
        ax1.text(
            df['referenceTime'].iloc[0],
            0.2,
            'Frysepunkt',
            color='blue',
            alpha=0.7,
            fontsize=9
        )

        ax1.set_ylabel('Temperatur (°C)', fontsize=12, fontweight='bold')
        ax1.legend(loc='upper right', fontsize=10)

        # Plot 2: Snødybde med normalisering (forbedret)
        ax2.plot(
            df['referenceTime'],
            df['surface_snow_thickness'],
            color='lightblue',
            alpha=0.3,  # Reduser synligheten av rådata
            label='Målt snødybde',
            linewidth=1.5,
            linestyle=':'
        )

        ax2.plot(
            df['referenceTime'],
            df['surface_snow_thickness_normalized'],
            color='blue',
            label='Normalisert snødybde',
            linewidth=3
        )

        # Fjern visualisering av usikre målinger
        # Marker kun signifikante endringer i snødybde
        for i, analysis in enumerate(snow_analyses):
            # Vis bare endringer som er større enn terskelen og er validert
            if analysis.change_type == 'increase' and analysis.is_valid and \
               abs(analysis.raw_depth - analysis.normalized_depth) < 3:  # Ignorer store avvik
                ax2.scatter(
                    df['referenceTime'].iloc[i],
                    analysis.normalized_depth,
                    color='green',
                    marker='^',
                    s=60,
                    alpha=0.8,
                    zorder=5
                )
            elif analysis.change_type == 'decrease' and analysis.is_valid and \
                 abs(analysis.raw_depth - analysis.normalized_depth) < 3:  # Ignorer store avvik
                ax2.scatter(
                    df['referenceTime'].iloc[i],
                    analysis.normalized_depth,
                    color='red',
                    marker='v',
                    s=60,
                    alpha=0.8,
                    zorder=5
                )

        ax2.set_ylabel('Snødybde (cm)', fontsize=12, fontweight='bold')
        ax2.legend(loc='upper right', fontsize=10)

        # Plot 3: Nedbør (forbedret)
        precip_col = 'sum(precipitation_amount PT1H)'
        daily_precip = df.groupby(
            df['referenceTime'].dt.date
        )[precip_col].sum()

        bar_positions = [
            datetime.combine(date, datetime.min.time())
            for date in daily_precip.index
        ]

        bars = ax3.bar(
            bar_positions,
            daily_precip.values,
            width=0.8,
            color='darkblue',
            alpha=0.6,
            label='Nedbør'
        )

        # Legg til verdier over søylene
        for bar, value in zip(bars, daily_precip.values, strict=False):
            if value > 0.5:  # Bare vis verdier over 0.5 mm
                ax3.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.3,
                    f'{value:.1f}',
                    ha='center',
                    va='bottom',
                    fontsize=9,
                    fontweight='bold',
                    color='darkblue'
                )

        ax3.set_ylabel('Nedbør (mm)', fontsize=12, fontweight='bold')
        ax3.legend(loc='upper right', fontsize=10)

        # Plot 4: Vindstyrke med snøfokkfare (forbedret)
        ax4.plot(
            df['referenceTime'],
            df['wind_speed'],
            color='green',
            label='Vindstyrke',
            linewidth=2.5
        )

        # Legg til vindkast med tydeligere markering
        ax4.scatter(
            df['referenceTime'],
            df['max(wind_speed PT1H)'],
            color='darkgreen',
            alpha=0.7,
            s=30,
            label='Vindkast',
            zorder=5
        )

        # Fyll området mellom gjennomsnittlig vind og vindkast
        ax4.fill_between(
            df['referenceTime'],
            df['wind_speed'],
            df['max(wind_speed PT1H)'],
            color='lightgreen',
            alpha=0.3,
            label='Vindvariasjon'
        )

        # Marker områder med snøfokkfare
        snofokk_mask = (
            (df['wind_speed'] > 6) &
            (df['air_temperature'] < -1)
        )

        if snofokk_mask.any():
            ax4.fill_between(
                df['referenceTime'],
                df['wind_speed'].where(snofokk_mask),
                y2=6,
                color='red',
                alpha=0.3,
                label='Snøfokkfare'
            )

        # Legg til referanselinjer med forbedret formatering
        vindstyrker = [
            (6, 'Snøfokkgrense', '--', 'gray'),
            (8, 'Frisk bris', ':', 'darkgray'),
            (10, 'Liten kuling', ':', 'darkgray'),
            (15, 'Stiv kuling', ':', 'darkgray')
        ]

        for styrke, navn, stil, farge in vindstyrker:
            ax4.axhline(
                y=styrke,
                color=farge,
                linestyle=stil,
                alpha=0.5
            )
            ax4.text(
                df['referenceTime'].iloc[0],
                styrke + 0.2,
                f'{navn} ({styrke} m/s)',
                color=farge,
                alpha=0.7,
                fontsize=9
            )

        # Juster y-akse
        max_vind = max(
            df['wind_speed'].max(),
            df['max(wind_speed PT1H)'].max()
        )
        ax4.set_ylim(0, max(15, max_vind * 1.1))
        ax4.set_ylabel('Vindstyrke (m/s)', fontsize=12, fontweight='bold')
        ax4.legend(loc='upper right', fontsize=10)

        # NY PLOT 5: Vindretning
        if 'wind_from_direction' in df.columns:
            # Konverter vindretning til radianer for plotting
            directions = df['wind_from_direction'].values
            times = df['referenceTime'].values
            speeds = df['wind_speed'].values

            # Bruk fargegradering basert på vindstyrke
            sc = ax5.scatter(
                times,
                directions,
                c=speeds,
                cmap='viridis',
                s=50,
                alpha=0.7,
                label='Vindretning'
            )

            # Legg til fargeindikator
            cbar = plt.colorbar(sc, ax=ax5)
            cbar.set_label('Vindstyrke (m/s)', fontsize=10)

            # Sett y-aksen til å vise kompassretninger
            ax5.set_ylim(0, 360)
            ax5.set_yticks([0, 90, 180, 270, 360])
            ax5.set_yticklabels(['N', 'Ø', 'S', 'V', 'N'])

            # Legg til horisontale linjer for hovedretningene
            for direction in [0, 90, 180, 270, 360]:
                ax5.axhline(y=direction, color='gray', linestyle=':', alpha=0.3)

            ax5.set_ylabel('Vindretning', fontsize=12, fontweight='bold')
        else:
            ax5.text(
                0.5, 0.5,
                'Vindretningsdata ikke tilgjengelig',
                horizontalalignment='center',
                verticalalignment='center',
                transform=ax5.transAxes,
                fontsize=12
            )

        # Legg til oppsummeringsboks med nøkkeltall
        props = dict(boxstyle='round', facecolor='white', alpha=0.7)

        # Beregn nøkkeltall
        max_temp = df['air_temperature'].max()
        min_temp = df['air_temperature'].min()
        avg_temp = df['air_temperature'].mean()
        total_precip = df['sum(precipitation_amount PT1H)'].sum()
        max_wind = df['max(wind_speed PT1H)'].max()
        snow_start = df['surface_snow_thickness_normalized'].iloc[0]
        snow_end = df['surface_snow_thickness_normalized'].iloc[-1]
        snow_change = snow_end - snow_start

        # Formater oppsummeringstekst
        summary_text = (
            f"OPPSUMMERING:\n"
            f"Temperatur: {min_temp:.1f}°C til {max_temp:.1f}°C (snitt: {avg_temp:.1f}°C)\n"
            f"Total nedbør: {total_precip:.1f} mm\n"
            f"Maks vindkast: {max_wind:.1f} m/s\n"
            f"Snøendring: {snow_change:+.1f} cm"
        )

        # Plasser oppsummeringsboksen
        fig.text(
            0.02, 0.01,
            summary_text,
            fontsize=11,
            bbox=props,
            verticalalignment='bottom'
        )

        # Legg til tidsstempel for generering
        timestamp = datetime.now(OSLO_TZ).strftime('%d.%m.%Y %H:%M')
        fig.text(
            0.98, 0.01,
            f"Generert: {timestamp}",
            fontsize=8,
            ha='right',
            va='bottom',
            alpha=0.7
        )

        # Juster layout og lagre
        plt.tight_layout()
        plt.subplots_adjust(bottom=0.08)  # Gi plass til oppsummeringsboksen
        plt.savefig(target_file, dpi=300, bbox_inches='tight')
        plt.close()

        return True

    except Exception as e:
        logger.error(f"Feil ved oppretting av værgraf: {str(e)}")
        return False

def send_enhanced_report(
    config: WeatherConfig,
    df: WeatherData,
    snow_analyses: list[SnowAnalysis],
    plot_file: Path
) -> None:
    """Send forbedret værrapport på e-post."""
    try:
        msg = MIMEMultipart()
        msg['From'] = config.email_from
        msg['To'] = config.email_to

        # Lag subject med norsk dato
        current_date = datetime.now(OSLO_TZ)
        subject = (
            f"Ukentlig værrapport for Fjellbergsskardet "
            f"{current_date.strftime('%d.%m.%Y')}"
        )
        msg['Subject'] = subject

        # Analyser perioden
        periode_start = df['referenceTime'].min()
        periode_slutt = df['referenceTime'].max()

        periode = (
            f"{periode_start.strftime('%d.%m')} - "
            f"{periode_slutt.strftime('%d.%m.%Y')}"
        )

        # Analyser siste 24 timer
        last_24h = df[
            df['referenceTime'] >= (
                df['referenceTime'].max() - timedelta(hours=24)
            )
        ]

        temp_range = (
            f"{last_24h['air_temperature'].min():.1f}°C til "
            f"{last_24h['air_temperature'].max():.1f}°C"
        )

        # Analyser snøforhold
        valid_analyses = [a for a in snow_analyses if a.is_valid]
        snow_changes = [
            a for a in valid_analyses
            if a.change_type != 'steady'
        ]

        snow_summary = []
        if snow_changes:
            changes_by_type = {
                'increase': len([
                    c for c in snow_changes
                    if c.change_type == 'increase'
                ]),
                'decrease': len([
                    c for c in snow_changes
                    if c.change_type == 'decrease'
                ])
            }

            if changes_by_type['increase'] > 0:
                snow_summary.append(
                    f"Økning i snødybde observert "
                    f"{changes_by_type['increase']} ganger"
                )
            if changes_by_type['decrease'] > 0:
                snow_summary.append(
                    f"Reduksjon i snødybde observert "
                    f"{changes_by_type['decrease']} ganger"
                )
        else:
            snow_summary.append("Stabile snøforhold i perioden")

        # Sjekk for snøfokkfare
        snofokk_tilfeller = len(
            df[(df['wind_speed'] > 6) & (df['air_temperature'] < -1)]
        )
        snofokk_melding_tekst = '- Fare for snøfokk observert flere ganger i perioden'
        snofokk_melding = snofokk_melding_tekst if snofokk_tilfeller > 0 else ''

        # Generer rapport
        body = f"""UKENTLIG VÆRRAPPORT FOR FJELLBERGSSKARDET
{periode}

SISTE 24 TIMER
- Temperatur: {temp_range}
- Gjennomsnittstemperatur: {last_24h['air_temperature'].mean():.1f}°C
- Nedbør: {last_24h['sum(precipitation_amount PT1H)'].sum():.1f} mm
- Gjennomsnittlig vind: {last_24h['wind_speed'].mean():.1f} m/s

SNØFORHOLD (UKE)
- Snødybde start: {df['surface_snow_thickness_normalized'].iloc[0]:.1f} cm
- Snødybde slutt: {df['surface_snow_thickness_normalized'].iloc[-1]:.1f} cm
- Endring: {df['surface_snow_thickness_normalized'].iloc[-1] -
            df['surface_snow_thickness_normalized'].iloc[0]:.1f} cm
- Analyse: {' '.join(snow_summary)}

TEMPERATUR (UKE)
- Høyeste: {df['air_temperature'].max():.1f}°C
- Laveste: {df['air_temperature'].min():.1f}°C
- Gjennomsnitt: {df['air_temperature'].mean():.1f}°C

NEDBØR (UKE)
- Total nedbør: {df['sum(precipitation_amount PT1H)'].sum():.1f} mm
- Dager med nedbør: {len(
        df[df['sum(precipitation_amount PT1H)'] > 0.1]
        .groupby(df['referenceTime'].dt.date).count()
    )} dager

VIND (UKE)
- Høyeste vindstyrke: {df['wind_speed'].max():.1f} m/s
- Gjennomsnittlig vind: {df['wind_speed'].mean():.1f} m/s

SPESIELLE FORHOLD
{snofokk_melding if snofokk_melding else 'Ingen spesielle forhold registrert'}
-------------------
Dette er en automatisk generert rapport basert på værdata fra 
Gullingen værstasjon. Rapporten sendes hver fredag.

Merk: Snødybdemålinger er normalisert for å fjerne feilmålinger og 
korte pulser. Se vedlagt graf for detaljer.

Kjøres med python3 scripts/weekly_weather_report_v2.py"""

        msg.attach(MIMEText(body, 'plain'))

        # Legg ved værgraf
        if plot_file.exists():
            with open(plot_file, 'rb') as f:
                img = MIMEImage(f.read())
                img.add_header(
                    'Content-Disposition',
                    'attachment',
                    filename='vaerdata_siste_uke.png'
                )
                msg.attach(img)

        # Send e-post
        with smtplib.SMTP(config.smtp_server, 587) as server:
            server.starttls()
            server.login(
                config.smtp_username,
                config.smtp_password
            )
            server.send_message(msg)

        logger.info("Ukesrapport sendt på e-post")

    except Exception as e:
        logger.error(f"Feil ved sending av rapport: {str(e)}")

def main(test_mode: bool = False) -> None:
    """Hovedfunksjon for ukentlig værrapport."""
    try:
        # Sjekk om det er fredag, med mindre vi er i test-modus
        if not test_mode and datetime.now().weekday() != 4:  # 4 = fredag
            logger.info("Ikke fredag - ingen rapport sendes")
            return

        start_msg = (
            f"\n=== UKENTLIG VÆRRAPPORT V2.0 STARTER "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ==="
        )
        if test_mode:
            start_msg += " (TEST-MODUS)"
        start_msg += "\n"
        logger.info(start_msg)

        # Last konfigurasjon
        config = load_config()

        # Sett opp tidsperiode
        now = datetime.now(OSLO_TZ)
        week_ago = now - timedelta(days=7)

        # Hent værdata
        weather_data = get_cached_weather_data(
            config.weather_station,
            week_ago.strftime('%Y-%m-%dT%H:%M:%S'),
            now.strftime('%Y-%m-%dT%H:%M:%S'),
            config.frost_client_id
        )

        if weather_data is None:
            logger.error("Kunne ikke hente værdata")
            return

        # Normaliser snødata
        weather_data = normalize_snow_data(weather_data)

        # Analyser snøforhold
        snow_analyses = analyze_snow_conditions(weather_data)

        # Opprett graf
        plot_file = DATA_DIR / 'weather_plot_v2.png'
        if create_enhanced_weather_plot(
            weather_data,
            snow_analyses,
            plot_file
        ):
            logger.info(f"Værgraf lagret til {plot_file}")

            # Send rapport
            send_enhanced_report(
                config,
                weather_data,
                snow_analyses,
                plot_file
            )
        else:
            logger.error("Kunne ikke generere værgraf")

    except Exception as e:
        logger.error(f"Feil i hovedfunksjon: {str(e)}")

if __name__ == '__main__':
    import sys
    test_mode = '--test' in sys.argv
    main(test_mode)
