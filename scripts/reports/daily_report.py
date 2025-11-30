import json
import logging
import os
import shutil
import smtplib
from datetime import UTC, datetime, timedelta
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import requests
from bs4 import BeautifulSoup
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# Sett opp logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

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

def get_weather_data(report_time):
    """Hent værdata for siste 24 timer."""
    try:
        config = load_config()
        endpoint = 'https://frost.met.no/observations/v0.jsonld'

        yesterday = report_time - timedelta(hours=24)

        # Log tidspunktene
        logger.info(f"Henter data fra {yesterday} til {report_time}")

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
            'referencetime': f"{yesterday.strftime('%Y-%m-%dT%H:%M:%S')}/{report_time.strftime('%Y-%m-%dT%H:%M:%S')}"
        }

        # Log API-kall detaljer
        logger.info(f"API-kall til: {endpoint}")
        logger.info(f"Parametere: {json.dumps(params, indent=2)}")

        response = requests.get(
            endpoint,
            params=params,
            auth=(config['frost_client_id'], '')
        )

        # Log respons
        logger.info(f"API respons status: {response.status_code}")
        if response.status_code != 200:
            logger.error(f"API respons: {response.text}")

        if response.status_code == 200:
            data = response.json()

            if not data.get('data'):
                logger.error("Ingen data mottatt fra API-en")
                return None

            # Log antall datapunkter
            logger.info(f"Mottok {len(data['data'])} datapunkter")

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

    except Exception as e:
        logger.error(f"Feil ved henting av værdata: {str(e)}")
        return None

def smooth_snow_depth(df, window_size=3):
    """Glatt ut snødybdemålinger med et glidende gjennomsnitt."""
    df['smooth_snow_depth'] = df['surface_snow_thickness'].rolling(
        window=window_size, center=True, min_periods=1
    ).mean()
    df['snow_change_smooth'] = df['smooth_snow_depth'].diff()
    return df

