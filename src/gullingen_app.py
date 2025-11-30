"""
Føreforhold Gullingen - Komplett varslingssystem.

Fire varslingskategorier for brøytemannskaper og hytteeiere:
1. ❄️ Nysnø - Behov for brøyting
2. 🌬️ Snøfokk - Redusert sikt, snødrev på veier
3. ❄️ Slaps - Tung snø/vann-blanding
4. 🧊 Glatte veier - Is, rimfrost, regn på snø
"""

import sys
from pathlib import Path

# Legg til prosjektrot i path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from datetime import UTC, datetime, timedelta

import matplotlib.pyplot as plt
import pandas as pd
import pydeck as pdk
import streamlit as st

from src.analyzers import (
    FreshSnowAnalyzer,
    RiskLevel,
    SlapsAnalyzer,
    SlipperyRoadAnalyzer,
    SnowdriftAnalyzer,
)
from src.config import settings
from src.frost_client import FrostAPIError, FrostClient
from src.netatmo_client import NetatmoClient
from src.plowing_service import PlowingInfo, get_plowing_info
from src.visualizations import WeatherPlots

logger = logging.getLogger(__name__)


# Page config
st.set_page_config(
    page_title="Føreforhold – Gullingen",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for mobile-first design
st.markdown("""
<style>
    /* Mobile-first responsive design */
    .stApp {
        max-width: 100%;
    }

    /* Risk cards */
    .risk-card {
        padding: 1rem;
        border-radius: 12px;
        margin-bottom: 0.5rem;
    }

    .risk-high {
        background: linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%);
        color: white;
    }

    .risk-medium {
        background: linear-gradient(135deg, #ffa726 0%, #ff9800 100%);
        color: white;
    }

    .risk-low {
        background: linear-gradient(135deg, #66bb6a 0%, #4caf50 100%);
        color: white;
    }

    /* Compact header */
    .compact-header {
        font-size: 1.5rem;
        margin-bottom: 0.5rem;
    }

    /* Metric styling */
    [data-testid="stMetricValue"] {
        font-size: 1.5rem;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Responsive columns */
    @media (max-width: 768px) {
        [data-testid="column"] {
            width: 100% !important;
            flex: 100% !important;
        }
    }
</style>
""", unsafe_allow_html=True)


def get_risk_emoji(level: RiskLevel) -> str:
    """Get emoji for risk level."""
    return {
        RiskLevel.HIGH: "🔴",
        RiskLevel.MEDIUM: "🟡",
        RiskLevel.LOW: "🟢",
        RiskLevel.UNKNOWN: "⚪"
    }.get(level, "⚪")


def get_risk_color(level: RiskLevel) -> str:
    """Get color class for risk level."""
    return {
        RiskLevel.HIGH: "risk-high",
        RiskLevel.MEDIUM: "risk-medium",
        RiskLevel.LOW: "risk-low",
        RiskLevel.UNKNOWN: "risk-low"
    }.get(level, "risk-low")


def render_compact_risk_card(icon: str, title: str, result, key: str):
    """Render a compact risk card."""
    get_risk_emoji(result.risk_level)

    # Status bar
    if result.risk_level == RiskLevel.HIGH:
        st.error(f"{icon} **{title}**: {result.message}")
    elif result.risk_level == RiskLevel.MEDIUM:
        st.warning(f"{icon} **{title}**: {result.message}")
    else:
        st.success(f"{icon} **{title}**: {result.message}")

    # Expand for details
    if result.factors:
        with st.expander("Se detaljer", expanded=False):
            for factor in result.factors:
                st.write(f"• {factor}")
            if result.scenario:
                st.caption(f"Scenario: {result.scenario}")


def render_risk_details(result):
    """Vis detaljer for et analyseresultat i tabber."""
    emoji = get_risk_emoji(result.risk_level)
    st.markdown(f"{emoji} **{result.risk_level.norwegian.upper()}** – {result.message}")

    if result.factors:
        st.caption("Nøkkelfaktorer:")
        for factor in result.factors:
            st.write(f"• {factor}")

    if result.scenario:
        st.caption(f"Scenario: {result.scenario}")


def render_key_metrics(df, plowing_info: PlowingInfo):
    """Render current weather metrics."""
    latest = df.iloc[-1]

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        temp = latest.get('air_temperature')
        surface_temp = latest.get('surface_temperature')
        if temp is not None:
            delta = None
            if surface_temp is not None:
                delta = f"Bakke: {surface_temp:.1f}°C"
            st.metric("Temp", f"{temp:.1f}°C", delta=delta)
        else:
            st.metric("Temp", "N/A")

    with col2:
        wind = latest.get('wind_speed')
        gust = latest.get('max_wind_gust')
        if wind is not None:
            delta = None
            if gust is not None:
                delta = f"Kast: {gust:.1f} m/s"
            st.metric("Vind", f"{wind:.1f} m/s", delta=delta)
        else:
            st.metric("Vind", "N/A")

    with col3:
        snow = latest.get('surface_snow_thickness', 0)
        st.metric("❄️ Snø", f"{snow:.0f} cm")

    with col4:
        precip = latest.get('precipitation_1h', 0)
        st.metric("Nedbør", f"{precip:.1f} mm/h")

    with col5:
        if plowing_info.last_plowing:
            st.metric(f"{plowing_info.status_emoji} Siste brøyting", plowing_info.formatted_time)
        else:
            st.metric("🚜 Siste brøyting", "Ingen registrert")
            if plowing_info.error:
                st.caption(plowing_info.error)


def get_overall_status(results: dict) -> tuple[str, str, RiskLevel]:
    """Get overall status based on all risk assessments."""
    # Find highest risk
    highest_risk = RiskLevel.LOW
    critical_warnings = []

    for name, result in results.items():
        if result.risk_level == RiskLevel.HIGH:
            highest_risk = RiskLevel.HIGH
            critical_warnings.append(name)
        elif result.risk_level == RiskLevel.MEDIUM and highest_risk != RiskLevel.HIGH:
            highest_risk = RiskLevel.MEDIUM

    if highest_risk == RiskLevel.HIGH:
        categories = ", ".join(critical_warnings)
        return "🚨 KRITISK", f"Kritiske forhold: {categories}", highest_risk
    elif highest_risk == RiskLevel.MEDIUM:
        return "⚠️ VÆR OPPMERKSOM", "Enkelte forhold krever oppmerksomhet", highest_risk
    else:
        return "✅ NORMALE FORHOLD", "Trygge kjøreforhold", highest_risk


def main():
    """Main app function."""

    # Header
    st.markdown("# ❄️ Føreforhold Gullingen")
    st.caption(f"{settings.station.name} ({settings.station.altitude_m} moh) | Oppdatert: {datetime.now().strftime('%H:%M')}")

    # Validate config
    valid, msg = settings.validate()
    if not valid:
        st.error(f"⚠️ Konfigurasjonsfeil: {msg}")
        st.info("Legg til FROST_CLIENT_ID i .env fil eller Streamlit secrets")
        st.stop()

    # Sidebar settings
    with st.sidebar:
        st.header("Innstillinger")

        local_now = datetime.now().astimezone()
        local_tz = local_now.tzinfo or UTC

        if "period_start_local" not in st.session_state:
            st.session_state["period_start_local"] = (local_now - timedelta(hours=24)).replace(second=0, microsecond=0)
        if "period_end_local" not in st.session_state:
            st.session_state["period_end_local"] = local_now.replace(second=0, microsecond=0)

        active_start = st.session_state["period_start_local"].astimezone(local_tz)
        active_end = st.session_state["period_end_local"].astimezone(local_tz)

        min_date = (local_now - timedelta(days=7)).date()
        max_date = local_now.date()

        start_date = st.date_input(
            "Startdato",
            value=active_start.date(),
            min_value=min_date,
            max_value=max_date,
            key="period_start_date"
        )
        start_time = st.time_input(
            "Starttid",
            value=active_start.time(),
            key="period_start_time"
        )

        end_date = st.date_input(
            "Sluttdato",
            value=max(start_date, active_end.date()),
            min_value=start_date,
            max_value=max_date,
            key="period_end_date"
        )
        end_time = st.time_input(
            "Slutttid",
            value=active_end.time(),
            key="period_end_time"
        )

        if st.button("Oppdater", width='stretch'):
            candidate_start = datetime.combine(start_date, start_time).replace(tzinfo=local_tz)
            candidate_end = datetime.combine(end_date, end_time).replace(tzinfo=local_tz)

            if candidate_end <= candidate_start:
                st.error("Slutttid må være etter starttid")
            elif candidate_end - candidate_start > timedelta(days=7):
                st.error("Velg en periode på maks 7 dager")
            else:
                st.session_state["period_start_local"] = candidate_start
                st.session_state["period_end_local"] = candidate_end
                st.cache_data.clear()
                st.rerun()

        st.divider()

        # Info-seksjon
        with st.expander("Om appen", expanded=False):
            st.markdown("""
            ### Føreforhold Gullingen

            Varslingssystem for **brøytemannskaper** og **hytteeiere**
            ved Fjellbergsskardet Hyttegrend på Gullingen.

            #### Datagrunnlag
            - **Værdata**: Frost API (Meteorologisk institutt)
            - **Stasjon**: SN46220 Gullingen (637 moh)
            - **Netatmo**: Private værstasjoner i området
            - **Validering**: 166 brøyteepisoder 2022-2025

            #### Hvordan grenseverdier er satt

            Kriteriene er validert mot historiske brøyterapporter:

            | Kategori | Kriterium | Kilde |
            |----------|-----------|-------|
            | **Nysnø** | ≥5 cm/6t | Korrelasjon 0.20 |
            | **Snøfokk** | Vindkast ≥15 m/s | Snitt 21.9 m/s ved brøyting |
            | **Slaps** | -1 til +4°C + nedbør | 33% av brøytinger |
            | **Glatte veier** | Bakke <0°C | 28 episoder med skjult is |

            #### Snøgrense-beregning

            Estimert fra Netatmo-stasjoner på ulike høyder:
            - Beregner temperaturgradient (°C/100m)
            - Interpolerer høyde der temp = 0°C
            - Normal gradient: -0.65°C per 100m

            #### Fargekoder
            - 🟢 **Grønn**: Trygge forhold
            - 🟡 **Gul**: Vær oppmerksom
            - 🔴 **Rød**: Kritiske forhold

            ---
            *Utviklet for Fjellbergsskardet Hyttegrend*
            """)

        st.divider()

        st.subheader("Målgrupper")
        st.markdown("""
        **Brøytemannskaper**
        - Nysnø > 5cm → brøyting
        - Snøfokk → veier blokkeres
        - Slaps → skraping/fresing

        **Hytteeiere**
        - Trygt å kjøre?
        - Planlegg ekstra tid
        - Vinterdekk påkrevd
        """)

    # Fetch data
    selected_start_utc = st.session_state["period_start_local"].astimezone(UTC)
    selected_end_utc = st.session_state["period_end_local"].astimezone(UTC)

    try:
        client = FrostClient()
        with st.spinner("Henter værdata..."):
            weather_data = client.fetch_period(selected_start_utc, selected_end_utc)
    except FrostAPIError as e:
        st.error(f"❌ Kunne ikke hente data: {e}")
        st.stop()

    if weather_data.is_empty:
        st.warning("Ingen data tilgjengelig for valgt periode")
        st.stop()

    df = weather_data.df

    # Run all analyzers
    analyzers = {
        "Nysnø": FreshSnowAnalyzer(),
        "Snøfokk": SnowdriftAnalyzer(),
        "Slaps": SlapsAnalyzer(),
        "Glatte veier": SlipperyRoadAnalyzer(),
    }

    results = {}
    for name, analyzer in analyzers.items():
        results[name] = analyzer.analyze(df)

    # Overall status banner
    status_title, status_msg, overall_risk = get_overall_status(results)

    if overall_risk == RiskLevel.HIGH:
        st.error(f"## {status_title}\n{status_msg}")
    elif overall_risk == RiskLevel.MEDIUM:
        st.warning(f"## {status_title}\n{status_msg}")
    else:
        st.success(f"## {status_title}\n{status_msg}")

    st.divider()

    # Current metrics
    st.subheader("Nåværende forhold")

    # Fetch plowing info
    try:
        plowing_info = get_cached_plowing_info()
    except Exception as e:
        logger.error(f"Error fetching plowing info: {e}")
        plowing_info = PlowingInfo(last_plowing=None, is_recent=False, hours_since=None, error=f"Klarte ikke hente brøyting: {e}")

    render_key_metrics(df, plowing_info)

    st.divider()

    st.subheader("Værgrafer")
    snow_tab, precip_tab, temp_tab, wind_tab, wind_dir_tab = st.tabs([
        "❄️ Snødybde",
        "🌧️ Nedbør",
        "🌡️ Temperatur",
        "🌬️ Vindstyrke",
        "🧭 Vindretning",
    ])

    with snow_tab:
        fig = WeatherPlots.create_snow_depth_plot(df)
        st.pyplot(fig)
        plt.close(fig)

    with precip_tab:
        col1, col2 = st.columns(2)
        with col1:
            fig = WeatherPlots.create_precip_plot(df)
            st.pyplot(fig)
            plt.close(fig)
        with col2:
            fig = WeatherPlots.create_accumulated_precip_plot(df)
            st.pyplot(fig)
            plt.close(fig)

    with temp_tab:
        fig = WeatherPlots.create_temperature_plot(df)
        st.pyplot(fig)
        st.caption("💡 Duggpunkt < 0°C = nedbør faller som snø")
        plt.close(fig)

    with wind_tab:
        fig = WeatherPlots.create_wind_plot(df)
        st.pyplot(fig)
        plt.close(fig)

    with wind_dir_tab:
        fig = WeatherPlots.create_wind_direction_plot(df)
        st.pyplot(fig)
        st.caption("⚠️ SE-S (135-225°) er kritisk retning for snøfokk på Gullingen")
        plt.close(fig)

    # Risiko og detaljer – linjert visning
    st.subheader("Varslingsstatus")
    st.markdown("### ❄️ Nysnø")
    render_risk_details(results["Nysnø"])

    st.divider()
    st.markdown("### ❄️ Slaps")
    render_risk_details(results["Slaps"])

    st.divider()
    st.markdown("### 🌬️ Snøfokk")
    render_risk_details(results["Snøfokk"])

    st.divider()
    st.markdown("### 🧊 Glatte veier")
    render_risk_details(results["Glatte veier"])

    st.divider()

    # Detailed data (collapsed by default)
    with st.expander("Værhistorikk og detaljer", expanded=False):
        tab1, tab2 = st.tabs(["Rådata", "Terskler"])

        with tab1:
            # Show recent data
            display_cols = ['reference_time', 'air_temperature', 'surface_temperature',
                           'wind_speed', 'max_wind_gust', 'surface_snow_thickness',
                           'precipitation_1h', 'dew_point_temperature']
            available_cols = [c for c in display_cols if c in df.columns]

            st.dataframe(
                df[available_cols].tail(24).sort_values('reference_time', ascending=False),
                use_container_width=True,
                hide_index=True
            )

        with tab2:
            st.markdown("""
            ### Validerte terskler (2025)

            | Kategori | Kriterium | Terskel |
            |----------|-----------|---------|
            | **Nysnø** | Snøøkning 6t | ≥ 5 cm |
            | **Nysnø** | Duggpunkt | < 0°C (snø) |
            | **Snøfokk** | Vindkast | ≥ 15 m/s |
            | **Snøfokk** | Vindkjøling | ≤ -12°C |
            | **Slaps** | Temperatur | -1 til +4°C |
            | **Slaps** | Nedbør | ≥ 1 mm/t |
            | **Glatte veier** | Bakketemperatur | < 0°C |
            | **Glatte veier** | Skjult frysefare | Luft > 0, bakke < 0 |
            """)

    # Footer
    st.divider()
    st.caption(
        f"Data: {weather_data.record_count} målinger fra Meteorologisk institutt | "
        f"Stasjon: SN46220 Gullingen"
    )

    # Netatmo temperaturkart
    render_netatmo_map()


@st.cache_data(ttl=300)  # Cache i 5 minutter
def fetch_netatmo_stations():
    """Hent Netatmo-stasjoner (cached)."""
    try:
        client = NetatmoClient()
        if client.authenticate():
            return client.get_fjellbergsskardet_area(radius_km=10)
    except Exception as e:
        logger.warning(f"Netatmo feil: {e}")
    return []


def render_netatmo_map():
    """Render Netatmo temperaturkart - alltid synlig med interaktive data."""

    st.subheader("Temperaturkart")

    stations = fetch_netatmo_stations()

    if not stations:
        st.info("Ingen Netatmo-data tilgjengelig. Sjekk at NETATMO_REFRESH_TOKEN er satt.")
        return

    # Filtrer stasjoner med temperatur
    temp_stations = [s for s in stations if s.temperature is not None]

    if not temp_stations:
        st.warning("Ingen temperaturdata fra Netatmo-stasjoner")
        return

    # Lag DataFrame for kart med alle data
    map_data = []
    for s in temp_stations:
        temp = s.temperature
        hum = s.humidity
        alt = s.altitude

        # Fargekode basert på temperatur (RGB)
        r, g, b = get_temp_rgb(temp)

        map_data.append({
            "lat": s.lat,
            "lon": s.lon,
            "name": s.name or "Netatmo",
            "altitude": alt,
            "temperature": temp,
            "humidity": hum if hum else 0,
            "temp_str": f"{temp:.1f}°C",
            "hum_str": f"{hum:.0f}%" if hum else "-",
            "alt_str": f"{alt} moh",
            "color": [r, g, b, 200],
        })

    # Legg til Gullingen (Frost) - grønn markør
    # Koordinater: 59.41172°N, 6.47204°Ø, 637 moh
    map_data.append({
        "lat": 59.41172,
        "lon": 6.47204,
        "name": "Gullingen (Frost)",
        "altitude": 637,
        "temperature": None,
        "humidity": None,
        "temp_str": "Se topp",
        "hum_str": "-",
        "alt_str": "637 moh",
        "color": [0, 200, 0, 255],  # Grønn
    })

    map_df = pd.DataFrame(map_data)

    # Beregn kartsentrum (midt mellom Gullingen og Fjellbergsskardet)
    center_lat = (59.41172 + 59.39205) / 2
    center_lon = (6.47204 + 6.42667) / 2

    # Pydeck kart med interaktive tooltips
    # Bruker radius_min_pixels og radius_max_pixels for å begrense størrelse ved zoom
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position=["lon", "lat"],
        get_fill_color="color",
        get_radius=300,  # Radius i meter
        radius_min_pixels=10,   # Litt større for synlighet
        radius_max_pixels=30,  # Maximum 30 piksler
        pickable=True,
        auto_highlight=True,
    )

    # Fjernet tekstlag - bruk tooltip ved hover i stedet
    # Tekst overlapper når stasjoner er nærme hverandre

    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=10,  # Litt nærmere for bedre oversikt
        pitch=0,
    )

    tooltip = {
        "html": "<b>{name}</b><br/>🌡️ {temp_str}<br/>📍 {alt_str}<br/>💧 {hum_str}",
        "style": {
            "backgroundColor": "rgba(0,0,0,0.85)",
            "color": "white",
            "fontSize": "14px",
            "padding": "12px",
            "borderRadius": "8px"
        }
    }

    deck = pdk.Deck(
        layers=[layer],  # Bare scatter-layer, ingen tekst
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",  # Lyst kart
    )

    st.pydeck_chart(deck, use_container_width=True)

    # Temperaturstatistikk under kartet
    temps = [s.temperature for s in temp_stations]
    avg_temp = sum(temps) / len(temps)
    min_temp = min(temps)
    max_temp = max(temps)

    # Finn høyfjell vs dal
    high_stations = [s for s in temp_stations if s.altitude >= 500]
    low_stations = [s for s in temp_stations if s.altitude < 200]

    # Beregn snøgrense
    snow_limit = estimate_snow_limit(temp_stations)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Netatmo snitt", f"{avg_temp:.1f}°C")
    with col2:
        st.metric("❄️ Kaldest", f"{min_temp:.1f}°C")
    with col3:
        st.metric("Varmest", f"{max_temp:.1f}°C")
    with col4:
        st.metric("Stasjoner", f"{len(temp_stations)}")

    # Snøgrense-info (sidebar-stil på siden)
    render_snow_limit_info(snow_limit, temp_stations, high_stations, low_stations)

    # Tabell med alle stasjoner (i expander)
    with st.expander("Alle Netatmo-stasjoner"):
        display_df = map_df[map_df["temperature"].notna()].copy()
        display_df = display_df.sort_values("altitude", ascending=False)

        st.dataframe(
            display_df[["name", "alt_str", "temp_str", "hum_str"]].rename(columns={
                "name": "Stasjon",
                "alt_str": "Høyde",
                "temp_str": "Temp",
                "hum_str": "Fukt"
            }),
            use_container_width=True,
            hide_index=True
        )


