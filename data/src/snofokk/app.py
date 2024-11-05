import os
import sys
import logging
import logging.handlers
from datetime import datetime
from typing import Dict, Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from . import (analyze_settings, calculate_snow_drift_risk, fetch_frost_data,
               plot_risk_analysis)
from .config import DEFAULT_PARAMS
from .db_utils import (delete_settings, get_saved_settings, init_db,
                       save_settings)
# Lokale imports
from .ml_utils import SnowDriftOptimizer
from .ml_evaluation import MLEvaluator

# Sett opp logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("snofokk.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Legg til i toppen av app.py etter eksisterende imports
import sys
import traceback

# Oppdater logging-oppsettet
def setup_logging():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
    # Filhåndtering
    file_handler = logging.FileHandler('logs/snofokk_debug.log')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # Konsolhåndtering
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def format_settings_summary(params, num_critical_periods):
    """
    Formatterer en lesbar oppsummering av innstillingene
    """
    return {
        "wind": {
            "strong": params["wind_strong"],
            "moderate": params["wind_moderate"],
            "gust": params["wind_gust"],
        },
        "temp": {"cold": params["temp_cold"], "cool": params["temp_cool"]},
        "snow": {
            "high": params["snow_high"],
            "moderate": params["snow_moderate"],
            "low": params["snow_low"],
        },
        "weights": {
            "wind": params["wind_weight"],
            "temp": params["temp_weight"],
            "snow": params["snow_weight"],
        },
        "critical_periods": num_critical_periods,
    }


