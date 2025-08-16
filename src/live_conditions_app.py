#!/usr/bin/env python3
"""
Sanntidsvurdering av føreforhold med ML-baserte grenseverdier
"""

import os
import warnings
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
from matplotlib.patches import Rectangle

# Konfigurer matplotlib for å unngå font-advarsler
plt.rcParams['font.family'] = ['DejaVu Sans', 'Arial', 'sans-serif']
warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')

# Last miljøvariabler
load_dotenv()

# Import ML-basert detektor
try:
    from ml_snowdrift_detector import MLSnowdriftDetector
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("ML-detektor ikke tilgjengelig - bruker tradisjonelle metoder")

# Import validert nedbørtype-logikk
try:
    # Først prøv normal import
    from validert_glattfore_logikk import detect_precipitation_type
    VALIDATED_LOGIC_AVAILABLE = True
except ImportError:
    # Hvis det feiler, prøv å legge til paths
    import sys

    # Håndter både script og Streamlit-kontekst
    try:
        # I Streamlit-kontekst
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
    except NameError:
        # I kommandolinje-kontekst
        current_dir = os.getcwd()
        parent_dir = os.path.dirname(current_dir)

    # Legg til relevante paths
    paths_to_add = [
        parent_dir,  # Parent directory (hvor validert_glattfore_logikk.py ligger)
        current_dir,  # Current directory
        '.',  # Explicit current directory
        os.path.join(parent_dir),  # Parent directory again
    ]

    for path in paths_to_add:
        if path and path not in sys.path:
            sys.path.insert(0, path)

    try:
        from validert_glattfore_logikk import detect_precipitation_type
        VALIDATED_LOGIC_AVAILABLE = True
    except ImportError:
        VALIDATED_LOGIC_AVAILABLE = False
        # Validert logikk ikke tilgjengelig - bruker standard logikk
        try:
            files_current = [f for f in os.listdir('.') if f.endswith('.py')][:5]
            files_parent = [f for f in os.listdir('..') if f.endswith('.py')][:5]
        except OSError:
            pass

# Konstanter
PRECIP_HOURLY_COL = 'sum(precipitation_amount PT1H)'
NO_DATA_MESSAGE = "Ingen data tilgjengelig"
TEMP_LABEL = 'Temperatur (°C)'
WIND_LABEL = 'Vindstyrke (m/s)'
UPPER_LEFT = 'upper left'
UPPER_RIGHT = 'upper right'

