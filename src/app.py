"""
Hovedapplikasjon - Føreforhold Gullingen.

Enkel og ren Streamlit entry point.
"""

import sys
from pathlib import Path

# Legg til prosjektrot i path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import matplotlib.pyplot as plt
from datetime import datetime

from src.config import settings
from src.frost_client import FrostClient, FrostAPIError
from src.analyzers import SnowdriftAnalyzer, SlipperyRoadAnalyzer, RiskLevel
from src.visualizations import WeatherPlots


def main():
    """Hovedfunksjon for Streamlit-app."""
    
    # Sidekonfigurasjon
    st.set_page_config(
        page_title="Føreforhold – Gullingen",
        page_icon="❄️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Sjekk konfigurasjon
    valid, msg = settings.validate()
    if not valid:
        st.error(f"⚠️ Konfigurasjonsfeil: {msg}")
        st.info("Legg til FROST_CLIENT_ID i .env fil eller Streamlit secrets")
        st.stop()
    
    # Header
    st.title("❄️ Føreforhold – Gullingen")
    st.caption(f"Stasjon: {settings.station.name} ({settings.station.station_id}) | {settings.station.altitude_m} moh")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Innstillinger")
        
        hours_back = st.slider(
            "Timer tilbake",
            min_value=6,
            max_value=168,
            value=24,
            step=6,
            help="Hvor mange timer tilbake skal vises"
        )
        
        st.divider()
        
        if st.button("🔄 Oppdater data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        st.divider()
        
        # Info
        with st.expander("ℹ️ Om appen"):
            st.markdown("""
            **Varslingssystem for snøfokk og glattføre**
            
            Bruker ML-baserte terskler validert mot historiske data.
            
            **Datakilder:**
            - Frost API (Meteorologisk institutt)
            - Stasjon: SN46220 Gullingen
            
            **Varslingskriterier:**
            - 🌬️ Snøfokk: Vindkjøling < -12°C + vind > 8 m/s
            - 🧊 Glattføre: Regn på snø, is-dannelse, rimfrost
            """)
    
    # Hent data
    try:
        client = FrostClient()
        with st.spinner("Henter værdata..."):
            weather_data = client.fetch_recent(hours_back=hours_back)
    except FrostAPIError as e:
        st.error(f"❌ Kunne ikke hente data: {e}")
        st.stop()
    
    if weather_data.is_empty:
        st.warning("Ingen data tilgjengelig for valgt periode")
        st.stop()
    
    df = weather_data.df
    
    # Analyser
    snowdrift_analyzer = SnowdriftAnalyzer()
    slippery_analyzer = SlipperyRoadAnalyzer()
    
    snowdrift_result = snowdrift_analyzer.analyze(df)
    slippery_result = slippery_analyzer.analyze(df)
    
    # Varsler øverst hvis kritisk
    if snowdrift_result.is_critical or slippery_result.is_critical:
        st.error("🚨 **KRITISK VARSEL**")
        if snowdrift_result.is_critical:
            st.error(f"🌬️ **Snøfokk:** {snowdrift_result.message}")
        if slippery_result.is_critical:
            st.error(f"🧊 **Glattføre:** {slippery_result.message}")
        st.divider()
    
    # Hovedinnhold
    col1, col2 = st.columns(2)
    
    with col1:
        render_risk_card("🌬️ Snøfokk-risiko", snowdrift_result)
    
    with col2:
        render_risk_card("🧊 Glattføre-risiko", slippery_result)
    
    st.divider()
    
    # Nøkkelverdier
    render_key_metrics(df)
    
    st.divider()
    
    # Grafer
    tab1, tab2, tab3 = st.tabs(["📈 Oversikt", "🌬️ Vindkjøling", "📊 Detaljer"])
    
    with tab1:
        fig = WeatherPlots.create_overview_plot(df)
        st.pyplot(fig)
        plt.close(fig)
    
    with tab2:
        fig = WeatherPlots.create_wind_chill_plot(df)
        st.pyplot(fig)
        plt.close(fig)
    
    with tab3:
        st.subheader("Rådata")
        st.dataframe(
            df.tail(24).style.format({
                'air_temperature': '{:.1f}°C',
                'wind_speed': '{:.1f} m/s',
                'surface_snow_thickness': '{:.0f} cm',
                'precipitation_1h': '{:.1f} mm',
            }),
            use_container_width=True
        )
    
    # Footer
    st.divider()
    st.caption(
        f"Sist oppdatert: {datetime.now().strftime('%d.%m.%Y %H:%M')} | "
        f"Data: {weather_data.record_count} målinger | "
        f"Kilde: Meteorologisk institutt"
    )


def render_risk_card(title: str, result):
    """Render risiko-kort med styling."""
    st.subheader(f"{result.risk_level.emoji} {title}")
    
    # Fargekoding
    if result.risk_level == RiskLevel.HIGH:
        st.error(result.message)
    elif result.risk_level == RiskLevel.MEDIUM:
        st.warning(result.message)
    elif result.risk_level == RiskLevel.LOW:
        st.success(result.message)
    else:
        st.info(result.message)
    
    # Scenario
    if result.scenario:
        st.caption(f"Scenario: {result.scenario}")
    
    # Faktorer
    if result.factors:
        with st.expander("Vurderingsgrunnlag"):
            for factor in result.factors:
                st.write(f"• {factor}")


def render_key_metrics(df):
    """Render nøkkelverdier fra siste måling."""
    st.subheader("📊 Nåværende forhold")
    
    latest = df.iloc[-1]
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        temp = latest.get('air_temperature')
        if temp is not None:
            st.metric("🌡️ Temperatur", f"{temp:.1f}°C")
        else:
            st.metric("🌡️ Temperatur", "N/A")
    
    with col2:
        wind = latest.get('wind_speed')
        if wind is not None:
            st.metric("💨 Vind", f"{wind:.1f} m/s")
        else:
            st.metric("💨 Vind", "N/A")
    
    with col3:
        snow = latest.get('surface_snow_thickness', 0)
        st.metric("❄️ Snødybde", f"{snow:.0f} cm")
    
    with col4:
        precip = latest.get('precipitation_1h', 0)
        st.metric("🌧️ Nedbør", f"{precip:.1f} mm/h")


if __name__ == "__main__":
    main()