def save_settings_ui(params, critical_periods, analysis=None):
    """UI-komponent for å lagre vellykkede innstillinger"""
    try:
        st.divider()
        st.subheader("📊 Analyse av gjeldende innstillinger")

        # Vis nøkkeltall
        total_duration = (
            critical_periods["duration"].sum() if not critical_periods.empty else 0
        )
        avg_risk = (
            critical_periods["max_risk_score"].mean()
            if not critical_periods.empty
            else 0
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Kritiske perioder", len(critical_periods))
        with col2:
            st.metric("Total varighet", f"{total_duration:.1f} timer")
        with col3:
            st.metric("Gjennomsnittlig risiko", f"{avg_risk:.1f}")

        # Vis parameterinfo i kolonner
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Vindparametere:**")
            st.write(f"- Sterk vind: {params['wind_strong']} m/s")
            st.write(f"- Moderat vind: {params['wind_moderate']} m/s")
            st.write(f"- Vindkast terskel: {params['wind_gust']} m/s")
            st.write(f"- Vindretningsendring: {params['wind_dir_change']}°")

            st.write("**Temperaturparametere:**")
            st.write(f"- Kald temperatur: {params['temp_cold']}°C")
            st.write(f"- Kjølig temperatur: {params['temp_cool']}°C")

        with col2:
            st.write("**Snøparametere:**")
            st.write(f"- Høy snøendring: {params['snow_high']} cm")
            st.write(f"- Moderat snøendring: {params['snow_moderate']} cm")
            st.write(f"- Lav snøendring: {params['snow_low']} cm")

            st.write("**Vekting og andre parametere:**")
            st.write(f"- Vindvekt: {params['wind_weight']}")
            st.write(f"- Temperaturvekt: {params['temp_weight']}")
            st.write(f"- Snøvekt: {params['snow_weight']}")
            st.write(f"- Minimum varighet: {params['min_duration']} timer")

        # Lagringsseksjon
        st.divider()
        st.write("💾 **Lagre disse innstillingene**")

        with st.form("save_settings_form"):
            settings_name = st.text_input(
                "Navn på innstillingene",
                placeholder="F.eks. 'Vinter 2024 - Høy sensitivitet'",
            )

            settings_desc = st.text_area(
                "Beskrivelse",
                placeholder="Beskriv hvorfor disse innstillingene fungerer bra...",
                help="Legg gjerne til informasjon om værforhold, sesong, etc.",
            )

            # Vis endringer fra standard
            st.write("Vesentlige endringer fra standardinnstillinger:")
            changes = []
            for key, value in params.items():
                if value != DEFAULT_PARAMS[key]:
                    changes.append(f"- {key}: {DEFAULT_PARAMS[key]} → {value}")

            if changes:
                st.code("\n".join(changes))
            else:
                st.info("Ingen endringer fra standardinnstillinger")

            # Lagre-knapp
            if st.form_submit_button("Lagre innstillinger"):
                if not settings_name:
                    st.error("Du må gi innstillingene et navn")
                    return

                # Forbered data for lagring
                settings_data = {
                    "name": settings_name,
                    "description": settings_desc,
                    "timestamp": datetime.now().isoformat(),
                    "parameters": format_settings_summary(
                        params, len(critical_periods)
                    ),
                    "changes": changes,
                }

                # Lagre til database
                success, message = save_settings(settings_data, critical_periods)
                if success:
                    st.success(message)
                else:
                    st.error(message)

    except Exception as e:
        logger.error(f"Feil i save_settings_ui: {str(e)}")
        st.error("Kunne ikke vise analysen. Sjekk loggene for detaljer.")


def show_settings():
    """Viser innstillingssiden"""
    st.title("⚙️ Innstillinger")

    # Hent lagrede innstillinger
    saved_settings = get_saved_settings()

    if saved_settings:
        st.write("### 💾 Lagrede innstillinger")
        for setting in saved_settings:
            with st.expander(f"Innstilling fra {setting['timestamp']}"):
                st.write("**Parametre:**")
                st.json(setting["params"])

                if st.button("Slett", key=f"delete_{setting['timestamp']}"):
                    delete_settings(setting["timestamp"])
                    st.success("Innstilling slettet!")
                    st.rerun()
    else:
        st.info("Ingen lagrede innstillinger funnet")


def plot_critical_periods(
    df: pd.DataFrame, periods_df: pd.DataFrame
) -> tuple[go.Figure, pd.DataFrame]:
    """
    Lager en detaljert visualisering av kritiske snøfokkperioder

    Args:
        df: DataFrame med værdata og risikoberegninger
        periods_df: DataFrame med identifiserte perioder
    Returns:
        Tuple med Plotly figur og kritiske perioder DataFrame
    """
    try:
        # Finn kritiske perioder
        critical_periods = periods_df[periods_df["risk_level"] == "Kritisk"].copy()

        if critical_periods.empty:
            st.warning("Ingen kritiske perioder funnet i valgt tidsperiode")
            return None, critical_periods

        # Opprett subplots
        fig = make_subplots(
            rows=5,
            cols=1,  # Redusert til 5 rader siden vi ikke trenger nedbør
            subplot_titles=(
                "Risikoscore",
                "Vindforhold under kritiske perioder",
                "Temperatur under kritiske perioder",
                "Snødybde og endring under kritiske perioder",
                "Oversikt over kritiske perioder",
            ),
            vertical_spacing=0.05,
            shared_xaxes=True,
            row_heights=[0.2, 0.2, 0.2, 0.2, 0.2],
        )

        # Marker kritiske perioder
        for _, period in critical_periods.iterrows():
            for row in range(1, 6):  # Oppdatert til 5 rader
                fig.add_vrect(
                    x0=period["start_time"],
                    x1=period["end_time"],
                    fillcolor="rgba(255, 0, 0, 0.1)",
                    layer="below",
                    line_width=0,
                    row=row,
                    col=1,
                )

        # Risikoscore
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["risk_score"],
                name="Risikoscore",
                line=dict(color="red", width=1),
            ),
            row=1,
            col=1,
        )
        fig.add_hline(
            y=70,
            line_dash="dash",
            line_color="red",
            row=1,
            col=1,
            annotation={"text": "Kritisk nivå (70)", "x": 0},
        )

        # Vindforhold
        if "sustained_wind" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["sustained_wind"],
                    name="Vedvarende vind",
                    line=dict(color="blue"),
                ),
                row=2,
                col=1,
            )

        if "max(wind_speed_of_gust PT1H)" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["max(wind_speed_of_gust PT1H)"],
                    name="Vindkast",
                    line=dict(color="lightblue", dash="dash"),
                ),
                row=2,
                col=1,
            )

        # Temperatur
        if "air_temperature" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["air_temperature"],
                    name="Temperatur",
                    line=dict(color="green"),
                ),
                row=3,
                col=1,
            )
            fig.add_hline(
                y=0,
                line_dash="dash",
                line_color="gray",
                row=3,
                col=1,
                annotation=dict(text="Frysepunkt", x=0),
            )

        # Snødybde og endring
        if "surface_snow_thickness" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["surface_snow_thickness"],
                    name="Snødybde",
                    line=dict(color="purple"),
                ),
                row=4,
                col=1,
            )

        if "snow_depth_change" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["snow_depth_change"],
                    name="Endring i snødybde",
                    line=dict(color="magenta", dash="dot"),
                ),
                row=4,
                col=1,
            )

        # Fokusert visning av kritiske perioder
        for _, period in critical_periods.iterrows():
            period_data = df[period["start_time"] : period["end_time"]]
            fig.add_trace(
                go.Scatter(
                    x=period_data.index,
                    y=period_data["risk_score"],
                    name=f"Kritisk periode {int(period['period_id'])}",
                    mode="lines+markers",
                    line=dict(width=3),
                    marker={"size": 8},
                ),
                row=5,
                col=1,
            )

        # Oppdater layout
        fig.update_layout(
            title={
                "text": "Detaljert analyse av kritiske snøfokkperioder",
                "y": 0.95,
                "x": 0.5,
                "xanchor": "center",
                "yanchor": "top",
            },
            height=1200,
            showlegend=True,
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
            },
        )

        # Legg til y-akse titler
        fig.update_yaxes(title_text="Score", row=1, col=1)
        fig.update_yaxes(title_text="m/s", row=2, col=1)
        fig.update_yaxes(title_text="°C", row=3, col=1)
        fig.update_yaxes(title_text="cm", row=4, col=1)
        fig.update_yaxes(title_text="Score", row=5, col=1)

        # Forbedret x-akse format
        fig.update_xaxes(tickformat="%d-%m-%Y\n%H:%M")

        return fig, critical_periods

    except Exception as e:
        logger.error(f"Feil i plotting av kritiske perioder: {str(e)}")
        return None, pd.DataFrame()


