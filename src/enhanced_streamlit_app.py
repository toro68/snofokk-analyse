#!/usr/bin/env python3
"""
Forbedret Streamlit Admin/Analysis UI med avansert caching og PWA-funksjoner
Port 8501 for desktop/admin bruk
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

# Import det nye cache-systemet
from components.performance_cache import DataCache, ProgressiveLoader, ErrorHandler

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
    from validert_glattfore_logikk import detect_precipitation_type
    VALIDATED_LOGIC_AVAILABLE = True
except ImportError:
    VALIDATED_LOGIC_AVAILABLE = False
    print("Validert glattføre-logikk ikke tilgjengelig")

# Importere hjelpeklasser fra original app
try:
    from live_conditions_app import LiveConditionsChecker, add_snowdrift_risk_background
    LIVE_CONDITIONS_AVAILABLE = True
except ImportError:
    LIVE_CONDITIONS_AVAILABLE = False
    print("Live conditions checker ikke tilgjengelig")


def configure_streamlit_admin():
    """Konfigurer Streamlit for admin/desktop bruk"""
    st.set_page_config(
        page_title="Admin/Analysis UI - Føreforhold Gullingen",
        page_icon="🏔️",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'Get Help': None,
            'Report a bug': None,
            'About': """
            # Admin/Analysis UI for Føreforhold
            
            Avansert analysetool for værdata og føreforhold ved Gullingen Skisenter.
            
            **Funksjoner:**
            - Sanntids væranalyse
            - Historisk dataanalyse  
            - ML-basert snøfokk-prediksjon
            - Avansert caching for ytelse
            - Progressive loading
            
            **Tekniske detaljer:**
            - Port: 8501 (admin)
            - Cache: TTL-basert system
            - API: Met.no Frost API
            """
        }
    )


def show_admin_header():
    """Vis admin header med systeminfo"""
    st.markdown("""
    <div style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); 
                padding: 1rem; border-radius: 10px; margin-bottom: 2rem; color: white;">
        <h1 style="margin: 0; font-size: 2rem;">🏔️ Admin/Analysis UI - Føreforhold</h1>
        <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">
            Avansert analysetool for Gullingen Skisenter • Port 8501 • Cache aktivert
        </p>
    </div>
    """, unsafe_allow_html=True)


def show_cache_status():
    """Vis cache-status i sidebar"""
    with st.sidebar:
        st.markdown("### 📊 Cache Status")
        
        cache_stats = DataCache.get_cache_stats()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Cache oppføringer", cache_stats.get('entries', 0))
        with col2:
            newest_age = cache_stats.get('newest_age')
            if newest_age is not None:
                st.metric("Nyeste alder", f"{newest_age:.0f}s")
            else:
                st.metric("Nyeste alder", "N/A")
        
        # Cache kontroller
        st.markdown("### 🔧 Cache Kontroll")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Tøm Cache", use_container_width=True):
                DataCache.invalidate_cache()
                st.success("Cache tømt!")
                st.rerun()
        
        with col2:
            if st.button("🔄 Tøm Værdata", use_container_width=True):
                DataCache.invalidate_cache("weather")
                st.success("Værdata tømt!")
                st.rerun()


def show_admin_controls():
    """Vis admin-kontroller"""
    with st.sidebar:
        st.markdown("### ⚙️ Admin Kontroller")
        
        # Environment info
        with st.expander("🔍 Systeminfo", expanded=False):
            st.write("**Python miljø:**")
            st.code(f"""