def create_graphs(df, report_time, output_dir):
    """Lag grafer for værutviklingen."""
    try:
        # Smooth snødybdedata før plotting
        df = smooth_snow_depth(df)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Klassifiser nedbørtype
        df['snow_depth_change'] = df['surface_snow_thickness'].diff()
        df['precip_type'] = None  # Start med ingen type

        # Definer masker for nedbør og snødybdeendring
        has_precip = df['sum(precipitation_amount PT1H)'] > 0
        snow_increasing = df['snow_depth_change'] > 0.2
        snow_decreasing = df['snow_depth_change'] < -0.2
        snow_stable = (df['snow_depth_change'].abs() <= 0.2)
        temp_freezing = df['air_temperature'] < 0

        # Klassifiser nedbør:
        # 1. Nysnø: når det er nedbør og snødybden øker
        df.loc[has_precip & snow_increasing, 'precip_type'] = 'snow'

        # 2. Regn: når det er nedbør, temp ≥ 0°C og snødybden synker
        df.loc[has_precip & ~temp_freezing & snow_decreasing, 'precip_type'] = 'rain'

        # 3. Sludd: når det er nedbør og snødybden er stabil
        df.loc[has_precip & snow_stable, 'precip_type'] = 'mixed'

        # Hvis det fortsatt er noen nedbørstimer uten type, sett dem til regn
        df.loc[has_precip & df['precip_type'].isna(), 'precip_type'] = 'rain'

        # Finn perioder med uoverensstemmelser
        discrepancies = analyze_precipitation_discrepancies(df)
        discrepancy_times = [d['time'] for d in discrepancies]

        # 1. Temperatur og snødybde
        plt.figure(figsize=(12, 6))
        ax1 = plt.gca()
        ax2 = ax1.twinx()

        # Tegn temperatur først (under)
        ax1.plot(df['referenceTime'], df['air_temperature'],
                'b-', label='Temperatur', alpha=0.6, linewidth=1)

        # Marker nullgrader
        ax1.axhline(y=0, color='k', linestyle='--', alpha=0.3)

        # Tegn snødybde over med tykkere linje (bruk smoothed data)
        ax2.plot(df['referenceTime'], df['smooth_snow_depth'],
                'g-', label='Snødybde', linewidth=2)

        # Marker perioder med uoverensstemmelser
        for time in discrepancy_times:
            ax1.axvline(x=time, color='r', alpha=0.2)

        ax1.set_xlabel('Tid')
        ax1.set_ylabel('Temperatur (°C)', color='b')
        ax2.set_ylabel('Snødybde (cm)', color='g')

        # Legg til forklaringer
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

        plt.title('Temperatur og snødybde siste 24 timer')
        plt.savefig(output_dir / 'temp_snow.png', dpi=300, bbox_inches='tight')
        plt.close()

        # 2. Nedbørsfordeling
        plt.figure(figsize=(12, 6))
        ax1 = plt.gca()
        ax2 = ax1.twinx()

        # Beregn totaler for legend
        snow_total = df.loc[df['precip_type'] == 'snow', 'sum(precipitation_amount PT1H)'].sum()
        mixed_total = df.loc[df['precip_type'] == 'mixed', 'sum(precipitation_amount PT1H)'].sum()
        rain_total = df.loc[df['precip_type'] == 'rain', 'sum(precipitation_amount PT1H)'].sum()
        total_precip = snow_total + mixed_total + rain_total

        # Lag fargekart for hver type nedbør
        color_map = {
            'snow': '#ADD8E6',    # Lysere blå
            'mixed': '#808080',   # Grå
            'rain': '#000080'     # Mørkere blå
        }

        # Lag én søyle per time med riktig farge
        colors = []
        for _idx, row in df.iterrows():
            if row['sum(precipitation_amount PT1H)'] > 0:
                colors.append(color_map[row['precip_type']])
            else:
                colors.append('none')

        # Plot nedbørssøyler
        ax1.bar(df['referenceTime'], df['sum(precipitation_amount PT1H)'],
               color=colors, alpha=0.8, width=0.01)

        # Tegn snødybdelinje (bruk smoothed data)
        ax2.plot(df['referenceTime'], df['smooth_snow_depth'],
                'g-', linewidth=2, label='Snødybde')

        # Marker perioder med uoverensstemmelser med røde vertikale linjer
        for time in discrepancy_times:
            ax1.axvline(x=time, color='r', alpha=0.3, linestyle='--')

        # Lag legend
        legend_elements = [
            Patch(facecolor='#ADD8E6', alpha=0.8, label=f'Snø ({snow_total:.1f}mm)'),
            Patch(facecolor='#808080', alpha=0.8, label=f'Sludd ({mixed_total:.1f}mm)'),
            Patch(facecolor='#000080', alpha=0.8, label=f'Regn ({rain_total:.1f}mm)'),
            Line2D([0], [0], color='g', linewidth=2, label='Snødybde'),
            Line2D([0], [0], color='r', linestyle='--', alpha=0.3,
                  label='Uoverensstemmelse')
        ]

        # Sett aksetitler og grid
        ax1.set_xlabel('Tid')
        ax1.set_ylabel('Nedbør (mm)')
        ax2.set_ylabel('Snødybde (cm)', color='g')
        ax1.grid(True, alpha=0.3)

        # Formater x-akse med klokkeslett
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax1.xaxis.set_major_locator(mdates.HourLocator(interval=3))

        # Øk fontstørrelsen på aksene
        ax1.tick_params(axis='both', which='major', labelsize=10)
        ax2.tick_params(axis='y', which='major', labelsize=10, colors='g')

        plt.title(f'Nedbør og snødybde siste 24t (totalt {total_precip:.1f}mm)')
        ax1.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.15, 1))

        plt.tight_layout()
        plt.savefig(output_dir / 'precipitation.png', dpi=300, bbox_inches='tight')
        plt.close()

        # 3. Vind (styrke og retning) - uendret
        plt.figure(figsize=(12, 6))
        ax1 = plt.gca()
        ax2 = ax1.twinx()

        # Vindstyrke
        ax1.plot(df['referenceTime'], df['wind_speed'], 'r-',
                label='Vindstyrke', linewidth=2)
        ax1.fill_between(df['referenceTime'], df['wind_speed'],
                        alpha=0.2, color='red')

        # Vindretning
        ax2.plot(df['referenceTime'], df['wind_from_direction'], 'b.',
                label='Vindretning', markersize=8)
        ax2.set_ylim(0, 360)
        ax2.set_yticks([0, 90, 180, 270, 360])
        ax2.set_yticklabels(['N', 'Ø', 'S', 'V', 'N'])

        # Marker perioder med uoverensstemmelser
        for time in discrepancy_times:
            ax1.axvline(x=time, color='k', alpha=0.2, linestyle='--')

        ax1.set_xlabel('Tid')
        ax1.set_ylabel('Vindstyrke (m/s)', color='r')
        ax2.set_ylabel('Vindretning', color='b')

        ax1.grid(True, alpha=0.3)

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        legend_elements = lines1 + lines2 + [
            Line2D([0], [0], color='k', linestyle='--', alpha=0.2,
                  label='Uoverensstemmelse')
        ]
        ax1.legend(legend_elements, labels1 + labels2 + ['Uoverensstemmelse'],
                  loc='upper left')

        plt.title('Vind siste 24 timer')
        plt.savefig(output_dir / 'wind.png', dpi=300, bbox_inches='tight')
        plt.close()

        return [
            str(output_dir / 'temp_snow.png'),
            str(output_dir / 'precipitation.png'),
            str(output_dir / 'wind.png')
        ]

    except Exception as e:
        logger.error(f"Feil ved oppretting av grafer: {str(e)}")
        return []