def plot_critical_periods_overview(df: pd.DataFrame, periods_df: pd.DataFrame):
    """
    Lager en oversiktsgraf som viser score-spennet for kun de mest kritiske periodene
    """
    try:
        if periods_df.empty:
            return None

        # Filtrer ut bare de mest kritiske periodene
        critical_threshold = 0.85  # Høy terskel for å få ca. 14 perioder
        min_duration = 3  # Timer

        # Filtrer og sorter periodene
        critical_periods = (
            periods_df[
                (periods_df["max_risk_score"] > critical_threshold)
                & (periods_df["duration"] >= min_duration)
            ]
            .sort_values("max_risk_score", ascending=False)
            .head(14)
        )

        if critical_periods.empty:
            return None

        # Opprett figur
        fig = go.Figure()

        # Legg til hver kritisk periode som en vertikal linje
        for _, period in critical_periods.iterrows():
            period_data = df[
                (df.index >= period["start_time"]) & (df.index <= period["end_time"])
            ]

            if not period_data.empty:
                # Beregn statistikk
                min_score = period_data["risk_score"].min() * 100
                max_score = period["max_risk_score"] * 100
                avg_wind = period_data["wind_speed"].mean()
                max_wind = period_data["wind_speed"].max()
                min_temp = period_data["air_temperature"].min()

                # Legg til vertikal linje
                fig.add_trace(
                    go.Scatter(
                        x=[period["start_time"], period["start_time"]],
                        y=[min_score, max_score],
                        mode="lines",
                        line=dict(color="red", width=3),
                        name=f"Kritisk periode {int(period['period_id'])}",
                        hovertemplate=(
                            "<b>Kritisk periode</b><br>"
                            + f"Start: {period['start_time'].strftime('%d-%m-%Y %H:%M')}<br>"
                            + f"Varighet: {period['duration']:.1f} timer<br>"
                            + f"Risiko: {max_score:.1f}%<br>"
                            + f"Vind: {avg_wind:.1f} m/s (maks {max_wind:.1f})<br>"
                            + f"Min temp: {min_temp:.1f}°C"
                        ),
                    )
                )

        # Oppdater layout
        fig.update_layout(
            title="Oversikt over mest kritiske perioder",
            height=300,
            showlegend=False,
            yaxis_title="Risikoscore (%)",
            xaxis_title="",
            hovermode="x unified",
            margin=dict(t=30, b=20, l=50, r=20),
            plot_bgcolor="white",
            yaxis=dict(gridcolor="lightgray", range=[0, 100], tickformat=",d"),
            xaxis=dict(gridcolor="lightgray", tickformat="%d-%m-%Y\n%H:%M"),
        )

        return fig

    except Exception as e:
        logger.error(f"Feil i plot_critical_periods_overview: {str(e)}")
        return None


