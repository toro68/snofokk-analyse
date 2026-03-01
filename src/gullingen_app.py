"""
Føreforhold Gullingen - Komplett varslingssystem.

Fire varslingskategorier for brøytemannskaper og hytteeiere:
1. Nysnø - Behov for brøyting
2. Snøfokk - Redusert sikt, snødrev på veier
3. Slaps - Tung snø/vann-blanding
4. Glatte veier - Is, rimfrost, regn på snø
"""

# pylint: disable=too-many-lines,wrong-import-position,line-too-long

import json
import sys
from pathlib import Path
from typing import Any

# Legg til prosjektrot i path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import html
import math
from datetime import UTC, datetime, timedelta

import matplotlib.pyplot as plt
import pandas as pd
import pydeck as pdk  # type: ignore[import-untyped]
import streamlit as st

from src.analyzers import (
    AnalysisResult,
    FreshSnowAnalyzer,
    RiskLevel,
    SlapsAnalyzer,
    SlipperyRoadAnalyzer,
    SnowdriftAnalyzer,
)
from src.components.smoreguide import generate_wax_recommendation, get_sources_section_markdown
from src.config import get_secret, settings
from src.forecast_client import ForecastClient, ForecastClientError
from src.frost_client import FrostAPIError, FrostClient
from src.logging_config import configure_logging
from src.netatmo_client import NetatmoClient, NetatmoStation
from src.operational_logger import log_medium_high_alerts
from src.plowing_service import (
    PlowingInfo,
    get_plowing_info,
    should_suppress_alerts,
)
from src.visualizations import WeatherPlots

configure_logging()
logger = logging.getLogger(__name__)

def _app_version() -> str | None:
    """Best effort app-versjon for feilsøking (vises i sidebar)."""

    env_sha = st.secrets.get("APP_GIT_SHA") if hasattr(st, "secrets") else None
    if env_sha:
        return str(env_sha)[:12]

    # Streamlit Cloud har ofte repo-checkout tilgjengelig; prøv å lese .git uten å kalle git.
    try:
        root = Path(__file__).parent.parent
        head_path = root / ".git" / "HEAD"
        if not head_path.exists():
            return None

        head = head_path.read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = head.split(":", 1)[1].strip()
            ref_path = root / ".git" / ref
            if ref_path.exists():
                return ref_path.read_text(encoding="utf-8").strip()[:12]
            return None
        return head[:12]
    except (OSError, ValueError):
        return None