class LiveConditionsChecker:
    """Sanntidsvurdering av føreforhold med ML-baserte grenseverdier."""

    def __init__(self):
        self.frost_client_id = os.getenv('FROST_CLIENT_ID')
        # Default to correct Gullingen Skisenter station; allow env override
        self.station_id = os.getenv("WEATHER_STATION", "SN46220")  # Gullingen Skisenter
        self.cache_duration = 3600  # 1 time cache

        # Initialiser ML-detektor hvis tilgjengelig
        if ML_AVAILABLE:
            self.ml_detector = MLSnowdriftDetector()
            self.use_ml = True
        else:
            self.ml_detector = None
            self.use_ml = False

    def is_winter_season(self) -> bool:
        """Sjekk om det er vintersesong (oktober-april)."""
        current_month = datetime.now().month
        return current_month in [10, 11, 12, 1, 2, 3, 4]

    def is_summer_season(self) -> bool:
        """Sjekk om det er sommersesong (mai-september)."""
        return not self.is_winter_season()

    @lru_cache(maxsize=10)
    def get_current_weather_data(self, hours_back: int = 24, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame | None:
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
                # Standard: siste X timer fra nå (timezone.utc)
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(hours=hours_back)

            fmt = "%Y-%m-%dT%H:%M:%SZ"
            start_iso = start_time.strftime(fmt)
            end_iso = end_time.strftime(fmt)

            # Utvidede elementer for bedre væranalyse - ALLE 15 VALIDERTE KJERNEELEMENTER
            elements = [
                'air_temperature',
                'wind_speed',
                'wind_from_direction',                    # KRITISK: vindretning for snøfokk-analyse
                'surface_snow_thickness',
                'sum(precipitation_amount PT1H)',        # HØY PRIORITET: timebasert nedbør
                'sum(precipitation_amount PT10M)',       # NY: 6x bedre oppløsning (144 vs 24 obs/dag)
                'accumulated(precipitation_amount)',     # NY: HØYESTE viktighet (7468.9-7721.4)
                'max_wind_speed(wind_from_direction PT1H)',  # NY: KRITISK for snøfokk (1555.9-1980.5)
                'relative_humidity',
                'surface_temperature',                   # REVOLUSJONERENDE: direkte veioverflate (168 obs/dag)
                'dew_point_temperature',                 # FROST-SPESIALIST: profesjonell frost-prediksjon
                'sum(duration_of_precipitation PT1H)',  # HØY PRIORITET: nedbørvarighet
                'max(wind_speed_of_gust PT1H)',         # MEDIUM PRIORITET: vindkast
                'weather_symbol',                        # MEDIUM PRIORITET: værsymbol
                'visibility'                             # MEDIUM PRIORITET: sikt
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
                        
                        # For nye elementer: spesifikk tidsoppløsning
                        if element == 'sum(precipitation_amount PT10M)' and time_res != 'PT10M':
                            continue
                        if element == 'max_wind_speed(wind_from_direction PT1H)' and time_res != 'PT1H':
                            continue

                        record[element] = value

                    records.append(record)

                if not records:
                    st.warning("Ingen gyldige målinger")
                    return None

                df = pd.DataFrame(records)
                
                # Normaliser nedbørskolonner
                if PRECIP_HOURLY_COL not in df.columns and 'precipitation_amount' in df.columns:
                    df[PRECIP_HOURLY_COL] = df['precipitation_amount']
                
                # Ny: Normaliser 10-minutters nedbør
                if 'sum(precipitation_amount PT10M)' in df.columns:
                    df['precipitation_amount_10m'] = df['sum(precipitation_amount PT10M)']
                
                # Ny: Normaliser akkumulert nedbør
                if 'accumulated(precipitation_amount)' in df.columns:
                    df['accumulated_precipitation'] = df['accumulated(precipitation_amount)']
                
                # Ny: Normaliser maks vindstyrke per retning
                if 'max_wind_speed(wind_from_direction PT1H)' in df.columns:
                    df['max_wind_per_direction'] = df['max_wind_speed(wind_from_direction PT1H)']
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

    def analyze_snowdrift_risk(self, df: pd.DataFrame) -> dict:
        """Analyser snøfokk-risiko - bruker ML-metoder hvis tilgjengelig."""

        if df is None or len(df) == 0:
            return {"risk_level": "unknown", "message": NO_DATA_MESSAGE}

        # Bruk ML-basert analyse hvis tilgjengelig
        if self.use_ml and self.ml_detector:
            try:
                result = self.ml_detector.analyze_snowdrift_risk_ml(df)

                return result

            except Exception as e:
                st.warning(f"ML-analyse feilet, bruker tradisjonell metode: {e}")
                # Fall back til tradisjonell metode

        # Tradisjonell analyse som backup
        return self._traditional_snowdrift_analysis(df)

    def _traditional_snowdrift_analysis(self, df: pd.DataFrame) -> dict:
        """Tradisjonell snøfokk-analyse som backup."""

        if df is None or len(df) == 0:
            return {"risk_level": "unknown", "message": NO_DATA_MESSAGE}

        # Beregn snødybde-endringer for dynamisk analyse
        if len(df) >= 2:
            df = df.copy()
            df['snow_change_1h'] = df['surface_snow_thickness'].diff()
            df['snow_change_6h'] = df['surface_snow_thickness'].diff(6) if len(df) >= 6 else 0
        else:
            df = df.copy()
            df['snow_change_1h'] = 0
            df['snow_change_6h'] = 0

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

        # Vintersesong: Full analyse med snødybde-dynamikk

        # Siste målinger
        latest = df.iloc[-1]
        # Bruk timezone.utc for sammenligning (referenceTime er tz-aware timezone.utc)
        last_24h = df[df['referenceTime'] >= (datetime.now(timezone.utc) - timedelta(hours=24))]

        # Grunnleggende kriterier
        current_temp = latest.get('air_temperature', None)
        current_wind = latest.get('wind_speed', None)
        current_snow = latest.get('surface_snow_thickness', 0)
        wind_direction = latest.get('wind_from_direction', None)  # KRITISK: vindretning
        
        # NYE EMPIRISK VALIDERTE ELEMENTER
        max_wind_per_direction = latest.get('max_wind_per_direction', current_wind)  # Maks vind per retning
        accumulated_precip = latest.get('accumulated_precipitation', 0)  # Akkumulert nedbør
        precip_10m = latest.get('precipitation_amount_10m', 0)  # Høyoppløselig nedbør
        wind_gust = latest.get('max(wind_speed_of_gust PT1H)', current_wind)  # Vindkast
        visibility = latest.get('visibility', None)  # Sikt
        weather_symbol = latest.get('weather_symbol', None)  # Værsymbol

        # FORBEDRET SNØDYBDE-DYNAMIKK med validerte terskler
        snow_change_1h = latest.get('snow_change_1h', 0)
        # Note: snow_change_6h beregnes men brukes ikke i denne versjonen
        fresh_snow = snow_change_1h >= 0.3  # Nysnø-indikator (empirisk validert)
        snow_transport = snow_change_1h <= -0.2  # Vindtransport-indikator (empirisk validert)
        
        # NY: Forbedret nysnø-deteksjon med akkumulert nedbør
        significant_precip = accumulated_precip >= 5.0  # Betydelig akkumulert nedbør
        high_res_precip = precip_10m >= 1.0  # Høyoppløselig nedbør-aktivitet

        if current_temp is None or current_wind is None:
            return {"risk_level": "unknown", "message": "Mangler kritiske målinger"}

        # FORBEDREDE DYNAMISKE VINDTERSKLER basert på alle nye elementer
        effective_wind = max(current_wind or 0, max_wind_per_direction or 0, wind_gust or 0)
        
        if fresh_snow or significant_precip or high_res_precip:
            wind_threshold = 5.0  # ML-optimert terskel ved nysnø (empirisk validert)
            dynamics_note = f"Nysnø/aktiv nedbør gjør snøfokk lettere"
            if high_res_precip:
                dynamics_note += f" (10-min nedbør: {precip_10m:.1f}mm)"
        elif snow_transport:
            wind_threshold = 5.0  # ML-optimert standard terskel
            dynamics_note = f"Vindtransport pågår (snøtap: {snow_change_1h:.1f} cm/h)"
        else:
            wind_threshold = 5.0  # ML-optimert standard terskel
            dynamics_note = None

        # Sjekk løssnø-tilgjengelighet (kritisk kriterium)
        mild_weather_recent = (last_24h['air_temperature'] > 0).any() if 'air_temperature' in last_24h.columns else True
        continuous_frost = (last_24h['air_temperature'] <= -1).all() if 'air_temperature' in last_24h.columns and len(last_24h) > 12 else False

        # FORBEDRET LØSSNØ-DETEKSJON med alle nye elementer
        if fresh_snow or significant_precip or high_res_precip:
            loose_snow_available = True  # Nysnø/nedbør gir alltid løssnø
            loose_snow_reason = "Nysnø/aktiv nedbør gir frisk løssnø"
        elif continuous_frost:
            loose_snow_available = True
            loose_snow_reason = "Kontinuerlig frost bevarer løssnø"
        elif mild_weather_recent:
            loose_snow_available = False
            loose_snow_reason = "Mildvær reduserer løssnø-kvalitet"
        else:
            loose_snow_available = True
            loose_snow_reason = "Usikker løssnø-kvalitet"

        # Klassifiser risiko med forbedrede kriterier
        risk_factors = []

        # FORBEDREDE METEOROLOGISKE KRITERIER med alle elementer
        if effective_wind >= wind_threshold:
            wind_desc = f"Sterk vind ({effective_wind:.1f} m/s"
            if max_wind_per_direction and max_wind_per_direction > current_wind:
                wind_desc += f", maks per retning: {max_wind_per_direction:.1f}"
            if wind_gust and wind_gust > current_wind:
                wind_desc += f", kast: {wind_gust:.1f}"
            wind_desc += f", terskel: {wind_threshold:.1f})"
            
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
                if 300 <= wind_direction <= 360 or 0 <= wind_direction <= 60:  # NV-N-NØ (standardisert)
                    risk_factors.append(wind_desc + " - høyrisiko-retning for Gullingen")
                else:
                    risk_factors.append(wind_desc)
            else:
                risk_factors.append(wind_desc + ")")
        if current_temp <= -1:
            risk_factors.append(f"Frost ({current_temp:.1f}°C)")
        if current_snow >= 3:
            risk_factors.append(f"Snødekke ({current_snow:.0f}cm)")

        # Snødynamikk-faktorer
        if fresh_snow:
            risk_factors.append(f"Nysnø (+{snow_change_1h:.1f} cm/h)")
        elif snow_transport:
            risk_factors.append(f"Vindtransport ({snow_change_1h:.1f} cm/h)")

        # FORBEDRET RISIKOKLASSIFISERING
        base_criteria_met = current_wind >= wind_threshold and current_temp <= -1 and current_snow >= 3

        # Mildvær-beskyttelse (med nysnø-unntak)
        if not loose_snow_available and not fresh_snow:
            return {
                "risk_level": "low",
                "message": f"Stabile forhold: {loose_snow_reason}. Vind: {current_wind:.1f} m/s, temp: {current_temp:.1f} °C",
                "factors": risk_factors,
                "loose_snow": loose_snow_reason,
                "dynamics": dynamics_note
            }

        # High-risk: Sterke kriterier + snødynamikk eller persistens
        high_risk_conditions = (
            base_criteria_met and
            (current_wind >= 8 or fresh_snow or snow_transport) and
            loose_snow_available
        )

        if high_risk_conditions:
            message = "Høy risiko for snøfokk: Sterke kriterier oppfylt"
            if fresh_snow:
                message += " + nysnø forsterker risiko"
            elif snow_transport:
                message += " + vindtransport bekreftet"

            return {
                "risk_level": "high",
                "message": message,
                "factors": risk_factors,
                "loose_snow": loose_snow_reason,
                "dynamics": dynamics_note
            }

        # Medium-risk: Grunnkriterier + løssnø
        elif base_criteria_met and loose_snow_available:
            message = "Moderat risiko: Grunnkriterier oppfylt"
            if dynamics_note:
                message += f" ({dynamics_note})"

            return {
                "risk_level": "medium",
                "message": message,
                "factors": risk_factors,
                "loose_snow": loose_snow_reason,
                "dynamics": dynamics_note
            }

        # Low-risk: Manglende kriterier
        else:
            return {
                "risk_level": "low",
                "message": "Lav risiko: Få eller ingen kriterier er oppfylt",
                "factors": risk_factors,
                "loose_snow": loose_snow_reason,
                "dynamics": dynamics_note
            }

    def analyze_slippery_road_risk(self, df: pd.DataFrame) -> dict:
        """Analyser glatt vei-risiko (regn-på-snø fokus + rimfrost)."""

        if df is None or len(df) == 0:
            return {"risk_level": "unknown", "message": NO_DATA_MESSAGE}

        latest = df.iloc[-1]
        current_temp = latest.get('air_temperature', None)
        current_snow = latest.get('surface_snow_thickness', 0)
        current_precip = latest.get(PRECIP_HOURLY_COL, 0)
        surface_temp = latest.get('surface_temperature', None)  # NY: bakketemperatur
        dew_point = latest.get('dew_point_temperature', None)   # NY: duggpunkt
        # Note: humidity hentes men brukes ikke i denne versjonen
        # humidity = latest.get('relative_humidity', None)

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
        # Bruk timezone.utc for sammenligning (referenceTime er tz-aware timezone.utc)
        last_6h = df[df['referenceTime'] >= (datetime.now(timezone.utc) - timedelta(hours=6))]
        # Beskyttelsesregel: Økende snødybde = nysnø → ikke glatt føre
        snow_increase = False
        if 'surface_snow_thickness' in last_6h.columns and len(last_6h) >= 2:
            try:
                s0 = last_6h['surface_snow_thickness'].iloc[0]
                s1 = last_6h['surface_snow_thickness'].iloc[-1]
                if pd.notna(s0) and pd.notna(s1):
                    snow_increase = (s1 - s0) >= 1.0  # ≥1 cm siste 6t
            except Exception:
                snow_increase = False

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

        # Klassifisering med utvidede kriterier (prioritet) og snøfalls-unntak
        if snow_increase:
            return {
                "risk_level": "low",
                "message": "Snøfall registrert – nysnø fungerer som naturlig strøing",
                "scenario": "Snøfall",
                "factors": risk_factors + ["Økende snødybde siste 6 t"]
            }

        # Deretter: regn-på-snø > is > rimfrost > temperaturovergang
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

    def classify_precipitation_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Klassifiser nedbørtype basert på validert logikk inkludert vindblåst snø og vindkjøling.
        
        Returns:
            DataFrame med kolonne 'precipitation_type' og 'confidence'
        """
        if not VALIDATED_LOGIC_AVAILABLE:
            # Fallback til enkel klassifisering
            df_copy = df.copy()
            df_copy['precipitation_type'] = 'ukjent'
            df_copy['confidence'] = 'lav'
            return df_copy

        df_copy = df.copy()
        df_copy['precipitation_type'] = 'ingen_nedbor'
        df_copy['confidence'] = 'høy'

        # Beregn snømengde-endring hvis ikke allerede tilgjengelig
        if 'snow_depth_change' not in df_copy.columns:
            if 'snow_depth' in df_copy.columns:
                df_copy['snow_depth_change'] = df_copy['snow_depth'].diff().fillna(0)
            else:
                df_copy['snow_depth_change'] = 0

        # Beregn vindkjøling hvis ikke allerede tilgjengelig
        if 'wind_chill' not in df_copy.columns:
            df_copy['wind_chill'] = self._calculate_wind_chill(
                df_copy.get('air_temperature', 0),
                df_copy.get('wind_speed', 0)
            )

        # Klassifiser hver rad
        for idx, row in df_copy.iterrows():
            temp = row.get('air_temperature', np.nan)

            # Prøv flere mulige kolonnenavn for nedbør
            precip = row.get(PRECIP_HOURLY_COL, 0)
            if precip == 0:
                precip = row.get('precipitation_amount', 0)
            if precip == 0:
                precip = row.get('precipitation_mm', 0)

            snow_change = row.get('snow_depth_change', 0)
            wind_speed = row.get('wind_speed', 0)
            wind_chill = row.get('wind_chill', temp)  # Fallback til temperatur

            # Bruk validert logikk med vindkjøling kun hvis det er nedbør
            if not pd.isna(temp) and precip > 0:
                precip_type, confidence = self._enhanced_precipitation_detection(
                    temp, precip, snow_change, wind_speed, wind_chill
                )
                df_copy.loc[idx, 'precipitation_type'] = precip_type
                df_copy.loc[idx, 'confidence'] = confidence

        return df_copy

    def _calculate_wind_chill(self, temp, wind_speed):
        """
        Beregn vindkjøling (gyldig for temp < 10°C og vind > 4.8 km/h).
        """
        if hasattr(temp, '__iter__'):
            # Pandas Series
            wind_chill = np.where(
                (temp < 10) & (wind_speed > 1.34),  # 4.8 km/h = 1.34 m/s
                13.12 + 0.6215 * temp - 11.37 * (wind_speed * 3.6) ** 0.16 + 0.3965 * temp * (wind_speed * 3.6) ** 0.16,
                temp
            )
        else:
            # Enkeltverdier
            if temp < 10 and wind_speed > 1.34:
                wind_chill = 13.12 + 0.6215 * temp - 11.37 * (wind_speed * 3.6) ** 0.16 + 0.3965 * temp * (wind_speed * 3.6) ** 0.16
            else:
                wind_chill = temp
        return wind_chill

    def _enhanced_precipitation_detection(self, temp, precip, snow_change, wind_speed, wind_chill):
        """
        Forbedret nedbørdeteksjon med vindkjøling.
        """
        try:
            # Bruk den eksisterende validerte logikken som base
            base_type, base_confidence = detect_precipitation_type(temp, precip, snow_change, wind_speed)

            # Forbedringer med vindkjøling
            if wind_chill < -15 and wind_speed > 8:
                # Ekstremt kaldt med vind - sannsynligvis vindblåst snø
                if snow_change and snow_change < -2:
                    return "vindblast_sno", "høy"
                elif base_type in ['sno', 'sno_med_vindpavirkning']:
                    return "vindblast_sno", "høy"

            # Vindkjøling i grenseområdet (verbedrer klassifisering)
            if -5 <= wind_chill <= 2 and wind_speed > 6:
                if snow_change and snow_change < -3:
                    if wind_chill < 0:
                        return "vindblast_sno", "høy"
                    else:
                        return "regn", "høy"  # Regn som smelter snø

            # Vindkjøling kan indikere regn på snø (glattføre-risiko)
            if 0 <= temp <= 3 and wind_chill < temp - 2 and snow_change and snow_change < 0:
                if base_type == "regn":
                    return "regn_pa_sno", "høy"  # Glattføre-risiko!

            return base_type, base_confidence

        except Exception:
            # Fallback til enkel klassifisering ved feil
            if temp > 2:
                return "regn", "medium"
            elif temp < -2:
                return "sno", "medium"
            else:
                return "usikker_grenseomrade", "lav"

    def create_slippery_road_risk_plot(self, df: pd.DataFrame) -> plt.Figure:
        """
        Lag optimalisert visualisering av potensielle glattføre-episoder med detaljerte værdata.
        """
        if df is None or len(df) == 0:
            fig, ax = plt.subplots(1, 1, figsize=(12, 6))
            ax.text(0.5, 0.5, NO_DATA_MESSAGE,
                   ha='center', va='center', fontsize=14, color='gray')
            ax.set_title('Glattføre-risiko Analyse', fontsize=16, fontweight='bold')
            return fig

        # Klassifiser nedbørtyper og identifiser glattføre-risiko
        df_classified = self.classify_precipitation_types(df)

        # Filtrer kun episoder med potensielt glattføre-risiko
        glattfore_types = ['regn', 'regn_pa_sno', 'usikker_grenseomrade']
        df_risk = df_classified[df_classified['precipitation_type'].isin(glattfore_types)]

        if len(df_risk) == 0:
            fig, ax = plt.subplots(1, 1, figsize=(12, 6))
            ax.text(0.5, 0.5, 'Ingen glattføre-risiko episoder funnet i perioden',
                   ha='center', va='center', fontsize=14, color='green')
            ax.set_title('Glattføre-risiko Analyse', fontsize=16, fontweight='bold')
            return fig

        # Optimalisert figure-oppsett med bedre proporsjoner
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 14),
                                           gridspec_kw={'height_ratios': [2, 2, 1.5], 'hspace': 0.3})

        # Forbered tidsakse med bedre formatering
        time_col = 'referenceTime'
        times_all = pd.to_datetime(df_classified[time_col])
        times_risk = pd.to_datetime(df_risk[time_col])

        # GRAF 1: Optimalisert temperaturplot med forbedret visualisering
        # Hovedtemperaturkurve med gradient
        ax1.plot(times_all, df_classified['air_temperature'], 'b-', alpha=0.7,
                linewidth=2.5, label=f'Temperatur ({len(df_classified)} målinger)', zorder=3)

        # Fremhev glattføre-risiko episoder med større markører og varierte farger
        risk_temps = df_risk['air_temperature']
        risk_colors_temp = {'regn': '#FF4444', 'regn_pa_sno': '#CC0000', 'usikker_grenseomrade': '#FF8800'}

        for risk_type, color in risk_colors_temp.items():
            mask = df_risk['precipitation_type'] == risk_type
            if mask.any():
                subset_times = times_risk[mask]
                subset_temps = risk_temps[mask]
                ax1.scatter(subset_times, subset_temps, c=color, s=80, alpha=0.9,
                           label=f'{risk_type.replace("_", " ").title()} ({len(subset_temps)})',
                           zorder=5, edgecolors='white', linewidth=1)

        # Forbedret frysepunkt-linje
        ax1.axhline(y=0, color='navy', linestyle='--', alpha=0.8, linewidth=2, label='Frysepunkt (0°C)')

        # Temperatur-soner med bakgrunnsfarge
        ax1.axhspan(-50, 0, alpha=0.1, color='lightblue', zorder=1)  # Frost-sone
        ax1.axhspan(0, 3, alpha=0.1, color='yellow', zorder=1)      # Kritisk sone
        ax1.axhspan(3, 50, alpha=0.1, color='lightgreen', zorder=1) # Trygg sone

        ax1.set_ylabel(TEMP_LABEL, fontsize=12, fontweight='bold')
        ax1.set_title('Temperatur med Glattfore-risiko Episoder', fontsize=14, fontweight='bold', pad=20)
        ax1.grid(True, alpha=0.4, linestyle='-', linewidth=0.5)
        ax1.legend(bbox_to_anchor=(1.05, 1), loc=UPPER_LEFT, fontsize=10)

        # Forbedret tidsakse-formatering
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m %H:%M'))
        ax1.xaxis.set_major_locator(mdates.HourLocator(interval=max(1, len(times_all)//10)))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # GRAF 2: Optimalisert nedbør og vindstyrke plot
        ax2_twin = ax2.twinx()

        # Finn nedbørkolonne
        precip_col = None
        for col in [PRECIP_HOURLY_COL, 'precipitation_amount', 'precipitation_mm']:
            if col in df_classified.columns:
                precip_col = col
                break

        if precip_col:
            # Nedbør med forbedret visualisering
            precip_all = df_classified[precip_col].fillna(0)
            precip_risk = df_risk[precip_col].fillna(0)

            # Bredere søyler for bedre synlighet
            bar_width = pd.Timedelta(minutes=30)

            # Bakgrunns-nedbør (alle episoder)
            ax2.bar(times_all, precip_all, alpha=0.3, color='lightsteelblue',
                   width=bar_width, label=f'Nedbør alle ({len(precip_all)} punkter)', zorder=2)

            # Fremhev risiko-nedbør med varierte farger
            for risk_type, color in risk_colors_temp.items():
                mask = df_risk['precipitation_type'] == risk_type
                if mask.any():
                    subset_times = times_risk[mask]
                    subset_precip = precip_risk[mask]
                    ax2.bar(subset_times, subset_precip, alpha=0.9, color=color,
                           width=bar_width, label=f'Nedbør {risk_type.replace("_", " ")} ({len(subset_precip)})', zorder=4)

        # Vindstyrke med forbedret linje og markører
        wind_all = df_classified['wind_speed'].fillna(0)
        wind_risk = df_risk['wind_speed'].fillna(0)

        ax2_twin.plot(times_all, wind_all, 'forestgreen', alpha=0.7, linewidth=2,
                     label=f'Vindstyrke ({len(wind_all)} målinger)', zorder=3)

        # Fremhev vindstyrke under risiko-episoder
        ax2_twin.scatter(times_risk, wind_risk, c='darkorange', s=60, alpha=0.9,
                        label=f'Vind ved risiko ({len(wind_risk)} punkter)', zorder=5,
                        edgecolors='white', linewidth=1)

        # Vindstyrke-terskler
        ax2_twin.axhline(y=8, color='orange', linestyle=':', alpha=0.7, linewidth=2, label='Vind-advarsel (8 m/s)')
        ax2_twin.axhline(y=12, color='red', linestyle='--', alpha=0.8, linewidth=2, label='Empirisk terskel (12 m/s)')

        # Forbedret akser og formatering
        ax2.set_ylabel('Nedbør (mm/t)', color='steelblue', fontsize=12, fontweight='bold')
        ax2_twin.set_ylabel(WIND_LABEL, color='forestgreen', fontsize=12, fontweight='bold')
        ax2.set_title('Nedbor og Vindstyrke under Glattfore-risiko', fontsize=14, fontweight='bold', pad=20)
        ax2.grid(True, alpha=0.4, linestyle='-', linewidth=0.5)

        # Forbedret legend-plassering
        ax2.legend(bbox_to_anchor=(0.02, 0.98), loc='upper left', fontsize=9)
        ax2_twin.legend(bbox_to_anchor=(0.98, 0.98), loc='upper right', fontsize=9)

        # Synkroniser x-akser
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m %H:%M'))
        ax2.xaxis.set_major_locator(mdates.HourLocator(interval=max(1, len(times_all)//10)))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # GRAF 3: Optimalisert detaljert glattføre-risiko klassifisering
        # Forbedret fargepalett med høyere kontrast
        risk_colors = {
            'regn': '#4285F4',                # Google Blue
            'regn_pa_sno': '#DB4437',         # Google Red
            'usikker_grenseomrade': '#FF9800' # Material Orange
        }

        # Forbedret tidsrekke-visualisering med kontinuerlige segmenter
        risk_episodes = []
        current_episode = {}

        for _, row in df_risk.iterrows():
            precip_type = row['precipitation_type']
            time_point = pd.to_datetime(row[time_col])

            if not current_episode or current_episode.get('type') != precip_type:
                # Start ny episode
                if current_episode:
                    risk_episodes.append(current_episode)
                current_episode = {
                    'type': precip_type,
                    'start': time_point,
                    'end': time_point,
                    'count': 1
                }
            else:
                # Forleng eksisterende episode
                current_episode['end'] = time_point
                current_episode['count'] += 1

        # Legg til siste episode
        if current_episode:
            risk_episodes.append(current_episode)

        # Tegn forbedrede episoder med bedre visning
        episode_height = 0.8
        y_center = 0.5

        for episode in risk_episodes:
            color = risk_colors.get(episode['type'], '#9E9E9E')

            # Beregn episode-varighet
            duration = episode['end'] - episode['start']
            if duration.total_seconds() == 0:
                duration = pd.Timedelta(hours=1)  # Minimum varighet for synlighet

            start_num = mdates.date2num(episode['start'])
            end_num = mdates.date2num(episode['end'] + duration)
            width = end_num - start_num

            if width > 0:
                # Hovedrektangel
                rect = Rectangle((start_num, y_center - episode_height/2), width, episode_height,
                               facecolor=color, alpha=0.8, edgecolor='white', linewidth=2)
                ax3.add_patch(rect)

                # Legg til episode-informasjon som tekst
                text_x = start_num + width/2
                text_y = y_center
                episode_label = f"{episode['type'].replace('_', ' ').title()}\n({episode['count']} obs)"

                ax3.text(text_x, text_y, episode_label, ha='center', va='center',
                        fontsize=9, fontweight='bold', color='white',
                        bbox={'boxstyle': 'round,pad=0.3', 'facecolor': color, 'alpha': 0.7})

        # Forbedret akser og formatering
        if len(times_all) > 0:
            time_range = times_all.max() - times_all.min()
            padding = time_range * 0.05
            ax3.set_xlim(times_all.min() - padding, times_all.max() + padding)

        ax3.set_ylim(0, 1)
        ax3.set_ylabel('Glattføre-risiko Status', fontsize=12, fontweight='bold')
        ax3.set_xlabel('Tid', fontsize=12, fontweight='bold')
        ax3.set_title('🚨 Detaljert Glattføre-risiko Klassifisering', fontsize=14, fontweight='bold', pad=20)
        ax3.grid(True, alpha=0.3, linestyle=':', linewidth=0.5)

        # Optimalisert legend med episode-statistikk
        legend_elements = []
        for precip_type, color in risk_colors.items():
            if precip_type in df_risk['precipitation_type'].values:
                count = len(df_risk[df_risk['precipitation_type'] == precip_type])
                episode_count = len([ep for ep in risk_episodes if ep['type'] == precip_type])

                label = f"{precip_type.replace('_', ' ').title()} ({count} obs, {episode_count} episoder)"
                legend_elements.append(Rectangle((0, 0), 1, 1, facecolor=color, alpha=0.8,
                                               edgecolor='white', linewidth=1, label=label))

        if legend_elements:
            ax3.legend(handles=legend_elements, bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10)

        # Forbedret tidsakse for alle subplot
        for ax in [ax1, ax2, ax3]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m\n%H:%M'))
            if len(times_all) > 20:
                ax.xaxis.set_major_locator(mdates.HourLocator(interval=max(2, len(times_all)//15)))
            else:
                ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha='center')

        # Optimalisert layout med bedre spacing og warning suppression
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            try:
                plt.tight_layout(pad=3.0)
            except (UserWarning, ValueError):
                # Fallback hvis tight_layout feiler
                plt.subplots_adjust(left=0.1, right=0.9, top=0.85, bottom=0.15, hspace=0.4, wspace=0.3)
            except Exception:
                # Siste fallback
                pass

        fig.suptitle('GLATTFORE-RISIKO ANALYSE - DETALJERT OVERSIKT',
                    fontsize=16, fontweight='bold', y=0.98)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            try:
                plt.subplots_adjust(top=0.94)
            except Exception:
                pass

        return fig

    def create_precipitation_classification_plot(self, df: pd.DataFrame) -> plt.Figure:
        """
        Lag optimalisert visualisering av nedbørtype-klassifisering over tid.
        """
        if df is None or len(df) == 0:
            fig, ax = plt.subplots(1, 1, figsize=(12, 6))
            ax.text(0.5, 0.5, NO_DATA_MESSAGE,
                   ha='center', va='center', fontsize=14, color='gray')
            ax.set_title('Nedbørtype-klassifisering', fontsize=16, fontweight='bold')
            return fig

        # Klassifiser nedbørtyper
        df_classified = self.classify_precipitation_types(df)

        # Optimalisert figure-oppsett
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 12),
                                           gridspec_kw={'height_ratios': [1.5, 1.5, 2], 'hspace': 0.25})

        # Robust tidsakse-håndtering
        time_col = None
        for col in ['referenceTime', 'time', 'datetime', 'timestamp']:
            if col in df_classified.columns:
                time_col = col
                break

        if time_col is None:
            times = pd.date_range('2025-01-01', periods=len(df_classified), freq='h')
            st.warning("⚠️ Ingen tidsserie funnet - bruker dummy-tider for visualisering")
        else:
            try:
                times = pd.to_datetime(df_classified[time_col])
            except Exception as e:
                times = pd.date_range('2025-01-01', periods=len(df_classified), freq='h')
                st.warning(f"⚠️ Feil ved parsing av tider ({e}) - bruker dummy-tider")

        # GRAF 1: Optimalisert temperatur og nedbør
        ax1_twin = ax1.twinx()

        # Temperaturkurve med forbedret design
        temp_data = df_classified['air_temperature'].fillna(0)
        ax1.plot(times, temp_data, 'steelblue', linewidth=3, alpha=0.8,
                label=f'Temperatur ({len(temp_data)} målinger)', zorder=3)

        # Temperatur-soner med bakgrunnsfarge
        ax1.axhspan(-50, 0, alpha=0.1, color='lightblue', zorder=1, label='Frost-sone')
        ax1.axhspan(0, 3, alpha=0.1, color='lightyellow', zorder=1, label='Kritisk sone (0-3°C)')
        ax1.axhspan(3, 50, alpha=0.1, color='lightgreen', zorder=1, label='Plussgradersone')

        # Finn riktig nedbørkolonne med fallback
        precip_col = None
        for col in [PRECIP_HOURLY_COL, 'precipitation_amount', 'precipitation_mm']:
            if col in df_classified.columns:
                precip_col = col
                break

        if precip_col:
            precip_data = df_classified[precip_col].fillna(0)
            # Optimalisert nedbør-bars med adaptive bredde
            bar_width = pd.Timedelta(minutes=max(15, min(60, len(times)//10)))
            ax1_twin.bar(times, precip_data, alpha=0.7, color='royalblue',
                        label=f'Nedbør ({len(precip_data)} målinger)', width=bar_width, zorder=4)
        else:
            ax1_twin.bar(times, [0] * len(times), alpha=0.3, color='lightgray',
                        label='Nedbør (ikke tilgjengelig)', width=pd.Timedelta(hours=1))

        # Forbedret frysepunkt-markering
        ax1.axhline(y=0, color='navy', linestyle='--', alpha=0.9, linewidth=2.5, label='Frysepunkt (0°C)', zorder=5)

        # Optimaliserte akser og formatering
        ax1.set_ylabel(TEMP_LABEL, color='steelblue', fontsize=12, fontweight='bold')
        ax1_twin.set_ylabel('Nedbør (mm/t)', color='royalblue', fontsize=12, fontweight='bold')
        ax1.set_title('Temperatur og Nedbor - Grunnlag for Klassifisering', fontsize=14, fontweight='bold', pad=15)
        ax1.grid(True, alpha=0.4, linestyle='-', linewidth=0.5)

        # Optimaliserte legends
        ax1.legend(bbox_to_anchor=(0.02, 0.98), loc='upper left', fontsize=10)
        ax1_twin.legend(bbox_to_anchor=(0.98, 0.98), loc='upper right', fontsize=10)

        # GRAF 2: Optimalisert vindstyrke og snømengde-endring
        ax2_twin = ax2.twinx()

        # Vindstyrke med forbedret visualisering
        wind_data = df_classified['wind_speed'].fillna(0)
        ax2.plot(times, wind_data, 'forestgreen', linewidth=3, alpha=0.8,
                label=f'Vindstyrke ({len(wind_data)} målinger)', zorder=3)

        # Snømengde-endring med forbedret design
        snow_data = df_classified['snow_depth_change'].fillna(0)
        ax2_twin.plot(times, snow_data, 'saddlebrown', linewidth=2.5, alpha=0.8,
                     label=f'Snømengde-endring ({len(snow_data)} målinger)', zorder=4)

        # Kritiske vindterskler med forbedrede linjer
        ax2.axhline(y=8, color='orange', linestyle=':', alpha=0.8, linewidth=2.5,
                   label='Vind-advarsel (8 m/s)', zorder=5)
        ax2.axhline(y=10, color='red', linestyle='--', alpha=0.9, linewidth=3,
                   label='Kritisk vind (10 m/s)', zorder=5)
        ax2.axhline(y=12, color='darkred', linestyle='-', alpha=0.9, linewidth=2,
                   label='Empirisk terskel (12 m/s)', zorder=5)

        # Snømengde-nullinje
        ax2_twin.axhline(y=0, color='black', linestyle='--', alpha=0.6, linewidth=2, zorder=5)

        # Vindstyrke-soner med bakgrunnsfarge
        ax2.axhspan(0, 8, alpha=0.05, color='lightgreen', zorder=1)    # Lav vind
        ax2.axhspan(8, 10, alpha=0.08, color='yellow', zorder=1)       # Advarsel
        ax2.axhspan(10, 12, alpha=0.1, color='orange', zorder=1)       # Kritisk
        ax2.axhspan(12, 50, alpha=0.12, color='red', zorder=1)         # Ekstrem

        # Optimaliserte akser og formatering
        ax2.set_ylabel(WIND_LABEL, color='forestgreen', fontsize=12, fontweight='bold')
        ax2_twin.set_ylabel('Snømengde-endring (cm)', color='saddlebrown', fontsize=12, fontweight='bold')
        ax2.set_title('Vind og Snomengde-endring - Vindblast Sno Indikatorer', fontsize=14, fontweight='bold', pad=15)
        ax2.grid(True, alpha=0.4, linestyle='-', linewidth=0.5)

        # Optimaliserte legends
        ax2.legend(bbox_to_anchor=(0.02, 0.98), loc='upper left', fontsize=9)
        ax2_twin.legend(bbox_to_anchor=(0.98, 0.98), loc='upper right', fontsize=9)

        # GRAF 3: Avansert nedbørtype-klassifisering visualisering
        # Forbedret fargepalett med høy kontrast og semantisk betydning
        type_colors = {
            'regn': '#1E88E5',              # Blå - vanlig regn
            'sno': '#E3F2FD',               # Lys blå - snø
            'vindblast_sno': '#D32F2F',     # Rød - vindblåst snø (kritisk)
            'sno_med_vindpavirkning': '#FF9800',  # Orange - snø med vind
            'vat_sno': '#00BCD4',           # Cyan - våt snø
            'regn_pa_sno': '#B71C1C',       # Mørk rød - regn på snø (glattføre!)
            'regn_eller_vindblast': '#9C27B0',    # Lilla - usikker
            'usikker_grenseomrade': '#FFEB3B',    # Gul - grenseområde
            'ukjent': '#E91E63'             # Rosa - ukjent type
        }

        # SKIP "ingen_nedbor" helt - vis kun interessante episoder
        interesting_df = df_classified[df_classified['precipitation_type'] != 'ingen_nedbor'].copy()

        if len(interesting_df) == 0:
            ax3.text(0.5, 0.5, 'Ingen aktiv nedbør i perioden\n(kun "ingen nedbør" episoder)',
                    ha='center', va='center', fontsize=14, color='gray',
                    bbox={'boxstyle': 'round,pad=0.5', 'facecolor': 'lightgray', 'alpha': 0.3})
            ax3.set_title('Nedbortype-klassifisering', fontsize=14, fontweight='bold')
        else:
            # Grupper kontinuerlige episoder av samme type
            episodes = []
            current_episode = {}

            for _, row in interesting_df.iterrows():
                precip_type = row['precipitation_type']
                confidence = row.get('confidence', 'medium')

                # Robust tidsbehandling
                if time_col and time_col in row:
                    try:
                        time_point = pd.to_datetime(row[time_col])
                    except Exception:
                        time_point = times[0] if len(times) > 0 else datetime.now()
                else:
                    time_point = times[0] if len(times) > 0 else datetime.now()

                # Start ny episode eller forleng eksisterende
                if (not current_episode or
                    current_episode.get('type') != precip_type or
                    (time_point - current_episode.get('end', time_point)).total_seconds() > 7200):  # 2 timer gap

                    if current_episode:
                        episodes.append(current_episode)

                    current_episode = {
                        'type': precip_type,
                        'confidence': confidence,
                        'start': time_point,
                        'end': time_point,
                        'count': 1,
                        'avg_confidence': confidence
                    }
                else:
                    current_episode['end'] = time_point
                    current_episode['count'] += 1
                    # Oppdater gjennomsnittlig konfidens (simplified)
                    if confidence == 'høy':
                        current_episode['avg_confidence'] = 'høy'

            # Legg til siste episode
            if current_episode:
                episodes.append(current_episode)

            # Tegn forbedrede episoder med høy detaljgrad
            for episode in episodes:
                precip_type = episode['type']
                confidence = episode['avg_confidence']
                color = type_colors.get(precip_type, '#9E9E9E')

                # Confidence-basert alpha
                alpha_map = {'høy': 0.9, 'medium': 0.7, 'lav': 0.5}
                alpha = alpha_map.get(confidence, 0.6)

                # Beregn episode-varighet
                duration = episode['end'] - episode['start']
                if duration.total_seconds() < 1800:  # Minimum 30 min for synlighet
                    duration = pd.Timedelta(minutes=30)

                start_num = mdates.date2num(episode['start'])
                end_num = mdates.date2num(episode['end'] + duration)
                width = end_num - start_num

                if width > 0:
                    # Hovedrektangel med forbedret design
                    rect = Rectangle((start_num, 0.1), width, 0.8,
                                   facecolor=color, alpha=alpha,
                                   edgecolor='white', linewidth=2)
                    ax3.add_patch(rect)

                    # Legg til detaljert episode-informasjon
                    text_x = start_num + width/2
                    text_y = 0.5

                    # Kort og informativ label
                    type_label = precip_type.replace('_', ' ').title()
                    duration_hours = duration.total_seconds() / 3600

                    if duration_hours < 2:
                        duration_str = f"{int(duration.total_seconds()/60)}min"
                    else:
                        duration_str = f"{duration_hours:.1f}t"

                    episode_text = f"{type_label}\n{episode['count']} obs ({duration_str})\nKonf: {confidence}"

                    # Intelligente tekst-farger basert på bakgrunn
                    text_color = 'white' if precip_type in ['vindblast_sno', 'regn_pa_sno'] else 'black'

                    ax3.text(text_x, text_y, episode_text, ha='center', va='center',
                            fontsize=8, fontweight='bold', color=text_color,
                            bbox={'boxstyle': 'round,pad=0.2', 'facecolor': color, 'alpha': 0.3})

            # Forbedret legend med statistikk
            legend_elements = []

            for precip_type in interesting_df['precipitation_type'].unique():
                if precip_type in type_colors:
                    count = len(interesting_df[interesting_df['precipitation_type'] == precip_type])
                    episode_count = len([ep for ep in episodes if ep['type'] == precip_type])

                    color = type_colors[precip_type]
                    label = f"{precip_type.replace('_', ' ').title()} ({count} obs, {episode_count} ep)"

                    legend_elements.append(Rectangle((0, 0), 1, 1,
                                                   facecolor=color, alpha=0.8,
                                                   edgecolor='white', linewidth=1,
                                                   label=label))

            if legend_elements:
                ax3.legend(handles=legend_elements, bbox_to_anchor=(1.05, 1),
                          loc='upper left', fontsize=9)

        # Formater x-akse
        for ax in [ax1, ax2, ax3]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m %H:%M'))
            ax.tick_params(axis='x', rotation=45)

        # Optimaliserte akser og tidsformatering
        if len(times) > 0:
            time_range = times.max() - times.min()
            padding = time_range * 0.05
            ax3.set_xlim(times.min() - padding, times.max() + padding)

        ax3.set_ylim(0, 1)
        ax3.set_ylabel('Nedbørtype', fontsize=12, fontweight='bold')
        ax3.set_xlabel('Tid', fontsize=12, fontweight='bold')
        ax3.set_title('Klassifisert Nedbortype (Kun Aktiv Nedbor - Empirisk Validert)',
                     fontsize=14, fontweight='bold', pad=20)
        ax3.grid(True, alpha=0.3, linestyle=':', linewidth=0.5)

        # Forbedret tidsakse for alle subplot
        for ax in [ax1, ax2, ax3]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m\n%H:%M'))
            if len(times) > 20:
                ax.xaxis.set_major_locator(mdates.HourLocator(interval=max(2, len(times)//15)))
            else:
                ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha='center')

        # Optimalisert layout med warning suppression
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            try:
                plt.tight_layout(pad=3.0)
            except (UserWarning, ValueError):
                # Fallback hvis tight_layout feiler
                plt.subplots_adjust(left=0.1, right=0.9, top=0.85, bottom=0.15, hspace=0.4, wspace=0.3)
            except Exception:
                # Siste fallback
                pass

        fig.suptitle('NEDBORTYPE-KLASSIFISERING - KOMPLETT ANALYSE',
                    fontsize=16, fontweight='bold', y=0.98)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            try:
                plt.subplots_adjust(top=0.94)
            except Exception:
                pass

        return fig

def create_streamlit_app():
    """Lag Streamlit web app for live føreforhold."""

    st.set_page_config(
        page_title="Føreforhold – Gullingen (live)",
        layout="wide"
    )

    st.title("Føreforhold – Gullingen (live)")

    # Sesonginfo
    checker = LiveConditionsChecker()
    if not checker.is_summer_season():
        st.info("**VINTERSESONG (OKTOBER-APRIL)**: Full snøfokk- og glatt føre-analyse tilgjengelig")

    # Opprett checker

    # Innstillinger
    with st.expander("Innstillinger", expanded=False):
        # Definer standardverdier for alle variabler først
        hours_back = 24
        start_date = datetime(2024, 2, 1).date()
        end_date = datetime(2024, 2, 15).date()
        start_time = datetime.now().time().replace(hour=0, minute=0)
        end_time = datetime.now().time().replace(hour=23, minute=59)

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
                    value=datetime(2024, 2, 15).date(),
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
                    pass
        with col_c:
            # Definer variabler før bruk
            period_hours = hours_back

            if use_custom_dates:
                period_info = f"{start_date} til {end_date}"
            else:
                period_info = f"Siste {period_hours} timer"

            st.info(f"Periode: {period_info}")

    # Oppdater stasjons-ID hvis endret
    if station_id_input:
        checker.station_id = station_id_input

    # Auto-refresh hver 5. minutt
    placeholder = st.empty()

    with placeholder.container():
        # Hent data (cached!)
        with st.spinner("Henter værdata …"):
            if use_custom_dates:
                # Kombiner dato og tid
                start_datetime = datetime.combine(start_date, start_time).isoformat()
                end_datetime = datetime.combine(end_date, end_time).isoformat()

                df = checker.get_current_weather_data(start_date=start_datetime, end_date=end_datetime)
                data_period_description = f"fra {start_date} til {end_date}"
            else:
                df = checker.get_current_weather_data(hours_back=hours_back)
                data_period_description = f"siste {hours_back} timer"

        if df is not None and len(df) > 0:

            # Periode-informasjon
            latest_time = df['referenceTime'].iloc[-1]
            earliest_time = df['referenceTime'].iloc[0]
            st.info(f"**Data for {data_period_description}** | Siste måling: {latest_time.strftime('%d.%m.%Y kl %H:%M')} | Første måling: {earliest_time.strftime('%d.%m.%Y kl %H:%M')} | {len(df)} målinger")

            # Tre kolonner for resultater
            col1, col2, col3 = st.columns(3)

            # NØKKELDATA (flyttet fra col3)
            with col1:
                st.subheader("Nøkkelverdier")
                latest = df.iloc[-1]

                st.metric("Temperatur", f"{latest.get('air_temperature', 'N/A'):.1f}°C")
                st.metric("Vind", f"{latest.get('wind_speed', 'N/A'):.1f} m/s")
                st.metric("Snødybde", f"{latest.get('surface_snow_thickness', 'N/A'):.0f} cm")

                precip = latest.get(PRECIP_HOURLY_COL, latest.get('precipitation_amount', 0))
                st.metric("Nedbør", f"{precip:.1f} mm/h")

                # NY: Snødybde-endringer
                if 'snow_change_1h' in latest and latest.get('snow_change_1h') is not None:
                    snow_change = latest.get('snow_change_1h')
                    if abs(snow_change) >= 0.1:  # Vis kun signifikante endringer
                        change_icon = "↗" if snow_change > 0 else "↘"
                        st.metric(f"Snøendring (1h) {change_icon}", f"{snow_change:+.1f} cm/h")

                        # Tolkningshjep
                        if snow_change >= 0.3:
                            st.caption("🌨️ Nysnø detektert")
                        elif snow_change <= -0.2:
                            st.caption("💨 Mulig vindtransport")
                        else:
                            st.caption("⚖️ Stabile snøforhold")

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
                    - Stabilt kaldt vær (under -1°C) gir gode kjøreforhold på snø
                    - Snøfall/nysnø fungerer som naturlig strøing
                    - Økende snødybde siste 6 timer (≥1 cm) tolkes som nysnø → klassifiseres ikke som glatt føre
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

            # Ledig plass for fremtidige funksjoner
            with col3:
                st.subheader("Sammendrag")
                st.info("💡 **Tips:** For grundig snøfokk-analyse, se egen seksjon nederst på siden.")

                # Vis kort sammendrag av alle risikoer
                if 'slippery_result' in locals():
                    if slippery_result['risk_level'] == 'high':
                        st.warning("⚠️ Høy glattføre-risiko")
                    elif slippery_result['risk_level'] == 'medium':
                        st.info("� Moderat glattføre-risiko")
                    else:
                        st.success("✅ Lav glattføre-risiko")

            # TREND-GRAF
            st.subheader("Værdata over valgt periode")

            # Datakvalitet og tilgjengelighet
            with st.expander("Datakvalitet og tilgjengelighet", expanded=False):
                st.write("**Kolonner i datasett:**", list(df.columns))
                st.write("**Antall målinger:**", len(df))

                # Datakvalitetsanalyse
                st.write("**Datakvalitet:**")
                missing_data = {}
                total_records = len(df)

                for col in ['air_temperature', 'wind_speed', 'surface_snow_thickness', 'surface_temperature']:
                    if col in df.columns:
                        missing_count = df[col].isna().sum()
                        missing_pct = (missing_count / total_records) * 100
                        missing_data[col] = missing_count

                        # Forbedret conditional logic
                        if missing_pct < 10:
                            status_icon = "✅"
                        elif missing_pct < 50:
                            status_icon = "⚠️"
                        else:
                            status_icon = "❌"

                        st.write(f"• {col}: {status_icon} {missing_count}/{total_records} mangler ({missing_pct:.1f}%)")

                # Snøfokk-analyse mulig?
                wind_available = missing_data.get('wind_speed', total_records) < total_records * 0.5
                temp_available = missing_data.get('air_temperature', total_records) < total_records * 0.5
                snow_available = missing_data.get('surface_snow_thickness', total_records) < total_records * 0.5

                analysis_possible = wind_available and temp_available and snow_available
                analysis_icon = "✅" if analysis_possible else "❌"
                st.write(f"**Snøfokk-analyse mulig:** {analysis_icon} {'Ja' if analysis_possible else 'Nei - for mye manglende data'}")

                if not analysis_possible:
                    st.warning("⚠️ **Datakvalitetsproblem:** Stor andel manglende vinddata kan påvirke nøyaktigheten av snøfokk-analysen. "
                             "Dette er vanlig for eldre data eller enkelte værstasjoner.")

                # Tidsperiode med beste data
                if 'wind_speed' in df.columns:
                    # Finn perioder med komplette data
                    complete_data = df.dropna(subset=['air_temperature', 'wind_speed', 'surface_snow_thickness'])
                    if len(complete_data) > 0:
                        st.write(f"**Komplette målinger:** {len(complete_data)} av {total_records} ({len(complete_data)/total_records*100:.1f}%)")
                        if len(complete_data) > 0:
                            first_complete = complete_data['referenceTime'].min()
                            last_complete = complete_data['referenceTime'].max()
                            st.write(f"**Beste dataperiode:** {first_complete.strftime('%d.%m.%Y %H:%M')} - {last_complete.strftime('%d.%m.%Y %H:%M')}")
                    else:
                        st.error("Ingen komplette målinger funnet!")

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
                # Filtrer ut NaN-verdier for plotting
                plot_data_clean = plot_data.dropna(subset=['air_temperature', 'wind_speed'], how='all')

                if len(plot_data_clean) == 0:
                    st.warning("Ingen gyldige temperatur- eller vinddata tilgjengelig for plotting")
                    st.info("Dette kan være normalt i sommerperioden med færre målinger")
                    return

                # Beregn vindkjøling for plotting hvis ML er tilgjengelig
                if checker.use_ml and 'air_temperature' in plot_data_clean.columns and 'wind_speed' in plot_data_clean.columns:
                    plot_data_copy = plot_data_clean.copy()
                    # Kun beregn vindkjøling hvor vi har både temp og vind
                    valid_mask = plot_data_copy['air_temperature'].notna() & plot_data_copy['wind_speed'].notna()
                    plot_data_copy.loc[valid_mask, 'wind_chill'] = plot_data_copy.loc[valid_mask].apply(
                        lambda row: checker.ml_detector.calculate_wind_chill(
                            row['air_temperature'], row['wind_speed']
                        ), axis=1
                    )
                    use_wind_chill = True
                    has_wind_chill_data = plot_data_copy['wind_chill'].notna().sum() > 0

                    # NYTT: Beregn snøfokk-risiko for alle datapunkter
                    plot_data_copy['snowdrift_risk'] = 'low'  # Default
                    for idx, row in plot_data_copy.iterrows():
                        if (pd.notna(row.get('wind_chill')) and pd.notna(row.get('wind_speed')) and
                            pd.notna(row.get('surface_snow_thickness'))):

                            # Bruk samme logikk som ML-detektoren
                            wind_chill = row['wind_chill']
                            wind_speed = row['wind_speed']
                            snow_depth = row['surface_snow_thickness']

                            # Sjekk kritiske kriterier (oppdatert til empirisk validerte vindterskler)
                            if (wind_chill < -15.0 and wind_speed > 10.0 and snow_depth > 0.26):
                                plot_data_copy.loc[idx, 'snowdrift_risk'] = 'high'
                            elif (wind_chill < -12.0 and wind_speed > 8.0 and snow_depth > 0.20):
                                plot_data_copy.loc[idx, 'snowdrift_risk'] = 'medium'
                else:
                    plot_data_copy = plot_data_clean.copy()
                    use_wind_chill = False
                    has_wind_chill_data = False

                # Opprett subplots basert på tilgjengelige data
                if use_wind_chill and has_wind_chill_data:
                    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10))
                else:
                    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6))
                fig.suptitle(f"{graph_title} | Målinger: {len(plot_data_clean)}")

                # NYTT: Funksjon for å legge til snøfokk-risikoperioder som bakgrunn
                def add_snowdrift_risk_background(ax, times, risks):
                    """Legg til fargede bakgrunnssoner for snøfokk-risiko."""
                    if 'snowdrift_risk' not in plot_data_copy.columns:
                        return

                    # Finn kontinuerlige risikoperioder
                    current_risk = None
                    start_time = None

                    for time, risk in zip(times, risks, strict=False):
                        if risk != current_risk:
                            # Avslutt forrige periode
                            if current_risk in ['medium', 'high'] and start_time is not None:
                                color = 'red' if current_risk == 'high' else 'orange'
                                alpha = 0.2 if current_risk == 'high' else 0.15
                                ax.axvspan(start_time, time, color=color, alpha=alpha, zorder=0)

                            # Start ny periode
                            current_risk = risk
                            start_time = time

                    # Håndter siste periode
                    if current_risk in ['medium', 'high'] and start_time is not None:
                        color = 'red' if current_risk == 'high' else 'orange'
                        alpha = 0.2 if current_risk == 'high' else 0.15
                        ax.axvspan(start_time, times.iloc[-1], color=color, alpha=alpha, zorder=0)

                # Tell risikoperioder for informasjon
                if checker.use_ml and 'snowdrift_risk' in plot_data_copy.columns:
                    high_risk_count = (plot_data_copy['snowdrift_risk'] == 'high').sum()
                    medium_risk_count = (plot_data_copy['snowdrift_risk'] == 'medium').sum()
                    risk_info = f" | Snøfokk-risiko: {high_risk_count} kritisk, {medium_risk_count} advarsel"
                    fig.suptitle(f"{graph_title} | Målinger: {len(plot_data_clean)}{risk_info}")

                # 1. Temperatur
                temp_data = plot_data_copy['air_temperature'].dropna()
                if len(temp_data) > 0:
                    temp_times = plot_data_copy.loc[temp_data.index, 'referenceTime']
                    # Legg til snøfokk-bakgrunn først
                    if checker.use_ml and 'snowdrift_risk' in plot_data_copy.columns:
                        temp_risks = plot_data_copy.loc[temp_data.index, 'snowdrift_risk']
                        add_snowdrift_risk_background(ax1, temp_times, temp_risks)

                    ax1.plot(temp_times, temp_data, 'r-', label=f'Temperatur (°C) - {len(temp_data)} målinger', marker='o', markersize=3)
                    ax1.axhline(y=0, color='blue', linestyle='--', alpha=0.5, label='Frysepunkt')
                    if checker.use_ml:
                        ax1.axhline(y=-5, color='red', linestyle='--', alpha=0.7, label='Snøfokk-grense (-5°C)')
                else:
                    ax1.text(0.5, 0.5, 'Ingen temperaturdata tilgjengelig', ha='center', va='center', transform=ax1.transAxes)
                ax1.set_ylabel(TEMP_LABEL)
                ax1.legend()
                ax1.grid(True, alpha=0.3)

                # 2. Vind
                wind_data = plot_data_copy['wind_speed'].dropna()
                if len(wind_data) > 0:
                    wind_times = plot_data_copy.loc[wind_data.index, 'referenceTime']
                    # Legg til snøfokk-bakgrunn først
                    if checker.use_ml and 'snowdrift_risk' in plot_data_copy.columns:
                        wind_risks = plot_data_copy.loc[wind_data.index, 'snowdrift_risk']
                        add_snowdrift_risk_background(ax2, wind_times, wind_risks)

                    ax2.plot(wind_times, wind_data, 'g-', label=f'Vindstyrke (m/s) - {len(wind_data)} målinger', marker='o', markersize=3)
                    if checker.use_ml:
                        ax2.axhline(y=10, color='red', linestyle='--', alpha=0.7, label='Snøfokk kritisk (10 m/s)')
                        ax2.axhline(y=8, color='orange', linestyle='--', alpha=0.5, label='Snøfokk advarsel (8 m/s)')
                    else:
                        ax2.axhline(y=10, color='orange', linestyle='--', alpha=0.5, label='Tradisjonell grense (10 m/s)')
                else:
                    ax2.text(0.5, 0.5, 'Ingen vinddata tilgjengelig', ha='center', va='center', transform=ax2.transAxes)
                ax2.set_ylabel(WIND_LABEL)
                ax2.legend()
                ax2.grid(True, alpha=0.3)

                # 3. Vindkjøling (kun hvis ML er tilgjengelig og vi har data)
                if use_wind_chill and has_wind_chill_data:
                    chill_data = plot_data_copy['wind_chill'].dropna()
                    if len(chill_data) > 0:
                        chill_times = plot_data_copy.loc[chill_data.index, 'referenceTime']
                        # Legg til snøfokk-bakgrunn først
                        if 'snowdrift_risk' in plot_data_copy.columns:
                            chill_risks = plot_data_copy.loc[chill_data.index, 'snowdrift_risk']
                            add_snowdrift_risk_background(ax3, chill_times, chill_risks)

                        ax3.plot(chill_times, chill_data, 'purple', label=f'Vindkjøling (°C) - {len(chill_data)} målinger', marker='o', markersize=3)
                        ax3.axhline(y=-15, color='red', linestyle='--', alpha=0.7, label='Snøfokk kritisk (-15°C)')
                        ax3.axhline(y=-12, color='orange', linestyle='--', alpha=0.5, label='Snøfokk advarsel (-12°C)')
                        ax3.set_ylabel('Vindkjøling (°C)')
                        ax3.legend()
                        ax3.grid(True, alpha=0.3)
                        ax3.set_xlabel('Tid')
                    else:
                        ax3.text(0.5, 0.5, 'Vindkjøling kunne ikke beregnes', ha='center', va='center', transform=ax3.transAxes)
                else:
                    ax2.set_xlabel('Tid')

                # Legg til forklaring av snøfokk-risikovisualiseringen
                if checker.use_ml and 'snowdrift_risk' in plot_data_copy.columns:
                    if high_risk_count > 0 or medium_risk_count > 0:
                        st.info("🌨️ **Snøfokk-risikoperioder markert i grafene:** "
                                f"🔴 Røde soner = Kritisk risiko ({high_risk_count} målinger), "
                                f"🟠 Oransje soner = Advarsel ({medium_risk_count} målinger)")

                # Rotér datoer for bedre lesbarhet
                for ax in fig.axes:
                    ax.tick_params(axis='x', rotation=45)

                # Juster layout med feilhåndtering
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    try:
                        plt.tight_layout()
                    except Exception:
                        plt.subplots_adjust(bottom=0.15, top=0.9)

                st.pyplot(fig)

                # NYTT: Nedbørtype-klassifisering
                st.markdown("---")
                st.subheader("🌧️ Nedbørtype-klassifisering (Validert Logikk)")

                # Debug validert logikk status
                st.write(f"🔍 **VALIDATED_LOGIC_AVAILABLE:** {VALIDATED_LOGIC_AVAILABLE}")
                st.write("🔍 **Vindkjøling beregnes automatisk** for forbedret klassifisering")

                with st.expander("Om nedbørtype-klassifiseringen"):
                    st.markdown("""
                    **Empirisk validert logikk basert på 149 episoder + vindkjøling:**
                    
                    **🌧️ Regn:** Temp > 0°C + snømengde minkende + vind < 8 m/s
                    **❄️ Snø:** Temp < 0°C + snømengde økende
                    **🌪️ Vindblåst snø:** Temp < 0°C + vind > 10 m/s + snømengde minkende
                    **🧊 Våt snø:** Temp rundt 0°C + snømengde økende
                    **🚨 Regn på snø:** Regn med vindkjøling < temp-2°C (GLATTFØRE-RISIKO!)
                    
                    **Vindkjøling-forbedringer:**
                    - Vindkjøling < -15°C + vind > 10 m/s → vindblåst snø
                    - Regn med vindkjøling-effekt → økt glattføre-risiko
                    - Grenseområde-klassifisering forbedret med vindkjøling
                    
                    **Kritiske terskler:**
                    - Median vindterskel for snømengde-reduksjon: 12.2 m/s
                    - Vindkjøling-terskel for ekstreme forhold: -15°C
                    
                    **Konfidensgrad:** Høy (mørke farger) / Medium (normal) / Lav (transparente)
                    """)

                if VALIDATED_LOGIC_AVAILABLE:
                    try:
                        precipitation_fig = checker.create_precipitation_classification_plot(df)
                        st.pyplot(precipitation_fig)

                        # Legg til debugging for tilpassede perioder
                        if len(df) > 0:
                            st.write(f"🔍 **Debug:** {len(df)} datapunkter lastet")
                            st.write(f"🔍 **Tidsperiode:** {df['referenceTime'].min()} til {df['referenceTime'].max()}")

                        # Legg til statistikk om klassifiseringen
                        df_classified = checker.classify_precipitation_types(df)
                        type_counts = df_classified['precipitation_type'].value_counts()

                        st.write(f"🔍 **Nedbørtyper funnet:** {list(type_counts.index)}")

                        # Info om visualisering
                        ingen_nedbor_count = type_counts.get('ingen_nedbor', 0)
                        total_count = len(df_classified)
                        active_precip_count = total_count - ingen_nedbor_count

                        st.info(f"ℹ️ **Visualiseringsinfo:** Av {total_count} timer vises {active_precip_count} timer med aktiv nedbør. "
                               f"{ingen_nedbor_count} timer med 'ingen nedbør' er skjult for bedre synlighet av værfenomener.")

                        if len(type_counts) > 0:
                            st.markdown("**Nedbørtype-fordeling i perioden:**")

                            # Vis som kolonner
                            type_cols = st.columns(min(len(type_counts), 4))
                            for i, (precip_type, count) in enumerate(type_counts.head(4).items()):
                                with type_cols[i]:
                                    st.metric(
                                        label=precip_type.replace('_', ' ').title(),
                                        value=f"{count} timer"
                                    )

                            # Vis glattføre-risiko basert på klassifisering
                            glattfore_episodes = 0
                            for _, row in df_classified.iterrows():
                                if row['precipitation_type'] in ['regn', 'regn_pa_sno']:
                                    temp = row.get('air_temperature', 0)

                                    # Prøv flere mulige kolonnenavn for nedbør
                                    precip = row.get(PRECIP_HOURLY_COL, 0)
                                    if precip == 0:
                                        precip = row.get('precipitation_amount', 0)
                                    if precip == 0:
                                        precip = row.get('precipitation_mm', 0)

                                    if temp < 2.0 and precip > 1.0:
                                        glattfore_episodes += 1

                            if glattfore_episodes > 0:
                                st.warning(f"⚠️ {glattfore_episodes} episoder med potensielt glattføre-risiko identifisert (regn ved lav temp)")
                            else:
                                st.success("✅ Ingen glattføre-risiko identifisert basert på nedbørtype-klassifisering")

                        # NY: Egen graf for glattføre-risiko episoder
                        st.markdown("---")
                        st.subheader("🧊 Detaljert Glattføre-risiko Analyse")

                        try:
                            slippery_fig = checker.create_slippery_road_risk_plot(df)
                            st.pyplot(slippery_fig)

                            # Statistikk for glattføre-episoder
                            df_classified = checker.classify_precipitation_types(df)
                            glattfore_types = ['regn', 'regn_pa_sno', 'usikker_grenseomrade']
                            df_risk = df_classified[df_classified['precipitation_type'].isin(glattfore_types)]

                            if len(df_risk) > 0:
                                st.markdown("**Glattføre-risiko episoder i perioden:**")

                                risk_cols = st.columns(3)
                                risk_counts = df_risk['precipitation_type'].value_counts()

                                for i, (risk_type, count) in enumerate(risk_counts.items()):
                                    if i < 3:
                                        with risk_cols[i]:
                                            risk_icon = "🌧️" if "regn" in risk_type else "⚠️"
                                            st.metric(
                                                label=f"{risk_icon} {risk_type.replace('_', ' ').title()}",
                                                value=f"{count} timer"
                                            )

                                # Temperaturstatistikk for risiko-episoder
                                temp_stats = df_risk['air_temperature'].describe()
                                st.markdown("**Temperaturforhold under glattføre-risiko:**")
                                temp_cols = st.columns(4)
                                with temp_cols[0]:
                                    st.metric("Min temp", f"{temp_stats['min']:.1f}°C")
                                with temp_cols[1]:
                                    st.metric("Gjennomsnitt", f"{temp_stats['mean']:.1f}°C")
                                with temp_cols[2]:
                                    st.metric("Max temp", f"{temp_stats['max']:.1f}°C")
                                with temp_cols[3]:
                                    critical_temp = len(df_risk[df_risk['air_temperature'] <= 0])
                                    st.metric("Timer ≤ 0°C", f"{critical_temp}")
                            else:
                                st.info("Ingen glattføre-risiko episoder funnet i denne perioden")

                        except Exception as e:
                            st.error(f"Feil ved generering av glattføre-risiko analyse: {e}")

                    except Exception as e:
                        st.error(f"Feil ved generering av nedbørtype-klassifisering: {e}")
                        st.info("Nedbørtype-klassifiseringen krever validert logikk-modul")
                else:
                    st.warning("Nedbørtype-klassifisering ikke tilgjengelig - mangler validert logikk-modul")

            else:
                st.warning("Ingen data å vise for valgt periode")
                ax2.set_ylabel('Vind (m/s)')
                ax2.set_xlabel('Tid')
                ax2.legend()
                ax2.grid(True, alpha=0.3)

                # Juster layout med feilhåndtering
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    try:
                        plt.tight_layout()
                    except Exception:
                        plt.subplots_adjust(bottom=0.15, top=0.9)

                st.pyplot(fig)

        else:
            st.error("Klarte ikke hente data. Kontroller nettverk eller API-nøkkel.")

    # Snøfokk-risiko seksjon (flyttet nederst)
    if df is not None and len(df) > 0:
        st.markdown("---")
        st.header("❄️ Snøfokk-risiko")

        st.markdown("""
        **Snøfokk oppstår når vindkjøling kombineres med løs puddersnø.** 
        Ved puddersnøforhold er vindkjøling den viktigste faktoren - når lufttemperaturen 
        blir kraftig redusert av vind, øker risikoen for snøtransport.
        """)

        # Snøfokk-analyse
        snowdrift_result = checker.analyze_snowdrift_risk(df)

        # Hovedresultat
        col_drift1, col_drift2 = st.columns([2, 1])

        with col_drift1:
            # Fargekoding
            if snowdrift_result['risk_level'] == 'high':
                st.error(f"🔴 **{snowdrift_result['message']}**")
            elif snowdrift_result['risk_level'] == 'medium':
                st.warning(f"🟡 **{snowdrift_result['message']}**")
            else:
                st.success(f"🟢 **{snowdrift_result['message']}**")

        with col_drift2:
            # Sjekk datakvalitet for snøfokk-analyse
            wind_missing_pct = (df['wind_speed'].isna().sum() / len(df)) * 100 if 'wind_speed' in df.columns else 100
            temp_missing_pct = (df['air_temperature'].isna().sum() / len(df)) * 100 if 'air_temperature' in df.columns else 100

            data_quality_warning = wind_missing_pct > 50 or temp_missing_pct > 50

            # Datakvalitetsindikator
            if data_quality_warning:
                st.warning(f"⚠️ **Datakvalitet:** {wind_missing_pct:.0f}% vinddata mangler")
            else:
                st.success("✅ **God datakvalitet**")

        # Detaljert analyse
        with st.expander("📊 Detaljert snøfokk-analyse", expanded=False):
            col_details1, col_details2 = st.columns(2)

            with col_details1:
                # Kriterieinfo
                if checker.use_ml:
                    st.markdown("""
                    **🤖 ML-BASERTE GRENSEVERDIER (2025):**
                    - **Vindkjøling:** < -15.0°C (dominerende faktor)
                    - **Vindstyrke:** > 10.0 m/s (empirisk median: 12.2 m/s)
                    - **Lufttemperatur:** < -5.0°C
                    - **Snødybde:** > 26cm
                    
                    *Vindkjøling har 73.1% viktighet i modellen*
                    """)
                else:
                    st.markdown("""
                    **📈 TRADISJONELLE KRITERIER (validert 2025):**
                    - **Vindstyrke:** ≥ 10 m/s (kritisk), ≥ 8 m/s (ideelle forhold)
                    - **Temperatur:** ≤ -1°C  
                    - **Snødybde:** ≥ 3 cm
                    - **Løssnø:** Tilgjengelig (ingen mildvær siste 24t)
                    """)

            with col_details2:
                # Vurderingsgrunnlag
                if 'factors' in snowdrift_result:
                    st.write("**🔍 Vurderingsgrunnlag:**")
                    for factor in snowdrift_result['factors']:
                        st.write(f"• {factor}")

                # ML-detaljer
                if checker.use_ml and 'ml_details' in snowdrift_result:
                    details = snowdrift_result['ml_details']
                    conditions = snowdrift_result.get('current_conditions', {})

                    st.write("**📊 Nåværende forhold:**")
                    if 'wind_chill' in details and pd.notna(details['wind_chill']):
                        st.write(f"• Vindkjøling: {details['wind_chill']:.1f}°C")
                    if 'wind_speed' in conditions and pd.notna(conditions['wind_speed']):
                        st.write(f"• Vindstyrke: {conditions['wind_speed']:.1f} m/s")
                    if 'temperature' in conditions and pd.notna(conditions['temperature']):
                        st.write(f"• Lufttemperatur: {conditions['temperature']:.1f}°C")
                    if 'snow_depth_cm' in conditions and pd.notna(conditions['snow_depth_cm']):
                        snow_cm = conditions['snow_depth_cm'] * 100 if conditions['snow_depth_cm'] < 10 else conditions['snow_depth_cm']
                        st.write(f"• Snødybde: {snow_cm:.1f} cm")

                # Tilleggsinformasjon
                if 'loose_snow' in snowdrift_result:
                    st.write(f"**❄️ Løssnøtilstand:** {snowdrift_result['loose_snow']}")

                if 'dynamics' in snowdrift_result and snowdrift_result['dynamics']:
                    st.info(f"**🌨️ Snødynamikk:** {snowdrift_result['dynamics']}")

                if 'seasonal_note' in snowdrift_result:
                    st.caption(snowdrift_result['seasonal_note'])

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
        st.caption("• Høyde: 639 moh")

    # Refresh-knapp for manuell oppdatering
    if st.button("Oppdater nå"):
        st.rerun()

if __name__ == "__main__":
    create_streamlit_app()