def display_critical_alerts(df: pd.DataFrame, periods_df: pd.DataFrame):
    """
    Viser en kompakt oversikt over kritiske varsler
    """
    try:
        if periods_df.empty:
            st.warning("Ingen kritiske perioder funnet i valgt tidsperiode.")
            return

        # Filtrer ut kritiske perioder (samme logikk som i plot_critical_periods_overview)
        critical_threshold = 0.85
        min_duration = 3
        critical_periods = (
            periods_df[
                (periods_df["max_risk_score"] > critical_threshold)
                & (periods_df["duration"] >= min_duration)
            ]
            .sort_values("max_risk_score", ascending=False)
            .head(14)
        )

        # Vis grafen med kritiske perioder først
        fig = plot_critical_periods_overview(df, periods_df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)

        # Vis detaljert liste under grafen
        if not critical_periods.empty:
            st.subheader("Detaljer for kritiske perioder")
            for _, period in critical_periods.iterrows():
                with st.expander(
                    f"Periode {int(period['period_id'])} - {period['start_time'].strftime('%Y-%m-%d %H:%M')}"
                ):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Varighet", f"{period['duration']:.1f} timer")
                    with col2:
                        st.metric("Maks risiko", f"{period['max_risk_score']*100:.0f}%")
                    with col3:
                        st.metric("Alvorlighet", period.get("severity", "Ukjent"))

    except Exception as e:
        logger.error(f"Feil i visning av kritiske varsler: {str(e)}")
        st.error("Kunne ikke vise kritiske varsler")