def analyze_precipitation_discrepancies(df):
    """Analyser uoverensstemmelser i nedbørsmålinger med smoothing."""
    discrepancies = []

    # Definer terskelverdier for endringer
    SNOW_INCREASE_THRESHOLD = 1.0  # cm
    SNOW_DECREASE_THRESHOLD = -1.0  # cm
    WIND_THRESHOLD = 5.0  # m/s

    # Sjekk hver time i datasettet
    for i in range(1, len(df)):
        time = df.iloc[i]['referenceTime']
        temp = df.iloc[i]['air_temperature']
        precip = df.iloc[i]['sum(precipitation_amount PT1H)']
        snow_change = df.iloc[i]['snow_change_smooth']  # Bruk smoothed verdier
        wind = df.iloc[i]['wind_speed']

        # Håndter NaN-verdier
        if pd.isna(precip):
            precip = 0.0
        if pd.isna(wind):
            wind = 0.0
        if pd.isna(snow_change):
            continue
        if pd.isna(temp):
            continue

        # Sjekk for betydelige uoverensstemmelser
        if precip > 0.5:  # Øk terskelen for nedbør
            if temp < 0 and snow_change < SNOW_DECREASE_THRESHOLD:
                discrepancies.append({
                    'time': time,
                    'issue': 'Minusgrader og nedbør, men betydelig synkende snødybde',
                    'temp': temp,
                    'precip': precip,
                    'snow_change': snow_change,
                    'wind': wind
                })
            elif temp >= 2 and snow_change > SNOW_INCREASE_THRESHOLD:
                discrepancies.append({
                    'time': time,
                    'issue': 'Plussgrader og nedbør, men betydelig økende snødybde',
                    'temp': temp,
                    'precip': precip,
                    'snow_change': snow_change,
                    'wind': wind
                })
        elif snow_change > SNOW_INCREASE_THRESHOLD and temp >= 0:
            discrepancies.append({
                'time': time,
                'issue': 'Betydelig økende snødybde uten registrert nedbør',
                'temp': temp,
                'precip': precip,
                'snow_change': snow_change,
                'wind': wind
            })
        elif snow_change < SNOW_DECREASE_THRESHOLD and wind < WIND_THRESHOLD and temp < 2:
            discrepancies.append({
                'time': time,
                'issue': 'Betydelig synkende snødybde uten sterk vind eller høy temperatur',
                'temp': temp,
                'precip': precip,
                'snow_change': snow_change,
                'wind': wind
            })

    return discrepancies

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
                f"Feil ved henting av brøytedata. Status: {response.status_code}"
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
                                    ).replace(tzinfo=UTC)
                                    timestamps.append(dt_utc)
                                except ValueError:
                                    continue

                        if timestamps:
                            # Sorter etter UTC tid
                            timestamps.sort()
                            # Konverter til Oslo tid og trekk fra 1 time
                            oslo_time = timestamps[-1].astimezone(ZoneInfo('Europe/Oslo'))
                            return oslo_time - timedelta(hours=1)

        return None

    except Exception as e:
        logger.error(f"Feil ved henting av brøytedata: {str(e)}")
        return None

