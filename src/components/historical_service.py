"""
Historisk værdata service med nysnø-beregninger og brøyting-tracking
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from functools import lru_cache


class HistoricalWeatherService:
    """Service for håndtering av historisk værdata og brøyting-tracking"""
    
    def __init__(self, frost_client_id: str, station_id: str = "SN46220"):
        self.frost_client_id = frost_client_id
        self.station_id = station_id
        self.cache_dir = "data/cache"
        self.february_data_file = "data/february_2024_weather.json"
        
        # Opprett cache directory
        os.makedirs(self.cache_dir, exist_ok=True)

    def validate_date_range(self, start_date: datetime, end_date: datetime) -> Tuple[bool, str]:
        """Valider datorekkefølge og begrensninger"""
        
        # Sjekk kronologisk rekkefølge
        if start_date >= end_date:
            return False, "Startdato må være før sluttdato"
        
        # Sjekk maksimal lengde (14 dager)
        if (end_date - start_date).days > 14:
            return False, "Maksimal periode er 14 dager"
        
        # Sjekk at det ikke er fremtid
        now = datetime.now()
        if start_date > now:
            return False, "Startdato kan ikke være i fremtiden"
        
        if end_date > now:
            return False, "Sluttdato kan ikke være i fremtiden"
        
        # Sjekk minimum varighet (minst 1 time)
        if (end_date - start_date).total_seconds() < 3600:
            return False, "Minimum periode er 1 time"
        
        return True, "OK"

    def load_february_data(self) -> pd.DataFrame:
        """Last forhåndslastet februar-data"""
        try:
            if os.path.exists(self.february_data_file):
                with open(self.february_data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Konverter til DataFrame
                df = pd.DataFrame(data)
                if 'time' in df.columns:
                    df['time'] = pd.to_datetime(df['time'])
                    df = df.sort_values('time').reset_index(drop=True)
                
                return df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            st.error(f"Feil ved lasting av februar-data: {e}")
            return pd.DataFrame()

    @lru_cache(maxsize=20)
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

            response = requests.get(
                url, 
                params=params, 
                auth=(self.frost_client_id, ''), 
                timeout=60  # Lengre timeout for historisk data
            )
            
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
        df.loc[df['snow_depth_cm'] > 10, 'snow_depth_cm'] = df.loc[df['snow_depth_cm'] > 10, snow_col]
        
        # Beregn snøendringer (diff)
        df['snow_change'] = df['snow_depth_cm'].diff()
        
        # Identifiser nysnø-perioder
        # Nysnø = positiv snøendring + nedbør + kald temperatur
        df['new_snow_candidate'] = (
            (df['snow_change'] > 0.5) &  # Minst 0.5cm økning
            (df.get('air_temperature', 0) < 2)  # Under 2°C
        )
        
        # Beregn akkumulert nysnø siden sist brøyting
        df['new_snow_cm'] = 0.0
        df.loc[df['new_snow_candidate'], 'new_snow_cm'] = df.loc[df['new_snow_candidate'], 'snow_change']
        
        # Smooth ut urealistiske verdier
        df.loc[df['new_snow_cm'] > 20, 'new_snow_cm'] = 20  # Max 20cm per time
        df.loc[df['new_snow_cm'] < 0, 'new_snow_cm'] = 0
        
        # Klassifiser nysnø-type basert på temperatur
        df['snow_type'] = 'ingen'
        
        temp_col = 'air_temperature'
        if temp_col in df.columns:
            df.loc[
                (df['new_snow_cm'] > 0) & (df[temp_col] < -5), 
                'snow_type'
            ] = 'tørr_pudder'
            
            df.loc[
                (df['new_snow_cm'] > 0) & (df[temp_col] >= -5) & (df[temp_col] < -1), 
                'snow_type'
            ] = 'tørr'
            
            df.loc[
                (df['new_snow_cm'] > 0) & (df[temp_col] >= -1) & (df[temp_col] < 1), 
                'snow_type'
            ] = 'våt'
            
            df.loc[
                (df['new_snow_cm'] > 0) & (df[temp_col] >= 1), 
                'snow_type'
            ] = 'slaps'
        
        return df

    def calculate_snow_since_plowing(self, df: pd.DataFrame, last_plowed: datetime) -> Dict:
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
        if dominant_type == 'våt' and total_new_snow >= 6:
            plowing_needed = True
            recommendation = f"Brøyting anbefalt: {total_new_snow:.1f}cm våt snø (terskel: 6cm)"
        elif dominant_type in ['tørr', 'tørr_pudder'] and total_new_snow >= 12:
            plowing_needed = True
            recommendation = f"Brøyting anbefalt: {total_new_snow:.1f}cm tørr snø (terskel: 12cm)"
        elif total_new_snow >= 15:
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
            'hours_since_plowing': (datetime.now() - last_plowed).total_seconds() / 3600
        }

    def save_plowing_event(self, timestamp: datetime, notes: str = ""):
        """Lagre brøyting-hendelse"""
        plowing_file = "data/plowing_log.json"
        
        # Last eksisterende data
        plowing_data = []
        if os.path.exists(plowing_file):
            try:
                with open(plowing_file, 'r', encoding='utf-8') as f:
                    plowing_data = json.load(f)
            except:
                plowing_data = []
        
        # Legg til ny hendelse
        new_event = {
            'timestamp': timestamp.isoformat(),
            'notes': notes,
            'recorded_at': datetime.now().isoformat()
        }
        
        plowing_data.append(new_event)
        
        # Behold kun siste 50 hendelser
        plowing_data = plowing_data[-50:]
        
        # Lagre
        os.makedirs(os.path.dirname(plowing_file), exist_ok=True)
        with open(plowing_file, 'w', encoding='utf-8') as f:
            json.dump(plowing_data, f, indent=2, ensure_ascii=False)

    def get_recent_plowing_events(self, limit: int = 10) -> List[Dict]:
        """Hent nylige brøyting-hendelser"""
        plowing_file = "data/plowing_log.json"
        
        if not os.path.exists(plowing_file):
            return []
        
        try:
            with open(plowing_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Konverter timestamps og sorter
            for event in data:
                event['timestamp'] = datetime.fromisoformat(event['timestamp'])
            
            data.sort(key=lambda x: x['timestamp'], reverse=True)
            return data[:limit]
            
        except Exception:
            return []

    def create_february_sample_data(self):
        """Opprett eksempel-data for 1-15 februar"""
        
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
        np.random.seed(42)  # For konsistente resultater
        
        records = []
        base_snow_depth = 45  # Start snødybde
        accumulated_precip = 0
        
        for i, ts in enumerate(timestamps):
            # Simuler realistiske værforhold
            day_of_period = (ts - start_date).days
            
            # Temperatur-variasjon (kaldere først i perioden)
            base_temp = -8 + day_of_period * 0.5 + np.sin(i/24 * 2*np.pi) * 4
            temp = base_temp + np.random.normal(0, 2)
            
            # Vind med storm-episoder
            if 3 <= day_of_period <= 5:  # Storm 3-5 februar
                wind = 12 + np.random.exponential(3)
            elif 9 <= day_of_period <= 10:  # Mindre storm 9-10 februar
                wind = 8 + np.random.exponential(2)
            else:
                wind = 3 + np.random.exponential(2)
            
            wind = min(wind, 25)  # Max 25 m/s
            
            # Nedbør-episoder
            precip_hour = 0
            if 2 <= day_of_period <= 3 and temp < 0:  # Snøfall 2-3 feb
                precip_hour = np.random.exponential(0.8) if np.random.random() < 0.4 else 0
            elif 7 <= day_of_period <= 8 and temp < 1:  # Snøfall 7-8 feb
                precip_hour = np.random.exponential(1.2) if np.random.random() < 0.3 else 0
            elif 12 <= day_of_period <= 13 and temp < 2:  # Lett snøfall 12-13 feb
                precip_hour = np.random.exponential(0.5) if np.random.random() < 0.2 else 0
            
            accumulated_precip += precip_hour
            
            # Snødybde (øker med snøfall, reduseres med vind og varme)
            if precip_hour > 0 and temp < 1:
                base_snow_depth += precip_hour * 2  # 2cm per mm nedbør
            
            if wind > 10 and temp < -2:  # Vindblåst snø
                base_snow_depth -= wind * 0.05
            
            if temp > 3:  # Smelting
                base_snow_depth -= (temp - 2) * 0.2
            
            base_snow_depth = max(base_snow_depth, 5)  # Minimum snødybde
            
            # Surface temperature litt kaldere enn lufttemperatur
            surface_temp = temp - np.random.uniform(0.5, 2.0)
            
            record = {
                'time': ts.isoformat(),
                'air_temperature': round(temp, 1),
                'wind_speed': round(wind, 1),
                'wind_from_direction': 225 + np.random.normal(0, 30),  # Hovedsakelig SV
                'surface_snow_thickness': round(base_snow_depth, 1),
                'sum(precipitation_amount PT1H)': round(precip_hour, 1),
                'accumulated(precipitation_amount)': round(accumulated_precip, 1),
                'surface_temperature': round(surface_temp, 1),
                'relative_humidity': round(60 + np.random.normal(0, 15), 1),
                'dew_point_temperature': round(temp - 5 + np.random.normal(0, 2), 1),
                'max(wind_speed_of_gust PT1H)': round(wind * 1.4, 1),
                'weather_symbol': 1 if precip_hour > 0 else (2 if wind > 8 else 3)
            }
            
            records.append(record)
        
        # Lagre til fil
        os.makedirs(os.path.dirname(self.february_data_file), exist_ok=True)
        with open(self.february_data_file, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        
        return pd.DataFrame(records)