def show_ml_optimization():
    """Viser ML-optimalisering av parametre"""
    st.title("🤖 ML-optimalisering av parametre")

    try:
        # Hent datoperiode
        start_date, end_date = show_date_selector()

        if start_date is None or end_date is None:
            return

        # Last inn data
        with st.spinner("Henter værdata fra Frost..."):
            df = fetch_frost_data(start_date=start_date, end_date=end_date)

        if df is None:
            st.error("Kunne ikke laste værdata")
            return

        # Hent gjeldende parametre fra session state
        current_params = st.session_state.get("params", DEFAULT_PARAMS.copy())

        # Initialiser optimizer med gjeldende parametre
        optimizer = SnowDriftOptimizer(initial_params=current_params)

        # Vis optimaliserings-opsjoner
        st.subheader("Optimaliseringsinnstillinger")
        target = st.selectbox(
            "Optimaliseringsmål",
            ["r2_score", "mean_squared_error", "mean_absolute_error"],
            help="Velg hvilken metrikk som skal optimaliseres",
        )

        if st.button("Start optimalisering"):
            with st.spinner("Optimaliserer parametre..."):
                results = optimizer.optimize_parameters(df, target)

                if results and results.get('status') == 'success':
                    # Vis sammendrag av forbedringer
                    st.write("### Modellytelse")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Original score", f"{results['current_score']:.4f}")
                    with col2:
                        st.metric("Optimalisert score", f"{results['best_score']:.4f}")
                    with col3:
                        forbedring = ((results['best_score'] - results['current_score']) / abs(results['current_score'])) * 100
                        st.metric("Forbedring", f"{forbedring:.1f}%")
                    
                    # Vis beste parametre i en pen tabell
                    st.write("### Beste Parametre")
                    param_df = pd.DataFrame({
                        'Parameter': list(results['best_params'].keys()),
                        'Verdi': [str(v) for v in results['best_params'].values()],
                        'Beskrivelse': [
                            'Antall beslutningstrær',
                            'Maksimal dybde for hvert tre',
                            'Minimum antall samples for split',
                            'Minimum antall samples i blad',
                            'Feature-utvalgsmetode'
                        ]
                    })
                    st.dataframe(
                        param_df,
                        column_config={
                            "Parameter": "Parameter",
                            "Verdi": "Optimalisert Verdi",
                            "Beskrivelse": "Forklaring"
                        },
                        hide_index=True
                    )
                    
                    # Vis optimaliseringshistorikk
                    st.write("### Optimaliseringshistorikk")
                    if 'optimization_history' in results:
                        history_df = pd.DataFrame(results['optimization_history'])
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            y=-history_df['value'],
                            mode='lines+markers',
                            name='Score'
                        ))
                        fig.update_layout(
                            title="Forbedring over tid",
                            yaxis_title="Score",
                            xaxis_title="Forsøk nr",
                            showlegend=False
                        )
                        st.plotly_chart(fig)

                    # Tilby mulighet til å bruke de nye parametrene
                    if st.button("Bruk optimaliserte parametre"):
                        st.session_state["params"] = results["best_params"]
                        st.rerun()

                    # Legg til parametereffekt-analyse
                    st.write("### Parametereffekt-analyse")
                    
                    # Opprett MLEvaluator og analyser
                    evaluator = MLEvaluator()
                    impact_analysis = evaluator.evaluate_parameter_impact(
                        df, 
                        original_params=optimizer.initial_params,
                        optimized_params=results['best_params']
                    )
                    
                    if impact_analysis:
                        # Vis anbefalinger
                        if impact_analysis.get('recommendations'):
                            st.write("#### Anbefalinger for parameterinnstillinger")
                            for rec in impact_analysis['recommendations']:
                                st.info(rec['message'])
                        
                        # Vis parameterendringer
                        if impact_analysis.get('risk_scores'):
                            st.write("#### Effekt på risikoscore")
                            scores = impact_analysis['risk_scores']
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Original gjennomsnitt", f"{scores['original']['mean']:.2f}")
                                st.metric("Original maks", f"{scores['original']['max']:.2f}")
                            with col2:
                                st.metric("Optimalisert gjennomsnitt", f"{scores['optimized']['mean']:.2f}")
                                st.metric("Optimalisert maks", f"{scores['optimized']['max']:.2f}")

                    # Vis ML-parametre
                    st.write("### ML-modellparametre")
                    ml_param_df = pd.DataFrame({
                        'Parameter': list(results['best_params'].keys()),
                        'Verdi': [str(v) for v in results['best_params'].values()],
                        'Beskrivelse': [
                            'Antall beslutningstrær',
                            'Maksimal dybde for hvert tre',
                            'Minimum antall samples for split',
                            'Minimum antall samples i blad',
                            'Feature-utvalgsmetode'
                        ]
                    })
                    st.dataframe(ml_param_df, hide_index=True)
                    
                    # Vis anbefalte snøfokk-parametre
                    st.write("### Anbefalte snøfokk-parametre")
                    if impact_analysis and impact_analysis.get('parameters'):
                        params = impact_analysis['parameters']
                        snofokk_param_df = pd.DataFrame({
                            'Parameter': list(params['optimized'].keys()),
                            'Original verdi': [params['original'][k] for k in params['optimized'].keys()],
                            'Anbefalt verdi': [params['optimized'][k] for k in params['optimized'].keys()],
                            'Beskrivelse': [
                                'Grense for sterk vind (m/s)',
                                'Grense for moderat vind (m/s)',
                                'Grense for vindkast (m/s)',
                                'Grense for vindretningsendring (grader)',
                                'Vekting av vindfaktor',
                                'Grense for kald temperatur (°C)',
                                'Grense for kjølig temperatur (°C)',
                                'Vekting av temperaturfaktor',
                                'Grense for høy snøendring (cm)',
                                'Grense for moderat snøendring (cm)',
                                'Grense for lav snøendring (cm)',
                                'Vekting av snøfaktor',
                                'Minimum varighet (timer)',
                                'Temperaturgrense (°C)',
                                'Minimum snødybde (cm)',
                                'Risikogrense'
                            ]
                        })
                        st.dataframe(snofokk_param_df, hide_index=True)

                else:
                    st.error(f"Optimalisering feilet: {results.get('error', 'Ukjent feil')}")

    except Exception as e:
        logger.error(f"Feil i ML-optimalisering: {str(e)}", exc_info=True)
        st.error("En feil oppstod under optimalisering")

