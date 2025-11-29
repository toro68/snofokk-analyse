#!/usr/bin/env python3
"""
MOBIL-FIRST Værapp for Gullingen Skisenter
Prioritering: Nysnø, Glatte veier og Snøfokk

Komplett mobil-optimalisert versjon med all eksisterende funksjonalitet beholdt.
"""

import os
import sys
import warnings
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
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

# Import eksisterende komponenter hvis tilgjengelig
try:
    from src.components.mobile_layout import MobileLayout
    from src.components.weather_utils import (
        simple_snowdrift_analysis, simple_slippery_analysis,
        calculate_wind_chill, validate_weather_data
    )
    COMPONENTS_AVAILABLE = True
except ImportError:
    COMPONENTS_AVAILABLE = False

# Import eksisterende logikk
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

# API konfigurasjon
FROST_CLIENT_ID = os.getenv('FROST_CLIENT_ID')
STATION_ID = os.getenv("WEATHER_STATION", "SN46220")  # Gullingen - samme som andre apper
API_BASE = "https://frost.met.no"

# Konstanter for å redusere duplisering
NO_DATA_MESSAGE = 'Ingen data'
FACTORS_LABEL = "Faktorer:"
ANALYSIS_ERROR_PREFIX = 'Feil i analyse: '
BASIC_ANALYSIS_SOURCE = 'Grunnleggende analyse'


