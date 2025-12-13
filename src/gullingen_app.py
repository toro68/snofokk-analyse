"""
Føreforhold Gullingen - Komplett varslingssystem.

Fire varslingskategorier for brøytemannskaper og hytteeiere:
1. Nysnø - Behov for brøyting
2. Snøfokk - Redusert sikt, snødrev på veier
3. Slaps - Tung snø/vann-blanding
4. Glatte veier - Is, rimfrost, regn på snø
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
    AnalysisResult,
    FreshSnowAnalyzer,
    RiskLevel,
    SlapsAnalyzer,
    SlipperyRoadAnalyzer,
    SnowdriftAnalyzer,
)
from src.config import settings
from src.components.smoreguide import generate_wax_recommendation, get_sources_section_markdown
from src.frost_client import FrostAPIError, FrostClient
from src.netatmo_client import NetatmoClient, NetatmoStation
from src.plowing_service import (
    PlowingInfo,
    get_maintenance_suppress_hours,
    get_plowing_info,
    should_suppress_alerts,
)
from src.operational_logger import log_medium_high_alerts
from src.visualizations import WeatherPlots

logger = logging.getLogger(__name__)


# Page config
st.set_page_config(
    page_title="Føreforhold – Gullingen",
    page_icon=None,
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
    return ""


def render_compact_risk_card(icon: str, title: str, result: AnalysisResult) -> None:
    """Render a compact risk card (Streamlit-native styling)."""
    if result.risk_level == RiskLevel.HIGH:
        st.error(f"**{title}**: {result.message}")
    elif result.risk_level == RiskLevel.MEDIUM:
        st.warning(f"**{title}**: {result.message}")
    elif result.risk_level == RiskLevel.UNKNOWN:
        st.info(f"**{title}**: {result.message}")
    else:
        st.success(f"**{title}**: {result.message}")

    # Keep it compact: optionally show scenario + up to 2 factors as a caption
    caption_parts: list[str] = []
    if result.scenario:
        caption_parts.append(f"Scenario: {result.scenario}")
    if result.factors:
        top_factors = [str(x) for x in result.factors[:2]]
        if top_factors:
            caption_parts.append(" | ".join(top_factors))
    if caption_parts:
        st.caption(" • ".join(caption_parts))


def render_risk_details(result):
    """Vis detaljer for et analyseresultat i tabber."""
    st.markdown(f"**{result.risk_level.norwegian.upper()}** – {result.message}")

    if result.factors:
        st.caption("Nøkkelfaktorer:")
        for factor in result.factors:
            st.write(f"• {factor}")

    if result.scenario:
        st.caption(f"Scenario: {result.scenario}")


def render_key_metrics(df, plowing_info: PlowingInfo):
    """Render current weather metrics."""
    latest = df.iloc[-1]

    col1, col2, col3, col4 = st.columns(4)

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
        st.metric("Snø", f"{snow:.0f} cm")

    with col4:
        precip = latest.get('precipitation_1h', 0)
        st.metric("Nedbør", f"{precip:.1f} mm/h")


def render_wax_guide(df: pd.DataFrame) -> None:
    """Vis en kompakt smøreguide under værdata."""

    st.markdown("#### Smøreguide")

    try:
        rec = generate_wax_recommendation(df)
    except (KeyError, ValueError, TypeError) as e:
        logger.debug("Smøreguide feilet: %s", e)
        st.info("Smøreguide utilgjengelig: mangler eller ugyldige værdata.")
        return

    if rec is None:
        st.info("Smøreguide utilgjengelig: mangler nok ferske værdata.")
        return
    st.caption(f"{rec.swix_family} | {rec.temp_band} | {rec.condition}")

    st.write(f"**Anbefaling:** {rec.headline}")
    if rec.swix_products:
        st.write("Produkter:")
        for product in rec.swix_products:
            st.write(f"- {product}")

    if rec.factors:
        top_factors = [f for f in rec.factors if f][:3]
        if top_factors:
            st.caption("Nøkkelfaktorer: " + " | ".join(top_factors))

    if rec.instructions:
        with st.expander("Fremgangsmåte", expanded=False):
            for step in rec.instructions:
                st.write(f"- {step}")

    with st.expander("Kilder og datagrunnlag", expanded=False):
        st.markdown(get_sources_section_markdown())


def render_maintenance_top(plowing_info: PlowingInfo, suppress_alerts: bool) -> None:
    """Viser 'Siste vedlikehold' øverst og forklarer nullstilling av varsler."""

    suppress_hours = get_maintenance_suppress_hours()

    if plowing_info.last_plowing:
        value = plowing_info.formatted_time
        # Vis work_types (f.eks. "skraping") i header, ikke event_type (f.eks. "SCRAPE")
        if plowing_info.last_work_types:
            value = f"{value} – {', '.join(plowing_info.last_work_types)}"

        st.metric("Siste vedlikehold", value)

        details_parts: list[str] = []
        # Vis kun nullstillings-info, ikke redundant type/operatør
        if suppress_alerts and plowing_info.hours_since is not None:
            remaining = max(0.0, suppress_hours - float(plowing_info.hours_since))
            details_parts.append(
                f"Nullstilling etter ferdig brøyting/strøing: {suppress_hours:.1f}t (telles fra tidspunktet over, {remaining:.1f}t igjen)"
            )
        else:
            details_parts.append(
                f"Nullstilling etter ferdig vedlikehold (brøyting/strøing): {suppress_hours:.1f}t (telles fra tidspunktet over)"
            )

        if details_parts:
            st.caption(" | ".join(details_parts))
    else:
        st.metric("Siste vedlikehold", "Ingen registrert")
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
        return "KRITISK", f"Kritiske forhold: {categories}", highest_risk
    elif highest_risk == RiskLevel.MEDIUM:
        return "VÆR OPPMERKSOM", "Enkelte forhold krever oppmerksomhet", highest_risk
    else:
        return "NORMALE FORHOLD", "Trygge kjøreforhold", highest_risk


def main():
    """Main app function."""

    # Header
    st.markdown("# Føreforhold Gullingen")
    st.caption(f"{settings.station.name} ({settings.station.altitude_m} moh) | Oppdatert: {datetime.now().strftime('%H:%M')}")

    # Validate config
    valid, msg = settings.validate()
    if not valid:
        st.error(f"Konfigurasjonsfeil: {msg}")
        st.info("Legg til FROST_CLIENT_ID i .env fil eller Streamlit secrets")
        st.stop()

    # Sidebar settings
    with st.sidebar:
        st.header("Innstillinger")

        local_now = datetime.now().astimezone()
        local_tz = local_now.tzinfo or UTC

        if "period_start_local" not in st.session_state:
            st.session_state["period_start_local"] = (
                local_now - timedelta(hours=settings.dashboard.default_period_hours)
            ).replace(second=0, microsecond=0)
        if "period_end_local" not in st.session_state:
            st.session_state["period_end_local"] = local_now.replace(second=0, microsecond=0)

        active_start = st.session_state["period_start_local"].astimezone(local_tz)
        active_end = st.session_state["period_end_local"].astimezone(local_tz)

        min_date = (local_now - timedelta(days=settings.dashboard.max_period_days)).date()
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
            elif candidate_end - candidate_start > timedelta(days=settings.dashboard.max_period_days):
                st.error(f"Velg en periode på maks {settings.dashboard.max_period_days} dager")
            else:
                st.session_state["period_start_local"] = candidate_start
                st.session_state["period_end_local"] = candidate_end
                st.cache_data.clear()
                st.rerun()

        st.divider()

        # Info-seksjon
        with st.expander("Om appen", expanded=False):
            st.markdown(f"""
            ### Føreforhold Gullingen

            Varslingssystem for **brøytemannskaper** og **hytteeiere**
            ved Fjellbergsskardet Hyttegrend på Gullingen.

            #### Datagrunnlag
            - **Værdata**: Frost API (Meteorologisk institutt)
            - **Stasjon**: {settings.station.station_id} {settings.station.name} ({settings.station.altitude_m} moh)
            - **Netatmo**: Private værstasjoner i området
            - **Validering**: 166 brøyteepisoder 2022-2025

            #### Hvordan grenseverdier er satt

            Kriteriene er validert mot historiske brøyterapporter:

            | Kategori | Kriterium | Kilde |
            |----------|-----------|-------|
            | **Nysnø** | ≥{settings.fresh_snow.snow_increase_warning:.0f} cm/{settings.fresh_snow.lookback_hours}t (moderat) / ≥{settings.fresh_snow.snow_increase_critical:.0f} cm/{settings.fresh_snow.lookback_hours}t (høy) | Kalibrert mot brøyting + vær |
            | **Snøfokk** | Vindkast ≥{settings.snowdrift.wind_gust_warning:.0f} m/s (advarsel) / ≥{settings.snowdrift.wind_gust_critical:.0f} m/s (kritisk) | Vindkast er primær trigger |
            | **Slaps** | {settings.slaps.temp_min:.0f} til {settings.slaps.temp_max:.0f}°C + {settings.slaps.precipitation_accum_hours}t nedbør ≥{settings.slaps.precipitation_12h_min:.0f} mm | Kalibrert mot slaps-episoder |
            | **Glatte veier** | Bakke ≤{settings.slippery.surface_temp_freeze:.0f}°C (is) | Bakketemperatur er primær indikator |

            #### Snøgrense-beregning

            Estimert fra Netatmo-stasjoner på ulike høyder:
            - Beregner temperaturgradient (°C/100m)
            - Interpolerer høyde der temp = 0°C
            - Normal gradient: -0.65°C per 100m

            #### Fargekoder
            - **Grønn**: Trygge forhold
            - **Gul**: Vær oppmerksom
            - **Rød**: Kritiske forhold

            ---
            *Utviklet for Fjellbergsskardet Hyttegrend*
            """)

        st.divider()

        st.subheader("Målgrupper")
        st.markdown(f"""
        **Brøytemannskaper**
        - Nysnø ≥ {settings.fresh_snow.snow_increase_warning:.0f} cm/{settings.fresh_snow.lookback_hours}t → brøyting
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
        st.error(f"Kunne ikke hente data: {e}")
        st.stop()

    if weather_data.is_empty:
        st.warning("Ingen data tilgjengelig for valgt periode")
        st.stop()

    df = weather_data.df

    # Fetch plowing/maintenance info (available via vedlikeholds-endepunkt)
    try:
        plowing_info = get_cached_plowing_info()
    except Exception as e:
        logger.error("Error fetching plowing info: %s", e)
        plowing_info = PlowingInfo(
            last_plowing=None,
            hours_since=None,
            is_recent=False,
            all_timestamps=[],
            source="error",
            error=f"Klarte ikke hente brøyting: {e}",
        )

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

    suppress_alerts = should_suppress_alerts(plowing_info)

    # Stans farevarsel ved nylig vedlikehold (brøyting/strøing)
    if suppress_alerts:
        suppressed = {}
        for name, r in results.items():
            if r.risk_level != RiskLevel.LOW:
                suppressed[name] = AnalysisResult(
                    risk_level=RiskLevel.LOW,
                    message="Nylig vedlikehold (brøyting/strøing) – farevarsel stanset",
                    scenario=r.scenario,
                    factors=(r.factors or []) + ["Nylig vedlikehold"],
                    details={
                        **(r.details or {}),
                        "suppressed_by_maintenance": True,
                        "maintenance_hours_since": plowing_info.hours_since,
                    },
                    timestamp=r.timestamp,
                )
            else:
                suppressed[name] = r
        results = suppressed

    # Overall status banner
    status_title, status_msg, overall_risk = get_overall_status(results)

    # Vis kun banner når det faktisk er noe å reagere på.
    # Ved normale forhold lar vi "Varsler nå" tale for seg.
    if overall_risk == RiskLevel.HIGH:
        st.error(f"## {status_title}\n{status_msg}")
    elif overall_risk == RiskLevel.MEDIUM:
        st.warning(f"## {status_title}\n{status_msg}")

    # Flyttet opp: Siste vedlikehold (erstatter tidligere "NORMALE FORHOLD"-banner)
    render_maintenance_top(plowing_info, suppress_alerts)

    st.divider()

    # Compact status summary
    st.subheader("Varsler nå")
    col1, col2 = st.columns(2)
    with col1:
        render_compact_risk_card("", "Nysnø", results["Nysnø"])
    with col2:
        render_compact_risk_card("", "Snøfokk", results["Snøfokk"])

    col3, col4 = st.columns(2)
    with col3:
        render_compact_risk_card("", "Slaps", results["Slaps"])
    with col4:
        render_compact_risk_card("", "Glatte veier", results["Glatte veier"])

    # Current metrics
    st.subheader("Nåværende forhold")

    # Operational logging: MEDIUM/HIGH only (deduped)
    try:
        log_medium_high_alerts(results=results, df=df, plowing_info=plowing_info)
    except Exception as e:
        logger.warning("Operational logger failed: %s", e)

    render_key_metrics(df, plowing_info)

    render_wax_guide(df)

    st.divider()

    st.subheader("Værgrafer")
    snow_tab, precip_tab, temp_tab, wind_tab, wind_dir_tab = st.tabs([
        "Snødybde",
        "Nedbør",
        "Temperatur",
        "Vindstyrke",
        "Vindretning",
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
        st.caption(f"Duggpunkt < {settings.fresh_snow.dew_point_max:.0f}°C: Nedbør faller som snø")
        plt.close(fig)

    with wind_tab:
        fig = WeatherPlots.create_wind_plot(df)
        st.pyplot(fig)
        plt.close(fig)

    with wind_dir_tab:
        fig = WeatherPlots.create_wind_direction_plot(df)
        st.pyplot(fig)
        st.caption(
            f"SE-S ({settings.snowdrift.critical_wind_dir_min:.0f}-{settings.snowdrift.critical_wind_dir_max:.0f}°) er kritisk retning for snøfokk"
        )
        plt.close(fig)

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
            st.markdown(f"""
            ### Validerte terskler (2025)

            | Kategori | Kriterium | Terskel |
            |----------|-----------|---------|
            | **Nysnø** | Snøøkning {settings.fresh_snow.lookback_hours}t | ≥ {settings.fresh_snow.snow_increase_warning:.0f} cm (moderat) / ≥ {settings.fresh_snow.snow_increase_critical:.0f} cm (høy) |
            | **Nysnø** | Duggpunkt | < {settings.fresh_snow.dew_point_max:.0f}°C (snø) |
            | **Snøfokk** | Vindkast | ≥ {settings.snowdrift.wind_gust_warning:.0f} m/s (advarsel) / ≥ {settings.snowdrift.wind_gust_critical:.0f} m/s (kritisk) |
            | **Snøfokk** | Vindkjøling | ≤ {settings.snowdrift.wind_chill_warning:.0f}°C (advarsel) / ≤ {settings.snowdrift.wind_chill_critical:.0f}°C (kritisk) |
            | **Slaps** | Temperatur | {settings.slaps.temp_min:.0f} til {settings.slaps.temp_max:.0f}°C |
            | **Slaps** | Nedbør ({settings.slaps.precipitation_accum_hours}t) | ≥ {settings.slaps.precipitation_12h_min:.0f} mm |
            | **Glatte veier** | Bakketemperatur | ≤ {settings.slippery.surface_temp_freeze:.0f}°C |
            | **Glatte veier** | Skjult frysefare | Luft {settings.slippery.hidden_freeze_air_min:.0f}-{settings.slippery.hidden_freeze_air_max:.0f}°C og bakke ≤ {settings.slippery.hidden_freeze_surface_max:.1f}°C |
            """)

    # Footer
    st.divider()
    st.caption(
        f"Data: {weather_data.record_count} målinger fra Meteorologisk institutt | "
        f"Stasjon: {settings.station.station_id} {settings.station.name}"
    )

    # Netatmo temperaturkart
    render_netatmo_map()


@st.cache_data(ttl=settings.netatmo.cache_ttl_seconds)
def fetch_netatmo_stations():
    """Hent Netatmo-stasjoner (cached).

    Viktig: `st.cache_data` krever at returverdien kan serialiseres.
    Derfor cacher vi kun en liste med enkle dicts, ikke NetatmoStation-objekter.
    """
    try:
        client = get_netatmo_client()
        if client.authenticate():
            stations = client.get_fjellbergsskardet_area(radius_km=settings.netatmo.search_radius_km)
            rows: list[dict] = []
            for s in stations:
                rows.append({
                    "station_id": s.station_id,
                    "name": s.name,
                    "lat": s.lat,
                    "lon": s.lon,
                    "altitude": s.altitude,
                    "temperature": s.temperature,
                    "humidity": s.humidity,
                    "timestamp": s.timestamp.isoformat() if s.timestamp else None,
                })
            return rows
    except Exception as e:
        logger.warning(f"Netatmo feil: {e}")
    return []


@st.cache_resource
def get_netatmo_client() -> NetatmoClient:
    """Gjenbruk Netatmo-klient mellom reruns for mindre overhead."""
    return NetatmoClient()


def render_netatmo_map():
    """Render Netatmo temperaturkart - alltid synlig med interaktive data."""

    st.subheader("Temperaturkart")

    cached_rows = fetch_netatmo_stations()

    stations: list[NetatmoStation] = []
    for r in cached_rows:
        ts = None
        if r.get("timestamp"):
            try:
                ts = datetime.fromisoformat(r["timestamp"])
            except Exception:
                ts = None

        stations.append(
            NetatmoStation(
                station_id=str(r.get("station_id") or ""),
                name=str(r.get("name") or ""),
                lat=float(r.get("lat") or 0.0),
                lon=float(r.get("lon") or 0.0),
                altitude=int(r.get("altitude") or 0),
                temperature=r.get("temperature"),
                humidity=r.get("humidity"),
                timestamp=ts,
            )
        )

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

    map_df = pd.DataFrame(map_data)

    # Beregn kartsentrum (midt mellom Gullingen og Fjellbergsskardet)
    center_lat = (settings.station.lat + settings.netatmo.fjellberg_lat) / 2
    center_lon = (settings.station.lon + settings.netatmo.fjellberg_lon) / 2

    # Pydeck kart med interaktive tooltips
    # Bruker radius_min_pixels og radius_max_pixels for å begrense størrelse ved zoom
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position=["lon", "lat"],
        get_fill_color="color",
        get_radius=settings.netatmo.map_point_radius_m,
        radius_min_pixels=settings.netatmo.map_point_radius_min_px,
        radius_max_pixels=settings.netatmo.map_point_radius_max_px,
        pickable=True,
        auto_highlight=True,
    )

    # Fjernet tekstlag - bruk tooltip ved hover i stedet
    # Tekst overlapper når stasjoner er nærme hverandre

    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=settings.netatmo.map_zoom,
        pitch=0,
    )

    tooltip = {
        "html": "<b>{name}</b><br/>Temp: {temp_str}<br/>Høyde: {alt_str}<br/>Fukt: {hum_str}",
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

    # Vis når Netatmo-data sist ble oppdatert (nyttig ift. caching/TTL)
    latest_ts = None
    for s in temp_stations:
        if s.timestamp is None:
            continue
        ts = s.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        if latest_ts is None or ts > latest_ts:
            latest_ts = ts

    if latest_ts is not None:
        now_utc = datetime.now(tz=UTC)
        age = max(timedelta(seconds=0), now_utc - latest_ts)
        minutes = int(age.total_seconds() // 60)
        try:
            latest_local = latest_ts.astimezone(datetime.now().astimezone().tzinfo)
        except Exception:
            latest_local = latest_ts

        st.caption(
            f"Sist oppdatert Netatmo: {latest_local.strftime('%d.%m %H:%M')} "
            f"(ca {minutes} min siden, cache 5 min)"
        )

    # Temperaturstatistikk under kartet
    temps = [s.temperature for s in temp_stations]
    avg_temp = sum(temps) / len(temps)
    min_temp = min(temps)
    max_temp = max(temps)

    # Finn høyfjell vs dal
    thresholds = settings.snow_limit
    high_stations = [s for s in temp_stations if s.altitude >= thresholds.high_station_min_altitude_m]
    low_stations = [s for s in temp_stations if s.altitude < thresholds.low_station_max_altitude_m]

    # Beregn snøgrense
    snow_limit = estimate_snow_limit(temp_stations)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Netatmo snitt", f"{avg_temp:.1f}°C")
    with col2:
        st.metric("Kaldest", f"{min_temp:.1f}°C")
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


@st.cache_data(ttl=settings.plowing_service.streamlit_cache_ttl_seconds)
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
    thresholds = settings.snow_limit

    if len(stations) < thresholds.min_stations:
        return {"snow_limit": None, "slaps_limit": None, "gradient": None, "confidence": "lav"}

    # Sorter etter høyde
    sorted_stations = sorted(stations, key=lambda s: s.altitude)

    # Beregn gradient fra laveste til høyeste
    low = sorted_stations[0]
    high = sorted_stations[-1]

    alt_diff = high.altitude - low.altitude
    temp_diff = high.temperature - low.temperature

    if alt_diff < thresholds.min_alt_diff_m:
        return {"snow_limit": None, "slaps_limit": None, "gradient": None, "confidence": "lav"}

    # Gradient i °C per 100m
    gradient = (temp_diff / alt_diff) * 100

    # Bruk lineær interpolasjon for å finne høyde der temp = 0°C
    # Formel: høyde = lav_høyde + (0 - lav_temp) / gradient * 100

    if gradient >= thresholds.inversion_gradient_min:
        # Inversjon - varmere høyere opp
        if high.temperature <= thresholds.snow_temp_c:
            snow_limit = 0  # Snø helt ned
        else:
            snow_limit = None  # Ingen snøgrense (inversjon)
    else:
        # Normal gradient (kaldere høyere opp)
        if low.temperature <= thresholds.snow_temp_c:
            snow_limit = 0  # Snø helt ned til sjøen
        elif high.temperature >= thresholds.snow_temp_c:
            snow_limit = None  # Ingen snø selv på toppen
        else:
            # Interpoler: hvor er 0°C?
            snow_limit = low.altitude + ((thresholds.snow_temp_c - low.temperature) / gradient) * 100
            snow_limit = max(0, min(snow_limit, thresholds.max_altitude_m))

    # Slaps-grense (+1°C)
    if gradient < 0 and low.temperature > thresholds.slaps_temp_c:
        slaps_limit = low.altitude + ((thresholds.slaps_temp_c - low.temperature) / gradient) * 100
        slaps_limit = max(0, min(slaps_limit, thresholds.max_altitude_m))
    else:
        slaps_limit = snow_limit

    # Vurder konfidens
    if alt_diff >= thresholds.confidence_high_alt_diff_m and len(stations) >= thresholds.confidence_high_station_count:
        confidence = "høy"
    elif alt_diff >= thresholds.confidence_medium_alt_diff_m and len(stations) >= thresholds.confidence_medium_station_count:
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

            thresholds = settings.snow_limit

            if high_avg > low_avg + thresholds.inversion_delta_c:
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

            thresholds = settings.snow_limit

            if limit <= 0:
                st.success("**Snø til sjøen**")
            elif limit < thresholds.display_low_m:
                st.success(f"**Snøgrense ~{int(limit)} moh**")
            elif limit < thresholds.display_medium_m:
                st.warning(f"**Snøgrense ~{int(limit)} moh**")
            else:
                st.error(f"**Snøgrense ~{int(limit)} moh**")

            # Gradient-info
            if gradient:
                grad_text = f"{gradient:.1f}°C/100m"
                if gradient > thresholds.gradient_weak_min:
                    st.caption(f"Svak gradient ({grad_text}) - ustabil")
                elif gradient < thresholds.gradient_steep_max:
                    st.caption(f"Bratt gradient ({grad_text})")
                else:
                    st.caption(f"Normal gradient ({grad_text})")
        else:
            thresholds = settings.snow_limit

            if snow_limit.get("gradient") and snow_limit["gradient"] >= thresholds.inversion_gradient_min:
                st.warning("Inversjon - snøgrense uklar")
            else:
                st.info("Snøgrense ikke beregnet")


def get_temp_rgb(temp: float) -> tuple:
    """Returner RGB-farge basert på temperatur."""
    thresholds = settings.display

    if temp <= thresholds.very_cold_max:
        return (0, 0, 180)      # Mørk blå
    elif temp <= thresholds.cold_max:
        return (50, 100, 255)   # Blå
    elif temp <= thresholds.chilly_max:
        return (100, 150, 255)  # Lys blå
    elif temp <= thresholds.freezing_max:
        return (150, 200, 255)  # Veldig lys blå
    elif temp <= thresholds.mild_max:
        return (255, 220, 50)   # Gul
    elif temp <= thresholds.warm_max:
        return (255, 150, 0)    # Oransje
    else:
        return (255, 80, 80)    # Rød


if __name__ == "__main__":
    main()