def show_main_analysis():
    """Viser hovedanalysen"""
    st.title("🌨️ Snøfokk-analyse")

    try:
        # Hent datoperiode
        start_date, end_date = show_date_selector()

        if start_date is None or end_date is None:
            return

        # Last inn værdata
        with st.spinner("Henter værdata fra Frost..."):
            df = fetch_frost_data(start_date=start_date, end_date=end_date)

        if df is not None:
            # Hent eller initialiser parametre
            params = st.session_state.get("params", DEFAULT_PARAMS.copy())

            # Beregn risiko og få kritiske perioder
            df_risk, critical_periods = calculate_snow_drift_risk(df, params)

            # Legg til valg mellom visualiseringer
            viz_type = st.radio(
                "Velg visualiseringstype",
                ["Standard", "Kombinert analyse"],
                horizontal=True,
            )

            if viz_type == "Standard":
                # Vis hovedplot
                fig = plot_risk_analysis(df_risk)
                if fig is not None:
                    st.plotly_chart(fig, use_container_width=True)
            else:
                # Midlertidig: vis bare standardvisning
                fig = plot_risk_analysis(df_risk)
                if fig is not None:
                    st.plotly_chart(fig, use_container_width=True)

            # Vis kritiske varsler
            display_critical_alerts(df_risk, critical_periods)

            # Beregn analyse
            analysis = analyze_settings(df_risk, critical_periods)

            # Vis lagringsmuligheter
            save_settings_ui(params, critical_periods, analysis)

    except Exception as e:
        logger.error(f"Feil i hovedanalyse: {str(e)}", exc_info=True)
        st.error("En feil oppstod i hovedanalysen")
        logger.exception(e)


