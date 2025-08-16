#!/usr/bin/env python3
"""
Mobil-first versjon av live conditions app med forbedrede ytelse og UX
"""

import os
import warnings
from datetime import UTC, datetime, timedelta
from functools import lru_cache

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

# Konfigurer matplotlib og advarsler
warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')

# Last miljøvariabler
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


class MobileWeatherApp:
    """Mobil-optimalisert værapp"""
    
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

    def get_weather_data_cached(self, hours_back: int = 24) -> pd.DataFrame | None:
        """Hent værdata med avansert caching"""
        
        def fetch_weather():
            return self._fetch_weather_from_api(hours_back)
        
        # Bruk kontekst-bevisst caching
        location_context = get_location_context()
        cache_ttl = location_context.get('refresh_interval', 300)
        
        return DataCache.get_cached_data(
            'weather_data',
            fetch_weather,
            ttl_seconds=cache_ttl,
            params={'station': self.station_id, 'hours': hours_back}
        )
    
    def _fetch_weather_from_api(self, hours_back: int) -> pd.DataFrame | None:
        """Hent værdata fra API (faktisk HTTP-kall)"""
        try:
            if not self.frost_client_id:
                return None

            # Tidsperiode
            end_time = datetime.now(UTC)
            start_time = end_time - timedelta(hours=hours_back)
            
            fmt = "%Y-%m-%dT%H:%M:%SZ"
            start_iso = start_time.strftime(fmt)
            end_iso = end_time.strftime(fmt)

            # Kritiske elementer for mobil (redusert for raskere lasting)
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
            response = requests.get(url, params=params, auth=(self.frost_client_id, ''), timeout=30)
            
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

    def analyze_snowdrift_risk(self, df: pd.DataFrame) -> dict:
        """Analyser snøfokk-risiko med forbedret fallback"""
        if df.empty:
            return {
                'risk_level': 'unknown',
                'message': 'Ingen data tilgjengelig',
                'confidence': 0.0
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
                    return self.ml_detector.predict_snowdrift_risk(features)
                except Exception:
                    # Fall back to simple analysis if ML fails
                    pass
            
            # Fallback til enkel analyse
            return simple_snowdrift_analysis(temp, wind, snow_depth)
            
        except Exception as e:
            return {
                'risk_level': 'unknown',
                'message': f'Analysefeil: {str(e)[:50]}...',
                'confidence': 0.0
            }

    def analyze_slippery_risk(self, df: pd.DataFrame) -> dict:
        """Analyser glattføre-risiko med forbedret fallback"""
        if df.empty:
            return {
                'risk_level': 'unknown', 
                'message': 'Ingen data tilgjengelig',
                'confidence': 0.0
            }

        try:
            latest = df.iloc[-1]
            
            temp = latest.get('air_temperature', None)
            surface_temp = latest.get('surface_temperature', None)
            humidity = latest.get('relative_humidity', None)
            
            # Bruk forbedret analyse
            return simple_slippery_analysis(temp, surface_temp, humidity)
                
        except Exception as e:
            return {
                'risk_level': 'unknown',
                'message': f'Analysefeil: {str(e)[:50]}...',
                'confidence': 0.0
            }

    def run_mobile_app(self):
        """Kjør mobil-app"""
        # Konfigurer mobil layout
        MobileLayout.configure_mobile_page()
        
        # Header
        MobileLayout.show_mobile_header()
        
        # Sjekk API-nøkkel
        if not self.frost_client_id:
            st.error("⚠️ FROST_CLIENT_ID mangler i .env-filen")
            st.info("Legg til din API-nøkkel for å bruke appen")
            return
        
        # Last værdata med forbedret caching
        with st.spinner("📡 Henter værdata..."):
            df = self.get_weather_data_cached(24)
        
        if df is None or df.empty:
            st.error("❌ Kunne ikke hente værdata")
            st.info("Sjekk internettforbindelse og API-nøkkel")
            return
        
        # Valider datakvalitet
        validation = validate_weather_data(df)
        if not validation['valid']:
            st.error("❌ Datakvalitet for dårlig for pålitelig analyse")
            with st.expander("🔍 Datakvalitet-detaljer"):
                st.write("**Problemer:**")
                for issue in validation['issues']:
                    st.write(f"• {issue}")
                st.write("**Anbefalinger:**")
                for rec in validation['recommendations']:
                    st.write(f"• {rec}")
            return
        
        # Vis datakvalitet
        if validation['score'] < 80:
            st.warning(f"⚠️ Datakvalitet: {validation['score']:.0f}%")
        else:
            st.success(f"✅ Datakvalitet: {validation['score']:.0f}%")
        
        # Vis nåværende forhold  
        # Normalize sentinel values (negative snow depth) before display/analysis
        if 'surface_snow_thickness' in df.columns:
            df['surface_snow_thickness'] = df['surface_snow_thickness'].apply(lambda x: x if pd.notna(x) and x >= 0 else None)

        MobileLayout.show_current_conditions(df)
        
        # Analyser risiko
        with st.spinner("🔍 Analyserer risiko..."):
            snowdrift_risk = self.analyze_snowdrift_risk(df)
            slippery_risk = self.analyze_slippery_risk(df)
        
        # Vis risikokort
        MobileLayout.show_risk_cards(snowdrift_risk, slippery_risk)
        
        # Hovedchart (alltid synlig)
        st.markdown("---")
        MobileLayout.show_mobile_chart(df)
        
        # Dato/tid kontroller
        st.markdown("---")
        st.markdown("### 📅 Tidsperiode")
        
        col1, col2 = st.columns(2)
        with col1:
            hours_back = st.selectbox(
                "Timer tilbake:",
                options=[6, 12, 24, 48, 72],
                index=2,  # Default 24 timer
                key="hours_selector"
            )
        
        with col2:
            if st.button("🔄 Oppdater data", type="primary"):
                st.rerun()
        
        # Last oppdaterte data hvis tidsperiode er endret
        if hours_back != 24:
            with st.spinner("� Henter nye data..."):
                df_new = self.get_weather_data(hours_back)
                if df_new is not None and not df_new.empty:
                    df = df_new
                    # Oppdater analyser
                    snowdrift_risk = self.analyze_snowdrift_risk(df)
                    slippery_risk = self.analyze_slippery_risk(df)
                    # Vis oppdaterte risikokort
                    MobileLayout.show_risk_cards(snowdrift_risk, slippery_risk)
        
        # Detaljert informasjon i ekspandable seksjoner (vises som standard for mobil)
        with st.expander("🔍 Detaljert risikoanalyse", expanded=True):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**🌪️ Snøfokk-detaljer:**")
                st.write(f"Nivå: {snowdrift_risk['risk_level']}")
                st.write(f"Tillit: {snowdrift_risk['confidence']:.1%}")
                if 'factors' in snowdrift_risk:
                    for factor in snowdrift_risk['factors'][:3]:  # Begrenset for mobil
                        st.caption(f"• {factor}")

            with col2:
                st.markdown("**🧊 Glattføre-detaljer:**")
                st.write(f"Nivå: {slippery_risk['risk_level']}")
                st.write(f"Tillit: {slippery_risk['confidence']:.1%}")

        with st.expander("ℹ️ Om analysene", expanded=True):
            st.markdown("""
            **🌪️ Snøfokk-kriterier:**
            - Vindstyrke > 8-12 m/s
            - Temperatur < -1°C til -5°C  
            - Tilgjengelig løssnø

            **🧊 Glattføre-kriterier:**
            - Temperatur rundt frysepunktet (-2°C til +2°C)
            - Høy luftfuktighet (>85%)
            - Veioverflate-temperatur prioriteres
            """)
        
        # Kontroller
        MobileLayout.show_mobile_controls()
        
        # Footer
        MobileLayout.show_mobile_footer()
        
        # Auto-refresh (hver 5 min)
        st.markdown("""
        <script>
        setTimeout(function(){
            window.location.reload();
        }, 300000); // 5 minutter
        </script>
        """, unsafe_allow_html=True)


def main():
    """Hovedfunksjon"""
    # Aktiver PWA-funksjonalitet for standalone app
    setup_pwa()
    
    app = MobileWeatherApp()
    app.run_mobile_app()


if __name__ == "__main__":
    main()