def analyze_conditions(df, report_time):
    """Analyser værforholdene og lag rapport."""
    try:
        # Hent siste brøytetidspunkt
        last_plowing = get_last_plowing()

        # Finn min/maks temperatur
        min_temp = df['min(air_temperature PT1H)'].min()
        max_temp = df['max(air_temperature PT1H)'].max()
        current_temp = df['air_temperature'].iloc[-1]
        avg_temp = df['air_temperature'].mean()

        # Finn snødybde og endring
        current_snow = df['surface_snow_thickness'].iloc[-1]
        prev_snow = df['surface_snow_thickness'].iloc[0]
        snow_change = current_snow - prev_snow

        # Beregn total nedbør og type
        total_precip = df['sum(precipitation_amount PT1H)'].sum()

        # Bestem nedbørtype basert på temperatur og snøendring
        if total_precip > 0:
            if current_temp < 0 and snow_change > 0:
                precip_type = "snø"
            elif current_temp > 2:
                precip_type = "regn"
            else:
                precip_type = "sludd"
        else:
            precip_type = "ingen"

        # Finn vind og luftfuktighet
        max_wind = df['max(wind_speed PT1H)'].max()
        avg_wind = df['wind_speed'].mean()

        # Håndter luftfuktighet - bruk gjennomsnitt hvis siste verdi er NaN
        humidity = df['relative_humidity'].iloc[-1]
        if pd.isna(humidity):
            humidity = df['relative_humidity'].mean()
            # Hvis fortsatt NaN, sett til None
            if pd.isna(humidity):
                humidity = None

        # Finn perioder med uoverensstemmelser
        discrepancies = analyze_precipitation_discrepancies(df)

        # Returner analyseverdier som dictionary
        return {
            'last_plowing': last_plowing,
            'min_temp': min_temp,
            'max_temp': max_temp,
            'current_temp': current_temp,
            'avg_temp': avg_temp,
            'current_snow': current_snow,
            'prev_snow': prev_snow,
            'snow_change': snow_change,
            'total_precip': total_precip,
            'precip_type': precip_type,
            'max_wind': max_wind,
            'avg_wind': avg_wind,
            'humidity': humidity,
            'discrepancies': discrepancies
        }

    except Exception as e:
        logger.error(f"Feil ved analyse av værdata: {str(e)}")
        return None