def show_parameter_controls():
    """Viser parameterinnstillinger i sidepanel"""
    logger.debug("Starter parameter-kontroller")
    st.sidebar.subheader("⚙️ Parameterinnstillinger")

    # Hent eller initialiser parametre med debugging
    params = st.session_state.get("params", DEFAULT_PARAMS.copy())
    logger.debug(f"Initielle parametre: {params}")

    # Lagre gamle verdier for sammenligning
    old_params = params.copy()

    # Vindparametere
    st.sidebar.write("**Vindparametere**")
    params["wind_strong"] = st.sidebar.slider(
        "Sterk vind (m/s)", 10.0, 25.0, float(params["wind_strong"]), step=0.5
    )
    params["wind_moderate"] = st.sidebar.slider(
        "Moderat vind (m/s)", 5.0, 15.0, float(params["wind_moderate"]), step=0.5
    )
    params["wind_gust"] = st.sidebar.slider(
        "Vindkast terskel (m/s)", 10.0, 30.0, float(params["wind_gust"]), step=0.5
    )
    params["wind_dir_change"] = st.sidebar.slider(
        "Vindretningsendring (grader)",
        0.0,
        180.0,
        float(params["wind_dir_change"]),
        step=0.5,
    )
    params["wind_weight"] = st.sidebar.slider(
        "Vindvekt", 0.0, 2.0, float(params["wind_weight"]), step=0.1
    )

    # Temperaturparametere
    st.sidebar.write("**Temperaturparametere**")
    params["temp_cold"] = st.sidebar.slider(
        "Kald temperatur (°C)", -20.0, -5.0, float(params["temp_cold"]), step=0.5
    )
    params["temp_cool"] = st.sidebar.slider(
        "Kjølig temperatur (°C)", -5.0, 2.0, float(params["temp_cool"]), step=0.5
    )
    params["temp_weight"] = st.sidebar.slider(
        "Temperaturvekt", 0.0, 2.0, float(params["temp_weight"]), step=0.1
    )

    # Snøparametere
    st.sidebar.write("**Snøparametere**")
    params["snow_high"] = st.sidebar.slider(
        "Høy snøendring (cm)", 5.0, 20.0, float(params["snow_high"]), step=0.5
    )
    params["snow_moderate"] = st.sidebar.slider(
        "Moderat snøendring (cm)", 2.0, 10.0, float(params["snow_moderate"]), step=0.5
    )
    params["snow_low"] = st.sidebar.slider(
        "Lav snøendring (cm)", 0.0, 5.0, float(params["snow_low"]), step=0.5
    )
    params["snow_weight"] = st.sidebar.slider(
        "Snøvekt", 0.0, 2.0, float(params["snow_weight"]), step=0.1
    )

    # Oppdater session state og trigger rerun hvis parameterne er endret
    if params != old_params:
        logger.info("Parametre endret:")
        for key in params:
            if params[key] != old_params[key]:
                logger.info(f"{key}: {old_params[key]} -> {params[key]}")

        st.session_state["params"] = params
        logger.debug("Parametre oppdatert i session state")
        st.rerun()

    return params


def show_date_selector():
    """Viser datovalgfunksjonalitet"""
    st.sidebar.write("**Velg datoperiode**")

    # Standard vinterperiode (1. november 2023 - 30. april 2024)
    default_start_date = datetime(2023, 11, 1)
    default_end_date = datetime(2024, 4, 30)

    # Dato-inputs
    start_date = st.sidebar.date_input(
        "Fra dato",
        value=default_start_date,
        min_value=datetime(2023, 11, 1),
        max_value=datetime(2024, 4, 30),
    )

    end_date = st.sidebar.date_input(
        "Til dato",
        value=default_end_date,
        min_value=datetime(2023, 11, 1),
        max_value=datetime(2024, 4, 30),
    )

    # Valider datoperioden
    if start_date > end_date:
        st.sidebar.error("Fra-dato må være før til-dato")
        return None, None

    # Konverter til string format
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    return start_date_str, end_date_str


# Oppdater main() funksjonen
def main():
    logger.info("Starter applikasjon")
    st.set_page_config(page_title="Snøfokk-analyse", layout="wide")
    
    try:
        # Initialiser database med debugging
        logger.debug("Initialiserer database...")
        init_db()
        logger.debug("Database initialisert")
        
        # Legg til menyvalg
        menu = ["Hovedanalyse", "ML-optimalisering", "Innstillinger"]
        choice = st.sidebar.selectbox("Velg analyse", menu)
        logger.debug(f"Menyvalg: {choice}")
        
        # Vis parameterkontrollen for relevante sider
        if choice in ["Hovedanalyse", "ML-optimalisering"]:
            logger.debug(f"Viser parameter-kontroller for {choice}")
            _ = show_parameter_controls()
        
        # Vis valgt side
        if choice == "Hovedanalyse":
            show_main_analysis()
        elif choice == "ML-optimalisering":
            show_ml_optimization()
        elif choice == "Innstillinger":
            show_settings()
            
    except Exception as e:
        logger.error("Kritisk feil i applikasjon", exc_info=True)
        st.error("En kritisk feil oppstod. Sjekk loggene for detaljer.")


if __name__ == "__main__":
    main()
