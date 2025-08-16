"""
Forbedret mobil weather app med alle de realistiske forbedringene implementert
"""
#!/usr/bin/env python3

import os
import warnings
from datetime import UTC, datetime, timedelta
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Import komponenter
from components.mobile_layout import MobileLayout
from components.pwa_integration import setup_pwa
from components.performance_cache import DataCache, ProgressiveLoader, ErrorHandler
from components.mobile_enhancements import setup_mobile_enhancements, get_location_context, is_near_gullingen
from components.weather_utils import (
    simple_snowdrift_analysis, simple_slippery_analysis,
    calculate_wind_chill, validate_weather_data
)

# Konfigurer miljø
warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')
load_dotenv()

# Import eksisterende logikk med fallback
try:
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    sys.path.insert(0, parent_dir)
    
    from validert_glattfore_logikk import detect_precipitation_type
    VALIDATED_LOGIC_AVAILABLE = True
except ImportError:
    VALIDATED_LOGIC_AVAILABLE = False

try:
    from ml_snowdrift_detector import MLSnowdriftDetector
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False


class EnhancedMobileWeatherApp:
    """Forbedret mobil-optimalisert værapp med alle realistiske forbedringer"""
    
    def __init__(self):
        self.frost_client_id = os.getenv('FROST_CLIENT_ID')
        self.station_id = os.getenv("WEATHER_STATION", "SN46220")
        self.cache_duration = 3600
        
        # Initialiser ML hvis tilgjengelig
        if ML_AVAILABLE:
            self.ml_detector = MLSnowdriftDetector()
            self.use_ml = True
        else:
            self.ml_detector = None
            self.use_ml = False
    
    def get_weather_data_progressive(self, hours_back: int = 24) -> dict:
        """Hent værdata med progressive loading"""
        
        def fetch_weather(hours):
            return self._fetch_weather_from_frost(hours)
        
        # Bruk kontekst-bevisst caching basert på lokasjon
        location_context = get_location_context()
        cache_ttl = location_context.get('refresh_interval', 300)
        
        # Progressive loading - kritiske data først
        result = {
            'critical': None,
            'detailed': None,
            'loading_detailed': False
        }
        
        # Last kritiske data (siste 3 timer)
        try:
            critical_data = DataCache.get_cached_data(
                'critical_weather',
                lambda: fetch_weather(3),
                ttl_seconds=min(cache_ttl, 60),  # Max 1 minutt for kritisk data
                params={'type': 'critical', 'hours': 3, 'station': self.station_id}
            )
            result['critical'] = critical_data
        except Exception as e:
            st.error(f"Kunne ikke hente kritiske værdata: {e}")
            return result
        
        # Last detaljerte data hvis ønsket
        if st.session_state.get('load_detailed', True):
            result['loading_detailed'] = True
            try:
                detailed_data = DataCache.get_cached_data(
                    'detailed_weather',
                    lambda: fetch_weather(hours_back),
                    ttl_seconds=cache_ttl,
                    params={'type': 'detailed', 'hours': hours_back, 'station': self.station_id}
                )
                result['detailed'] = detailed_data
                result['loading_detailed'] = False
            except Exception as e:
                st.warning(f"Kunne ikke hente detaljerte data: {e}")
                result['loading_detailed'] = False
        
        return result
    
    def _fetch_weather_from_frost(self, hours_back: int) -> pd.DataFrame | None:
        """Hent værdata fra Frost API"""
        if not self.frost_client_id:
            return None
        
        try:
            # Tidsperiode
            end_time = datetime.now(UTC)
            start_time = end_time - timedelta(hours=hours_back)
            
            fmt = "%Y-%m-%dT%H:%M:%SZ"
            start_iso = start_time.strftime(fmt)
            end_iso = end_time.strftime(fmt)

            # Elementer optimalisert for mobil
            elements = [
                'air_temperature',
                'wind_speed', 
                'wind_from_direction',
                'surface_snow_thickness',
                'sum(precipitation_amount PT1H)',
                'surface_temperature',
                'relative_humidity'
            ]

            url = 'https://frost.met.no/observations/v0.jsonld'
            params = {
                'sources': self.station_id,
                'elements': ','.join(elements),
                'referencetime': f'{start_iso}/{end_iso}',
                'timeoffsets': 'PT0H',
                'maxage': 'PT3H'
            }

            import requests
            response = requests.get(
                url, 
                params=params, 
                auth=(self.frost_client_id, ''), 
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if not data.get('data'):
                    return None

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
                    return None

                df = pd.DataFrame(records)
                df['time'] = pd.to_datetime(df['time'])
                df = df.sort_values('time').reset_index(drop=True)
                
                return df
                
            else:
                return None
                
        except Exception as e:
            print(f"Feil ved henting av værdata: {e}")
            return None
    
    def analyze_snowdrift_risk_enhanced(self, df: pd.DataFrame) -> dict:
        """Forbedret snøfokk-analyse med ML og fallbacks"""
        if df.empty:
            return {
                'risk_level': 'unknown',
                'message': 'Ingen data tilgjengelig',
                'confidence': 0.0,
                'factors': []
            }

        try:
            latest = df.iloc[-1]
            
            # Hent verdier
            temp = latest.get('air_temperature', None)
            wind = latest.get('wind_speed', None)  
            snow_depth = latest.get('surface_snow_thickness', None)
            
            # Bruk ML hvis tilgjengelig og data er komplett
            if self.use_ml and pd.notna(temp) and pd.notna(wind):
                try:
                    features = {
                        'wind_speed': wind,
                        'air_temperature': temp, 
                        'snow_depth': snow_depth * 100 if pd.notna(snow_depth) and snow_depth < 10 else snow_depth
                    }
                    ml_result = self.ml_detector.predict_snowdrift_risk(features)
                    ml_result['source'] = 'ML model'
                    return ml_result
                except Exception:
                    # Fall back to simple analysis if ML fails
                    pass
            
            # Fallback til enkel analyse
            simple_result = simple_snowdrift_analysis(temp, wind, snow_depth)
            simple_result['source'] = 'Simple heuristics'
            return simple_result
            
        except Exception as e:
            return {
                'risk_level': 'unknown',
                'message': f'Analysefeil: {str(e)[:50]}...',
                'confidence': 0.0,
                'factors': ['Feil i analyse'],
                'source': 'Error handler'
            }

    def analyze_slippery_risk_enhanced(self, df: pd.DataFrame) -> dict:
        """Forbedret glattføre-analyse"""
        if df.empty:
            return {
                'risk_level': 'unknown', 
                'message': 'Ingen data tilgjengelig',
                'confidence': 0.0,
                'factors': []
            }

        try:
            latest = df.iloc[-1]
            
            temp = latest.get('air_temperature', None)
            surface_temp = latest.get('surface_temperature', None)
            humidity = latest.get('relative_humidity', None)
            
            # Bruk forbedret analyse
            result = simple_slippery_analysis(temp, surface_temp, humidity)
            result['source'] = 'Enhanced analysis'
            return result
                
        except Exception as e:
            return {
                'risk_level': 'unknown',
                'message': f'Analysefeil: {str(e)[:50]}...',
                'confidence': 0.0,
                'factors': ['Feil i analyse'],
                'source': 'Error handler'
            }
    
    def show_app_status(self):
        """Vis app-status og forbedringer"""
        
        # Vis cache status hvis i debug-modus
        if st.sidebar.checkbox("🔧 Debug-modus", value=False):
            st.sidebar.markdown("### 📊 Cache Status")
            cache_stats = DataCache.get_cache_stats()
            st.sidebar.json(cache_stats)
            
            # Location context
            st.sidebar.markdown("### 📍 Lokasjon")
            location_context = get_location_context()
            st.sidebar.json(location_context)
            
            # Clear cache button
            if st.sidebar.button("🗑️ Tøm cache"):
                DataCache.invalidate_cache()
                st.sidebar.success("Cache tømt!")
                st.rerun()
        
        # Vis forbedringer som er aktive
        if is_near_gullingen():
            st.success("📍 Du er nær Gullingen - høy oppdateringsfrekvens aktivert!")
    
    def run_enhanced_mobile_app(self):
        """Kjør forbedret mobil-app"""
        # Konfigurer mobil layout
        MobileLayout.configure_mobile_page()
        
        # Setup alle mobile enhancements
        setup_mobile_enhancements()
        
        # Show app status
        self.show_app_status()
        
        # Header
        MobileLayout.show_mobile_header()
        
        # Sjekk API-nøkkel
        if not self.frost_client_id:
            st.error("⚠️ FROST_CLIENT_ID mangler i .env-filen")
            st.info("Legg til din API-nøkkel for å bruke appen")
            return
        
        # Progressive loading med forbedrede features
        self.run_progressive_app()
    
    def run_progressive_app(self):
        """Kjør progressive loading"""
        
        # Show skeleton loaders while loading
        progress_container = st.empty()
        critical_container = st.empty()
        detailed_container = st.empty()
        
        with progress_container:
            st.info("📡 Henter kritiske værdata...")
            MobileLayout.show_skeleton_loader("card")
        
        # Hent data progressivt
        progressive_data = self.get_weather_data_progressive(24)
        
        # Clear skeleton loader
        progress_container.empty()
        
        # Vis kritiske data først
        critical_df = progressive_data.get('critical')
        if critical_df is None or critical_df.empty:
            st.error("❌ Kunne ikke hente værdata")
            st.info("Sjekk internettforbindelse og API-nøkkel")
            return
        
        # Vis kritisk informasjon
        with critical_container:
            self.show_critical_weather_info(critical_df)
        
        # Håndter detaljerte data
        detailed_df = progressive_data.get('detailed', critical_df)
        loading_detailed = progressive_data.get('loading_detailed', False)
        
        with detailed_container:
            if loading_detailed:
                st.info("🔄 Laster detaljerte data...")
                MobileLayout.show_skeleton_loader("chart")
            else:
                self.show_detailed_weather_info(detailed_df)
    
    def show_critical_weather_info(self, df: pd.DataFrame):
        """Vis kritisk værinformasjon"""
        
        # Normalize data
        if 'surface_snow_thickness' in df.columns:
            df['surface_snow_thickness'] = df['surface_snow_thickness'].apply(
                lambda x: x if pd.notna(x) and x >= 0 else None
            )
        
        # Valider datakvalitet
        validation = validate_weather_data(df)
        if not validation['valid']:
            st.error("❌ Datakvalitet for dårlig for pålitelig analyse")
            with st.expander("🔍 Datakvalitet-detaljer"):
                for issue in validation['issues']:
                    st.write(f"• {issue}")
            return
        
        # Vis kvalitetsindikator
        if validation['score'] < 80:
            st.warning(f"⚠️ Datakvalitet: {validation['score']:.0f}%")
        else:
            st.success(f"✅ Datakvalitet: {validation['score']:.0f}%")
        
        # Vis nåværende forhold
        MobileLayout.show_current_conditions(df)
        
        # Analyser risiko med forbedrede algoritmer
        with st.spinner("🔍 Analyserer risiko..."):
            snowdrift_risk = self.analyze_snowdrift_risk_enhanced(df)
            slippery_risk = self.analyze_slippery_risk_enhanced(df)
        
        # Vis risikokort
        MobileLayout.show_risk_cards(snowdrift_risk, slippery_risk)
        
        # Vis kilde for analysen
        col1, col2 = st.columns(2)
        with col1:
            if 'source' in snowdrift_risk:
                st.caption(f"🌪️ Kilde: {snowdrift_risk['source']}")
        with col2:
            if 'source' in slippery_risk:
                st.caption(f"🧊 Kilde: {slippery_risk['source']}")
    
    def show_detailed_weather_info(self, df: pd.DataFrame):
        """Vis detaljert værinformasjon"""
        
        # Chart med progressive loading
        st.markdown("---")
        MobileLayout.show_mobile_chart(df)
        
        # Kontroller
        st.markdown("---")
        st.markdown("### 📅 Kontroller")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            hours_back = st.selectbox(
                "Tidsperiode:",
                options=[6, 12, 24, 48, 72],
                index=2,  # Default 24 timer
                key="hours_selector"
            )
        
        with col2:
            if st.button("🔄 Oppdater", type="primary"):
                # Clear relevant cache and reload
                DataCache.invalidate_cache("weather")
                st.rerun()
        
        with col3:
            if st.button("📱 PWA Info"):
                st.info("""
                💡 **Installer som app:**
                - Chrome: Trykk menyen → "Installer app"
                - Safari: Del → "Legg til på startskjerm"
                """)
        
        # Ekspandable detaljer
        with st.expander("🔍 Detaljert analyse", expanded=False):
            
            # Reanalyse med valgt tidsperiode hvis endret
            if hours_back != 24:
                with st.spinner("🔄 Henter nye data..."):
                    new_data = self.get_weather_data_progressive(hours_back)
                    new_df = new_data.get('detailed') or new_data.get('critical')
                    if new_df is not None and not new_df.empty:
                        df = new_df
                        snowdrift_risk = self.analyze_snowdrift_risk_enhanced(df)
                        slippery_risk = self.analyze_slippery_risk_enhanced(df)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**🌪️ Snøfokk:**")
                            st.write(f"Nivå: {snowdrift_risk['risk_level']}")
                            st.write(f"Tillit: {snowdrift_risk['confidence']:.1%}")
                        with col2:
                            st.markdown("**🧊 Glattføre:**")
                            st.write(f"Nivå: {slippery_risk['risk_level']}")
                            st.write(f"Tillit: {slippery_risk['confidence']:.1%}")
            
            # Vis kriterier
            st.markdown("""
            **📊 Analysekriterier:**
            
            🌪️ **Snøfokk:**
            - Vind > 8-12 m/s  
            - Temp: -1°C til -5°C
            - Tilgjengelig snø
            
            🧊 **Glattføre:**
            - Temp: -2°C til +2°C
            - Luftfuktighet > 85%
            - Veioverflate-temp
            """)
        
        # Footer med forbedret informasjon
        MobileLayout.show_mobile_footer()


def main():
    """Hovedfunksjon med forbedringer"""
    # PWA setup
    setup_pwa()
    
    # Initialiser og kjør app
    app = EnhancedMobileWeatherApp()
    app.run_enhanced_mobile_app()


if __name__ == "__main__":
    main()