STREAMLIT_VERSION: {st.__version__}
CACHE_ENTRIES: {DataCache.get_cache_stats()['entries']}
ML_AVAILABLE: {ML_AVAILABLE}
VALIDATED_LOGIC: {VALIDATED_LOGIC_AVAILABLE}
LIVE_CONDITIONS: {LIVE_CONDITIONS_AVAILABLE}
            """)
        
        # Performance settings
        with st.expander("⚡ Ytelsesinnstillinger", expanded=False):
            st.markdown("**Cache TTL (sekunder):**")
            
            critical_ttl = st.slider("Kritiske data", 30, 300, 60)
            detailed_ttl = st.slider("Detaljerte data", 60, 600, 300)
            
            st.session_state['cache_settings'] = {
                'critical_ttl': critical_ttl,
                'detailed_ttl': detailed_ttl
            }
        
        # Data sources
        with st.expander("📡 Datakilder", expanded=False):
            st.markdown("**API Status:**")
            
            # Test API tilkobling
            try:
                response = requests.get("https://frost.met.no/status", timeout=5)
                if response.status_code == 200:
                    st.success("✅ Met.no Frost API: Online")
                else:
                    st.warning(f"⚠️ Met.no Frost API: Status {response.status_code}")
            except Exception as e:
                st.error(f"❌ Met.no Frost API: Offline ({str(e)[:30]}...)")


def enhanced_weather_data_fetch(checker, **kwargs):
    """Forbedret værdata-henting med caching"""
    
    def fetch_func():
        """Intern funksjon for å hente data"""
        if LIVE_CONDITIONS_AVAILABLE:
            return checker.get_current_weather_data(**kwargs)
        else:
            # Fallback hvis live conditions ikke er tilgjengelig
            return pd.DataFrame()
    
    # Bruk cache med konfigurerbare TTL-verdier
    cache_settings = st.session_state.get('cache_settings', {
        'critical_ttl': 60,
        'detailed_ttl': 300
    })
    
    # Bestem TTL basert på data type
    is_critical = kwargs.get('hours_back', 24) <= 6
    ttl = cache_settings['critical_ttl'] if is_critical else cache_settings['detailed_ttl']
    
    return DataCache.get_cached_data(
        key='weather_data',
        fetch_func=fetch_func,
        ttl_seconds=ttl,
        params=kwargs
    )


def show_enhanced_weather_analysis():
    """Hovedseksjon for væranalyse med forbedret caching"""
    
    if not LIVE_CONDITIONS_AVAILABLE:
        st.error("❌ Live conditions checker ikke tilgjengelig. Kan ikke vise væranalyse.")
        return
    
    checker = LiveConditionsChecker()
    
    # Progressive loading setup
    st.markdown("### 🌤️ Væranalyse")
    
    # Innstillinger i ekspander
    with st.expander("⚙️ Innstillinger", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            hours_back = st.slider("Timer tilbake", 6, 168, 24)
            
        with col2:
            station_id = st.text_input("Stasjons-ID", value=checker.station_id)
            
        with col3:
            auto_refresh = st.checkbox("Auto-refresh", value=True)
            if auto_refresh:
                refresh_interval = st.slider("Refresh interval (sek)", 30, 300, 60)
    
    # Progressive loading med skeleton
    loading_container = st.container()
    data_container = st.container()
    
    with loading_container:
        with st.spinner("Laster værdata..."):
            # Steg 1: Last kritiske data først (progressive loading)
            if hours_back <= 6:
                # For korte perioder, last alt på en gang
                try:
                    df = enhanced_weather_data_fetch(
                        checker, 
                        hours_back=hours_back
                    )
                    
                    if df is not None and len(df) > 0:
                        st.success(f"✅ Lastet {len(df)} målinger for siste {hours_back} timer")
                    else:
                        st.warning("⚠️ Ingen data tilgjengelig")
                        return
                        
                except Exception as e:
                    st.error(f"❌ Feil ved datahenting: {e}")
                    return
            else:
                # For lengre perioder, bruk progressive loading
                with st.status("Laster data progressivt...", expanded=True) as status:
                    st.write("🔄 Laster kritiske data...")
                    
                    # Først kritiske data (siste 3 timer)
                    critical_df = enhanced_weather_data_fetch(
                        checker, 
                        hours_back=3
                    )
                    
                    if critical_df is not None and len(critical_df) > 0:
                        st.write(f"✅ Kritiske data lastet ({len(critical_df)} målinger)")
                    
                    st.write("🔄 Laster full dataset...")
                    
                    # Deretter full dataset
                    df = enhanced_weather_data_fetch(
                        checker, 
                        hours_back=hours_back
                    )
                    
                    if df is not None and len(df) > 0:
                        st.write(f"✅ Full dataset lastet ({len(df)} målinger)")
                        status.update(label="Data lastet!", state="complete", expanded=False)
                    else:
                        st.write("⚠️ Ingen utvidet data tilgjengelig")
                        df = critical_df  # Bruk kritiske data som fallback
    
    # Vis data i container
    with data_container:
        if df is not None and len(df) > 0:
            show_enhanced_data_analysis(df, checker)
        else:
            st.warning("Ingen data å vise")


def show_enhanced_data_analysis(df, checker):
    """Vis forbedret dataanalyse"""
    
    st.markdown("### 📊 Dataanalyse")
    
    # Hovedmetrikker med forbedret layout
    col1, col2, col3, col4 = st.columns(4)
    
    latest = df.iloc[-1]
    
    with col1:
        temp = latest.get('air_temperature', np.nan)
        if pd.notna(temp):
            st.metric(
                "🌡️ Temperatur", 
                f"{temp:.1f}°C",
                delta=None,
                help="Lufttemperatur siste måling"
            )
        else:
            st.metric("🌡️ Temperatur", "N/A")
    
    with col2:
        wind = latest.get('wind_speed', np.nan)
        if pd.notna(wind):
            # Beregn vindstyrke kategori
            if wind < 3:
                wind_desc = "Svak"
            elif wind < 8:
                wind_desc = "Moderat"
            elif wind < 13:
                wind_desc = "Frisk"
            else:
                wind_desc = "Sterk"
                
            st.metric(
                "💨 Vind", 
                f"{wind:.1f} m/s",
                delta=wind_desc,
                help="Vindstyrke siste måling"
            )
        else:
            st.metric("💨 Vind", "N/A")
    
    with col3:
        snow = latest.get('surface_snow_thickness', np.nan)
        if pd.notna(snow):
            st.metric(
                "❄️ Snødybde", 
                f"{snow:.0f} cm",
                delta=None,
                help="Snødybde siste måling"
            )
        else:
            st.metric("❄️ Snødybde", "N/A")
    
    with col4:
        # Beregn overall risiko
        if all(pd.notna([temp, wind, snow])):
            # Enkel risikoberegning
            temp_risk = 1 if temp < -5 else 0
            wind_risk = 1 if wind > 10 else 0
            snow_risk = 1 if snow > 10 else 0
            
            total_risk = temp_risk + wind_risk + snow_risk
            
            if total_risk >= 2:
                risk_level = "🔴 Høy"
                risk_color = "red"
            elif total_risk == 1:
                risk_level = "🟡 Moderat"
                risk_color = "orange"
            else:
                risk_level = "🟢 Lav"
                risk_color = "green"
                
            st.metric(
                "⚠️ Samlet Risiko", 
                risk_level,
                help="Automatisk risikovurdering basert på temp, vind og snø"
            )
        else:
            st.metric("⚠️ Samlet Risiko", "N/A")
    
    # Detaljert analyse i tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Tidsserier", 
        "🌨️ Snøfokk-analyse", 
        "🧊 Glattføre", 
        "📋 Datakvalitet"
    ])
    
    with tab1:
        show_enhanced_time_series(df, checker)
    
    with tab2:
        show_enhanced_snowdrift_analysis(df, checker)
    
    with tab3:
        show_enhanced_slippery_analysis(df, checker)
    
    with tab4:
        show_enhanced_data_quality(df)


def show_enhanced_time_series(df, checker):
    """Forbedret tidsserievisning"""
    st.markdown("#### 📈 Tidsserier")
    
    # Plotting options
    col1, col2 = st.columns([3, 1])
    
    with col2:
        plot_options = st.multiselect(
            "Velg variabler:",
            ["Temperatur", "Vind", "Snødybde", "Nedbør"],
            default=["Temperatur", "Vind"]
        )
        
        plot_height = st.slider("Plot høyde", 300, 800, 400)
    
    with col1:
        if plot_options:
            # Opprett subplots
            n_plots = len(plot_options)
            fig, axes = plt.subplots(n_plots, 1, figsize=(12, plot_height/100), sharex=True)
            
            if n_plots == 1:
                axes = [axes]
            
            plot_idx = 0
            
            for option in plot_options:
                ax = axes[plot_idx]
                
                if option == "Temperatur" and 'air_temperature' in df.columns:
                    temp_data = df['air_temperature'].dropna()
                    if len(temp_data) > 0:
                        ax.plot(df.loc[temp_data.index, 'referenceTime'], temp_data, 'r-', label='Temperatur (°C)')
                        ax.axhline(y=0, color='blue', linestyle='--', alpha=0.5, label='Frysepunkt')
                        ax.set_ylabel('Temperatur (°C)')
                        ax.legend()
                        ax.grid(True, alpha=0.3)
                
                elif option == "Vind" and 'wind_speed' in df.columns:
                    wind_data = df['wind_speed'].dropna()
                    if len(wind_data) > 0:
                        ax.plot(df.loc[wind_data.index, 'referenceTime'], wind_data, 'g-', label='Vindstyrke (m/s)')
                        ax.axhline(y=10, color='orange', linestyle='--', alpha=0.5, label='Snøfokk grense')
                        ax.set_ylabel('Vindstyrke (m/s)')
                        ax.legend()
                        ax.grid(True, alpha=0.3)
                
                elif option == "Snødybde" and 'surface_snow_thickness' in df.columns:
                    snow_data = df['surface_snow_thickness'].dropna()
                    if len(snow_data) > 0:
                        ax.plot(df.loc[snow_data.index, 'referenceTime'], snow_data, 'b-', label='Snødybde (cm)')
                        ax.set_ylabel('Snødybde (cm)')
                        ax.legend()
                        ax.grid(True, alpha=0.3)
                
                elif option == "Nedbør":
                    # Prøv flere mulige kolonnenavn for nedbør
                    precip_col = None
                    for col in ['precipitation_amount', 'precipitation_amount_hourly', 'precip']:
                        if col in df.columns:
                            precip_col = col
                            break
                    
                    if precip_col:
                        precip_data = df[precip_col].dropna()
                        if len(precip_data) > 0:
                            ax.bar(df.loc[precip_data.index, 'referenceTime'], precip_data, alpha=0.7, label='Nedbør (mm/h)')
                            ax.set_ylabel('Nedbør (mm/h)')
                            ax.legend()
                            ax.grid(True, alpha=0.3)
                
                plot_idx += 1
            
            # Formatér x-aksen på siste plot
            if axes:
                axes[-1].tick_params(axis='x', rotation=45)
                axes[-1].set_xlabel('Tid')
            
            plt.tight_layout()
            st.pyplot(fig)
        else:
            st.info("Velg variabler å plotte")


def show_enhanced_snowdrift_analysis(df, checker):
    """Forbedret snøfokk-analyse"""
    st.markdown("#### 🌨️ Snøfokk-analyse")
    
    if not hasattr(checker, 'analyze_snowdrift_risk'):
        st.warning("Snøfokk-analyse ikke tilgjengelig")
        return
    
    # Bruk cached snøfokk-analyse
    def snowdrift_analysis():
        return checker.analyze_snowdrift_risk(df)
    
    snowdrift_result = DataCache.get_cached_data(
        key='snowdrift_analysis',
        fetch_func=snowdrift_analysis,
        ttl_seconds=60,  # 1 minutt cache for analyse
        params={'data_hash': hash(str(df.values.tobytes()))}
    )
    
    if snowdrift_result:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Hovedresultat
            if snowdrift_result.get('risk_level') == 'high':
                st.error(f"🔴 **{snowdrift_result.get('message', 'Høy snøfokk-risiko')}**")
            elif snowdrift_result.get('risk_level') == 'medium':
                st.warning(f"🟡 **{snowdrift_result.get('message', 'Moderat snøfokk-risiko')}**")
            else:
                st.success(f"🟢 **{snowdrift_result.get('message', 'Lav snøfokk-risiko')}**")
            
            # Faktorer
            if 'factors' in snowdrift_result:
                st.write("**Vurderingsgrunnlag:**")
                for factor in snowdrift_result['factors']:
                    st.write(f"• {factor}")
        
        with col2:
            # ML-detaljer hvis tilgjengelig
            if 'ml_details' in snowdrift_result:
                st.write("**📊 ML-analyse:**")
                details = snowdrift_result['ml_details']
                
                if 'wind_chill' in details:
                    st.metric("Vindkjøling", f"{details['wind_chill']:.1f}°C")
                
                if 'confidence' in details:
                    st.metric("Tillit", f"{details['confidence']:.1%}")
    else:
        st.warning("Kunne ikke utføre snøfokk-analyse")


def show_enhanced_slippery_analysis(df, checker):
    """Forbedret glattføre-analyse"""
    st.markdown("#### 🧊 Glattføre-analyse")
    
    if not hasattr(checker, 'analyze_slippery_conditions'):
        st.warning("Glattføre-analyse ikke tilgjengelig")
        return
    
    # Bruk cached glattføre-analyse
    def slippery_analysis():
        return checker.analyze_slippery_conditions(df)
    
    slippery_result = DataCache.get_cached_data(
        key='slippery_analysis',
        fetch_func=slippery_analysis,
        ttl_seconds=60,
        params={'data_hash': hash(str(df.values.tobytes()))}
    )
    
    if slippery_result:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Hovedresultat
            if slippery_result.get('risk_level') == 'high':
                st.error(f"🔴 **{slippery_result.get('message', 'Høy glattføre-risiko')}**")
            elif slippery_result.get('risk_level') == 'medium':
                st.warning(f"🟡 **{slippery_result.get('message', 'Moderat glattføre-risiko')}**")
            else:
                st.success(f"🟢 **{slippery_result.get('message', 'Lav glattføre-risiko')}**")
            
            # Faktorer
            if 'factors' in slippery_result:
                st.write("**Vurderingsgrunnlag:**")
                for factor in slippery_result['factors']:
                    st.write(f"• {factor}")
        
        with col2:
            # Ekstra info
            if 'temperature_trend' in slippery_result:
                st.metric("Temperaturtrend", slippery_result['temperature_trend'])
            
            if 'precipitation_type' in slippery_result:
                st.metric("Nedbørtype", slippery_result['precipitation_type'])
    else:
        st.warning("Kunne ikke utføre glattføre-analyse")


def show_enhanced_data_quality(df):
    """Forbedret datakvalitetsanalyse"""
    st.markdown("#### 📋 Datakvalitet")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**📊 Datastatistikk:**")
        
        total_records = len(df)
        st.metric("Totale målinger", total_records)
        
        if 'referenceTime' in df.columns:
            time_span = df['referenceTime'].max() - df['referenceTime'].min()
            st.metric("Tidsperiode", f"{time_span.total_seconds()/3600:.1f} timer")
        
        # Missing data oversikt
        missing_data = {}
        important_cols = ['air_temperature', 'wind_speed', 'surface_snow_thickness']
        
        for col in important_cols:
            if col in df.columns:
                missing_count = df[col].isna().sum()
                missing_pct = (missing_count / total_records) * 100
                missing_data[col] = missing_pct
        
        st.write("**📉 Manglende data (%):**")
        for col, pct in missing_data.items():
            if pct < 10:
                st.success(f"✅ {col}: {pct:.1f}%")
            elif pct < 25:
                st.warning(f"⚠️ {col}: {pct:.1f}%")
            else:
                st.error(f"❌ {col}: {pct:.1f}%")
    
    with col2:
        st.write("**🔍 Datavalidering:**")
        
        # Temperatur validering
        if 'air_temperature' in df.columns:
            temp_data = df['air_temperature'].dropna()
            if len(temp_data) > 0:
                temp_range = temp_data.max() - temp_data.min()
                if temp_range > 30:
                    st.warning(f"⚠️ Stort temperaturspenn: {temp_range:.1f}°C")
                else:
                    st.success(f"✅ Temperaturspenn: {temp_range:.1f}°C")
        
        # Vind validering
        if 'wind_speed' in df.columns:
            wind_data = df['wind_speed'].dropna()
            if len(wind_data) > 0:
                max_wind = wind_data.max()
                if max_wind > 25:
                    st.warning(f"⚠️ Høy vindstyrke: {max_wind:.1f} m/s")
                else:
                    st.success(f"✅ Maks vindstyrke: {max_wind:.1f} m/s")
        
        # Snø validering
        if 'surface_snow_thickness' in df.columns:
            snow_data = df['surface_snow_thickness'].dropna()
            if len(snow_data) > 0:
                max_snow = snow_data.max()
                if max_snow > 200:
                    st.warning(f"⚠️ Høy snødybde: {max_snow:.0f} cm")
                else:
                    st.success(f"✅ Maks snødybde: {max_snow:.0f} cm")


def main():
    """Hovedfunksjon for forbedret Streamlit admin app"""
    
    # Konfigurer Streamlit
    configure_streamlit_admin()
    
    # Vis header
    show_admin_header()
    
    # Sidebar med admin kontroller
    show_cache_status()
    show_admin_controls()
    
    # Hovedinnhold
    tab1, tab2, tab3 = st.tabs([
        "🌤️ Live Analyse", 
        "📊 Historisk Analyse", 
        "🔧 Admin Tools"
    ])
    
    with tab1:
        show_enhanced_weather_analysis()
    
    with tab2:
        st.markdown("### 📊 Historisk Analyse")
        st.info("Historisk analyse kommer i neste versjon")
        
        # Placeholder for historisk analyse
        with st.expander("🔍 Avanserte analyser", expanded=False):
            st.markdown("""
            **Planlagte funksjoner:**
            - Sesongsammenligning
            - Trendanalyse
            - Prediksjonsmodeller
            - Eksport til CSV/Excel
            - API-tilgang
            """)
    
    with tab3:
        st.markdown("### 🔧 Admin Tools")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🗄️ Database")
            if st.button("🔄 Resync Cache"):
                DataCache.invalidate_cache()
                st.success("Cache resynced!")
            
            if st.button("🧹 Cleanup Old Data"):
                # Placeholder for cleanup
                st.success("Cleanup complete!")
        
        with col2:
            st.markdown("#### 📈 Performance")
            
            # Vis cache statistikk
            stats = DataCache.get_cache_stats()
            st.json(stats)


if __name__ == "__main__":
    main()