class MobileFirstWeatherApp:
    """
    Mobil-first værapp med prioritet på:
    1. Nysnø
    2. Glatte veier  
    3. Snøfokk
    """
    
    def __init__(self):
        self.frost_client_id = FROST_CLIENT_ID
        self.station_id = STATION_ID
        
        # ML-detektor hvis tilgjengelig
        self.ml_detector = None
        if ML_AVAILABLE:
            try:
                self.ml_detector = MLSnowdriftDetector()
            except Exception:
                pass
    
    def configure_mobile_page(self):
        """Konfigurer siden for mobil-first design"""
        st.set_page_config(
            page_title="❄️ Gullingen Værvarsel",
            page_icon="❄️",
            layout="wide",
            initial_sidebar_state="collapsed",
            menu_items={
                'Get Help': 'https://github.com/toro68/snofokk-analyse',
                'About': """
                # ❄️ Gullingen Skisenter - Værvarsel
                
                **Mobil-first app for operative beslutninger**
                
                **Prioritet:**
                - 🆕 Nysnø
                - 🧊 Glatte veier  
                - 🌪️ Snøfokk
                
                Data fra Meteorologisk institutt
                """
            }
        )
        
        # Mobil-optimalisert CSS
        st.markdown("""
        <style>
        /* MOBIL-FIRST DESIGN */
        
        /* PWA Mode - skjul Streamlit UI når installert som app */
        @media (display-mode: standalone) {
            header[data-testid="stHeader"] {
                display: none !important;
            }
            .main .block-container {
                padding-top: 0.5rem;
            }
        }
        
        /* Hovedlayout - mobile first */
        .main .block-container {
            padding: 0.5rem;
            max-width: 100%;
        }
        
        /* Prioriterte værforhold - store kort */
        .priority-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px;
            padding: 1.5rem;
            margin: 0.75rem 0;
            color: white;
            text-align: center;
            box-shadow: 0 8px 16px rgba(0,0,0,0.15);
            border: 3px solid transparent;
            transition: all 0.3s ease;
            min-height: 120px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        
        .priority-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 24px rgba(0,0,0,0.2);
        }
        
        /* Prioriterte risikokort - fargekoding */
        .priority-high {
            background: linear-gradient(135deg, #ff4757 0%, #c44569 100%);
            border-color: #ff3742;
            animation: pulse-red 2s infinite;
        }
        
        .priority-medium {
            background: linear-gradient(135deg, #ffa502 0%, #ff6348 100%);
            border-color: #ff9ff3;
            color: #2d3436;
        }
        
        .priority-low {
            background: linear-gradient(135deg, #26de81 0%, #20bf6b 100%);
            border-color: #1dd1a1;
        }
        
        .priority-unknown {
            background: linear-gradient(135deg, #747d8c 0%, #57606f 100%);
            border-color: #5f27cd;
        }
        
        /* Pulserende animasjon for høy risiko */
        @keyframes pulse-red {
            0% { box-shadow: 0 8px 16px rgba(255,71,87,0.3); }
            50% { box-shadow: 0 8px 24px rgba(255,71,87,0.6); }
            100% { box-shadow: 0 8px 16px rgba(255,71,87,0.3); }
        }
        
        /* Kompakte metrikker */
        .metric-mini {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 0.75rem;
            margin: 0.25rem;
            text-align: center;
            border: 2px solid #e9ecef;
            min-height: 80px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        
        .metric-value {
            font-size: 1.8rem;
            font-weight: bold;
            color: #2d3436;
            line-height: 1;
        }
        
        .metric-label {
            font-size: 0.75rem;
            color: #636e72;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 0.25rem;
        }
        
        /* Alert banners */
        .alert-banner {
            background: linear-gradient(90deg, #ff4757, #ff6b7d);
            color: white;
            padding: 1rem;
            border-radius: 12px;
            margin: 1rem 0;
            text-align: center;
            font-weight: bold;
            animation: pulse-alert 1.5s infinite;
        }
        
        @keyframes pulse-alert {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.8; }
        }
        
        /* Responsive grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 0.5rem;
            margin: 1rem 0;
        }
        
        /* Status indikatorer */
        .status-dot {
            display: inline-block;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            margin-right: 8px;
            border: 2px solid white;
        }
        
        .status-high { background: #ff4757; }
        .status-medium { background: #ffa502; }
        .status-low { background: #26de81; }
        .status-unknown { background: #747d8c; }
        
        /* Knapper */
        .stButton > button {
            width: 100%;
            border-radius: 12px;
            border: none;
            padding: 0.75rem 1.5rem;
            font-weight: 600;
            font-size: 1rem;
            transition: all 0.3s ease;
        }
        
        /* Skjul unødvendige elementer på mobil */
        @media (max-width: 768px) {
            .main .block-container {
                padding: 0.25rem;
            }
            
            h1 { font-size: 1.5rem !important; }
            h2 { font-size: 1.25rem !important; }
            h3 { font-size: 1.1rem !important; }
            
            .priority-card {
                margin: 0.5rem 0;
                padding: 1rem;
                min-height: 100px;
            }
            
            .metric-value { font-size: 1.5rem; }
        }
        
        /* Footer */
        .mobile-footer {
            text-align: center;
            color: #636e72;
            font-size: 0.8rem;
            margin-top: 2rem;
            padding: 1rem;
            border-top: 1px solid #e9ecef;
        }
        
        /* Loading skeletons */
        .skeleton {
            background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite;
            border-radius: 8px;
        }
        
        @keyframes shimmer {
            0% { background-position: -200% 0; }
            100% { background-position: 200% 0; }
        }
        
        .skeleton-card {
            height: 120px;
            margin: 0.75rem 0;
        }
        </style>
        """, unsafe_allow_html=True)

    def get_weather_data(self, hours_back: int = 24) -> Optional[pd.DataFrame]:
        """Hent værdata fra Frost API"""
        if not self.frost_client_id:
            return None
        
        try:
            parameters = self._build_api_parameters(hours_back)
            response = self._make_api_request(parameters)
            
            if response and response.status_code == 200:
                return self._parse_weather_response(response.json())
            else:
                return None
                
        except Exception as e:
            st.error(f"Feil ved henting av værdata: {e}")
            return None
    
    def _build_api_parameters(self, hours_back: int) -> Dict[str, str]:
        """Bygg API-parametere"""
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours_back)
        
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        start_iso = start_time.strftime(fmt)
        end_iso = end_time.strftime(fmt)
        
        # Prioriterte elementer for mobil app
        elements = [
            'air_temperature',
            'wind_speed',
            'wind_from_direction', 
            'surface_snow_thickness',
            'sum(precipitation_amount PT1H)',
            'sum(precipitation_amount PT6H)',
            'surface_temperature',
            'relative_humidity'
        ]
        
        return {
            'sources': self.station_id,
            'elements': ','.join(elements),
            'referencetime': f"{start_iso}/{end_iso}"
        }
    
    def _make_api_request(self, parameters: Dict[str, str]):
        """Gjør API-forespørsel"""
        url = 'https://frost.met.no/observations/v0.jsonld'
        return requests.get(url, parameters, auth=(self.frost_client_id, ''), timeout=30)
    
    def _parse_weather_response(self, data: Dict) -> Optional[pd.DataFrame]:
        """Parse værdata-respons"""
        if not data.get('data'):
            return None
        
        records = []
        for obs in data['data']:
            record = {'time': pd.to_datetime(obs['referenceTime'])}
            
            for observation in obs['observations']:
                element = observation['elementId']
                value = observation['value']
                
                # Map til standardnavn
                record.update(self._map_element_name(element, value))
        
            records.append(record)
        
        if not records:
            return None
        
        df = pd.DataFrame(records)
        return df.sort_values('time').reset_index(drop=True)
    
    def _map_element_name(self, element: str, value: float) -> Dict[str, float]:
        """Map elementnavn til standardnavn"""
        mapping = {
            'air_temperature': 'temperature',
            'wind_speed': 'wind_speed',
            'surface_snow_thickness': 'snow_depth',
            'sum(precipitation_amount PT1H)': 'precipitation_1h',
            'sum(precipitation_amount PT6H)': 'precipitation_6h',
            'relative_humidity': 'humidity',
            'wind_from_direction': 'wind_direction',
            'surface_temperature': 'surface_temperature'
        }
        
        mapped_name = mapping.get(element, element)
        return {mapped_name: value}

    def analyze_fresh_snow(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyser nysnø - FØRSTE prioritet"""
        if df.empty:
            return self._create_error_result(NO_DATA_MESSAGE, 0)
        
        try:
            latest = df.iloc[-1]
            precip_6h = latest.get('precipitation_6h', 0) or 0
            temp = latest.get('temperature', 0)
            
            factors = []
            
            # Beregn nysnø basert på temperatur og nedbør
            if pd.notna(temp) and temp <= 1:  # Snøtemperatur
                return self._analyze_snow_precipitation(temp, precip_6h, factors)
            else:
                return self._analyze_rain_conditions(temp, precip_6h, factors)
            
        except Exception as e:
            return self._create_error_result(f'{ANALYSIS_ERROR_PREFIX}{str(e)[:50]}', 0)
    
    def _analyze_snow_precipitation(self, temp: float, precip_6h: float, factors: List[str]) -> Dict[str, Any]:
        """Analyser snønedbør"""
        factors.append(f"Nedbør siste 6t: {precip_6h:.1f}mm")
        factors.append(f"Temperatur: {temp:.1f}°C")
        
        if precip_6h >= 10:
            return {
                'risk_level': 'high',
                'amount': precip_6h,
                'message': f'Mye nysnø: ~{precip_6h:.0f}cm',
                'confidence': 0.9,
                'factors': factors
            }
        elif precip_6h >= 5:
            return {
                'risk_level': 'medium',
                'amount': precip_6h,
                'message': f'Moderat nysnø: ~{precip_6h:.0f}cm',
                'confidence': 0.8,
                'factors': factors
            }
        elif precip_6h >= 1:
            return {
                'risk_level': 'low',
                'amount': precip_6h,
                'message': f'Litt nysnø: ~{precip_6h:.0f}cm',
                'confidence': 0.7,
                'factors': factors
            }
        else:
            factors.append("Ingen nedbør registrert")
            return {
                'risk_level': 'low',
                'amount': precip_6h,
                'message': 'Ingen nysnø',
                'confidence': 0.8,
                'factors': factors
            }
    
    def _analyze_rain_conditions(self, temp: float, precip_6h: float, factors: List[str]) -> Dict[str, Any]:
        """Analyser regnforhold"""
        if precip_6h > 0:
            factors.append(f"For varmt for snø: {temp:.1f}°C")
            return {
                'risk_level': 'low',
                'amount': precip_6h,
                'message': f'Regn ({temp:.1f}°C) - ikke snø',
                'confidence': 0.8,
                'factors': factors
            }
        else:
            factors.append("Ingen nedbør registrert")
            return {
                'risk_level': 'low',
                'amount': precip_6h,
                'message': 'Ingen nedbør',
                'confidence': 0.8,
                'factors': factors
            }
    
    def _create_error_result(self, message: str, amount: float) -> Dict[str, Any]:
        """Hjelpefunksjon for å lage feilresultat"""
        return {
            'risk_level': 'unknown',
            'amount': amount,
            'message': message,
            'confidence': 0.0,
            'factors': ['Analysefeil'] if 'Feil' in message else [message]
        }

    def analyze_slippery_conditions(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyser glatte veier - ANDRE prioritet"""
        if df.empty:
            return {
                'risk_level': 'unknown',
                'message': NO_DATA_MESSAGE,
                'confidence': 0.0,
                'factors': []
            }
        
        try:
            latest = df.iloc[-1]
            temp = latest.get('temperature', None)
            surface_temp = latest.get('surface_temperature', None)
            humidity = latest.get('humidity', None)
            precip_1h = latest.get('precipitation_1h', 0) or 0
            
            # Bruk overflatetemperatur hvis tilgjengelig
            analysis_temp = surface_temp if pd.notna(surface_temp) else temp
            
            if pd.isna(analysis_temp):
                return {
                    'risk_level': 'unknown',
                    'message': 'Mangler temperaturdata',
                    'confidence': 0.0,
                    'factors': ['Ingen temperaturdata']
                }
            
            return self._evaluate_slippery_risk(analysis_temp, humidity, precip_1h, temp, surface_temp)
            
        except Exception as e:
            return {
                'risk_level': 'unknown',
                'message': f'{ANALYSIS_ERROR_PREFIX}{str(e)[:50]}',
                'confidence': 0.0,
                'factors': ['Analysefeil']
            }
    
    def _evaluate_slippery_risk(self, analysis_temp: float, humidity: Optional[float], 
                               precip_1h: float, temp: Optional[float], surface_temp: Optional[float]) -> Dict[str, Any]:
        """Evaluer glattføre-risiko basert på parametere"""
        factors = []
        
        # Kritisk temperaturområde for glattføre
        if -3 <= analysis_temp <= 3:
            return self._analyze_critical_temperature(analysis_temp, humidity, precip_1h, factors)
        elif analysis_temp < -10:
            return self._analyze_stable_cold(analysis_temp, factors)
        elif analysis_temp > 8:
            return self._analyze_warm_conditions(analysis_temp, factors)
        else:
            return self._analyze_moderate_conditions(analysis_temp, factors, temp, surface_temp)
    
    def _analyze_critical_temperature(self, analysis_temp: float, humidity: Optional[float], 
                                    precip_1h: float, factors: List[str]) -> Dict[str, Any]:
        """Analyser kritiske temperaturforhold"""
        factors.append(f"Kritisk temperatur: {analysis_temp:.1f}°C")
        
        # Sjekk for undervann/rim
        if pd.notna(humidity) and humidity > 90:
            factors.append(f"Meget høy luftfuktighet: {humidity:.0f}%")
            return {
                'risk_level': 'high',
                'message': 'Høy risiko - rim/undervann',
                'confidence': 0.9,
                'factors': factors
            }
        
        # Sjekk for regn på kald vei
        elif precip_1h > 0 and analysis_temp <= 2:
            factors.append(f"Nedbør siste time: {precip_1h:.1f}mm")
            return {
                'risk_level': 'high',
                'message': 'Høy risiko - regn på kald vei',
                'confidence': 0.95,
                'factors': factors
            }
        
        # Moderat risiko
        elif pd.notna(humidity) and humidity > 80:
            factors.append(f"Høy luftfuktighet: {humidity:.0f}%")
            return {
                'risk_level': 'medium',
                'message': 'Moderat risiko for glattføre',
                'confidence': 0.7,
                'factors': factors
            }
        
        else:
            factors.append("Grensetemperatur for glattføre")
            return {
                'risk_level': 'medium',
                'message': 'Temperatur i risikoområde',
                'confidence': 0.6,
                'factors': factors
            }
    
    def _analyze_stable_cold(self, analysis_temp: float, factors: List[str]) -> Dict[str, Any]:
        """Analyser stabile kalde forhold"""
        factors.append(f"Stabilt kaldt: {analysis_temp:.1f}°C")
        return {
            'risk_level': 'low',
            'message': 'Stabilt kaldt - godt føre',
            'confidence': 0.9,
            'factors': factors
        }
    
    def _analyze_warm_conditions(self, analysis_temp: float, factors: List[str]) -> Dict[str, Any]:
        """Analyser varme forhold"""
        factors.append(f"Varmt: {analysis_temp:.1f}°C")
        return {
            'risk_level': 'low',
            'message': 'For varmt for glattføre',
            'confidence': 0.9,
            'factors': factors
        }
    
    def _analyze_moderate_conditions(self, analysis_temp: float, factors: List[str],
                                   temp: Optional[float], surface_temp: Optional[float]) -> Dict[str, Any]:
        """Analyser moderate temperaturforhold"""
        factors.append(f"Moderat temperatur: {analysis_temp:.1f}°C")
        
        # Legg til sammenligning av overflate vs luft
        if pd.notna(surface_temp) and pd.notna(temp):
            diff = abs(surface_temp - temp)
            if diff > 3:
                factors.append(f"Stor forskjell luft/vei: {diff:.1f}°C")
        
        return {
            'risk_level': 'low',
            'message': 'Lav risiko for glattføre',
            'confidence': 0.7,
            'factors': factors
        }

    def analyze_snowdrift_risk(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyser snøfokk - TREDJE prioritet"""
        if df.empty:
            return {
                'risk_level': 'unknown',
                'message': NO_DATA_MESSAGE,
                'confidence': 0.0,
                'factors': []
            }
        
        try:
            latest = df.iloc[-1]
            temp = latest.get('temperature', None)
            wind = latest.get('wind_speed', None)
            snow_depth = latest.get('snow_depth', None)
            
            # Bruk ML hvis tilgjengelig
            if self.ml_detector and pd.notna(temp) and pd.notna(wind):
                ml_result = self._try_ml_analysis(temp, wind, snow_depth)
                if ml_result:
                    return ml_result
            
            # Fallback til enkel analyse
            return self._simple_snowdrift_analysis(temp, wind, snow_depth)
            
        except Exception as e:
            return {
                'risk_level': 'unknown',
                'message': f'{ANALYSIS_ERROR_PREFIX}{str(e)[:50]}',
                'confidence': 0.0,
                'factors': ['Analysefeil']
            }
    
    def _try_ml_analysis(self, temp: float, wind: float, snow_depth: Optional[float]) -> Optional[Dict[str, Any]]:
        """Forsøk ML-analyse"""
        try:
            features = {
                'wind_speed': wind,
                'air_temperature': temp,
                'snow_depth': snow_depth if pd.notna(snow_depth) and snow_depth >= 0 else 0
            }
            
            ml_result = self.ml_detector.predict_snowdrift_risk(features)
            ml_result['source'] = 'ML-analyse'
            return ml_result
        except Exception:
            return None
    
    def _simple_snowdrift_analysis(self, temp: Optional[float], wind: Optional[float], 
                                  snow_depth: Optional[float]) -> Dict[str, Any]:
        """Enkel snøfokk-analyse"""
        if pd.isna(temp) or pd.isna(wind):
            return {
                'risk_level': 'unknown',
                'message': 'Mangler værdata',
                'confidence': 0.0,
                'factors': ['Mangler temperatur eller vinddata']
            }
        
        # Bruk eksisterende komponentlogikk hvis tilgjengelig
        if COMPONENTS_AVAILABLE:
            result = simple_snowdrift_analysis(temp, wind, snow_depth)
            result['source'] = 'Enkel analyse'
            return result
        
        # Manuell grunnleggende analyse
        return self._basic_snowdrift_analysis(temp, wind)
    
    def _basic_snowdrift_analysis(self, temp: float, wind: float) -> Dict[str, Any]:
        """Grunnleggende snøfokk-analyse"""
        factors = [f"Temperatur: {temp:.1f}°C", f"Vind: {wind:.1f} m/s"]
        
        if temp <= -5 and wind >= 12:
            return {
                'risk_level': 'high',
                'message': 'Høy snøfokk-risiko',
                'confidence': 0.8,
                'factors': factors,
                'source': BASIC_ANALYSIS_SOURCE
            }
        elif temp <= -2 and wind >= 8:
            return {
                'risk_level': 'medium',
                'message': 'Moderat snøfokk-risiko',
                'confidence': 0.7,
                'factors': factors,
                'source': BASIC_ANALYSIS_SOURCE
            }
        else:
            return {
                'risk_level': 'low',
                'message': 'Lav snøfokk-risiko',
                'confidence': 0.6,
                'factors': factors,
                'source': BASIC_ANALYSIS_SOURCE
            }

    def show_priority_alerts(self, snow_analysis: Dict, slippery_analysis: Dict, snowdrift_analysis: Dict):
        """Vis prioriterte varsler"""
        
        # Samle høy-risiko forhold
        high_risks = []
        if snow_analysis['risk_level'] == 'high':
            high_risks.append(f"🆕 NYSNØ: {snow_analysis['message']}")
        if slippery_analysis['risk_level'] == 'high':
            high_risks.append(f"🧊 GLATTFØRE: {slippery_analysis['message']}")
        if snowdrift_analysis['risk_level'] == 'high':
            high_risks.append(f"🌪️ SNØFOKK: {snowdrift_analysis['message']}")
        
        # Vis alert banner hvis høy risiko
        if high_risks:
            st.markdown(f"""
            <div class="alert-banner">
                🚨 VÆRALERT 🚨<br>
                {' • '.join(high_risks)}
            </div>
            """, unsafe_allow_html=True)

    def show_priority_cards(self, snow_analysis: Dict, slippery_analysis: Dict, snowdrift_analysis: Dict):
        """Vis prioriterte værkort"""
        
        # Prioritet 1: Nysnø
        self.show_priority_card(
            title="🆕 NYSNØ",
            analysis=snow_analysis,
            priority=1
        )
        
        # Prioritet 2: Glatte veier  
        self.show_priority_card(
            title="🧊 GLATTE VEIER",
            analysis=slippery_analysis,
            priority=2
        )
        
        # Prioritet 3: Snøfokk
        self.show_priority_card(
            title="🌪️ SNØFOKK",
            analysis=snowdrift_analysis,
            priority=3
        )

    def show_priority_card(self, title: str, analysis: Dict, priority: int):
        """Vis enkelt prioriteringskort"""
        risk_level = analysis.get('risk_level', 'unknown')
        message = analysis.get('message', 'Ukjent status')
        confidence = analysis.get('confidence', 0.0)
        
        # CSS-klasse basert på risiko
        css_class = f"priority-{risk_level}"
        
        # Status-indikator
        status_dot = f'<span class="status-dot status-{risk_level}"></span>'
        
        st.markdown(f"""
        <div class="priority-card {css_class}">
            <h2 style="margin: 0; font-size: 1.3rem;">
                {status_dot}{title}
            </h2>
            <div style="margin: 0.75rem 0;">
                <div style="font-size: 1.1rem; font-weight: bold;">
                    {message}
                </div>
                <div style="font-size: 0.9rem; margin-top: 0.5rem; opacity: 0.9;">
                    Tillit: {confidence:.0%} • Prioritet #{priority}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    def show_current_metrics(self, df: pd.DataFrame):
        """Vis nåværende målinger i kompakt format"""
        if df.empty:
            st.warning("Ingen værdata tilgjengelig")
            return
        
        latest = df.iloc[-1]
        
        st.markdown("### 📊 Nåværende forhold")
        
        # Responsive grid for metrikker
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            temp = latest.get('temperature', None)
            if pd.notna(temp):
                st.markdown(f"""
                <div class="metric-mini">
                    <div class="metric-value">{temp:.1f}°</div>
                    <div class="metric-label">Luft</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-mini">
                    <div class="metric-value">-</div>
                    <div class="metric-label">Luft</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            wind = latest.get('wind_speed', None)
            if pd.notna(wind):
                st.markdown(f"""
                <div class="metric-mini">
                    <div class="metric-value">{wind:.1f}</div>
                    <div class="metric-label">Vind m/s</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-mini">
                    <div class="metric-value">-</div>
                    <div class="metric-label">Vind m/s</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col3:
            snow = latest.get('snow_depth', None)
            if pd.notna(snow) and snow >= 0:
                snow_cm = snow * 100 if snow < 10 else snow
                st.markdown(f"""
                <div class="metric-mini">
                    <div class="metric-value">{snow_cm:.0f}</div>
                    <div class="metric-label">Snø cm</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-mini">
                    <div class="metric-value">-</div>
                    <div class="metric-label">Snø cm</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col4:
            precip = latest.get('precipitation_1h', None)
            if pd.notna(precip):
                st.markdown(f"""
                <div class="metric-mini">
                    <div class="metric-value">{precip:.1f}</div>
                    <div class="metric-label">Nedbør mm</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-mini">
                    <div class="metric-value">-</div>
                    <div class="metric-label">Nedbør mm</div>
                </div>
                """, unsafe_allow_html=True)

    def show_detailed_info(self, df: pd.DataFrame, analyses: Dict):
        """Vis detaljert informasjon i ekspandbare seksjoner"""
        
        # Chart
        st.markdown("---")
        st.markdown("### 📈 Værtrend")
        
        if not df.empty and 'time' in df.columns:
            chart_type = st.selectbox(
                "Velg data:",
                ["🌡️ Temperatur", "💨 Vind", "❄️ Snø", "🌧️ Nedbør"],
                key="chart_selector"
            )
            
            if chart_type == "🌡️ Temperatur" and 'temperature' in df.columns:
                st.line_chart(df.set_index('time')['temperature'], height=300)
            elif chart_type == "💨 Vind" and 'wind_speed' in df.columns:
                st.line_chart(df.set_index('time')['wind_speed'], height=300)
            elif chart_type == "❄️ Snø" and 'snow_depth' in df.columns:
                # Rens snødata
                snow_data = df['snow_depth'].where(df['snow_depth'] >= 0)
                st.line_chart(df.set_index('time')[snow_data.name], height=300)
            elif chart_type == "🌧️ Nedbør" and 'precipitation_1h' in df.columns:
                st.bar_chart(df.set_index('time')['precipitation_1h'], height=300)
        
        # Detaljerte analyser
        with st.expander("🔍 Detaljerte analyser", expanded=False):
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**🆕 Nysnø-detaljer:**")
                snow_analysis = analyses['snow']
                st.write(f"Status: {snow_analysis['message']}")
                st.write(f"Mengde: {snow_analysis.get('amount', 0):.1f}mm")
                st.write(f"Tillit: {snow_analysis['confidence']:.0%}")
                
                if snow_analysis.get('factors'):
                    st.caption("Faktorer:")
                    for factor in snow_analysis['factors'][:3]:
                        st.caption(f"• {factor}")
            
            with col2:
                st.markdown("**🧊 Glattføre-detaljer:**")
                slippery_analysis = analyses['slippery']
                st.write(f"Status: {slippery_analysis['message']}")
                st.write(f"Tillit: {slippery_analysis['confidence']:.0%}")
                
                if slippery_analysis.get('factors'):
                    st.caption("Faktorer:")
                    for factor in slippery_analysis['factors'][:3]:
                        st.caption(f"• {factor}")
            
            with col3:
                st.markdown("**🌪️ Snøfokk-detaljer:**")
                snowdrift_analysis = analyses['snowdrift']
                st.write(f"Status: {snowdrift_analysis['message']}")
                st.write(f"Tillit: {snowdrift_analysis['confidence']:.0%}")
                
                if snowdrift_analysis.get('factors'):
                    st.caption("Faktorer:")
                    for factor in snowdrift_analysis['factors'][:3]:
                        st.caption(f"• {factor}")
        
        # Kriterier og info
        with st.expander("ℹ️ Analysekriterier", expanded=False):
            st.markdown("""
            **🆕 Nysnø-kriterier:**
            - Nedbør siste 6t + temperatur ≤ 1°C
            - Høy: ≥10mm, Moderat: ≥5mm, Lav: ≥1mm
            
            **🧊 Glattføre-kriterier:**
            - Temperatur: -3°C til +3°C (kritisk område)
            - Høy fuktighet: >90%, Nedbør på kald vei
            
            **🌪️ Snøfokk-kriterier:**
            - Temperatur: ≤-2°C, Vind: ≥8 m/s
            - Tilgjengelig løssnø
            """)

    def show_mobile_footer(self):
        """Mobil-tilpasset footer"""
        st.markdown("""
        <div class="mobile-footer">
            <strong>❄️ Gullingen Skisenter Værvarsel</strong><br>
            📡 Data: Meteorologisk institutt • 🏔️ Stasjon: {station} (639 moh)<br>
            📱 Mobil-first design • ⚡ Sanntidsdata<br>
            <small>Sist oppdatert: {timestamp}</small>
        </div>
        """.format(
            station=self.station_id,
            timestamp=datetime.now().strftime("%H:%M")
        ), unsafe_allow_html=True)

    def run_mobile_app(self):
        """Kjør mobil-first appen"""
        
        # Konfigurer mobil layout
        self.configure_mobile_page()
        
        # Header
        st.markdown("""
        <div style="text-align: center; margin-bottom: 1.5rem;">
            <h1 style="margin: 0; color: #2d3436;">❄️ Gullingen Værvarsel</h1>
        </div>
        """, unsafe_allow_html=True)
        
        # Sjekk API-konfigurering
        if not self.frost_client_id:
            st.error("⚠️ FROST_CLIENT_ID mangler i .env-filen")
            st.info("""
            **For å bruke appen:**
            1. Registrer deg på frost.met.no
            2. Få en client ID  
            3. Legg til FROST_CLIENT_ID=din_id i .env fil
            """)
            return
        
        # Vis loading
        with st.spinner("📡 Henter værdata..."):
            df = self.get_weather_data(24)
        
        if df is None or df.empty:
            st.error("❌ Kunne ikke hente værdata")
            st.info("Sjekk internettforbindelse og API-nøkkel")
            return
        
        # Valider datakvalitet
        if COMPONENTS_AVAILABLE:
            validation = validate_weather_data(df)
            if not validation['valid']:
                st.error("❌ Datakvalitet for dårlig for pålitelig analyse")
                return
            
            if validation['score'] < 80:
                st.warning(f"⚠️ Datakvalitet: {validation['score']:.0f}%")
        
        # Analyser alle prioriterte forhold
        with st.spinner("🔍 Analyserer værforhold..."):
            snow_analysis = self.analyze_fresh_snow(df)
            slippery_analysis = self.analyze_slippery_conditions(df)
            snowdrift_analysis = self.analyze_snowdrift_risk(df)
        
        analyses = {
            'snow': snow_analysis,
            'slippery': slippery_analysis, 
            'snowdrift': snowdrift_analysis
        }
        
        # Vis prioriterte varsler
        self.show_priority_alerts(snow_analysis, slippery_analysis, snowdrift_analysis)
        
        # Vis prioriterte kort
        self.show_priority_cards(snow_analysis, slippery_analysis, snowdrift_analysis)
        
        # Vis nåværende målinger
        self.show_current_metrics(df)
        
        # Kontroller
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            hours_back = st.selectbox(
                "📅 Tidsperiode:",
                options=[6, 12, 24, 48, 72],
                index=2,
                key="time_selector"
            )
        
        with col2:
            if st.button("🔄 Oppdater", type="primary"):
                st.rerun()
        
        # Last nye data hvis tidsperiode endret
        if hours_back != 24:
            with st.spinner("🔄 Henter nye data..."):
                df_new = self.get_weather_data(hours_back)
                if df_new is not None and not df_new.empty:
                    df = df_new
                    # Oppdater analyser
                    analyses['snow'] = self.analyze_fresh_snow(df)
                    analyses['slippery'] = self.analyze_slippery_conditions(df)
                    analyses['snowdrift'] = self.analyze_snowdrift_risk(df)
        
        # Detaljert informasjon
        self.show_detailed_info(df, analyses)
        
        # Footer
        self.show_mobile_footer()


def main():
    """Hovedfunksjon"""
    app = MobileFirstWeatherApp()
    app.run_mobile_app()


if __name__ == "__main__":
    main()
