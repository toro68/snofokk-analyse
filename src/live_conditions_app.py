#!/usr/bin/env python3
"""
Sanntidsvurdering av føreforhold med effektiv datahenting
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import requests
import json
from typing import Dict, List, Tuple, Optional
import time
from functools import lru_cache
import os
from dotenv import load_dotenv

# Last miljøvariabler
load_dotenv()

# Konstanter
PRECIP_HOURLY_COL = 'sum(precipitation_amount PT1H)'

class LiveConditionsChecker:
    """Sanntidsvurdering av føreforhold med effektiv datahenting."""
    
    def __init__(self):
        self.frost_client_id = os.getenv('FROST_CLIENT_ID')
        # Default to correct Gullingen Skisenter station; allow env override
        self.station_id = os.getenv("WEATHER_STATION", "SN46220")  # Gullingen Skisenter
        self.cache_duration = 3600  # 1 time cache
    
    def is_winter_season(self) -> bool:
        """Sjekk om det er vintersesong (oktober-april)."""
        current_month = datetime.now().month
        return current_month in [10, 11, 12, 1, 2, 3, 4]
    
    def is_summer_season(self) -> bool:
        """Sjekk om det er sommersesong (mai-september)."""
        return not self.is_winter_season()
        
    @lru_cache(maxsize=10)
    def get_current_weather_data(self, hours_back: int = 24, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Henter værdata for spesifisert periode (bufret)."""
        
        try:
            if not self.frost_client_id:
                st.error("FROST_CLIENT_ID mangler. Kontroller .env-filen.")
                return None
            
            # Beregn tidsperiode
            if start_date and end_date:
                # Bruk spesifiserte datoer
                start_time = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
                end_time = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
            else:
                # Standard: siste X timer fra nå (UTC)
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(hours=hours_back)
            
            fmt = "%Y-%m-%dT%H:%M:%SZ"
            start_iso = start_time.strftime(fmt)
            end_iso = end_time.strftime(fmt)
            
            # Utvidede elementer for bedre væranalyse
            elements = [
                'air_temperature',
                'wind_speed',
                'wind_from_direction',                    # NY: vindretning for snøfokk-analyse
                'surface_snow_thickness',
                'sum(precipitation_amount PT1H)',        # FIX: korrekt nedbør-element
                'relative_humidity',
                'surface_temperature',                   # NY: bakketemperatur for is-deteksjon
                'dew_point_temperature'                  # NY: duggpunkt for rimfrost-analyse
            ]
            
            # Frost API request
            url = 'https://frost.met.no/observations/v0.jsonld'
            parameters = {
                'sources': self.station_id,
                'elements': ','.join(elements),
                'referencetime': f"{start_iso}/{end_iso}"
            }
            
            # Tidsavbrudd og robust feilhandtering
            response = requests.get(url, parameters, auth=(self.frost_client_id, ''), timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if not data.get('data'):
                    st.warning("Ingen data mottatt fra API-et")
                    return None
                
                # Parse til DataFrame
                records = []
                for obs in data['data']:
                    record = {'referenceTime': pd.to_datetime(obs['referenceTime'])}
                    
                    for observation in obs['observations']:
                        element = observation['elementId']
                        value = observation['value']
                        
                        # For luftfuktighet og temperatur: kun PT1H oppløsning
                        time_res = observation.get('timeResolution', 'PT1H')
                        if element in ['air_temperature', 'relative_humidity'] and time_res != 'PT1H':
                            continue
                        
                        # For vinddata: bruk PT1H oppløsning hvis tilgjengelig
                        if element == 'wind_speed' and time_res != 'PT1H':
                            continue
                            
                        record[element] = value
                    
                    records.append(record)
                
                if not records:
                    st.warning("Ingen gyldige målinger")
                    return None
                
                df = pd.DataFrame(records)
                # Normaliser nedbørskolonne til 'sum(precipitation_amount PT1H)'
                if PRECIP_HOURLY_COL not in df.columns and 'precipitation_amount' in df.columns:
                    df[PRECIP_HOURLY_COL] = df['precipitation_amount']
                df = df.sort_values('referenceTime').drop_duplicates('referenceTime').reset_index(drop=True)
                
                return df
                
            elif response.status_code == 401:
                st.error("API 401 (Unauthorized) – kontroller API-nøkkel")
                return None
            elif response.status_code == 403:
                st.error("API 403 (Forbidden) – API-nøkkel mangler tilgang")
                return None
            elif response.status_code == 404:
                st.error("API 404 (Not Found) – stasjon ikke funnet")
                return None
            else:
                st.error(f"API-feil: {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            st.error("Tidsavbrudd mot API. Prøv igjen.")
            return None
        except requests.exceptions.ConnectionError:
            st.error("Tilkoblingsfeil. Kontroller nettverkstilkoblingen.")
            return None
        except Exception as e:
            st.error(f"Ukjent feil: {e}")
            return None
    
    def analyze_snowdrift_risk(self, df: pd.DataFrame) -> Dict:
        """Analyser snøfokk-risiko basert på våre kriterier."""
        
        if df is None or len(df) == 0:
            return {"risk_level": "unknown", "message": "Ingen data tilgjengelig"}
        
        # Sommersesong: Begrenset snøanalyse
        if self.is_summer_season():
            latest = df.iloc[-1]
            current_temp = latest.get('air_temperature', None)
            current_snow = latest.get('surface_snow_thickness', 0)
            
            if current_snow < 1:
                return {
                    "risk_level": "low",
                    "message": f"Sommersesong: Ingen snø registrert (temp: {current_temp:.1f} °C)",
                    "factors": [],
                    "seasonal_note": "Snøfokk-analyse ikke relevant i sommerperioden"
                }
            # Uvanlig snø på sommeren
            return {
                "risk_level": "medium",
                "message": f"Uvanlig snødekke registrert i sommermånedene ({current_snow:.0f} cm)",
                "factors": [f"Snødybde: {current_snow:.0f} cm", f"Temperatur: {current_temp:.1f} °C"],
                "seasonal_note": "Bør verifiseres - uvanlig forhold for årstiden"
            }
        
        # Vintersesong: Full analyse
        
        # Siste målinger
        latest = df.iloc[-1]
        # Bruk UTC for sammenligning (referenceTime er tz-aware UTC)
        last_24h = df[df['referenceTime'] >= (datetime.now(timezone.utc) - timedelta(hours=24))]
        
        # Grunnleggende kriterier
        current_temp = latest.get('air_temperature', None)
        current_wind = latest.get('wind_speed', None) 
        current_snow = latest.get('surface_snow_thickness', 0)
        wind_direction = latest.get('wind_from_direction', None)  # NY: vindretning
        
        if current_temp is None or current_wind is None:
            return {"risk_level": "unknown", "message": "Mangler kritiske målinger"}
        
        # Sjekk løssnø-tilgjengelighet (kritisk kriterium)
        mild_weather_recent = (last_24h['air_temperature'] > 0).any() if 'air_temperature' in last_24h.columns else True
        continuous_frost = (last_24h['air_temperature'] <= -1).all() if 'air_temperature' in last_24h.columns and len(last_24h) > 12 else False
        
        # Klassifiser risiko
        risk_factors = []
        
        # Meteorologiske kriterier
        if current_wind >= 6:
            wind_desc = f"Sterk vind ({current_wind:.1f} m/s"
            if wind_direction is not None:
                # Legg til vindretning og evaluer for Gullingen (lokalt terreng)
                direction_desc = ""
                if 315 <= wind_direction or wind_direction < 45:  # Nord (315-45°)
                    direction_desc = "N"
                elif 45 <= wind_direction < 135:  # Øst (45-135°)
                    direction_desc = "Ø"
                elif 135 <= wind_direction < 225:  # Sør (135-225°)
                    direction_desc = "S"
                elif 225 <= wind_direction < 315:  # Vest (225-315°)
                    direction_desc = "V"
                wind_desc += f" fra {direction_desc})"
                
                # Vurder lokal terrengeffekt for Gullingen
                if 270 <= wind_direction <= 360 or 0 <= wind_direction <= 90:  # NV-N-NØ
                    risk_factors.append(wind_desc + " - høyrisiko-retning for Gullingen")
                else:
                    risk_factors.append(wind_desc)
            else:
                risk_factors.append(wind_desc + ")")
        if current_temp <= -1:
            risk_factors.append(f"Frost ({current_temp:.1f}°C)")
        if current_snow >= 3:
            risk_factors.append(f"Snødekke ({current_snow:.0f}cm)")
        
    # Løssnø-vurdering
        if mild_weather_recent:
            return {
                "risk_level": "low",
        "message": f"Stabile forhold: Mildvær siste 24 t reduserer løssnø. Vind: {current_wind:.1f} m/s, temp: {current_temp:.1f} °C",
                "factors": risk_factors,
        "loose_snow": "Redusert av mildvær"
            }
        
        # Hvis alle kriterier oppfylt OG løssnø tilgjengelig
        if len(risk_factors) >= 3 and continuous_frost:
            return {
                "risk_level": "high", 
                "message": "Høy risiko for snøfokk: Kriterier oppfylt og løssnø tilgjengelig",
                "factors": risk_factors,
                "loose_snow": "Tilgjengelig (kontinuerlig frost)"
            }
        elif len(risk_factors) >= 2:
            return {
                "risk_level": "medium",
                "message": "Moderat risiko: Flere kriterier er oppfylt",
                "factors": risk_factors,
                "loose_snow": "Usikker kvalitet"
            }
        else:
            return {
                "risk_level": "low",
                "message": "Lav risiko: Få eller ingen kriterier er oppfylt",
                "factors": risk_factors,
                "loose_snow": "Ikke avgjørende"
            }
    
    def analyze_slippery_road_risk(self, df: pd.DataFrame) -> Dict:
        """Analyser glatt vei-risiko (regn-på-snø fokus + rimfrost)."""
        
        if df is None or len(df) == 0:
            return {"risk_level": "unknown", "message": "Ingen data tilgjengelig"}
        
        latest = df.iloc[-1]
        current_temp = latest.get('air_temperature', None)
        current_snow = latest.get('surface_snow_thickness', 0)
        current_precip = latest.get(PRECIP_HOURLY_COL, 0)
        surface_temp = latest.get('surface_temperature', None)  # NY: bakketemperatur
        dew_point = latest.get('dew_point_temperature', None)   # NY: duggpunkt
        humidity = latest.get('relative_humidity', None)
        
        if current_temp is None:
            return {"risk_level": "unknown", "message": "Mangler temperaturdata"}
        
        # Sommersesong: Fokus på regn og varme forhold
        if self.is_summer_season():
            factors = []
            
            # Rimfrost-sjekk (også relevant om sommeren på kalde netter)
            if dew_point is not None and surface_temp is not None:
                frost_risk = surface_temp <= 0 and abs(current_temp - dew_point) < 2
                if frost_risk:
                    factors.append(f"Rimfrost-risiko (bakke: {surface_temp:.1f}°C, duggp: {dew_point:.1f}°C)")
                    
            if current_precip >= 0.5:
                factors.append(f"Nedbør: {current_precip:.1f} mm/h")
                risk_level = "high" if factors and "rimfrost" in factors[0].lower() else "medium"
                return {
                    "risk_level": risk_level,
                    "message": f"Regn kan gi glatte forhold ({current_precip:.1f} mm/h, {current_temp:.1f} °C)",
                    "scenario": "Sommerregn" + (" + rimfrost" if factors and "rimfrost" in factors[0].lower() else ""),
                    "factors": factors
                }
            elif factors:  # Kun rimfrost
                return {
                    "risk_level": "medium",
                    "message": f"Rimfrost-forhold (temp: {current_temp:.1f} °C)",
                    "scenario": "Rimfrost",
                    "factors": factors
                }
            else:
                return {
                    "risk_level": "low",
                    "message": f"Normale sommerforhold (temp: {current_temp:.1f} °C)",
                    "scenario": "Sommerperiode",
                    "factors": []
                }
        
        # Vintersesong: Full regn-på-snø analyse + rimfrost/is-deteksjon
        # Bruk UTC for sammenligning (referenceTime er tz-aware UTC)
        last_6h = df[df['referenceTime'] >= (datetime.now(timezone.utc) - timedelta(hours=6))]
        
        # Regn-på-snø scenario (hovedfokus)
        mild_weather = 0 <= current_temp <= 4
        existing_snow = current_snow >= 5  # cm
        rain_now = current_precip >= 0.3  # mm/h
        
        # Nye is/rimfrost-kriterier med utvidede data
        ice_risk = False
        frost_risk = False
        if surface_temp is not None and dew_point is not None:
            ice_risk = surface_temp <= 0 and current_temp > -1  # Bakken kald, lufta mildere
            frost_risk = surface_temp <= 0 and abs(current_temp - dew_point) < 2  # Rimfrost-forhold
        
        # Temperaturovergang-scenario
        recent_temp_rise = False
        if len(last_6h) > 3:
            temp_change = last_6h['air_temperature'].diff().max()
            recent_temp_rise = temp_change > 1  # Økning >1°C
        
        risk_factors = []
        
        if mild_weather:
            risk_factors.append(f"Mildvær ({current_temp:.1f}°C)")
        if existing_snow:
            risk_factors.append(f"Snødekke ({current_snow:.0f}cm)")
        if rain_now:
            risk_factors.append(f"Regn ({current_precip:.1f}mm/h)")
        if recent_temp_rise:
            risk_factors.append("Temperaturøkning")
        if ice_risk:
            risk_factors.append(f"Is-risiko (bakke: {surface_temp:.1f}°C)")
        if frost_risk:
            risk_factors.append(f"Rimfrost (duggp: {dew_point:.1f}°C)")
        
        # Klassifisering med utvidede kriterier (prioritering: regn-på-snø > is > rimfrost > temperaturovergang)
        if mild_weather and existing_snow and rain_now:
            return {
                "risk_level": "high",
                "message": "Høy risiko for glatt føre: Regn på snødekt vei",
                "scenario": "Regn på snø",
                "factors": risk_factors
            }
        elif ice_risk and (rain_now or existing_snow):
            return {
                "risk_level": "high",
                "message": "Høy risiko for glatt føre: Is-dannelse på vei",
                "scenario": "Is-risiko",
                "factors": risk_factors
            }
        elif frost_risk:
            return {
                "risk_level": "medium",
                "message": "Moderat risiko: Rimfrost-forhold på vei",
                "scenario": "Rimfrost",
                "factors": risk_factors
            }
        elif mild_weather and existing_snow and recent_temp_rise:
            return {
                "risk_level": "medium", 
                "message": "Moderat risiko: Snøsmelting og overgang rundt 0 °C",
                "scenario": "Temperaturovergang",
                "factors": risk_factors
            }
        elif current_temp < -5 and existing_snow:
            return {
                "risk_level": "low",
                "message": f"Stabile forhold: Kaldt og tørt gir gode kjøreforhold på snø ({current_temp:.1f} °C)",
                "scenario": "Stabilt kaldt",
                "factors": risk_factors
            }
        else:
            return {
                "risk_level": "low",
        "message": "Lav risiko: Mangler kritiske kombinasjoner",
                "scenario": "Normale forhold",
                "factors": risk_factors
            }

def create_streamlit_app():
    """Lag Streamlit web app for live føreforhold."""
    
    st.set_page_config(
        page_title="Føreforhold – Gullingen (live)",
        layout="wide"
    )
    
    st.title("Føreforhold – Gullingen (live)")
    
    # Sesonginfo
    checker = LiveConditionsChecker()
    if checker.is_summer_season():
        st.info("**Sommersesong aktiv** – Snø- og isanalyse er begrenset til unormale forhold")
    else:
        st.info("**Vintersesong aktiv** – Full analyse av snøfokk og glatt føre")
    
    # Opprett checker
    
    # Innstillinger
    with st.expander("Innstillinger", expanded=False):
        # Datovalg
        st.subheader("Tidsperiode")
        col_time1, col_time2 = st.columns(2)
        
        with col_time1:
            use_custom_dates = st.checkbox("Bruk spesifikke datoer", value=False)
            
        with col_time2:
            if not use_custom_dates:
                hours_back = st.slider("Timer tilbake fra nå", 6, 168, 24, help="Standard: siste 24 timer")
        
        # Datovalg for historiske data
        if use_custom_dates:
            col_date1, col_date2 = st.columns(2)
            with col_date1:
                start_date = st.date_input(
                    "Fra dato", 
                    value=datetime(2024, 2, 1).date(),
                    min_value=datetime(2018, 1, 1).date(),
                    max_value=datetime.now().date()
                )
                start_time = st.time_input("Fra tidspunkt", value=datetime.now().time().replace(hour=0, minute=0))
            
            with col_date2:
                end_date = st.date_input(
                    "Til dato", 
                    value=datetime(2024, 2, 2).date(),
                    min_value=datetime(2018, 1, 1).date(),
                    max_value=datetime.now().date()
                )
                end_time = st.time_input("Til tidspunkt", value=datetime.now().time().replace(hour=23, minute=59))
        
        # Andre innstillinger
        st.subheader("Andre innstillinger")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            station_id_input = st.text_input("Stasjons-ID", value=checker.station_id)
        with col_b:
            if st.button("Tøm mellomlager"):
                try:
                    LiveConditionsChecker.get_current_weather_data.cache_clear()  # type: ignore[attr-defined]
                    st.success("Mellomlager tømt.")
                except Exception:
                    st.info("Mellomlager kunne ikke tømmes.")
        with col_c:
            if use_custom_dates:
                period_info = f"{start_date} til {end_date}"
            else:
                period_info = f"Siste {hours_back if 'hours_back' in locals() else 24} timer"
            st.info(f"Periode: {period_info}")
    
    if 'station_id_input' in locals() and station_id_input:
        checker.station_id = station_id_input
    
    # Auto-refresh hver 5. minutt
    placeholder = st.empty()
    
    with placeholder.container():
        # Hent data (cached!)
        with st.spinner("Henter værdata …"):
            if 'use_custom_dates' in locals() and use_custom_dates and 'start_date' in locals() and 'end_date' in locals():
                # Kombiner dato og tid
                start_datetime = datetime.combine(start_date, start_time).isoformat()
                end_datetime = datetime.combine(end_date, end_time).isoformat()
                df = checker.get_current_weather_data(start_date=start_datetime, end_date=end_datetime)
                data_period_description = f"fra {start_date} til {end_date}"
            else:
                df = checker.get_current_weather_data(hours_back=hours_back if 'hours_back' in locals() else 24)
                hours_used = hours_back if 'hours_back' in locals() else 24
                data_period_description = f"siste {hours_used} timer"
        
        if df is not None and len(df) > 0:
            
            # Periode-informasjon
            latest_time = df['referenceTime'].iloc[-1]
            earliest_time = df['referenceTime'].iloc[0]
            st.info(f"📊 **Data for {data_period_description}** | Siste måling: {latest_time.strftime('%d.%m.%Y kl %H:%M')} | Første måling: {earliest_time.strftime('%d.%m.%Y kl %H:%M')} | {len(df)} målinger")
            
            # Tre kolonner for resultater
            col1, col2, col3 = st.columns(3)
            
            # SNØFOKK-ANALYSE
            with col1:
                st.subheader("Snøfokk – risikovurdering")
                
                # Kriterieinfo
                with st.expander("Kriterier for snøfokk"):
                    st.markdown("""
                    **Snøfokk oppstår når alle disse kriteriene er oppfylt:**
                    - **Vindstyrke:** ≥ 6 m/s
                    - **Temperatur:** ≤ -1°C  
                    - **Snødybde:** ≥ 3 cm
                    - **Løssnø:** Tilgjengelig (ingen mildvær siste 24t)
                    
                    **Begrensende faktorer:**
                    - Mildvær (>0°C) ødelegger løssnø
                    - Sammenhengende frost nødvendig for løssnø-kvalitet
                    """)
                
                snowdrift_result = checker.analyze_snowdrift_risk(df)
                
                # Fargekoding
                if snowdrift_result['risk_level'] == 'high':
                    st.error(snowdrift_result['message'])
                elif snowdrift_result['risk_level'] == 'medium':
                    st.warning(snowdrift_result['message'])
                else:
                    st.success(snowdrift_result['message'])
                
                # Detaljer
                if 'factors' in snowdrift_result:
                    st.write("**Vurderingsgrunnlag:**")
                    for factor in snowdrift_result['factors']:
                        st.write(f"• {factor}")
                
                if 'loose_snow' in snowdrift_result:
                    st.write(f"**Løssnøtilstand:** {snowdrift_result['loose_snow']}")
                
                if 'seasonal_note' in snowdrift_result:
                    st.caption(snowdrift_result['seasonal_note'])
            
            # GLATT VEI-ANALYSE  
            with col2:
                st.subheader("Glatt føre – risikovurdering")
                
                # Kriterieinfo
                with st.expander("Kriterier for glatt føre"):
                    st.markdown("""
                    **Hovedscenarier for glatte veier:**
                    
                    **1. Regn på snø (vinter):**
                    - Mildvær (0-4°C) + regn (≥0.3 mm/h)
                    - Eksisterende snødekke (≥5 cm)
                    
                    **2. Temperaturovergang:**
                    - Temperaturstigning >1°C på 6 timer
                    - Snøsmelting + påfølgende frysing
                    
                    **3. Sommerregn:**
                    - Intens nedbør (≥0.5 mm/h) kan gi glatte forhold
                    
                    **Beskyttende faktorer:**
                    - Stabilt kaldt vær (<-5°C) gir gode kjøreforhold på snø
                    - Snøfall fungerer som naturlig strøing
                    """)
                
                slippery_result = checker.analyze_slippery_road_risk(df)
                
                # Fargekoding
                if slippery_result['risk_level'] == 'high':
                    st.error(slippery_result['message'])
                elif slippery_result['risk_level'] == 'medium':
                    st.warning(slippery_result['message'])
                else:
                    st.success(slippery_result['message'])
                
                # Detaljer
                if 'scenario' in slippery_result:
                    st.write(f"**Scenario:** {slippery_result['scenario']}")
                
                if 'factors' in slippery_result:
                    st.write("**Vurderingsgrunnlag:**")
                    for factor in slippery_result['factors']:
                        st.write(f"• {factor}")
            
            # NØKKELDATA
            with col3:
                st.subheader("Nøkkelverdier")
                latest = df.iloc[-1]
                
                st.metric("Temperatur", f"{latest.get('air_temperature', 'N/A'):.1f}°C")
                st.metric("Vind", f"{latest.get('wind_speed', 'N/A'):.1f} m/s")
                st.metric("Snødybde", f"{latest.get('surface_snow_thickness', 'N/A'):.0f} cm")
                
                precip = latest.get(PRECIP_HOURLY_COL, latest.get('precipitation_amount', 0))
                st.metric("Nedbør", f"{precip:.1f} mm/h")
            
            # TREND-GRAF
            st.subheader("Værdata over valgt periode")
            
            # Debug-info for tilgjengelige kolonner
            with st.expander("Debug: Tilgjengelige data", expanded=False):
                st.write("**Kolonner i datasett:**", list(df.columns))
                st.write("**Antall målinger:**", len(df))
                if 'wind_speed' in df.columns:
                    wind_stats = df['wind_speed'].describe()
                    st.write("**Vinddata statistikk:**", wind_stats)
                    st.write("**Manglende vindverdier:**", df['wind_speed'].isna().sum())
                else:
                    st.write("**Vinddata:** Ikke tilgjengelig i datasettet")
            
            # Vis alle data hvis historisk periode, eller siste 24t hvis live
            if 'use_custom_dates' in locals() and use_custom_dates:
                plot_data = df  # Vis all historisk data
                graph_title = f"Værdata {start_date} til {end_date}"
            else:
                # For live data: vis siste 24 timer hvis tilgjengelig
                last_24h = df[df['referenceTime'] >= (datetime.now(timezone.utc) - timedelta(hours=24))]
                if len(last_24h) > 0:
                    plot_data = last_24h
                    graph_title = "Værdata siste 24 timer"
                else:
                    plot_data = df
                    graph_title = f"Værdata {data_period_description}"
            
            if len(plot_data) > 0:
                import matplotlib.pyplot as plt
                
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6))
                fig.suptitle(graph_title)
                
                # Temperatur
                if 'air_temperature' in plot_data.columns:
                    ax1.plot(plot_data['referenceTime'], plot_data['air_temperature'], 'r-', label='Temperatur (°C)')
                    ax1.axhline(y=0, color='blue', linestyle='--', alpha=0.5, label='Frysepunkt')
                else:
                    ax1.text(0.5, 0.5, 'Temperaturdata ikke tilgjengelig', ha='center', va='center', transform=ax1.transAxes)
                ax1.set_ylabel('Temperatur (°C)')
                ax1.legend()
                ax1.grid(True, alpha=0.3)
                
                # Vind
                if 'wind_speed' in plot_data.columns and not plot_data['wind_speed'].isna().all():
                    ax2.plot(plot_data['referenceTime'], plot_data['wind_speed'], 'g-', label='Vindstyrke (m/s)')
                    ax2.axhline(y=6, color='orange', linestyle='--', alpha=0.5, label='Snøfokk-terskel')
                else:
                    ax2.text(0.5, 0.5, 'Vinddata ikke tilgjengelig', ha='center', va='center', transform=ax2.transAxes)
                ax2.set_ylabel('Vind (m/s)')
                ax2.set_xlabel('Tid')
                ax2.legend()
                ax2.grid(True, alpha=0.3)
                
                plt.tight_layout()
                st.pyplot(fig)
        
        else:
            st.error("Klarte ikke hente data. Kontroller nettverk eller API-nøkkel.")
    
    # Auto-refresh
    st.markdown("---")
    col_footer1, col_footer2 = st.columns(2)
    with col_footer1:
        st.markdown("**Teknisk informasjon:**")
        st.caption("• Data oppdateres automatisk (standard: siste 24 timer)")
        st.caption("• Historisk data tilgjengelig fra 2018")
        st.caption("• Mellomlagring: 1 time for optimal ytelse")
        st.caption("• Datakilde: Meteorologisk institutt (Frost API)")
    
    with col_footer2:
        st.markdown("**Kildestasjon:**")
        st.caption(f"• Stasjon: {checker.station_id} (Gullingen Skisenter)")
        st.caption("• Høyde: ~400 moh")
    
    # Refresh-knapp for manuell oppdatering
    if st.button("Oppdater nå"):
        st.rerun()

if __name__ == "__main__":
    create_streamlit_app()