@st.cache_data(ttl=900)  # Cache plowing info for 15 minutter
def get_cached_plowing_info() -> PlowingInfo:
    """Henter brøyteinformasjon fra service (cached)."""
    return get_plowing_info()


def estimate_snow_limit(stations) -> dict:
    """
    Estimer snøgrense basert på temperaturprofil fra værstasjoner.

    Metode:
    1. Finn temperaturgradient (°C per 100m høydeforskjell)
    2. Bruk 0°C som snøgrense (nedbør faller som snø)
    3. For slaps-grense bruker vi +1°C (våt snø)

    Normal gradient: -0.65°C per 100m (tørr luft: -1°C, fuktig: -0.5°C)
    """
    if len(stations) < 2:
        return {"snow_limit": None, "slaps_limit": None, "gradient": None, "confidence": "lav"}

    # Sorter etter høyde
    sorted_stations = sorted(stations, key=lambda s: s.altitude)

    # Beregn gradient fra laveste til høyeste
    low = sorted_stations[0]
    high = sorted_stations[-1]

    alt_diff = high.altitude - low.altitude
    temp_diff = high.temperature - low.temperature

    if alt_diff < 100:
        return {"snow_limit": None, "slaps_limit": None, "gradient": None, "confidence": "lav"}

    # Gradient i °C per 100m
    gradient = (temp_diff / alt_diff) * 100

    # Bruk lineær interpolasjon for å finne høyde der temp = 0°C
    # Formel: høyde = lav_høyde + (0 - lav_temp) / gradient * 100

    if gradient >= 0:
        # Inversjon - varmere høyere opp
        if high.temperature <= 0:
            snow_limit = 0  # Snø helt ned
        else:
            snow_limit = None  # Ingen snøgrense (inversjon)
    else:
        # Normal gradient (kaldere høyere opp)
        if low.temperature <= 0:
            snow_limit = 0  # Snø helt ned til sjøen
        elif high.temperature >= 0:
            snow_limit = None  # Ingen snø selv på toppen
        else:
            # Interpoler: hvor er 0°C?
            snow_limit = low.altitude + ((0 - low.temperature) / gradient) * 100
            snow_limit = max(0, min(snow_limit, 1500))  # Begrens til rimelige verdier

    # Slaps-grense (+1°C)
    if gradient < 0 and low.temperature > 1:
        slaps_limit = low.altitude + ((1 - low.temperature) / gradient) * 100
        slaps_limit = max(0, min(slaps_limit, 1500))
    else:
        slaps_limit = snow_limit

    # Vurder konfidens
    if alt_diff >= 400 and len(stations) >= 5:
        confidence = "høy"
    elif alt_diff >= 200 and len(stations) >= 3:
        confidence = "middels"
    else:
        confidence = "lav"

    return {
        "snow_limit": snow_limit,
        "slaps_limit": slaps_limit,
        "gradient": gradient,
        "confidence": confidence,
        "low_station": low,
        "high_station": high,
    }


