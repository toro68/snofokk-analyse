#!/usr/bin/env python3
"""
Korrelerer vedlikeholdsdata (brøyting/strøing) med værforhold.
Analyserer sammenheng mellom brøyting/strøing og snøfokk/glatt vei-episoder.
"""

import os
import sys
from datetime import UTC, datetime, timedelta

import matplotlib.pyplot as plt
import pandas as pd
import requests
from dotenv import load_dotenv

# Legg til src-mappen i Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# Import våre egne moduler
try:
    from ml_snowdrift_detector import MLSnowdriftDetector
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("Warning: ML-detektor ikke tilgjengelig")

load_dotenv()

class MaintenanceWeatherCorrelator:
    """Korrelerer vedlikeholdsdata med værforhold."""

    def __init__(self):
        self.frost_client_id = os.getenv('FROST_CLIENT_ID')
        self.station_id = "SN46220"  # Gullingen Skisenter

        if ML_AVAILABLE:
            self.ml_detector = MLSnowdriftDetector()

        # Definer vedlikeholds-kategorier basert på varighet, distanse og værforhold
        self.maintenance_categories = {
            'light_treatment': {'max_duration_hours': 2, 'max_distance_km': 15},
            'medium_treatment': {'max_duration_hours': 5, 'max_distance_km': 50},
            'heavy_treatment': {'max_duration_hours': 12, 'max_distance_km': 200}
        }

        # Definer sesonger basert på strøingskvalitet
        self.seasons = {
            'insufficient_salt_period': {'start': '2022-11-01', 'end': '2024-04-30'},  # For lite strøing
            'realistic_salt_period': {'start': '2024-11-01', 'end': '2025-04-30'}     # Realistisk strøing 2024-2025
        }

        # Vedlikeholdsmønstre
        self.maintenance_patterns = {
            'weekly_clearing': 'fredager',  # Tunbrøyting på fredager
            'emergency_response': 'akutt',  # Umiddelbar respons på værforhold
            'routine_maintenance': 'rutinemessig'  # Standard vedlikehold
        }

    def load_maintenance_data(self, csv_file: str) -> pd.DataFrame:
        """Last vedlikeholdsdata fra CSV."""
        print(f"Laster vedlikeholdsdata fra: {csv_file}")

        df = pd.read_csv(csv_file, sep=';', encoding='utf-8')

        # Norsk måneds-mapping
        month_map = {
            'jan.': 'Jan', 'feb.': 'Feb', 'mars': 'Mar', 'apr.': 'Apr',
            'mai': 'May', 'juni': 'Jun', 'juli': 'Jul', 'aug.': 'Aug',
            'sep.': 'Sep', 'okt.': 'Oct', 'nov.': 'Nov', 'des.': 'Dec'
        }

        def parse_norwegian_date(date_str, time_str):
            """Parse norske datoer til datetime."""
            try:
                # Erstatt norske måneder med engelske
                for norsk, engelsk in month_map.items():
                    date_str = date_str.replace(norsk, engelsk)

                # Parse dato og tid
                combined = f"{date_str} {time_str}"
                return pd.to_datetime(combined, format='%d. %b %Y %H:%M:%S')
            except Exception as e:
                print(f"Feil ved parsing av dato '{date_str} {time_str}': {e}")
                return None

        # Parse datoer og tider
        df['start_datetime'] = df.apply(lambda row: parse_norwegian_date(row['Dato'], row['Starttid']), axis=1)
        df['end_datetime'] = df.apply(lambda row: parse_norwegian_date(row['Dato'], row['Sluttid']), axis=1)

        # Fjern rader med ugyldig dato-parsing
        valid_dates = df['start_datetime'].notna() & df['end_datetime'].notna()
        df = df[valid_dates].copy()

        # Parse varighet (HH:MM:SS format)
        def parse_duration(duration_str):
            try:
                parts = duration_str.split(':')
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = int(parts[2])
                return hours + minutes/60 + seconds/3600
            except Exception:
                return 0

        df['duration_hours'] = df['Varighet'].apply(parse_duration)
        df['distance_km'] = df['Distanse (km)'].astype(float)

        # Kategoriser vedlikehold
        df['maintenance_type'] = df.apply(self._categorize_maintenance, axis=1)

        # Filtrer bort totalsummen
        df = df[df['Dato'] != 'Totalt'].copy()

        print(f"Lastet {len(df)} vedlikeholds-episoder")
        if len(df) > 0:
            print(f"Tidsperiode: {df['start_datetime'].min()} til {df['start_datetime'].max()}")

        return df

    def _categorize_maintenance(self, row) -> str:
        """Kategoriser vedlikehold basert på varighet og distanse."""
        duration = row['duration_hours']
        distance = row['distance_km']

        if (duration <= self.maintenance_categories['light_treatment']['max_duration_hours'] and
            distance <= self.maintenance_categories['light_treatment']['max_distance_km']):
            return 'light_treatment'
        elif (duration <= self.maintenance_categories['medium_treatment']['max_duration_hours'] and
              distance <= self.maintenance_categories['medium_treatment']['max_distance_km']):
            return 'medium_treatment'
        else:
            return 'heavy_treatment'

    def get_weather_data(self, start_date: datetime, end_date: datetime) -> pd.DataFrame | None:
        """Hent værdata for spesifisert periode."""
        print(f"Henter værdata fra {start_date} til {end_date}")

        if not self.frost_client_id:
            print("ERROR: FROST_CLIENT_ID mangler")
            return None

        # Utvid periode med 12 timer før og etter for kontekst
        extended_start = start_date - timedelta(hours=12)
        extended_end = end_date + timedelta(hours=12)

        start_iso = extended_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = extended_end.strftime("%Y-%m-%dT%H:%M:%SZ")

        elements = [
            'air_temperature',
            'wind_speed',
            'wind_from_direction',
            'surface_snow_thickness',
            'sum(precipitation_amount PT1H)',
            'relative_humidity',
            'surface_temperature',
            'dew_point_temperature'
        ]

        url = 'https://frost.met.no/observations/v0.jsonld'
        parameters = {
            'sources': self.station_id,
            'elements': ','.join(elements),
            'referencetime': f"{start_iso}/{end_iso}"
        }

        try:
            response = requests.get(url, parameters, auth=(self.frost_client_id, ''), timeout=60)

            if response.status_code == 200:
                data = response.json()

                if not data.get('data'):
                    print("Ingen værdata mottatt")
                    return None

                records = []
                for obs in data['data']:
                    record = {'referenceTime': pd.to_datetime(obs['referenceTime'])}

                    for observation in obs['observations']:
                        element = observation['elementId']
                        value = observation['value']
                        time_res = observation.get('timeResolution', 'PT1H')

                        # Prioriter PT1H oppløsning
                        if element in ['air_temperature', 'relative_humidity', 'wind_speed'] and time_res != 'PT1H':
                            continue

                        record[element] = value

                    records.append(record)

                if records:
                    df = pd.DataFrame(records)
                    df = df.sort_values('referenceTime').drop_duplicates('referenceTime').reset_index(drop=True)
                    print(f"Hentet {len(df)} værobservasjoner")
                    return df

            else:
                print(f"API-feil: {response.status_code}")
                return None

        except Exception as e:
            print(f"Feil ved henting av værdata: {e}")
            return None

    def analyze_weather_conditions(self, weather_df: pd.DataFrame, timestamp: datetime, window_hours: int = 6) -> dict:
        """Analyser værforhold rundt et tidspunkt."""
        if weather_df is None or len(weather_df) == 0:
            return {"status": "no_data"}

        # Finn relevante målinger innenfor tidsvinduet
        start_window = timestamp - timedelta(hours=window_hours)
        end_window = timestamp + timedelta(hours=window_hours)

        # Håndter timezone-forskjeller
        if hasattr(weather_df['referenceTime'].dtype, 'tz') and weather_df['referenceTime'].dt.tz is not None:
            # Weather data har timezone, konverter timestamps
            if start_window.tzinfo is None:
                start_window = start_window.replace(tzinfo=UTC)
            if end_window.tzinfo is None:
                end_window = end_window.replace(tzinfo=UTC)
        else:
            # Weather data er naive, fjern timezone fra timestamps
            if start_window.tzinfo is not None:
                start_window = start_window.replace(tzinfo=None)
            if end_window.tzinfo is not None:
                end_window = end_window.replace(tzinfo=None)

        window_data = weather_df[
            (weather_df['referenceTime'] >= start_window) &
            (weather_df['referenceTime'] <= end_window)
        ].copy()

        if len(window_data) == 0:
            return {"status": "no_data_in_window"}

        # Grunnleggende værstatistikk
        analysis = {
            "status": "success",
            "window_hours": window_hours,
            "observations_count": len(window_data),
            "time_range": {
                "start": window_data['referenceTime'].min(),
                "end": window_data['referenceTime'].max()
            }
        }

        # Temperatur-analyse
        if 'air_temperature' in window_data.columns:
            temp_data = window_data['air_temperature'].dropna()
            if len(temp_data) > 0:
                analysis['temperature'] = {
                    'min': temp_data.min(),
                    'max': temp_data.max(),
                    'mean': temp_data.mean(),
                    'around_freezing': (temp_data >= -2).any() and (temp_data <= 2).any()
                }

        # Nedbør-analyse
        precip_col = 'sum(precipitation_amount PT1H)'
        if precip_col in window_data.columns:
            precip_data = window_data[precip_col].dropna()
            if len(precip_data) > 0:
                analysis['precipitation'] = {
                    'total': precip_data.sum(),
                    'max_hourly': precip_data.max(),
                    'hours_with_precip': (precip_data > 0.1).sum(),
                    'rain_on_snow': False  # Vil bli oppdatert nedenfor
                }

        # Vind-analyse
        if 'wind_speed' in window_data.columns:
            wind_data = window_data['wind_speed'].dropna()
            if len(wind_data) > 0:
                analysis['wind'] = {
                    'max': wind_data.max(),
                    'mean': wind_data.mean(),
                    'strong_wind': (wind_data >= 5.0).any(),
                    'extreme_wind': (wind_data >= 10.0).any()
                }

        # Snø-analyse
        if 'surface_snow_thickness' in window_data.columns:
            snow_data = window_data['surface_snow_thickness'].dropna()
            if len(snow_data) > 0:
                analysis['snow'] = {
                    'depth_cm': snow_data.mean() * 100,  # Konverter til cm
                    'min_depth_cm': snow_data.min() * 100,
                    'max_depth_cm': snow_data.max() * 100,
                    'snow_present': snow_data.mean() > 0.05,  # >5cm
                    'snow_change': snow_data.max() - snow_data.min()
                }

        # Spesifikke værsituasjoner
        self._detect_weather_scenarios(analysis, window_data)

        # Snøfokk-analyse hvis ML tilgjengelig
        if ML_AVAILABLE and len(window_data) > 5:
            try:
                snowdrift_result = self.ml_detector.analyze_snowdrift_risk_ml(window_data)
                analysis['snowdrift_risk'] = {
                    'risk_level': snowdrift_result.get('risk_level', 'unknown'),
                    'message': snowdrift_result.get('message', 'N/A')
                }
            except Exception as e:
                analysis['snowdrift_risk'] = {'error': str(e)}

        return analysis

    def _detect_weather_scenarios(self, analysis: dict, weather_data: pd.DataFrame):
        """Detekterer spesifikke værscenarioer som krever vedlikehold."""
        scenarios = []

        # Hent temperatur- og nedbørdata fra riktig datastruktur
        temp_data = analysis.get('temperature', {})
        precip_data = analysis.get('precipitation', {})

        temp_mean = temp_data.get('mean', 0)
        temp_max = temp_data.get('max', 0)
        temp_min = temp_data.get('min', 0)
        precip_total = precip_data.get('total', 0)

        # Snøfokk-risiko
        if analysis.get('snowdrift_risk', {}).get('risk_level') in ['Høy', 'Meget høy']:
            scenarios.append('snowdrift_risk')

        # Glatt vei
        if analysis.get('icy_road_risk') in ['Høy', 'Meget høy']:
            scenarios.append('icy_road_risk')

        # Regn på snø (fører til glatt vei)
        if (temp_mean > -1 and temp_mean < 3 and precip_total > 1):
            scenarios.append('rain_on_snow')

        # NYTT: Slush-risiko (mildvær med nedbør)
        if (temp_mean > 0 and temp_mean < 4 and precip_total > 2):
            scenarios.append('slush_conditions')

        # NYTT: Tining/refreezing (fare for is)
        if (temp_max > 2 and temp_min < -1):
            scenarios.append('freeze_thaw_cycle')

        # NYTT: Regn som fjerner snøkappe (skaper svarte veier)
        if (temp_mean > 3 and precip_total > 10):
            scenarios.append('snow_cap_removal')

        # NYTT: Langvarig mildvær som ødelegger snøkappe
        if (temp_mean > 4 and precip_total > 5):
            scenarios.append('mild_period_snow_loss')

        analysis['weather_scenarios'] = scenarios
        return analysis

    def calculate_weekly_snow_accumulation(self, date: datetime) -> dict:
        """Beregner snøakkumulering i uken før en gitt dato."""
        week_start = date - timedelta(days=7)
        week_end = date

        weather_data = self.get_weather_data(week_start, week_end)

        weekly_stats = {
            'week_start': week_start.strftime('%Y-%m-%d'),
            'week_end': week_end.strftime('%Y-%m-%d'),
            'total_snow_mm': 0,
            'snow_days': 0,
            'max_daily_snow': 0,
            'week_temp_avg': None
        }

        if weather_data is not None and not weather_data.empty:
            # Håndter timezone i weather_data
            temp_col = 'air_temperature' if 'air_temperature' in weather_data.columns else 'temperature'
            precip_col = 'sum(precipitation_amount PT1H)' if 'sum(precipitation_amount PT1H)' in weather_data.columns else 'precipitation'

            if temp_col in weather_data.columns and precip_col in weather_data.columns:
                # Beregn snøfall (antar at snø = nedbør når temp < 1°C)
                snow_conditions = (weather_data[temp_col] < 1) & (weather_data[precip_col] > 0)

                if snow_conditions.any():
                    snow_data = weather_data[snow_conditions]
                    weekly_stats['total_snow_mm'] = snow_data[precip_col].sum()
                    # Konverter til daglig for counting
                    daily_snow = snow_data.set_index('referenceTime')[precip_col].resample('D').sum()
                    weekly_stats['snow_days'] = len(daily_snow[daily_snow > 0])
                    weekly_stats['max_daily_snow'] = daily_snow.max() if len(daily_snow) > 0 else 0

                weekly_stats['week_temp_avg'] = weather_data[temp_col].mean()

        return weekly_stats

    def classify_maintenance_by_season_and_weather(self, df: pd.DataFrame) -> pd.DataFrame:
        """Klassifiserer vedlikehold basert på sesong og værforhold."""
        df = df.copy()

        # Legg til sesong-klassifisering
        df['season_period'] = 'unknown'
        df['likely_salt_quality'] = 'unknown'

        for _, row in df.iterrows():
            date = pd.to_datetime(row['start_datetime']).date()

            # Sjekk hvilken periode
            insufficient_start = pd.to_datetime(self.seasons['insufficient_salt_period']['start']).date()
            insufficient_end = pd.to_datetime(self.seasons['insufficient_salt_period']['end']).date()
            realistic_start = pd.to_datetime(self.seasons['realistic_salt_period']['start']).date()
            realistic_end = pd.to_datetime(self.seasons['realistic_salt_period']['end']).date()

            if insufficient_start <= date <= insufficient_end:
                df.loc[df.index == row.name, 'season_period'] = 'insufficient_salt_period'
                df.loc[df.index == row.name, 'likely_salt_quality'] = 'for_lite'
            elif realistic_start <= date <= realistic_end:
                df.loc[df.index == row.name, 'season_period'] = 'realistic_salt_period'
                df.loc[df.index == row.name, 'likely_salt_quality'] = 'realistisk'

        # Klassifiser trolig vedlikeholdstype basert på værforhold og timing
        df['likely_maintenance_purpose'] = 'ukjent'
        df['weekly_snow_context'] = None
        df['is_friday_clearing'] = False

        for idx, row in df.iterrows():
            scenarios = row.get('weather_scenarios', [])
            temp_mean = row.get('temp_mean', 0)
            date = pd.to_datetime(row['start_datetime'])
            weekday = date.weekday()  # 0=Monday, 4=Friday

            # NYTT: Sjekk om det er fredag og beregn ukentlig snøakkumulering
            if weekday == 4:  # Fredag
                weekly_snow = self.calculate_weekly_snow_accumulation(date)
                df.loc[idx, 'weekly_snow_context'] = f"{weekly_snow['total_snow_mm']:.1f}mm i {weekly_snow['snow_days']} dager"
                df.loc[idx, 'is_friday_clearing'] = True

                # Klassifiser basert på ukentlig snøakkumulering
                if weekly_snow['total_snow_mm'] > 10:  # Betydelig snø siste uke
                    df.loc[idx, 'likely_maintenance_purpose'] = 'tunbrøyting_ukentlig_snø'
                elif weekly_snow['total_snow_mm'] > 5:
                    df.loc[idx, 'likely_maintenance_purpose'] = 'tunbrøyting_moderat_snø'
                else:
                    df.loc[idx, 'likely_maintenance_purpose'] = 'tunbrøyting_rutinemessig'
            else:
                # Akutt respons på værforhold (ikke fredag)
                if 'snow_cap_removal' in scenarios or 'mild_period_snow_loss' in scenarios:
                    df.loc[idx, 'likely_maintenance_purpose'] = 'ingen_strøing_svarte_veier'
                elif 'slush_conditions' in scenarios:
                    df.loc[idx, 'likely_maintenance_purpose'] = 'akutt_slush_fjerning'
                elif 'rain_on_snow' in scenarios:
                    df.loc[idx, 'likely_maintenance_purpose'] = 'akutt_strøing_regn_på_snø'
                elif 'freeze_thaw_cycle' in scenarios:
                    df.loc[idx, 'likely_maintenance_purpose'] = 'akutt_strøing_tining_frysing'
                elif 'snowdrift_risk' in scenarios:
                    df.loc[idx, 'likely_maintenance_purpose'] = 'akutt_brøyting_snøfokk'
                elif 'icy_road_risk' in scenarios:
                    df.loc[idx, 'likely_maintenance_purpose'] = 'akutt_strøing_glatt_vei'
                elif temp_mean < -5:
                    df.loc[idx, 'likely_maintenance_purpose'] = 'brøyting_kuldegrader'
                elif temp_mean > 0:
                    df.loc[idx, 'likely_maintenance_purpose'] = 'akutt_slush_eller_tining'
                else:
                    df.loc[idx, 'likely_maintenance_purpose'] = 'standard_vinterdrift'

        return df

    def generate_enhanced_season_report(self, correlation_df: pd.DataFrame, output_dir: str = "data/analyzed"):
        """Generer forbedret rapport med sesong- og slush-analyse."""
        print("Genererer forbedret sesongrapport...")

        os.makedirs(output_dir, exist_ok=True)

        # Filtrer gyldig data
        valid_df = correlation_df[correlation_df['temp_min'].notna()].copy()

        if len(valid_df) == 0:
            print("Ingen gyldig data for rapport")
            return

        # Generer detaljert rapport
        report_file = os.path.join(output_dir, f"enhanced_maintenance_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.md")

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# VEDLIKEHOLD-VÆR ANALYSE 2022-2025\n\n")
            f.write(f"**Generert:** {datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
            f.write("**Dataperiode:** 2022-2025 (med fokus på sesongforskjeller)\n\n")

            f.write("## VIKTIGE FUNN\n\n")
            f.write("- **Strøingen var REALISTISK vinteren 2024-2025**\n")
            f.write("- **Tidligere år (2022-2024) hadde FOR LITE strøing**\n")
            f.write("- **Slush-fjerning i mildværsperioder er viktig faktor**\n")
            f.write("- **Regn på snø krever umiddelbar strøing**\n")
            f.write("- **Tunbrøyting utføres fredager basert på ukentlig snøakkumulering**\n")
            f.write("- **Regn over tid fjerner snøkappen - svarte veier trenger ikke strøing**\n\n")

            # Oversikt
            f.write("## OVERSIKT\n\n")
            f.write(f"- Totalt analysert: {len(correlation_df)} episoder\n")
            f.write(f"- Med værdata: {len(valid_df)} episoder\n")
            f.write(f"- Tidsrom: {valid_df['start_datetime'].min().strftime('%d.%m.%Y')} - {valid_df['start_datetime'].max().strftime('%d.%m.%Y')}\n\n")

            # Sesonganalyse
            if 'season_period' in valid_df.columns:
                f.write("## SESONGSAMMENLIGNING\n\n")

                for season in ['insufficient_salt_period', 'realistic_salt_period']:
                    season_data = valid_df[valid_df['season_period'] == season]
                    if len(season_data) > 0:
                        period_name = "**FOR LITE STRØING (2022-2024)**" if season == 'insufficient_salt_period' else "**REALISTISK STRØING (2024-2025)**"

                        f.write(f"### {period_name}\n\n")
                        f.write(f"- Antall episoder: {len(season_data)}\n")
                        f.write(f"- Gjennomsnittlig varighet: {season_data['duration_hours'].mean():.1f} timer\n")
                        f.write(f"- Gjennomsnittlig distanse: {season_data['distance_km'].mean():.1f} km\n")
                        f.write(f"- Temperaturspenn: {season_data['temp_min'].min():.1f}°C til {season_data['temp_max'].max():.1f}°C\n")

                        if 'likely_maintenance_purpose' in season_data.columns:
                            purpose_counts = season_data['likely_maintenance_purpose'].value_counts().head(3)
                            f.write("- Vanligste vedlikeholdsformål:\n")
                            for purpose, count in purpose_counts.items():
                                f.write(f"  - {purpose}: {count} episoder\n")
                        f.write("\n")

            # Spesialscenarioer
            if 'likely_maintenance_purpose' in valid_df.columns:
                f.write("## SPESIELLE VEDLIKEHOLDSSCENARIOER\n\n")

                # Slush-episoder
                slush_episodes = valid_df[valid_df['likely_maintenance_purpose'].str.contains('slush', na=False, case=False)]
                if len(slush_episodes) > 0:
                    f.write(f"### SLUSH-FJERNING ({len(slush_episodes)} episoder)\n\n")
                    f.write("Mildværsperioder som krever slush-fjerning:\n")
                    f.write(f"- Gjennomsnittstemp: {slush_episodes['temp_mean'].mean():.1f}°C (ideelt for slush-dannelse)\n")
                    f.write(f"- Gjennomsnittlig nedbør: {slush_episodes['precip_total'].mean():.1f}mm\n")
                    f.write(f"- Gjennomsnittlig varighet: {slush_episodes['duration_hours'].mean():.1f} timer\n\n")

                    f.write("**Detaljerte slush-episoder:**\n")
                    for _, episode in slush_episodes.iterrows():
                        f.write(f"- {episode['maintenance_date']}: {episode['temp_mean']:.1f}°C, {episode['precip_total']:.1f}mm nedbør\n")
                    f.write("\n")

                # Regn på snø
                rain_on_snow = valid_df[valid_df['likely_maintenance_purpose'].str.contains('regn_på_snø', na=False)]
                if len(rain_on_snow) > 0:
                    f.write(f"### REGN PÅ SNØ ({len(rain_on_snow)} episoder)\n\n")
                    f.write("Kritiske episoder som krever umiddelbar strøing:\n")
                    for _, episode in rain_on_snow.iterrows():
                        f.write(f"- **{episode['maintenance_date']}**: {episode['temp_mean']:.1f}°C, {episode['precip_total']:.1f}mm regn\n")
                    f.write("\n")

                # Freeze-thaw sykluser
                freeze_thaw = valid_df[valid_df['likely_maintenance_purpose'].str.contains('tining_frysing', na=False)]
                if len(freeze_thaw) > 0:
                    f.write(f"### TINING/FRYSING SYKLUSER ({len(freeze_thaw)} episoder)\n\n")
                    f.write("Farlige temperatursykluser som skaper is:\n")
                    for _, episode in freeze_thaw.iterrows():
                        f.write(f"- {episode['maintenance_date']}: {episode['temp_min']:.1f}°C til {episode['temp_max']:.1f}°C\n")
                    f.write("\n")

            # NYTT: Tunbrøyting-analyse
            friday_clearing = valid_df[valid_df.get('is_friday_clearing', False) == True]
            if len(friday_clearing) > 0:
                f.write("## TUNBRØYTING ANALYSE\n\n")
                f.write(f"Totalt {len(friday_clearing)} episoder av tunbrøyting på fredager.\n\n")

                # Kategoriser tunbrøyting basert på snømengde
                heavy_snow_clearing = friday_clearing[friday_clearing['likely_maintenance_purpose'] == 'tunbrøyting_ukentlig_snø']
                moderate_snow_clearing = friday_clearing[friday_clearing['likely_maintenance_purpose'] == 'tunbrøyting_moderat_snø']
                routine_clearing = friday_clearing[friday_clearing['likely_maintenance_purpose'] == 'tunbrøyting_rutinemessig']

                if len(heavy_snow_clearing) > 0:
                    f.write(f"### TUNBRØYTING ETTER MYE SNØ ({len(heavy_snow_clearing)} episoder)\n")
                    f.write("Fredager med >10mm snø siste uke:\n")
                    for _, episode in heavy_snow_clearing.iterrows():
                        f.write(f"- **{episode['maintenance_date']}**: {episode.get('weekly_snow_context', 'N/A')}, varighet: {episode['duration_hours']:.1f}t\n")
                    f.write("\n")

                if len(moderate_snow_clearing) > 0:
                    f.write(f"### TUNBRØYTING ETTER MODERAT SNØ ({len(moderate_snow_clearing)} episoder)\n")
                    f.write("Fredager med 5-10mm snø siste uke:\n")
                    for _, episode in moderate_snow_clearing.iterrows():
                        f.write(f"- {episode['maintenance_date']}: {episode.get('weekly_snow_context', 'N/A')}\n")
                    f.write("\n")

                if len(routine_clearing) > 0:
                    f.write(f"### RUTINEMESSIG TUNBRØYTING ({len(routine_clearing)} episoder)\n")
                    f.write("Fredager med minimal snø (<5mm) siste uke:\n")
                    for _, episode in routine_clearing.iterrows():
                        f.write(f"- {episode['maintenance_date']}: {episode.get('weekly_snow_context', 'N/A')}\n")
                    f.write("\n")

        print(f"Forbedret rapport lagret: {report_file}")
        return report_file

    def correlate_maintenance_weather(self, maintenance_df: pd.DataFrame) -> pd.DataFrame:
        """Korrelér vedlikeholdsdata med værforhold."""
        print("Starter korrelasjon mellom vedlikehold og vær...")

        results = []

        for idx, maintenance in maintenance_df.iterrows():
            print(f"Analyserer episode {idx+1}/{len(maintenance_df)}: {maintenance['Dato']}")

            # Hent værdata for perioden
            weather_data = self.get_weather_data(
                maintenance['start_datetime'] - timedelta(days=1),
                maintenance['start_datetime'] + timedelta(days=1)
            )

            if weather_data is not None:
                # Analyser værforhold
                weather_analysis = self.analyze_weather_conditions(
                    weather_data,
                    maintenance['start_datetime'],
                    window_hours=12
                )

                result = {
                    'maintenance_date': maintenance['Dato'],
                    'start_datetime': maintenance['start_datetime'],
                    'end_datetime': maintenance['end_datetime'],
                    'duration_hours': maintenance['duration_hours'],
                    'distance_km': maintenance['distance_km'],
                    'maintenance_type': maintenance['maintenance_type'],
                    'equipment': maintenance['Enhet'],
                    'weather_analysis': weather_analysis
                }

                # Utpakk værdata for enklere analyse
                if weather_analysis.get('status') == 'success':
                    temp = weather_analysis.get('temperature', {})
                    precip = weather_analysis.get('precipitation', {})
                    snow = weather_analysis.get('snow', {})
                    wind = weather_analysis.get('wind', {})

                    result.update({
                        'temp_min': temp.get('min'),
                        'temp_max': temp.get('max'),
                        'temp_mean': temp.get('mean'),
                        'around_freezing': temp.get('around_freezing', False),
                        'precip_total': precip.get('total', 0),
                        'precip_max_hourly': precip.get('max_hourly', 0),
                        'rain_on_snow': precip.get('rain_on_snow', False),
                        'snow_depth_cm': snow.get('depth_cm', 0),
                        'snow_present': snow.get('snow_present', False),
                        'wind_max': wind.get('max', 0),
                        'strong_wind': wind.get('strong_wind', False),
                        'weather_scenarios': ','.join(weather_analysis.get('weather_scenarios', [])),
                        'snowdrift_risk': weather_analysis.get('snowdrift_risk', {}).get('risk_level', 'unknown')
                    })

                results.append(result)
            else:
                # Vedlikehold uten værdata
                result = {
                    'maintenance_date': maintenance['Dato'],
                    'start_datetime': maintenance['start_datetime'],
                    'maintenance_type': maintenance['maintenance_type'],
                    'weather_analysis': {"status": "no_weather_data"}
                }
                results.append(result)

        correlation_df = pd.DataFrame(results)

        # NYTT: Klassifiser basert på sesong og værforhold
        if not correlation_df.empty:
            correlation_df = self.classify_maintenance_by_season_and_weather(correlation_df)

        return correlation_df

    def generate_analysis_report(self, correlation_df: pd.DataFrame, output_dir: str = "data/analyzed"):
        """Generer analyserapport."""
        print("Genererer analyserapport...")

        # Opprett output-katalog
        os.makedirs(output_dir, exist_ok=True)

        # Filtrer kun episoder med værdata
        valid_df = correlation_df[correlation_df['temp_min'].notna()].copy()

        if len(valid_df) == 0:
            print("Ingen gyldige korrelasjoner funnet")
            return

        print(f"Analyserer {len(valid_df)} episoder med værdata")

        # Tekstrapport
        report_file = os.path.join(output_dir, f"maintenance_weather_correlation_{datetime.now().strftime('%Y%m%d_%H%M')}.md")

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# Korrelasjon Vedlikehold vs Værforhold\n\n")
            f.write(f"**Analysedato:** {datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
            f.write(f"**Analyserte episoder:** {len(valid_df)}\n")
            f.write(f"**Tidsperiode:** {valid_df['start_datetime'].min().strftime('%d.%m.%Y')} - {valid_df['start_datetime'].max().strftime('%d.%m.%Y')}\n\n")

            # Hovedfunn
            f.write("## Hovedfunn\n\n")

            # Regn-på-snø episoder
            rain_on_snow = valid_df[valid_df['rain_on_snow'] == True]
            f.write(f"### Regn på snø-episoder: {len(rain_on_snow)}\n")
            if len(rain_on_snow) > 0:
                f.write("Disse episodene representerer sannsynlig strøing pga glatt føre:\n")
                for _, episode in rain_on_snow.iterrows():
                    f.write(f"- **{episode['maintenance_date']}**: {episode['precip_total']:.1f}mm nedbør, "
                           f"temp: {episode['temp_min']:.1f}-{episode['temp_max']:.1f}°C, "
                           f"snødybde: {episode['snow_depth_cm']:.0f}cm\n")
                f.write("\n")

            # Snøfokk-relatert vedlikehold
            snowdrift_episodes = valid_df[valid_df['snowdrift_risk'].isin(['high', 'medium'])]
            f.write(f"### Snøfokk-relatert vedlikehold: {len(snowdrift_episodes)}\n")
            if len(snowdrift_episodes) > 0:
                f.write("Episoder med høy/medium snøfokk-risiko:\n")
                for _, episode in snowdrift_episodes.iterrows():
                    f.write(f"- **{episode['maintenance_date']}**: {episode['snowdrift_risk']} risiko, "
                           f"vind: {episode['wind_max']:.1f}m/s, "
                           f"temp: {episode['temp_min']:.1f}°C\n")
                f.write("\n")

            # Vedlikeholdstyper
            f.write("## Vedlikeholdstyper\n\n")
            type_counts = valid_df['maintenance_type'].value_counts()
            for mtype, count in type_counts.items():
                f.write(f"- **{mtype}**: {count} episoder\n")
            f.write("\n")

            # Værsituasjoner
            f.write("## Værsituasjoner\n\n")
            scenario_counts = {}
            for scenarios_str in valid_df['weather_scenarios'].dropna():
                for scenario in scenarios_str.split(','):
                    if scenario:
                        scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1

            for scenario, count in sorted(scenario_counts.items(), key=lambda x: x[1], reverse=True):
                f.write(f"- **{scenario}**: {count} episoder\n")

        print(f"Rapport lagret til: {report_file}")

        # CSV-eksport for videre analyse
        csv_file = os.path.join(output_dir, f"maintenance_weather_data_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
        correlation_df.to_csv(csv_file, index=False, encoding='utf-8')
        print(f"Rådata lagret til: {csv_file}")

        # Visualiseringer
        self._create_visualizations(valid_df, output_dir)

    def _create_visualizations(self, df: pd.DataFrame, output_dir: str):
        """Lag visualiseringer av korrelasjonsdata."""
        print("Lager visualiseringer...")

        plt.style.use('default')

        # 1. Månedlig distribusjon av vedlikehold
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))

        df['month'] = pd.to_datetime(df['start_datetime']).dt.month
        monthly_counts = df['month'].value_counts().sort_index()

        axes[0,0].bar(monthly_counts.index, monthly_counts.values)
        axes[0,0].set_title('Vedlikehold per måned')
        axes[0,0].set_xlabel('Måned')
        axes[0,0].set_ylabel('Antall episoder')

        # 2. Temperatur vs vedlikeholdstype
        temp_by_type = df.groupby('maintenance_type')['temp_mean'].mean()
        axes[0,1].bar(temp_by_type.index, temp_by_type.values)
        axes[0,1].set_title('Gjennomsnittstemp per vedlikeholdstype')
        axes[0,1].set_ylabel('Temperatur (°C)')
        axes[0,1].tick_params(axis='x', rotation=45)

        # 3. Nedbør vs vedlikehold
        axes[1,0].scatter(df['precip_total'], df['duration_hours'], alpha=0.6)
        axes[1,0].set_xlabel('Nedbør (mm)')
        axes[1,0].set_ylabel('Varighet (timer)')
        axes[1,0].set_title('Nedbør vs Vedlikeholdsvarighet')

        # 4. Snøfokk-risiko distribusjon
        risk_counts = df['snowdrift_risk'].value_counts()
        axes[1,1].pie(risk_counts.values, labels=risk_counts.index, autopct='%1.1f%%')
        axes[1,1].set_title('Snøfokk-risiko distribusjon')

        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, f"maintenance_weather_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.png"),
                   dpi=300, bbox_inches='tight')
        plt.close()

        print("Visualiseringer lagret")

def main():
    """Hovedfunksjon."""
    correlator = MaintenanceWeatherCorrelator()

    # Last vedlikeholdsdata
    csv_file = "data/analyzed/Rapport 2022-2025.csv"

    if not os.path.exists(csv_file):
        print(f"ERROR: Finner ikke vedlikeholdsfil: {csv_file}")
        return

    maintenance_df = correlator.load_maintenance_data(csv_file)

    # Korreler med værdata
    correlation_df = correlator.correlate_maintenance_weather(maintenance_df)

    # Generer rapport
    correlator.generate_analysis_report(correlation_df)

    # NYTT: Generer forbedret sesongrapport
    correlator.generate_enhanced_season_report(correlation_df)

    print("Analyse fullført! Se rapporter i data/analyzed/")

if __name__ == "__main__":
    main()