def send_report(config, analysis, graph_paths, report_time):
    """Send daglig rapport på e-post."""
    try:
        msg = MIMEMultipart()
        msg['From'] = config['email_from']
        msg['To'] = config['email_to']
        msg['Subject'] = f"Daglig værrapport for Fjellbergsskardet {report_time.strftime('%d.%m.%Y')}"

        # Lag brøyteinformasjon
        plowing_info = ""
        if analysis['last_plowing']:
            plowing_info = f"🚜 Siste brøyting: {analysis['last_plowing'].strftime('%d.%m.%Y kl. %H:%M')}\n"

        # Lag luftfuktighetsinformasjon
        humidity_info = "- Relativ luftfuktighet: Ikke tilgjengelig"
        if analysis['humidity'] is not None:
            humidity_info = f"- Relativ luftfuktighet: {analysis['humidity']:.1f}%"

        body = f"""DAGLIG VÆRRAPPORT FOR FJELLBERGSSKARDET
{report_time.strftime('%d.%m.%Y kl. %H:%M')}

{plowing_info}
VÆRFORHOLD SISTE 24 TIMER:
- Total nedbør: {analysis['total_precip']:.1f} mm ({analysis['precip_type']})
- Endring i snødybde: {analysis['snow_change']:.1f} cm
- Nåværende snødybde: {analysis['current_snow']:.1f} cm
- Temperatur: {analysis['current_temp']:.1f}°C (min: {analysis['min_temp']:.1f}°C, maks: {analysis['max_temp']:.1f}°C)
- Gjennomsnittlig temperatur: {analysis['avg_temp']:.1f}°C
- Gjennomsnittlig vindstyrke: {analysis['avg_wind']:.1f} m/s
- Maksimal vindstyrke: {analysis['max_wind']:.1f} m/s
{humidity_info}

ENDRING I SNØDYBDE:
- Fra {analysis['prev_snow']:.1f} cm til {analysis['current_snow']:.1f} cm
- Total endring: {analysis['snow_change']:.1f} cm

UOVERENSSTEMMELSER I NEDBØRSMÅLINGER:"""

        if analysis['discrepancies']:
            for d in analysis['discrepancies']:
                body += f"""
- {d['time'].strftime('%H:%M')}: {d['issue']}
  Temp: {d['temp']:.1f}°C, Nedbør: {d['precip']:.1f}mm, Snøendring: {d['snow_change']:.1f}cm, Vind: {d['wind']:.1f}m/s"""
        else:
            body += "\nIngen betydelige uoverensstemmelser funnet"

        body += """

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
        # Bruk rapporttidspunktet konsistent gjennom hele kjøringen
        report_time = datetime.now().replace(minute=0, second=0, microsecond=0)

        config = load_config()
        df = get_weather_data(report_time)

        if df is None:
            return

        # Opprett en unik mappe for denne rapporten
        output_dir = Path('data/graphs') / report_time.strftime('%Y%m%d_%H')
        graph_paths = create_graphs(df, report_time, output_dir)
        analysis = analyze_conditions(df, report_time)

        if analysis:
            send_report(config, analysis, graph_paths, report_time)

            # Rydd opp gamle rapportmapper (behold siste 7 dager)
            cleanup_old_reports(7)

    except Exception as e:
        logger.error(f"Feil i hovedfunksjon: {str(e)}")

def cleanup_old_reports(days_to_keep):
    """Rydd opp i gamle rapportmapper."""
    try:
        base_dir = Path('data/graphs')
        if not base_dir.exists():
            return

        cutoff = datetime.now() - timedelta(days=days_to_keep)

        for folder in base_dir.iterdir():
            if not folder.is_dir():
                continue

            try:
                # Prøv å parse mappenavnet som dato
                folder_date = datetime.strptime(folder.name, '%Y%m%d_%H')
                if folder_date < cutoff:
                    shutil.rmtree(folder)
            except ValueError:
                # Hopp over mapper som ikke følger navnekonvensjonen
                continue

    except Exception as e:
        logger.error(f"Feil ved opprydding av gamle rapporter: {str(e)}")

if __name__ == '__main__':
    logger.info(f"\n=== VÆRRAPPORT STARTET {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    main()
