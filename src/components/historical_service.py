"""
Historisk værdata service med nysnø-beregninger og brøyting-tracking
"""
import json
import os
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import pandas as pd
import streamlit as st

from src.config import settings
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class HistoricalWeatherService:
    """Service for håndtering av historisk værdata og brøyting-tracking"""

    def __init__(self, frost_client_id: str, station_id: str = settings.station.station_id):
        self.frost_client_id = frost_client_id
        self.station_id = station_id
        self.cache_dir = "data/cache"
        self.february_data_file = "data/february_2024_weather.json"

        # Opprett cache directory
        os.makedirs(self.cache_dir, exist_ok=True)

    def validate_date_range(self, start_date: datetime, end_date: datetime) -> tuple[bool, str]:
        """Valider datorekkefølge og begrensninger"""

        cfg = settings.historical

        # Sjekk kronologisk rekkefølge
        if start_date >= end_date:
            return False, "Startdato må være før sluttdato"

        # Sjekk maksimal lengde
        if (end_date - start_date).days > cfg.date_range_max_days:
            return False, f"Maksimal periode er {cfg.date_range_max_days} dager"

        # Sjekk at det ikke er fremtid
        now = datetime.now(UTC)
        if start_date > now:
            return False, "Startdato kan ikke være i fremtiden"

        if end_date > now:
            return False, "Sluttdato kan ikke være i fremtiden"

        # Sjekk minimum varighet
        if end_date - start_date < timedelta(hours=cfg.date_range_min_hours):
            return False, f"Minimum periode er {cfg.date_range_min_hours} time(r)"

        return True, "OK"

    def load_february_data(self) -> pd.DataFrame:
        """Last forhåndslastet februar-data"""
        try:
            if os.path.exists(self.february_data_file):
                with open(self.february_data_file, encoding='utf-8') as f:
                    data = json.load(f)

                # Konverter til DataFrame
                df = pd.DataFrame(data)
                if 'time' in df.columns:
                    df['time'] = pd.to_datetime(df['time'])
                    df = df.sort_values('time').reset_index(drop=True)

                return df
            else:
                return pd.DataFrame()

        except (OSError, json.JSONDecodeError, ValueError, TypeError) as e:
            st.error(f"Feil ved lasting av februar-data: {e}")
            return pd.DataFrame()

    @lru_cache(maxsize=settings.historical.fetch_cache_maxsize)  # noqa: B019 - bevisst caching
    def fetch_historical_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Hent historisk data fra API med caching"""

        try:
            import requests

            # Utvidede elementer inkludert nysnø-beregning
            elements = [
                'air_temperature',
                'wind_speed',
                'wind_from_direction',
                'surface_snow_thickness',
                'sum(precipitation_amount PT1H)',
                'sum(precipitation_amount PT10M)',  # For nysnø-presisjon
                'accumulated(precipitation_amount)',
                'surface_temperature',
                'relative_humidity',
                'dew_point_temperature',
                'max(wind_speed_of_gust PT1H)',
                'weather_symbol',
                'min(air_temperature PT1H)',
                'max(air_temperature PT1H)'
            ]

            url = 'https://frost.met.no/observations/v0.jsonld'
            params = {
                'sources': self.station_id,
                'elements': ','.join(elements),
                'referencetime': f'{start_date}/{end_date}',
                'timeoffsets': 'PT0H',
                'maxage': 'PT168H'  # 7 dager max age for historisk data
            }

            class _RetryableRequestError(Exception):
                pass

            @retry(
                reraise=True,
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=0.5, min=0.5, max=6),
                retry=retry_if_exception_type(_RetryableRequestError),
            )
            def _get_with_retry() -> requests.Response:
                try:
                    resp = requests.get(
                        url,
                        params=params,
                        auth=(self.frost_client_id, ''),
                        timeout=settings.historical.http_timeout_seconds,  # Lengre timeout for historiske data
                    )
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    raise _RetryableRequestError(str(e)) from e

                if resp.status_code in {429, 500, 502, 503, 504}:
                    raise _RetryableRequestError(f"Frost API svarte {resp.status_code}")

                return resp

            response = _get_with_retry()

            if response.status_code == 200:
                data = response.json()

                if not data.get('data'):
                    return pd.DataFrame()

                records = []
                for obs in data['data']:
                    record = {'time': obs['referenceTime']}
                    for observation in obs.get('observations', []):
                        element_id = observation['elementId']
                        value = observation.get('value')
                        if value is not None:
                            record[element_id] = float(value)
                    records.append(record)

                if not records:
                    return pd.DataFrame()

                df = pd.DataFrame(records)
                df['time'] = pd.to_datetime(df['time'])
                df = df.sort_values('time').reset_index(drop=True)

                return df

            else:
                st.error(f"API-feil: {response.status_code}")
                return pd.DataFrame()

        except requests.RequestException as e:
            st.error(f"Feil ved henting av historisk data (HTTP): {e}")
            return pd.DataFrame()
        except (ValueError, KeyError, TypeError) as e:
            st.error(f"Feil ved parsing av historisk data: {e}")
            return pd.DataFrame()
        except Exception as e:
            st.error(f"Feil ved henting av historisk data: {e}")
            return pd.DataFrame()

    def calculate_new_snow(self, df: pd.DataFrame) -> pd.DataFrame:
        """Beregn nysnø basert på snødybde-endringer og nedbør"""

        if df.empty or 'surface_snow_thickness' not in df.columns:
            return df

        df = df.copy()

        # Konverter snødybde til cm hvis nødvendig
        snow_col = 'surface_snow_thickness'
        df['snow_depth_cm'] = df[snow_col] * 100
        df.loc[
            df['snow_depth_cm'] > settings.historical.snow_depth_conversion_cutoff_cm,
            'snow_depth_cm'
        ] = df.loc[
            df['snow_depth_cm'] > settings.historical.snow_depth_conversion_cutoff_cm,
            snow_col
        ]

        # Beregn snøendringer (diff)
        df['snow_change'] = df['snow_depth_cm'].diff()

        # Identifiser nysnø-perioder
        # Nysnø = positiv snøendring + nedbør + kald temperatur
        df['new_snow_candidate'] = (
            (df['snow_change'] > settings.historical.new_snow_change_min_cm) &
            (df.get('air_temperature', 0) < settings.historical.new_snow_air_temp_max)
        )

        # Beregn akkumulert nysnø siden sist brøyting
        df['new_snow_cm'] = 0.0
        df.loc[df['new_snow_candidate'], 'new_snow_cm'] = df.loc[df['new_snow_candidate'], 'snow_change']

        # Smooth ut urealistiske verdier
        df.loc[df['new_snow_cm'] > settings.historical.new_snow_hourly_cap_cm, 'new_snow_cm'] = settings.historical.new_snow_hourly_cap_cm
        df.loc[df['new_snow_cm'] < 0, 'new_snow_cm'] = 0

        # Klassifiser nysnø-type basert på temperatur
        df['snow_type'] = 'ingen'

        temp_col = 'air_temperature'
        if temp_col in df.columns:
            df.loc[
                (df['new_snow_cm'] > 0) & (df[temp_col] < settings.historical.snow_type_powder_air_temp_max),
                'snow_type'
            ] = 'tørr_pudder'

            df.loc[
                (df['new_snow_cm'] > 0) &
                (df[temp_col] >= settings.historical.snow_type_powder_air_temp_max) &
                (df[temp_col] < settings.historical.snow_type_dry_air_temp_max),
                'snow_type'
            ] = 'tørr'

            df.loc[
                (df['new_snow_cm'] > 0) &
                (df[temp_col] >= settings.historical.snow_type_dry_air_temp_max) &
                (df[temp_col] < settings.historical.snow_type_wet_air_temp_max),
                'snow_type'
            ] = 'våt'

            df.loc[
                (df['new_snow_cm'] > 0) & (df[temp_col] >= settings.historical.snow_type_wet_air_temp_max),
                'snow_type'
            ] = 'slaps'

        return df

    def calculate_snow_since_plowing(self, df: pd.DataFrame, last_plowed: datetime) -> dict:
        """Beregn snøfall siden sist brøyting"""

        if df.empty:
            return {
                'total_new_snow': 0,
                'snow_events': 0,
                'dominant_type': 'ukjent',
                'plowing_needed': False,
                'recommendation': 'Ingen data tilgjengelig'
            }

        # Filtrer data siden sist brøyting
        df_since_plowing = df[df['time'] >= last_plowed].copy()

        if df_since_plowing.empty:
            return {
                'total_new_snow': 0,
                'snow_events': 0,
                'dominant_type': 'ingen',
                'plowing_needed': False,
                'recommendation': 'Ingen data siden sist brøyting'
            }

        # Beregn akkumulert nysnø
        total_new_snow = df_since_plowing['new_snow_cm'].sum()

        # Tell snø-hendelser (sammenhengende perioder)
        snow_events = (df_since_plowing['new_snow_cm'] > 0).astype(int).diff().clip(lower=0).sum()

        # Finn dominerende snøtype
        snow_types = df_since_plowing[df_since_plowing['new_snow_cm'] > 0]['snow_type']
        if len(snow_types) > 0:
            dominant_type = snow_types.mode().iloc[0] if not snow_types.mode().empty else 'ukjent'
        else:
            dominant_type = 'ingen'

        # Vurder brøytebehov basert på empiriske terskler
        if dominant_type == 'våt' and total_new_snow >= settings.historical.plowing_threshold_wet_cm:
            plowing_needed = True
            recommendation = (
                f"Brøyting anbefalt: {total_new_snow:.1f}cm våt snø "
                f"(terskel: {settings.historical.plowing_threshold_wet_cm:g}cm)"
            )
        elif dominant_type in ['tørr', 'tørr_pudder'] and total_new_snow >= settings.historical.plowing_threshold_dry_cm:
            plowing_needed = True
            recommendation = (
                f"Brøyting anbefalt: {total_new_snow:.1f}cm tørr snø "
                f"(terskel: {settings.historical.plowing_threshold_dry_cm:g}cm)"
            )
        elif total_new_snow >= settings.historical.plowing_threshold_total_cm:
            plowing_needed = True
            recommendation = f"Brøyting anbefalt: {total_new_snow:.1f}cm total snø"
        else:
            plowing_needed = False
            recommendation = f"Brøyting ikke nødvendig: {total_new_snow:.1f}cm snø"

        return {
            'total_new_snow': round(total_new_snow, 1),
            'snow_events': snow_events,
            'dominant_type': dominant_type,
            'plowing_needed': plowing_needed,
            'recommendation': recommendation,
            'hours_since_plowing': (datetime.now(UTC) - last_plowed).total_seconds() / 3600
        }

    def save_plowing_event(self, timestamp: datetime, notes: str = ""):
        """Lagre brøyting-hendelse"""
        plowing_file = "data/plowing_log.json"

        # Last eksisterende data
        plowing_data = []
        if os.path.exists(plowing_file):
            try:
                with open(plowing_file, encoding='utf-8') as f:
                    plowing_data = json.load(f)
            except (json.JSONDecodeError, OSError, ValueError):
                plowing_data = []

        # Legg til ny hendelse
        new_event = {
            'timestamp': timestamp.isoformat(),
            'notes': notes,
            'recorded_at': datetime.now(UTC).isoformat()
        }

        plowing_data.append(new_event)

        # Behold kun siste 50 hendelser
        plowing_data = plowing_data[-50:]

        # Lagre
        os.makedirs(os.path.dirname(plowing_file), exist_ok=True)
        with open(plowing_file, 'w', encoding='utf-8') as f:
            json.dump(plowing_data, f, indent=2, ensure_ascii=False)

    def get_recent_plowing_events(self, limit: int = 10) -> list[dict]:
        """Hent nylige brøyting-hendelser"""
        plowing_file = "data/plowing_log.json"

        if not os.path.exists(plowing_file):
            return []

        try:
            with open(plowing_file, encoding='utf-8') as f:
                data = json.load(f)

            # Konverter timestamps og sorter
            for event in data:
                event['timestamp'] = datetime.fromisoformat(event['timestamp'])

            data.sort(key=lambda x: x['timestamp'], reverse=True)
            return data[:limit]

        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            return []

    def create_february_sample_data(self):
        """Opprett eksempel-data for 1-15 februar"""

        cfg = settings.historical

        # Generer realistisk vinterdata for Gullingen
        start_date = datetime(2024, 2, 1)
        end_date = datetime(2024, 2, 15, 23, 59)

        # Lag timebaserte datapunkter
        timestamps = []
        current = start_date
        while current <= end_date:
            timestamps.append(current)
            current += timedelta(hours=1)

        import numpy as np
        np.random.seed(cfg.feb_sample_seed)  # For konsistente resultater

        records = []
        base_snow_depth = cfg.feb_sample_start_snow_depth_cm  # Start snødybde
        accumulated_precip = 0

        for i, ts in enumerate(timestamps):
            # Simuler realistiske værforhold
            day_of_period = (ts - start_date).days

            # Temperatur-variasjon (kaldere først i perioden)
            base_temp = (
                cfg.feb_sample_base_temp_start_c
                + day_of_period * cfg.feb_sample_base_temp_daily_increase_c
                + np.sin(i / 24 * 2 * np.pi) * cfg.feb_sample_base_temp_diurnal_amp_c
            )
            temp = base_temp + np.random.normal(0, cfg.feb_sample_temp_noise_sigma_c)

            # Vind med storm-episoder
            if cfg.feb_sample_storm_main_day_start <= day_of_period <= cfg.feb_sample_storm_main_day_end:
                wind = cfg.feb_sample_storm_main_wind_base_ms + np.random.exponential(cfg.feb_sample_storm_main_wind_exp_scale)
            elif cfg.feb_sample_storm_minor_day_start <= day_of_period <= cfg.feb_sample_storm_minor_day_end:
                wind = cfg.feb_sample_storm_minor_wind_base_ms + np.random.exponential(cfg.feb_sample_storm_minor_wind_exp_scale)
            else:
                wind = cfg.feb_sample_wind_base_ms + np.random.exponential(cfg.feb_sample_wind_exp_scale)

            wind = min(wind, cfg.feb_sample_wind_cap_ms)

            # Nedbør-episoder
            precip_hour = 0
            if cfg.feb_sample_precip_ep1_day_start <= day_of_period <= cfg.feb_sample_precip_ep1_day_end and temp < cfg.feb_sample_precip_ep1_temp_max_c:
                precip_hour = np.random.exponential(cfg.feb_sample_precip_ep1_exp_scale) if np.random.random() < cfg.feb_sample_precip_ep1_prob else 0
            elif cfg.feb_sample_precip_ep2_day_start <= day_of_period <= cfg.feb_sample_precip_ep2_day_end and temp < cfg.feb_sample_precip_ep2_temp_max_c:
                precip_hour = np.random.exponential(cfg.feb_sample_precip_ep2_exp_scale) if np.random.random() < cfg.feb_sample_precip_ep2_prob else 0
            elif cfg.feb_sample_precip_ep3_day_start <= day_of_period <= cfg.feb_sample_precip_ep3_day_end and temp < cfg.feb_sample_precip_ep3_temp_max_c:
                precip_hour = np.random.exponential(cfg.feb_sample_precip_ep3_exp_scale) if np.random.random() < cfg.feb_sample_precip_ep3_prob else 0

            accumulated_precip += precip_hour

            # Snødybde (øker med snøfall, reduseres med vind og varme)
            if precip_hour > 0 and temp < cfg.feb_sample_snow_accum_temp_max_c:
                base_snow_depth += precip_hour * cfg.feb_sample_snow_accum_cm_per_mm

            if wind > cfg.feb_sample_blowing_wind_min_ms and temp < cfg.feb_sample_blowing_temp_max_c:
                base_snow_depth -= wind * cfg.feb_sample_blowing_snow_depth_reduction_coef

            if temp > cfg.feb_sample_melt_temp_min_c:
                base_snow_depth -= (temp - cfg.feb_sample_melt_offset_c) * cfg.feb_sample_melt_coef

            base_snow_depth = max(base_snow_depth, cfg.feb_sample_snow_min_depth_cm)

            # Surface temperature litt kaldere enn lufttemperatur
            surface_temp = temp - np.random.uniform(cfg.feb_sample_surface_temp_drop_min_c, cfg.feb_sample_surface_temp_drop_max_c)

            record = {
                'time': ts.isoformat(),
                'air_temperature': round(temp, 1),
                'wind_speed': round(wind, 1),
                'wind_from_direction': cfg.feb_sample_wind_dir_base_deg + np.random.normal(0, cfg.feb_sample_wind_dir_sigma_deg),
                'surface_snow_thickness': round(base_snow_depth, 1),
                'sum(precipitation_amount PT1H)': round(precip_hour, 1),
                'accumulated(precipitation_amount)': round(accumulated_precip, 1),
                'surface_temperature': round(surface_temp, 1),
                'relative_humidity': round(cfg.feb_sample_humidity_base_pct + np.random.normal(0, cfg.feb_sample_humidity_sigma_pct), 1),
                'dew_point_temperature': round(temp + cfg.feb_sample_dew_point_offset_c + np.random.normal(0, cfg.feb_sample_dew_point_sigma_c), 1),
                'max(wind_speed_of_gust PT1H)': round(wind * cfg.feb_sample_gust_multiplier, 1),
                'weather_symbol': (
                    cfg.feb_sample_weather_symbol_precip
                    if precip_hour > 0
                    else (cfg.feb_sample_weather_symbol_wind if wind > cfg.feb_sample_weather_symbol_wind_min_ms else cfg.feb_sample_weather_symbol_clear)
                )
            }

            records.append(record)

        # Lagre til fil
        os.makedirs(os.path.dirname(self.february_data_file), exist_ok=True)
        with open(self.february_data_file, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, ensure_ascii=False)

        return pd.DataFrame(records)
