#!/usr/bin/env python3
"""
FAKTISK profesjonell app - med ekte funktionalitet, ikke bare CSS-kosmetikk
"""

import os
import sys
import warnings
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

# Legg til project root i path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Suppress warnings
warnings.filterwarnings('ignore')
load_dotenv()

# Import EKTE moduler med substans
try:
    from src.live_conditions_app import LiveConditionsChecker
    LIVE_CONDITIONS_AVAILABLE = True
except ImportError:
    LIVE_CONDITIONS_AVAILABLE = False

try:
    from validert_glattfore_logikk import detect_precipitation_type
    VALIDATED_LOGIC_AVAILABLE = True
except ImportError:
    VALIDATED_LOGIC_AVAILABLE = False

try:
    from src.ml_snowdrift_detector import MLSnowdriftDetector
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

# Real configuration
FROST_CLIENT_ID = os.getenv('FROST_CLIENT_ID')
STATION_ID = "SN59300"  # Gullingen
API_BASE = "https://frost.met.no"


def configure_app():
    """Basic professional configuration - no BS"""
    st.set_page_config(
        page_title="Føreforhold Gullingen",
        page_icon="🏔️",
        layout="wide"
    )


def get_real_weather_data(hours_back: int = 6) -> Optional[pd.DataFrame]:
    """
    Hent EKTE værdata fra Met.no - bruker FUNGERENDE logikk fra live_conditions_app
    """
    if not FROST_CLIENT_ID:
        st.error("FROST_CLIENT_ID mangler i .env fil")
        return None
    
    try:
        # Bruk NØYAKTIG samme logikk som fungerer
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours_back)
        
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        start_iso = start_time.strftime(fmt)
        end_iso = end_time.strftime(fmt)
        
        # Bruk validerte elementer fra fungerende app
        elements = [
            'air_temperature',
            'wind_speed', 
            'surface_snow_thickness',
            'sum(precipitation_amount PT1H)',
            'relative_humidity',
            'wind_from_direction'
        ]
        
        url = 'https://frost.met.no/observations/v0.jsonld'
        parameters = {
            'sources': STATION_ID,
            'elements': ','.join(elements),
            'referencetime': f"{start_iso}/{end_iso}"
        }
        
        # NØYAKTIG samme request som fungerer
        response = requests.get(url, parameters, auth=(FROST_CLIENT_ID, ''), timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if not data.get('data'):
                st.warning("Ingen data mottatt fra API-et")
                return None
            
            # Parse NØYAKTIG som i fungerende app
            records = []
            for obs in data['data']:
                record = {'referenceTime': pd.to_datetime(obs['referenceTime'])}
                
                for observation in obs['observations']:
                    element = observation['elementId']
                    value = observation['value']
                    
                    # Map til standard navn
                    if element == 'air_temperature':
                        record['temperature'] = value
                    elif element == 'wind_speed':
                        record['wind_speed'] = value
                    elif element == 'surface_snow_thickness':
                        record['snow_depth'] = value
                    elif element == 'sum(precipitation_amount PT1H)':
                        record['precipitation'] = value
                    elif element == 'relative_humidity':
                        record['humidity'] = value
                    elif element == 'wind_from_direction':
                        record['wind_direction'] = value
                
                records.append(record)
            
            if not records:
                st.warning("Ingen gyldige observasjoner funnet")
                return None
            
            df = pd.DataFrame(records)
            df.set_index('referenceTime', inplace=True)
            return df
            
        else:
            st.error(f"API returned status {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed: {e}")
        return None


def analyze_real_snow_drift(df: pd.DataFrame) -> Dict[str, Any]:
    """
    EKTE snøfokk-analyse basert på reelle data
    """
    if df.empty:
        return {'risk': 'Unknown', 'reason': 'No data'}
    
    latest = df.iloc[-1]
    
    # Bruk ML-detektor hvis tilgjengelig
    if ML_AVAILABLE:
        try:
            detector = MLSnowdriftDetector()
            
            features = {
                'temperature': latest.get('temperature', 0),
                'wind_speed': latest.get('wind_speed', 0),
                'precipitation': latest.get('precipitation', 0),
                'snow_depth': latest.get('snow_depth', 0)
            }
            
            ml_result = detector.predict_snowdrift_risk(features)
            return {
                'risk': ml_result.get('risk_level', 'Unknown'),
                'confidence': ml_result.get('confidence', 0),
                'reason': 'ML-based prediction',
                'method': 'ML'
            }
        except Exception as e:
            pass
    
    # Fallback til tradisjonell logikk
    temp = latest.get('temperature', 0)
    wind = latest.get('wind_speed', 0)
    
    if temp <= -2 and wind >= 10:
        risk = 'High'
        reason = f"Temp: {temp:.1f}°C, Wind: {wind:.1f} m/s"
    elif temp <= 0 and wind >= 7:
        risk = 'Medium'
        reason = f"Temp: {temp:.1f}°C, Wind: {wind:.1f} m/s"
    else:
        risk = 'Low'
        reason = f"Temp: {temp:.1f}°C, Wind: {wind:.1f} m/s"
    
    return {
        'risk': risk,
        'reason': reason,
        'method': 'Traditional'
    }


def analyze_real_ice_risk(df: pd.DataFrame) -> Dict[str, Any]:
    """
    EKTE glattføre-analyse med validert logikk
    """
    if df.empty:
        return {'risk': 'Unknown', 'type': 'No data'}
    
    latest = df.iloc[-1]
    temp = latest.get('temperature', 0)
    precip = latest.get('precipitation', 0)
    
    if VALIDATED_LOGIC_AVAILABLE and precip > 0:
        try:
            precip_type, confidence = detect_precipitation_type(temp, precip)
            
            if precip_type == 'rain' and temp <= 2:
                return {
                    'risk': 'High',
                    'type': f'Rain at {temp:.1f}°C',
                    'confidence': confidence,
                    'method': 'Validated logic'
                }
            elif precip_type == 'sleet':
                return {
                    'risk': 'Medium', 
                    'type': f'Sleet at {temp:.1f}°C',
                    'confidence': confidence,
                    'method': 'Validated logic'
                }
            else:
                return {
                    'risk': 'Low',
                    'type': f'{precip_type} at {temp:.1f}°C',
                    'confidence': confidence,
                    'method': 'Validated logic'
                }
        except Exception as e:
            pass
    
    # Fallback til enkel logikk
    if temp <= 2 and temp >= -1 and precip > 0:
        return {
            'risk': 'Medium',
            'type': f'Precipitation at {temp:.1f}°C',
            'method': 'Simple logic'
        }
    
    return {
        'risk': 'Low',
        'type': f'No ice risk (temp: {temp:.1f}°C)',
        'method': 'Simple logic'
    }


def display_real_metrics(df: pd.DataFrame):
    """
    Vis EKTE metrikker fra EKTE data - ikke dummy verdier
    """
    if df.empty:
        st.error("Ingen data tilgjengelig")
        return
    
    latest = df.iloc[-1]
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        temp = latest.get('temperature')
        if temp is not None:
            st.metric("Temperatur", f"{temp:.1f}°C")
        else:
            st.metric("Temperatur", "N/A")
    
    with col2:
        wind = latest.get('wind_speed')
        if wind is not None:
            st.metric("Vindstyrke", f"{wind:.1f} m/s")
        else:
            st.metric("Vindstyrke", "N/A")
    
    with col3:
        snow_drift = analyze_real_snow_drift(df)
        st.metric("Snøfokk risiko", snow_drift['risk'])
    
    with col4:
        ice_risk = analyze_real_ice_risk(df)
        st.metric("Glattføre risiko", ice_risk['risk'])


def display_real_analysis(df: pd.DataFrame):
    """
    Vis EKTE analyse av EKTE data
    """
    st.subheader("Detaljert analyse")
    
    if df.empty:
        st.warning("Ingen data å analysere")
        return
    
    # Snøfokk analyse
    with st.expander("🌨️ Snøfokk analyse", expanded=True):
        snow_analysis = analyze_real_snow_drift(df)
        
        risk_color = {
            'High': 'red',
            'Medium': 'orange', 
            'Low': 'green'
        }.get(snow_analysis['risk'], 'gray')
        
        st.markdown(f"**Risiko:** :{risk_color}[{snow_analysis['risk']}]")
        st.write(f"**Årsak:** {snow_analysis['reason']}")
        st.write(f"**Metode:** {snow_analysis['method']}")
        
        if 'confidence' in snow_analysis:
            st.write(f"**Konfidans:** {snow_analysis['confidence']:.1%}")
    
    # Glattføre analyse
    with st.expander("🧊 Glattføre analyse", expanded=True):
        ice_analysis = analyze_real_ice_risk(df)
        
        risk_color = {
            'High': 'red',
            'Medium': 'orange',
            'Low': 'green'
        }.get(ice_analysis['risk'], 'gray')
        
        st.markdown(f"**Risiko:** :{risk_color}[{ice_analysis['risk']}]")
        st.write(f"**Type:** {ice_analysis['type']}")
        st.write(f"**Metode:** {ice_analysis['method']}")
        
        if 'confidence' in ice_analysis:
            st.write(f"**Konfidans:** {ice_analysis['confidence']}")
    
    # Data kvalitet
    with st.expander("📊 Data kvalitet"):
        st.write(f"**Antall målinger:** {len(df)}")
        st.write(f"**Siste måling:** {df.index[-1].strftime('%Y-%m-%d %H:%M')}")
        
        # Vis tilgjengelige kolonner
        available_cols = [col for col in df.columns if not df[col].isna().all()]
        st.write(f"**Tilgjengelige data:** {', '.join(available_cols)}")
        
        # Vis rå data
        if st.checkbox("Vis rå data"):
            st.dataframe(df.tail(10))


def show_system_status():
    """
    Vis FAKTISK system status - ikke dummy indicators
    """
    with st.sidebar:
        st.subheader("System Status")
        
        # API test
        if FROST_CLIENT_ID:
            st.success("✅ API konfigurert")
        else:
            st.error("❌ API ikke konfigurert")
            st.info("Legg til FROST_CLIENT_ID i .env fil")
        
        # Module status
        modules = [
            ("Live Conditions", LIVE_CONDITIONS_AVAILABLE),
            ("Validated Logic", VALIDATED_LOGIC_AVAILABLE), 
            ("ML Detection", ML_AVAILABLE)
        ]
        
        for name, available in modules:
            if available:
                st.success(f"✅ {name}")
            else:
                st.warning(f"⚠️ {name} ikke tilgjengelig")


def main():
    """
    EKTE profesjonell app - substans over stil
    """
    configure_app()
    
    st.title("🏔️ Føreforhold Gullingen")
    st.caption("Faktisk analyse basert på reelle værdata")
    
    show_system_status()
    
    # Hent EKTE data
    with st.spinner("Henter værdata..."):
        df = get_real_weather_data(hours_back=6)
    
    if df is not None and not df.empty:
        st.success(f"✅ Hentet {len(df)} målinger")
        
        # Vis EKTE metrikker
        display_real_metrics(df)
        
        # Vis EKTE analyse
        display_real_analysis(df)
        
    else:
        st.error("❌ Kunne ikke hente værdata")
        
        if not FROST_CLIENT_ID:
            st.info("""
            **For å få ekte data:**
            1. Registrer deg på frost.met.no
            2. Få en client ID
            3. Legg til FROST_CLIENT_ID=din_id i .env fil
            """)
        
        # Vis i det minste tilgjengelige moduler
        st.subheader("Tilgjengelige moduler")
        
        if LIVE_CONDITIONS_AVAILABLE:
            st.info("✅ Live conditions checker er tilgjengelig")
        if VALIDATED_LOGIC_AVAILABLE:
            st.info("✅ Validert glattføre-logikk er tilgjengelig")
        if ML_AVAILABLE:
            st.info("✅ ML snøfokk-detektor er tilgjengelig")


if __name__ == "__main__":
    main()