def render_snow_limit_info(snow_limit: dict, all_stations, high_stations, low_stations):
    """Render snøgrense-info som en informasjonsboks."""

    col1, col2 = st.columns([2, 1])

    with col1:
        # Inversjon sjekk - inversjon = høyfjell VARMERE enn dal
        if high_stations and low_stations:
            high_avg = sum(s.temperature for s in high_stations) / len(high_stations)
            low_avg = sum(s.temperature for s in low_stations) / len(low_stations)

            if high_avg > low_avg + 1:
                # Ekte inversjon - varmere på fjellet
                st.warning(f"**Inversjon**: Høyfjell {high_avg:.1f}°C, dal {low_avg:.1f}°C (uvanlig!)")
            else:
                # Normal gradient - vis temperaturforskjell
                diff = low_avg - high_avg
                st.caption(f"Dal {low_avg:.1f}°C → Fjell {high_avg:.1f}°C (diff: {diff:.1f}°C)")

    with col2:
        # Snøgrense-boks
        if snow_limit.get("snow_limit") is not None:
            limit = snow_limit["snow_limit"]
            gradient = snow_limit.get("gradient", 0)
            snow_limit.get("confidence", "lav")

            if limit <= 0:
                st.success("❄️ **Snø til sjøen**")
            elif limit < 300:
                st.success(f"❄️ **Snøgrense ~{int(limit)} moh**")
            elif limit < 600:
                st.warning(f"❄️ **Snøgrense ~{int(limit)} moh**")
            else:
                st.error(f"❄️ **Snøgrense ~{int(limit)} moh**")

            # Gradient-info
            if gradient:
                grad_text = f"{gradient:.1f}°C/100m"
                if gradient > -0.4:
                    st.caption(f"Svak gradient ({grad_text}) - ustabil")
                elif gradient < -0.8:
                    st.caption(f"Bratt gradient ({grad_text})")
                else:
                    st.caption(f"Normal gradient ({grad_text})")
        else:
            if snow_limit.get("gradient") and snow_limit["gradient"] >= 0:
                st.warning("Inversjon - snøgrense uklar")
            else:
                st.info("Snøgrense ikke beregnet")


def get_temp_rgb(temp: float) -> tuple:
    """Returner RGB-farge basert på temperatur."""
    if temp <= -10:
        return (0, 0, 180)      # Mørk blå
    elif temp <= -5:
        return (50, 100, 255)   # Blå
    elif temp <= -2:
        return (100, 150, 255)  # Lys blå
    elif temp <= 0:
        return (150, 200, 255)  # Veldig lys blå
    elif temp <= 2:
        return (255, 220, 50)   # Gul
    elif temp <= 5:
        return (255, 150, 0)    # Oransje
    else:
        return (255, 80, 80)    # Rød


if __name__ == "__main__":
    main()