# Page config
st.set_page_config(
    page_title="Føreforhold – Gullingen",
    page_icon="\u2745",
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

    /* Varselkort */
    .alert-card {
        border-radius: 12px;
        padding: 1rem 1.15rem;
        margin: 0 0 0.35rem 0;
        border: 1px solid transparent;
    }
    .alert-card-title {
        font-size: 1.05rem;
        font-weight: 700;
        margin-right: 0.25rem;
    }
    .alert-card-message {
        font-size: 1.05rem;
        font-weight: 500;
    }
    .alert-low {
        background: #e6f4ea;
        color: #0b6b2f;
        border-color: #cde8d4;
    }
    .alert-medium {
        background: #fff4db;
        color: #7a4b00;
        border-color: #f6e0ad;
    }
    .alert-high {
        background: #fde7e9;
        color: #8b1e2d;
        border-color: #f3c6cc;
    }
    .alert-unknown {
        background: #e8eef7;
        color: #2a4b73;
        border-color: #d2def0;
    }
</style>
""", unsafe_allow_html=True)


def render_compact_risk_card(title: str, result: AnalysisResult, confidence: int | None = None) -> None:
    """Render a compact risk card."""
    if result.risk_level == RiskLevel.HIGH:
        card_style = "background:#fde7e9;color:#8b1e2d;border:1px solid #f3c6cc;"
    elif result.risk_level == RiskLevel.MEDIUM:
        card_style = "background:#fff4db;color:#7a4b00;border:1px solid #f6e0ad;"
    elif result.risk_level == RiskLevel.UNKNOWN:
        card_style = "background:#e8eef7;color:#2a4b73;border:1px solid #d2def0;"
    else:
        card_style = "background:#e6f4ea;color:#0b6b2f;border:1px solid #cde8d4;"

    safe_title = html.escape(title)
    safe_message = html.escape(result.message or "")
    st.markdown(
        f"""
        <div class="alert-card" style="{card_style}">
          <span class="alert-card-title">{safe_title}:</span>
          <span class="alert-card-message">{safe_message}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
    if confidence is not None:
        if confidence >= 75:
            confidence_label = "Tillit: H\u00f8y"
        elif confidence >= 50:
            confidence_label = "Tillit: Moderat"
        else:
            confidence_label = "Tillit: Lav"
        st.caption(confidence_label)
    if result.caveat:
        st.caption(f"Forbehold: {result.caveat}")


def render_risk_details(result: Any) -> None:
    """Vis detaljer for et analyseresultat i tabber."""
    st.markdown(f"**{result.risk_level.norwegian.upper()}** – {result.message}")

    if result.factors:
        st.caption("Nøkkelfaktorer:")
        for factor in result.factors:
            st.write(f"• {factor}")

    if result.scenario:
        st.caption(f"Scenario: {result.scenario}")
    if result.caveat:
        st.caption(f"Forbehold: {result.caveat}")


def render_key_metrics(df: pd.DataFrame | None) -> None:
    """Render current weather metrics."""
    if df is None or df.empty:
        st.info("Ingen værdata tilgjengelig")
        return

    def _to_float(value: Any) -> float | None:
        try:
            if value is None or pd.isna(value):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _delta_text(series_name: str, unit: str, decimals: int = 1) -> str | None:
        if series_name not in df.columns:
            return None

        series = pd.to_numeric(df[series_name], errors='coerce').dropna()
        if len(series) < 2:
            return None

        latest_value = float(series.iloc[-1])
        prev_index = max(0, len(series) - 4)
        previous_value = float(series.iloc[prev_index])
        delta = latest_value - previous_value
        sign = "+" if delta > 0 else ""
        return f"3t: {sign}{delta:.{decimals}f}{unit}"

    latest = df.iloc[-1]

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        temp = _to_float(latest.get('air_temperature'))
        surface_temp = _to_float(latest.get('surface_temperature'))
        if temp is not None:
            metric_delta = _delta_text('air_temperature', '°C')
            if surface_temp is not None:
                surface_text = f"Bakke: {surface_temp:.1f}°C"
                metric_delta = f"{metric_delta} | {surface_text}" if metric_delta else surface_text
            st.metric("Temp", f"{temp:.1f}°C", delta=metric_delta)
        else:
            st.metric("Temp", "N/A")

    with col2:
        wind = _to_float(latest.get('wind_speed'))
        gust = _to_float(latest.get('max_wind_gust'))
        if wind is not None:
            metric_delta = _delta_text('wind_speed', ' m/s')
            if gust is not None:
                gust_text = f"Kast: {gust:.1f} m/s"
                metric_delta = f"{metric_delta} | {gust_text}" if metric_delta else gust_text
            st.metric("Vind", f"{wind:.1f} m/s", delta=metric_delta)
        else:
            st.metric("Vind", "N/A")

    with col3:
        snow = _to_float(latest.get('surface_snow_thickness'))
        if snow is not None:
            snow_delta = _delta_text('surface_snow_thickness', ' cm', decimals=1)
            st.metric("Snø", f"{snow:.0f} cm", delta=snow_delta)
        else:
            st.metric("Snø", "N/A")

    with col4:
        precip = _to_float(latest.get('precipitation_1h'))
        if precip is not None:
            precip_delta = _delta_text('precipitation_1h', ' mm/h')
            st.metric("Nedbør", f"{precip:.1f} mm/h", delta=precip_delta)
        else:
            st.metric("Nedbør", "N/A")


def render_period_summary(df: pd.DataFrame, selected_start_utc: datetime, selected_end_utc: datetime) -> None:
    """Vis kompakt periodestatus for bedre situasjonsforståelse."""
    metrics = get_data_quality_metrics(df, selected_start_utc, selected_end_utc)
    if not metrics.get("valid", False):
        return

    latest_age_min = int(metrics["latest_age_min"])
    coverage_pct = float(metrics["coverage_pct"])
    selected_hours = float(metrics["selected_hours"])
    measured_start = metrics["measured_start"]
    measured_end = metrics["measured_end"]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Valgt periode", f"{selected_hours:.1f} timer")
    with col2:
        st.metric("Datadekning", f"{coverage_pct:.0f}%", delta=f"{metrics['count']} målinger")
    with col3:
        st.metric("Siste måling", f"{latest_age_min} min siden")

    st.caption(
        f"Målinger i datasettet: {measured_start.strftime('%d.%m %H:%M')}–{measured_end.strftime('%d.%m %H:%M')}"
    )

    if latest_age_min > settings.dashboard.data_stale_warning_minutes:
        st.warning(
            f"Værdata er eldre enn {settings.dashboard.data_stale_warning_minutes} minutter. "
            "Vurder å oppdatere perioden."
        )


def get_data_quality_metrics(
    df: pd.DataFrame,
    selected_start_utc: datetime,
    selected_end_utc: datetime,
) -> dict[str, Any]:
    """Beregn datakvalitet for valgt tidsperiode."""
    if df is None or df.empty:
        return {"valid": False}

    ref_col = df["reference_time"] if "reference_time" in df.columns else pd.Series(dtype=object)
    times = pd.to_datetime(ref_col, errors="coerce", utc=True).dropna()
    if times.empty:
        return {"valid": False}

    measured_start = times.iloc[0]
    measured_end = times.iloc[-1]
    latest_age = datetime.now(UTC) - measured_end.to_pydatetime().astimezone(UTC)
    latest_age_min = max(0, int(latest_age.total_seconds() // 60))

    selected_hours = max(1.0, (selected_end_utc - selected_start_utc).total_seconds() / 3600)
    expected_points = max(1, int(round(selected_hours)) + 1)
    coverage_pct = min(100.0, (len(times) / expected_points) * 100.0)

    return {
        "valid": True,
        "count": len(times),
        "selected_hours": selected_hours,
        "coverage_pct": coverage_pct,
        "latest_age_min": latest_age_min,
        "measured_start": measured_start,
        "measured_end": measured_end,
        "latest_time_utc": measured_end.to_pydatetime().astimezone(UTC),
    }


def _risk_rank(level: RiskLevel) -> int:
    return {
        RiskLevel.UNKNOWN: 0,
        RiskLevel.LOW: 1,
        RiskLevel.MEDIUM: 2,
        RiskLevel.HIGH: 3,
    }[level]


def _decrease_risk(level: RiskLevel) -> RiskLevel:
    if level == RiskLevel.HIGH:
        return RiskLevel.MEDIUM
    if level == RiskLevel.MEDIUM:
        return RiskLevel.LOW
    return level


def apply_data_quality_guard(
    results: dict[str, AnalysisResult],
    quality: dict[str, Any],
) -> tuple[dict[str, AnalysisResult], str | None]:
    """Nedjuster risikopresentasjon når datakvalitet er lav."""
    if not quality.get("valid", False):
        adjusted = {
            name: AnalysisResult(
                risk_level=RiskLevel.UNKNOWN,
                message="Utilstrekkelig datagrunnlag for sikker vurdering",
                scenario=result.scenario,
                factors=(result.factors or []) + ["Datakvalitet: manglende tidsserie"],
                details={**(result.details or {}), "data_quality_guard": "invalid"},
                timestamp=result.timestamp,
            )
            for name, result in results.items()
        }
        return adjusted, "Datakvalitet utilstrekkelig: manglende tidsstempler i perioden."

    latest_age_min = int(quality["latest_age_min"])
    coverage_pct = float(quality["coverage_pct"])

    unknown_mode = (
        latest_age_min >= settings.dashboard.data_stale_unknown_minutes
        or coverage_pct < settings.dashboard.data_coverage_unknown_pct
    )
    warning_mode = (
        latest_age_min >= settings.dashboard.data_stale_warning_minutes
        or coverage_pct < settings.dashboard.data_coverage_warning_pct
    )

    if unknown_mode:
        adjusted = {
            name: AnalysisResult(
                risk_level=RiskLevel.UNKNOWN,
                message="Datakvalitet for lav til sikker varsling",
                scenario=result.scenario,
                factors=(result.factors or []) + [
                    f"Datadekning: {coverage_pct:.0f}%",
                    f"Alder siste måling: {latest_age_min} min",
                ],
                details={**(result.details or {}), "data_quality_guard": "unknown"},
                timestamp=result.timestamp,
            )
            for name, result in results.items()
        }
        return adjusted, "Datakvalitet kritisk lav: varsler settes til ukjent nivå."

    if warning_mode:
        adjusted = {}
        for name, result in results.items():
            new_level = _decrease_risk(result.risk_level)
            if new_level != result.risk_level:
                adjusted[name] = AnalysisResult(
                    risk_level=new_level,
                    message=f"{result.message} (nedjustert pga datakvalitet)",
                    scenario=result.scenario,
                    factors=(result.factors or []) + [
                        f"Datadekning: {coverage_pct:.0f}%",
                        f"Alder siste måling: {latest_age_min} min",
                    ],
                    details={**(result.details or {}), "data_quality_guard": "warning"},
                    timestamp=result.timestamp,
                )
            else:
                adjusted[name] = result
        return adjusted, "Datakvalitet moderat: risikonivå er nedjustert ett trinn der relevant."

    return results, None


def apply_alert_stability(
    results: dict[str, AnalysisResult],
    reference_time_utc: datetime,
) -> dict[str, AnalysisResult]:
    """Hold på høyere nivå kort tid ved nedgradering for å redusere varselstøy."""
    hold_window = timedelta(minutes=settings.dashboard.alert_downgrade_hold_minutes)
    state: dict[str, dict[str, str]] = st.session_state.setdefault("alert_stability_state", {})
    stabilized: dict[str, AnalysisResult] = {}

    for name, result in results.items():
        previous = state.get(name, {})
        previous_level_name = previous.get("level")
        previous_changed_at_str = previous.get("changed_at")

        previous_level = result.risk_level
        if previous_level_name is not None and previous_level_name in RiskLevel.__members__:
            previous_level = RiskLevel[previous_level_name]

        previous_changed_at = reference_time_utc
        if previous_changed_at_str:
            try:
                previous_changed_at = datetime.fromisoformat(previous_changed_at_str)
                if previous_changed_at.tzinfo is None:
                    previous_changed_at = previous_changed_at.replace(tzinfo=UTC)
                else:
                    previous_changed_at = previous_changed_at.astimezone(UTC)
            except (ValueError, TypeError):
                previous_changed_at = reference_time_utc

        incoming_level = result.risk_level
        is_downgrade = _risk_rank(incoming_level) < _risk_rank(previous_level)
        within_hold = (reference_time_utc - previous_changed_at) < hold_window

        if is_downgrade and within_hold:
            stabilized[name] = AnalysisResult(
                risk_level=previous_level,
                message=f"{result.message} (stabilisert {settings.dashboard.alert_downgrade_hold_minutes} min)",
                scenario=result.scenario,
                factors=(result.factors or []) + [
                    f"Stabilisering: holder {previous_level.norwegian.lower()} kortvarig"
                ],
                details={**(result.details or {}), "stabilized_from": incoming_level.value},
                timestamp=result.timestamp,
            )
            continue

        stabilized[name] = result
        if incoming_level != previous_level or name not in state:
            state[name] = {
                "level": incoming_level.name,
                "changed_at": reference_time_utc.isoformat(),
            }

    st.session_state["alert_stability_state"] = state
    return stabilized


def render_recommended_actions(
    results: dict[str, AnalysisResult],
    suppress_alerts: bool,
    maintenance_reason: str,
    quality_note: str | None,
) -> None:
    """Vis anbefalt handling for operativ bruk."""
    st.subheader("Anbefalt handling nå")

    if quality_note:
        st.info(quality_note)

    if suppress_alerts:
        st.info(f"Varsler er midlertidig undertrykt av vedlikehold ({maintenance_reason}).")
        return

    high_categories = [name for name, r in results.items() if r.risk_level == RiskLevel.HIGH]
    medium_categories = [name for name, r in results.items() if r.risk_level == RiskLevel.MEDIUM]

    col_crew, col_owners = st.columns(2)

    with col_crew:
        st.markdown("**Br\u00f8ytemannskap**")
        if high_categories:
            st.error("Planlegg utrykning for: " + ", ".join(high_categories))
        elif medium_categories:
            st.warning("F\u00f8lg tett med, mulig behov for tiltak: " + ", ".join(medium_categories))
        else:
            st.success("Ingen akutte tiltak n\u00f8dvendig")

    with col_owners:
        st.markdown("**Hytteeiere**")
        if high_categories:
            st.error("Vurder \u00e5 utsette avreise eller beregn betydelig ekstra tid")
        elif medium_categories:
            st.warning("Kj\u00f8r med ekstra margin \u2013 f\u00f8lg oppdateringer f\u00f8r avreise")
        else:
            st.success("Trygge kj\u00f8reforhold. Fortsett som normalt.")


def render_alert_overview(results: dict[str, AnalysisResult]) -> None:
    """Vis kort oppsummering av aktive varsler."""
    level_counts = {
        RiskLevel.HIGH: 0,
        RiskLevel.MEDIUM: 0,
        RiskLevel.UNKNOWN: 0,
        RiskLevel.LOW: 0,
    }
    active_categories: list[str] = []

    for category, result in results.items():
        level_counts[result.risk_level] = level_counts.get(result.risk_level, 0) + 1
        if result.risk_level in (RiskLevel.HIGH, RiskLevel.MEDIUM):
            active_categories.append(category)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Høy", str(level_counts.get(RiskLevel.HIGH, 0)))
    with col2:
        st.metric("Moderat", str(level_counts.get(RiskLevel.MEDIUM, 0)))
    with col3:
        st.metric("Ukjent", str(level_counts.get(RiskLevel.UNKNOWN, 0)))
    with col4:
        st.metric("Lav", str(level_counts.get(RiskLevel.LOW, 0)))

    if active_categories:
        st.caption("Aktive varsler: " + ", ".join(active_categories))
    else:
        st.caption("Ingen aktive høy/moderat-varsler i valgt periode")


def _calculate_confidence(
    result: AnalysisResult,
    quality_metrics: dict[str, Any],
    suppress_alerts: bool,
) -> int:
    """Beregn enkel usikkerhetsscore (0-100) per varsel."""
    base = {
        RiskLevel.HIGH: 82,
        RiskLevel.MEDIUM: 74,
        RiskLevel.LOW: 86,
        RiskLevel.UNKNOWN: 35,
    }[result.risk_level]

    score = float(base)

    if suppress_alerts:
        score -= 10

    if quality_metrics.get("valid", False):
        coverage = float(quality_metrics.get("coverage_pct", 100.0))
        latest_age = float(quality_metrics.get("latest_age_min", 0.0))
        score -= max(0.0, (100.0 - coverage) * 0.35)
        score -= max(0.0, (latest_age - 30.0) * 0.08)
    else:
        score -= 30

    if (result.details or {}).get("data_quality_guard") in {"unknown", "invalid"}:
        score -= 25
    elif (result.details or {}).get("data_quality_guard") == "warning":
        score -= 12

    return max(0, min(100, int(round(score))))


def _compute_confidence_map(
    results: dict[str, AnalysisResult],
    quality_metrics: dict[str, Any],
    suppress_alerts: bool,
) -> dict[str, int]:
    return {
        name: _calculate_confidence(result, quality_metrics, suppress_alerts)
        for name, result in results.items()
    }


def render_operational_kpis() -> None:
    """Vis KPI-panel for operasjonelle varsler (proxy-mål)."""
    st.subheader("Operasjonelle KPI-er (14 dager)")

    root = Path(__file__).parent.parent
    log_rel = get_secret("OPERATIONAL_LOG_PATH", "data/logs/operational_alerts.csv")
    state_rel = get_secret("OPERATIONAL_LOG_STATE_PATH", "data/logs/operational_alerts_state.json")
    enabled = str(get_secret("OPERATIONAL_LOG_ENABLED", "true")).strip().lower() in {"1", "true", "yes", "y", "on"}

    log_path = (root / log_rel).resolve()
    state_path = (root / state_rel).resolve()

    if not enabled:
        st.info("Operasjonell logging er slått av (OPERATIONAL_LOG_ENABLED=false).")
        st.caption("Aktiver logging for å få KPI-er over tid.")
        return

    if not log_path.exists():
        state_entries = 0
        if state_path.exists():
            try:
                raw = json.loads(state_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    state_entries = len(raw)
            except (OSError, ValueError, TypeError):
                state_entries = 0

        st.info("Ingen operasjonell logg tilgjengelig ennå.")
        st.caption(
            f"Forventer logg på: {log_rel}. "
            "CSV opprettes først når minst ett MEDIUM/HIGH-varsel logges."
        )
        if state_entries > 0:
            st.caption(f"Det finnes dedupliseringsstate med {state_entries} nøkler i {state_rel}.")
        return

    try:
        df = pd.read_csv(log_path)
    except (OSError, ValueError, pd.errors.EmptyDataError):
        st.info("Kunne ikke lese operasjonell logg.")
        return

    if df.empty or "logged_at_utc" not in df.columns:
        st.info("Operasjonell logg mangler data for KPI-beregning.")
        return

    logged = pd.to_datetime(df["logged_at_utc"], errors="coerce", utc=True)
    recent_mask = logged >= (datetime.now(UTC) - timedelta(days=14))
    recent = df.loc[recent_mask].copy()

    if recent.empty:
        st.info("Ingen varsler logget siste 14 dager.")
        return

    total = len(recent)
    high_share = float((recent["risk_level"] == "HIGH").sum()) / total * 100 if "risk_level" in recent.columns else 0.0
    suppressed_share = (
        pd.to_numeric(recent["suppressed_by_maintenance"], errors="coerce").fillna(0).astype(int).clip(0, 1).mean() * 100
        if "suppressed_by_maintenance" in recent.columns
        else 0.0
    )

    maint_hours = pd.to_numeric(recent["maintenance_hours_since"] if "maintenance_hours_since" in recent.columns else pd.Series(dtype=float), errors="coerce")
    tp_proxy = int((maint_hours <= 6).sum())
    fp_proxy = int(((maint_hours > 24) | maint_hours.isna()).sum())
    precision_proxy = (tp_proxy / (tp_proxy + fp_proxy) * 100) if (tp_proxy + fp_proxy) > 0 else 0.0

    maintenance_events = recent.get("maintenance_last_utc")
    if maintenance_events is not None:
        unique_events = maintenance_events.dropna().astype(str).unique()
        denom = len(unique_events)
        recall_proxy = (tp_proxy / denom * 100) if denom > 0 else 0.0
    else:
        recall_proxy = 0.0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Varsler (14d)", str(total))
    with col2:
        st.metric("Høy-andel", f"{high_share:.0f}%")
    with col3:
        st.metric("Presisjon (proxy)", f"{precision_proxy:.0f}%")
    with col4:
        st.metric("Recall (proxy)", f"{recall_proxy:.0f}%")

    st.caption(
        f"Undertrykket andel: {suppressed_share:.0f}%. "
        "Presisjon/recall er proxy basert på vedlikeholdstid, ikke full sannhetstabell."
    )


@st.cache_resource
def get_forecast_client() -> ForecastClient:
    """Gjenbruk prognoseklient mellom reruns."""
    return ForecastClient()


@st.cache_data(ttl=settings.api.streamlit_cache_ttl_seconds)
def fetch_forecast_cached(lat: float, lon: float, hours: int) -> pd.DataFrame:
    """Hent prognosedata med cache."""
    client = get_forecast_client()
    points = client.fetch_hourly_forecast(lat=lat, lon=lon, hours=hours)
    rows = []
    for p in points:
        rows.append(
            {
                "reference_time": p.reference_time,
                "air_temperature": p.air_temperature,
                "wind_speed": p.wind_speed,
                "max_wind_gust": p.wind_gust,
                "precipitation_1h": p.precipitation_1h,
            }
        )
    return pd.DataFrame(rows)


def render_forecast_section() -> None:
    """Vis korttidsprognose for neste timer."""
    horizon_hours = max(1, int(settings.api.forecast_hours))
    st.subheader(f"Prognose neste {horizon_hours} timer")
    try:
        forecast_df = fetch_forecast_cached(
            settings.station.lat,
            settings.station.lon,
            horizon_hours,
        )
    except ForecastClientError as e:
        st.info(f"Prognose utilgjengelig: {e}")
        return

    if forecast_df is None or forecast_df.empty:
        st.info("Ingen prognosedata tilgjengelig akkurat nå.")
        return

    temp_series = pd.to_numeric(forecast_df.get("air_temperature"), errors="coerce")  # type: ignore[call-overload]
    wind_series = pd.to_numeric(forecast_df.get("wind_speed"), errors="coerce")  # type: ignore[call-overload]
    precip_series = pd.to_numeric(forecast_df.get("precipitation_1h"), errors="coerce").fillna(0)  # type: ignore[call-overload]

    col1, col2, col3 = st.columns(3)
    with col1:
        if temp_series.notna().any():
            st.metric("Temp min/maks", f"{temp_series.min():.1f} / {temp_series.max():.1f}°C")
        else:
            st.metric("Temp min/maks", "N/A")
    with col2:
        if wind_series.notna().any():
            st.metric("Maks vind", f"{wind_series.max():.1f} m/s")
        else:
            st.metric("Maks vind", "N/A")
    with col3:
        st.metric("Nedbør sum", f"{precip_series.sum():.1f} mm")

    fig = WeatherPlots.create_compact_plot(forecast_df, title="Prognose: temperatur, vind og nedbør")
    st.pyplot(fig)
    plt.close(fig)
    st.caption(f"Kilde: MET Locationforecast (kompakt prognose, horisont {horizon_hours}t)")


def render_wax_guide(df: pd.DataFrame) -> None:
    """Vis en kompakt smøreguide under værdata."""

    # Ikke vis smøreguide når det ikke er snø (da er det ikke skiforhold).
    # Bruk siste tilgjengelige (ikke-NaN) snødybde hvis vi har den.
    if df is not None and not df.empty and "surface_snow_thickness" in df.columns:
        snow_series = df["surface_snow_thickness"].dropna()
        if not snow_series.empty:
            snow_depth = float(snow_series.iloc[-1])
            if snow_depth <= 0.5:
                return

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

    if plowing_info.last_plowing:
        value = plowing_info.formatted_time
        # Vis work_types (f.eks. "skraping") i header, ikke event_type (f.eks. "SCRAPE")
        if plowing_info.last_work_types:
            value = f"{value} – {', '.join(plowing_info.last_work_types)}"

        st.metric("Siste vedlikehold", value)

        details_parts: list[str] = []
        # Vis kun nullstillings-info, ikke redundant type/operatør
        if suppress_alerts and plowing_info.hours_since is not None:
            details_parts.append(
                f"Brøyting/skraping/strøing nuller ut værhendelsen. "
                f"Teller fra siste brøyting: {float(plowing_info.hours_since):.1f}t siden. "
                f"Varsler beregnes videre fra siste brøyting."
            )
        else:
            details_parts.append(
                f"Brøyting/skraping/strøing nuller ut værhendelsen. "
                f"Teller fra siste brøyting. "
                f"Varsler beregnes videre fra siste brøyting."
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
    unknown_categories = []

    for name, result in results.items():
        if result.risk_level == RiskLevel.HIGH:
            highest_risk = RiskLevel.HIGH
            critical_warnings.append(name)
        elif result.risk_level == RiskLevel.MEDIUM and highest_risk != RiskLevel.HIGH:
            highest_risk = RiskLevel.MEDIUM
        elif result.risk_level == RiskLevel.UNKNOWN:
            unknown_categories.append(name)

    if highest_risk == RiskLevel.HIGH:
        categories = ", ".join(critical_warnings)
        return "KRITISK", f"Kritiske forhold: {categories}", highest_risk
    elif highest_risk == RiskLevel.MEDIUM:
        return "VÆR OPPMERKSOM", "Enkelte forhold krever oppmerksomhet", highest_risk
    elif unknown_categories:
        categories = ", ".join(unknown_categories)
        return "UKJENTE FORHOLD", f"Manglende datagrunnlag for: {categories}", RiskLevel.UNKNOWN
    else:
        return "NORMALE FORHOLD", "Trygge kjøreforhold", highest_risk


@st.cache_resource
def get_frost_client() -> FrostClient:
    """Gjenbruk Frost-klient mellom reruns for mindre overhead."""
    return FrostClient()


@st.cache_data(ttl=settings.api.streamlit_cache_ttl_seconds)
def fetch_weather_period_cached(start_iso: str, end_iso: str) -> pd.DataFrame:
    """Hent værdata for valgt periode med Streamlit-cache."""
    start_time = datetime.fromisoformat(start_iso)
    end_time = datetime.fromisoformat(end_iso)
    client = get_frost_client()
    weather_data = client.fetch_period(start_time, end_time)
    return weather_data.df


def main() -> None:
    """Main app function."""

    # Header
    st.markdown("# Føreforhold Gullingen")
    st.caption(f"{settings.station.name} ({settings.station.altitude_m} moh)")

    # Validate config
    valid, msg = settings.validate()
    if not valid:
        st.error(f"Konfigurasjonsfeil: {msg}")
        st.info("Legg til FROST_CLIENT_ID i .env fil eller Streamlit secrets")
        st.stop()

    # Sidebar settings
    with st.sidebar:
        st.header("Innstillinger")
        version = _app_version()
        if version:
            st.caption(f"Versjon: {version}")

        local_now = datetime.now().astimezone()
        local_tz = local_now.tzinfo or UTC

        if "period_start_local" not in st.session_state:
            st.session_state["period_start_local"] = (
                local_now - timedelta(hours=settings.dashboard.default_period_hours)
            ).replace(second=0, microsecond=0)
        if "period_end_local" not in st.session_state:
            st.session_state["period_end_local"] = local_now.replace(second=0, microsecond=0)

        st.caption("Hurtigvalg")
        quick1, quick2, quick3, quick4 = st.columns(4)
        if quick1.button("6t", width='stretch'):
            st.session_state["period_end_local"] = local_now.replace(second=0, microsecond=0)
            st.session_state["period_start_local"] = (local_now - timedelta(hours=6)).replace(second=0, microsecond=0)
            st.rerun()
        if quick2.button("24t", width='stretch'):
            st.session_state["period_end_local"] = local_now.replace(second=0, microsecond=0)
            st.session_state["period_start_local"] = (local_now - timedelta(hours=24)).replace(second=0, microsecond=0)
            st.rerun()
        if quick3.button("72t", width='stretch'):
            st.session_state["period_end_local"] = local_now.replace(second=0, microsecond=0)
            st.session_state["period_start_local"] = (local_now - timedelta(hours=72)).replace(second=0, microsecond=0)
            st.rerun()
        if quick4.button("7d", width='stretch'):
            st.session_state["period_end_local"] = local_now.replace(second=0, microsecond=0)
            st.session_state["period_start_local"] = (local_now - timedelta(days=7)).replace(second=0, microsecond=0)
            st.rerun()

        st.divider()

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
        with st.spinner("Henter værdata..."):
            df = fetch_weather_period_cached(
                selected_start_utc.isoformat(),
                selected_end_utc.isoformat(),
            )
    except FrostAPIError as e:
        st.error(f"Kunne ikke hente data: {e}")
        st.stop()

    if df is None or df.empty:
        st.warning("Ingen data tilgjengelig for valgt periode")
        st.stop()

    quality_metrics = get_data_quality_metrics(df, selected_start_utc, selected_end_utc)
    with st.expander("Datakvalitet og periode", expanded=False):
        render_period_summary(df, selected_start_utc, selected_end_utc)

    # Fetch plowing/maintenance info (available via vedlikeholds-endepunkt)
    try:
        plowing_info = get_cached_plowing_info()
    except (RuntimeError, ValueError, TypeError, KeyError, OSError) as e:
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

    # Capture raw analyzer output BEFORE any downstream transformations.
    # This ensures audit logging records what sensors actually detected,
    # regardless of whether data_quality_guard later downgrades to UNKNOWN.
    raw_results_for_log = dict(results)

    results, quality_note = apply_data_quality_guard(results, quality_metrics)

    reference_time_utc = quality_metrics.get("latest_time_utc") if quality_metrics.get("valid") else datetime.now(UTC)
    if not isinstance(reference_time_utc, datetime):
        reference_time_utc = datetime.now(UTC)
    results = apply_alert_stability(results, reference_time_utc)

    suppress_alerts = should_suppress_alerts(plowing_info)

    maintenance_reason = "ukjent vedlikeholdstype"
    if plowing_info.last_work_types:
        maintenance_reason = ", ".join([str(x) for x in plowing_info.last_work_types if str(x).strip()])
    elif plowing_info.last_event_type:
        maintenance_reason = str(plowing_info.last_event_type)

    # Stans farevarsel ved nylig vedlikehold (brøyting/strøing)
    if suppress_alerts:
        suppressed = {}
        for name, r in results.items():
            if r.risk_level != RiskLevel.LOW:
                suppressed[name] = AnalysisResult(
                    risk_level=RiskLevel.LOW,
                    message=f"Nylig vedlikehold ({maintenance_reason}) – farevarsel stanset",
                    scenario=r.scenario,
                    factors=(r.factors or []) + [f"Nylig vedlikehold: {maintenance_reason}"],
                    details={
                        **(r.details or {}),
                        "suppressed_by_maintenance": True,
                        "maintenance_hours_since": plowing_info.hours_since,
                        "maintenance_event_type": plowing_info.last_event_type,
                        "maintenance_work_types": plowing_info.last_work_types,
                        "maintenance_operator_id": plowing_info.last_operator_id,
                    },
                    timestamp=r.timestamp,
                )
            else:
                suppressed[name] = r
        results = suppressed

    confidence_map = _compute_confidence_map(results, quality_metrics, suppress_alerts)

    # Ingen overordnet varselboks over kortene.
    # Brukeren forholder seg til de fire kortene i "Varsler nå".

    # Flyttet opp: Siste vedlikehold (erstatter tidligere "NORMALE FORHOLD"-banner)
    render_maintenance_top(plowing_info, suppress_alerts)

    if suppress_alerts:
        if plowing_info.hours_since is not None:
            st.caption(
                f"Varsler er midlertidig undertrykt av vedlikehold: {maintenance_reason} "
                f"({float(plowing_info.hours_since):.1f}t siden)"
            )
        else:
            st.caption(
                f"Varsler er midlertidig undertrykt av vedlikehold: {maintenance_reason}"
            )

    st.divider()

    # Compact status summary
    st.subheader("Varsler nå")

    col1, col2 = st.columns(2)
    with col1:
        render_compact_risk_card("Nysnø", results["Nysnø"], confidence_map.get("Nysnø"))
    with col2:
        render_compact_risk_card("Snøfokk", results["Snøfokk"], confidence_map.get("Snøfokk"))

    col3, col4 = st.columns(2)
    with col3:
        render_compact_risk_card("Slaps", results["Slaps"], confidence_map.get("Slaps"))
    with col4:
        render_compact_risk_card("Glatte veier", results["Glatte veier"], confidence_map.get("Glatte veier"))

    # Current metrics
    st.subheader("Nåværende forhold")

    # Operational logging: use raw analyzer results (before quality guard and
    # suppression) so that HIGH-risk events are captured even when
    # data_quality_guard has downgraded them to UNKNOWN for display purposes.
    try:
        log_medium_high_alerts(
            results=raw_results_for_log,
            df=df,
            plowing_info=plowing_info,
            suppressed_by_maintenance=suppress_alerts,
            suppression_reason=maintenance_reason if suppress_alerts else "",
            quality_guard_note=quality_note or "",
        )
    except (RuntimeError, ValueError, TypeError, KeyError, OSError) as e:
        logger.warning("Operational logger failed: %s", e)

    render_key_metrics(df)

    st.divider()

    render_forecast_section()
    st.divider()

    st.subheader("Værgrafer")
    snow_tab, precip_tab, temp_tab, wind_tab, wind_chill_tab, wind_dir_tab = st.tabs([
        "Snødybde",
        "Nedbør",
        "Temperatur",
        "Vindstyrke",
        "Vindkjøling",
        "Vindretning",
    ])

    with snow_tab:
        fig = WeatherPlots.create_snow_depth_plot(df)
        st.pyplot(fig)
        st.caption(f"Nysnø vises som endring siste {settings.fresh_snow.lookback_hours} timer")
        plt.close(fig)

    with precip_tab:
        slaps_precip_scale = max(settings.slaps.precipitation_accum_hours, 1) / 12.0
        slaps_precip_threshold = settings.slaps.precipitation_12h_min * slaps_precip_scale
        col1, col2 = st.columns(2)
        with col1:
            fig = WeatherPlots.create_precip_plot(df)
            st.pyplot(fig)
            st.caption(
                f"{settings.slaps.precipitation_accum_hours}t akkumulert linje og slaps-terskel "
                f"({slaps_precip_threshold:.1f} mm)"
            )
            plt.close(fig)
        with col2:
            fig = WeatherPlots.create_accumulated_precip_plot(df)
            st.pyplot(fig)
            st.caption("Total nedbør i valgt periode")
            plt.close(fig)

    with temp_tab:
        fig = WeatherPlots.create_temperature_plot(df)
        st.pyplot(fig)
        st.caption(f"Duggpunkt < {settings.fresh_snow.dew_point_max:.0f}°C: Nedbør faller som snø")
        plt.close(fig)

    with wind_tab:
        fig = WeatherPlots.create_wind_plot(df)
        st.pyplot(fig)
        st.caption(
            f"Markering når vindkast overstiger {settings.snowdrift.wind_gust_warning:.0f} m/s"
        )
        plt.close(fig)

    with wind_chill_tab:
        fig = WeatherPlots.create_wind_chill_plot(df)
        st.pyplot(fig)
        st.caption(
            f"Vindkjøling advarsel/kritisk: {settings.snowdrift.wind_chill_warning:.0f}°C / "
            f"{settings.snowdrift.wind_chill_critical:.0f}°C"
        )
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
                width="stretch",
                hide_index=True
            )

        with tab2:
            slaps_precip_scale = max(settings.slaps.precipitation_accum_hours, 1) / 12.0
            slaps_precip_threshold = settings.slaps.precipitation_12h_min * slaps_precip_scale
            st.markdown(f"""
            ### Validerte terskler (2025)

            | Kategori | Kriterium | Terskel |
            |----------|-----------|---------|
            | **Nysnø** | Snøøkning {settings.fresh_snow.lookback_hours}t | Våt: ≥ {settings.fresh_snow.snow_increase_warning:.0f} / {settings.fresh_snow.snow_increase_critical:.0f} cm, Tørr: ≥ {settings.fresh_snow.snow_increase_warning_dry:.0f} / {settings.fresh_snow.snow_increase_critical_dry:.0f} cm |
            | **Nysnø** | Duggpunkt | < {settings.fresh_snow.dew_point_max:.0f}°C (snø) |
            | **Nysnø** | Fallback nedbør (6t, ved vind) | Våt: ≥ {settings.fresh_snow.precipitation_6h_warning_mm:.0f} / {settings.fresh_snow.precipitation_6h_critical_mm:.0f} mm, Tørr: ≥ {settings.fresh_snow.precipitation_6h_warning_mm_dry:.0f} / {settings.fresh_snow.precipitation_6h_critical_mm_dry:.0f} mm |
            | **Snøfokk** | Vindkast | ≥ {settings.snowdrift.wind_gust_warning:.0f} m/s (advarsel) / ≥ {settings.snowdrift.wind_gust_critical:.0f} m/s (kritisk) |
            | **Snøfokk** | Vindkjøling | ≤ {settings.snowdrift.wind_chill_warning:.0f}°C (advarsel) / ≤ {settings.snowdrift.wind_chill_critical:.0f}°C (kritisk) |
            | **Slaps** | Temperatur | {settings.slaps.temp_min:.0f} til {settings.slaps.temp_max:.0f}°C |
            | **Slaps** | Nedbør ({settings.slaps.precipitation_accum_hours}t) | ≥ {slaps_precip_threshold:.1f} mm |
            | **Glatte veier** | Bakketemperatur | ≤ {settings.slippery.surface_temp_freeze:.0f}°C |
            | **Glatte veier** | Skjult frysefare | Luft {settings.slippery.hidden_freeze_air_min:.0f}-{settings.slippery.hidden_freeze_air_max:.0f}°C og bakke ≤ {settings.slippery.hidden_freeze_surface_max:.1f}°C |
            """)

    # Footer
    st.divider()
    st.caption(
        f"Data: {len(df)} målinger fra Meteorologisk institutt | "
        f"Stasjon: {settings.station.station_id} {settings.station.name}"
    )

    # Netatmo temperaturkart
    render_netatmo_map()

    # Smøreguide under temperaturkart
    render_wax_guide(df)

    with st.expander("Operasjonelle KPI-er (admin)", expanded=False):
        render_operational_kpis()


@st.cache_data(ttl=settings.netatmo.cache_ttl_seconds)
def fetch_netatmo_stations() -> dict[str, Any]:
    """Hent Netatmo-stasjoner (cached).

    Viktig: `st.cache_data` krever at returverdien kan serialiseres.
    Derfor cacher vi kun en liste med enkle dicts, ikke NetatmoStation-objekter.
    """
    try:
        client = get_netatmo_client()
        if client.authenticate():
            public_stations: list[NetatmoStation] = []
            private_stations: list[NetatmoStation] = []

            # Offentlige stasjoner rundt Fjellbergsskardet (primær for temperaturkart med mange punkter)
            try:
                public_radius = max(int(settings.netatmo.search_radius_km), 35)
                public_stations = client.get_fjellbergsskardet_area(radius_km=public_radius)
            except (RuntimeError, ValueError, TypeError, KeyError, OSError):
                public_stations = []

            # Private konto-stasjoner (sekundær/fallback)
            if hasattr(client, "get_private_stations"):
                private_stations = client.get_private_stations()
            elif hasattr(client, "get_fjellbergsskardet_private"):
                private_stations = client.get_fjellbergsskardet_private(
                    radius_km=max(int(settings.netatmo.search_radius_km), 35)
                )

            combined: list[NetatmoStation] = []
            seen: set[tuple[str, str, float, float]] = set()
            for s in public_stations + private_stations:
                key = (
                    str(s.station_id or "").strip(),
                    str(s.name or "").strip(),
                    round(float(s.lat or 0.0), 6),
                    round(float(s.lon or 0.0), 6),
                )
                if key in seen:
                    continue
                seen.add(key)
                combined.append(s)

            rows: list[dict] = []
            for s in combined:
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
            diagnostics = {
                "public_count": len(public_stations),
                "private_count": len(private_stations),
                "combined_count": len(rows),
            }
            if rows:
                logger.info(
                    "Netatmo kartdata: public=%d private=%d combined=%d",
                    len(public_stations),
                    len(private_stations),
                    len(rows),
                )
                source = "both" if public_stations and private_stations else ("public" if public_stations else "private")
                return {"rows": rows, "error": None, "auth_ok": True, "source": source, "diagnostics": diagnostics}

            if client.last_error:
                return {"rows": [], "error": client.last_error, "auth_ok": False, "source": "none", "diagnostics": diagnostics}
            return {"rows": [], "error": None, "auth_ok": True, "source": "none", "diagnostics": diagnostics}
        return {
            "rows": [],
            "error": client.last_error or "Ukjent autentiseringsfeil",
            "auth_ok": False,
            "source": "none",
            "diagnostics": {"public_count": 0, "private_count": 0, "combined_count": 0},
        }
    except (RuntimeError, ValueError, TypeError, KeyError, OSError) as e:
        logger.warning("Netatmo feil: %s", e)
        return {
            "rows": [],
            "error": f"Netatmo feil: {e}",
            "auth_ok": False,
            "source": "none",
            "diagnostics": {"public_count": 0, "private_count": 0, "combined_count": 0},
        }


@st.cache_resource
def get_netatmo_client() -> NetatmoClient:
    """Gjenbruk Netatmo-klient mellom reruns for mindre overhead."""
    return NetatmoClient()


def render_netatmo_map() -> None:
    """Render temperaturkart for tilgjengelige Netatmo-stasjoner."""

    col_title, col_btn = st.columns([4, 1])
    with col_title:
        st.subheader("Temperaturkart")
    with col_btn:
        if st.button("Oppdater", key="netatmo_refresh"):
            fetch_netatmo_stations.clear()
            st.rerun()

    cached = fetch_netatmo_stations()
    cached_rows = cached.get("rows", [])
    cached_error = cached.get("error")
    auth_ok = bool(cached.get("auth_ok"))
    source = str(cached.get("source") or "none")
    diagnostics = cached.get("diagnostics") or {}

    stations: list[NetatmoStation] = []
    for r in cached_rows:
        ts = None
        if r.get("timestamp"):
            try:
                ts = datetime.fromisoformat(r["timestamp"])
            except ValueError:
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
        if cached_error:
            st.info(f"Ingen Netatmo-data tilgjengelig ({cached_error}).")
        elif auth_ok:
            st.info("Ingen private Netatmo-stasjoner med data tilgjengelig akkurat nå.")
        else:
            st.info(
                "Ingen Netatmo-data tilgjengelig. "
                "Sett NETATMO_ACCESS_TOKEN eller NETATMO_CLIENT_ID/NETATMO_CLIENT_SECRET/NETATMO_REFRESH_TOKEN."
            )
        return

    # Filtrer stasjoner med temperatur
    temp_stations = [s for s in stations if s.temperature is not None]

    if not temp_stations:
        st.warning("Ingen temperaturdata fra Netatmo-stasjoner")
        return

    # Lag DataFrame for kart med alle data
    map_data = []
    coord_seen: dict[tuple[float, float], int] = {}
    for s in temp_stations:
        temp = s.temperature
        hum = s.humidity
        alt = s.altitude

        # Flere private moduler kan dele identisk koordinat.
        # Gi små, deterministiske offset slik at punktene ikke tegnes oppå hverandre.
        base_lat = float(s.lat)
        base_lon = float(s.lon)
        key = (round(base_lat, 6), round(base_lon, 6))
        idx = coord_seen.get(key, 0)
        coord_seen[key] = idx + 1

        plot_lat = base_lat
        plot_lon = base_lon
        if idx > 0:
            angle = idx * 2.399963229728653  # Golden angle
            radius_deg = 0.00018 * ((idx + 2) / 2.0)  # ca 20-50m
            plot_lat = base_lat + (radius_deg * math.sin(angle))
            plot_lon = base_lon + (radius_deg * math.cos(angle))

        # Fargekode basert på temperatur (RGB)
        r, g, b = get_temp_rgb(temp or 0.0)

        map_data.append({
            "lat": plot_lat,
            "lon": plot_lon,
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

    st.pydeck_chart(deck, width="stretch")

    if source == "private":
        st.caption("Kilde: Private Netatmo-stasjoner")
    elif source == "public":
        st.caption("Kilde: Offentlige Netatmo-stasjoner")
    elif source == "both":
        st.caption("Kilde: Offentlige + private Netatmo-stasjoner")
    st.caption(f"Viser {len(temp_stations)} stasjon(er) med temperatur")

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
        except (ValueError, OSError):
            latest_local = latest_ts

        st.caption(
            f"Sist oppdatert Netatmo: {latest_local.strftime('%d.%m %H:%M')} "
            f"(ca {minutes} min siden, cache 5 min)"
        )
    else:
        minutes = None

    with st.expander("Netatmo diagnose", expanded=False):
        st.caption(
            f"Kilde: {source} | Public: {int(diagnostics.get('public_count', 0))} | "
            f"Private: {int(diagnostics.get('private_count', 0))} | "
            f"Kombinert: {int(diagnostics.get('combined_count', 0))} | "
            f"Med temperatur: {len(temp_stations)}"
        )
        st.caption(f"Auth OK: {'ja' if auth_ok else 'nei'}")
        if minutes is not None:
            st.caption(f"Siste datapunkt alder: ca {minutes} min")

    # Temperaturstatistikk under kartet
    temps: list[float] = [s.temperature for s in temp_stations if s.temperature is not None]
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
    render_snow_limit_info(snow_limit, high_stations, low_stations)

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
            width="stretch",
            hide_index=True
        )


@st.cache_data(ttl=settings.plowing_service.streamlit_cache_ttl_seconds)
def get_cached_plowing_info() -> PlowingInfo:
    """Henter brøyteinformasjon fra service (cached)."""
    return get_plowing_info()


def estimate_snow_limit(stations: list) -> dict[str, Any]:
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


def render_snow_limit_info(snow_limit: dict[str, Any], high_stations: list, low_stations: list) -> None:
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
