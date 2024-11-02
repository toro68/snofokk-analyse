import logging
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from config import DEFAULT_PARAMS
from db_utils import delete_settings, get_saved_settings, init_db, save_settings

# Lokale imports
from ml_utils import SnowDriftOptimizer
from snofokk import analyze_settings, calculate_snow_drift_risk, fetch_frost_data

# Sett opp logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("snofokk.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


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


def save_settings_ui(params, critical_periods, analysis):
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


def plot_risk_analysis(df):
    """Lager interaktiv visualisering av risikoanalysen"""
    fig = make_subplots(
        rows=5,
        cols=1,
        subplot_titles=(
            "Risikoscore og Nivå",
            "Vind og Vindkast",
            "Temperatur",
            "Snødybde og Endring",
            "Nedbør",
        ),
        vertical_spacing=0.08,
    )

    # Risikoscore
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df["risk_score"], name="Risikoscore", line=dict(color="red")
        ),
        row=1,
        col=1,
    )

    # Vind
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

    # Nedbør - med riktig kolonnenavn for nedbørsvarighet
    if "sum(duration_of_precipitation PT1H)" in df.columns:
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["sum(duration_of_precipitation PT1H)"],
                name="Nedbørsvarighet",  # Oppdatert navn
                marker_color="lightblue",
            ),
            row=5,
            col=1,
        )
    elif "precipitation_amount" in df.columns:  # Sjekk alternativt kolonnenavn
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["precipitation_amount"],
                name="Nedbør",
                marker_color="lightblue",
            ),
            row=5,
            col=1,
        )
    else:
        # Legg til en tom trace for å beholde subplot-strukturen
        fig.add_trace(
            go.Bar(
                x=[df.index[0]],
                y=[0],
                name="Nedbør (ingen data)",
                marker_color="lightgray",
            ),
            row=5,
            col=1,
        )

    # Oppdater layout
    fig.update_layout(title="Snøfokk-risikoanalyse", showlegend=True, height=1200)

    # Legg til y-akse titler
    fig.update_yaxes(title_text="Score", row=1, col=1)
    fig.update_yaxes(title_text="m/s", row=2, col=1)
    fig.update_yaxes(title_text="°C", row=3, col=1)
    fig.update_yaxes(title_text="cm", row=4, col=1)
    fig.update_yaxes(
        title_text="Nedbørsvarighet (min)", row=5, col=1
    )  # Endret enhet til minutter

    return fig


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
            annotation=dict(text="Kritisk nivå (70)", x=0),
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
                    marker=dict(size=8),
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
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
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
    if periods_df.empty:
        return None

    # Hent gjeldende parametre fra session state
    params = st.session_state.get("params", DEFAULT_PARAMS)

    # Beregn kritisk grense basert på wind_weight
    # Høyere vindvekt betyr at vi bør være mer selektive med kritiske perioder
    critical_threshold = 0.8  # Standard grense
    if params["wind_weight"] > 1.5:
        critical_threshold = 0.85  # Øk grensen for høy vindvekt
    elif params["wind_weight"] < 1.0:
        critical_threshold = 0.75  # Senk grensen for lav vindvekt

    # Filtrer ut bare de mest kritiske periodene
    critical_periods = periods_df[
        (periods_df["max_risk_score"] > critical_threshold)
        & (periods_df["duration"] >= params["min_duration"])
    ].copy()

    if critical_periods.empty:
        return None

    # Opprett figur
    fig = go.Figure()

    # Definer fargepalett - bruk rød for høy risiko
    color = "red"

    # Legg til hver kritisk periode som en vertikal linje
    for i, period in critical_periods.iterrows():
        period_data = df[
            (df.index >= period["start_time"]) & (df.index <= period["end_time"])
        ]

        # Beregn min og max risikoscore for perioden
        min_score = period_data["risk_score"].min() * 100
        max_score = period["max_risk_score"] * 100

        # Legg til vertikal linje
        fig.add_trace(
            go.Scatter(
                x=[period["start_time"], period["start_time"]],
                y=[min_score, max_score],
                mode="lines",
                line=dict(color=color, width=3),
                name="Høy risiko",
                hovertemplate=(
                    "<b>Kritisk periode</b><br>"
                    + f"Start: {period['start_time'].strftime('%d-%m-%Y %H:%M')}<br>"
                    + f"Varighet: {period['duration']:.1f} timer<br>"
                    + f"Score: {max_score:.0f}%<br>"
                    + f"Vind: {period.get('avg_wind_speed', 0):.1f} m/s<br>"
                    + f"Temp: {period.get('min_temp', 0):.1f}°C"
                ),
                hoverlabel=dict(bgcolor="white", font_size=12, bordercolor=color),
            )
        )

    # Oppdater layout
    fig.update_layout(
        title=f"Kritiske perioder (score > {critical_threshold*100:.0f}%)",
        xaxis_title="",
        yaxis_title="Risikoscore (%)",
        yaxis_range=[0, 100],
        height=300,
        margin=dict(t=30, b=20, l=50, r=20),
        showlegend=False,
        plot_bgcolor="white",
        yaxis=dict(
            gridcolor="lightgray",
            zeroline=True,
            zerolinecolor="lightgray",
            tickformat=",d",
        ),
        xaxis=dict(
            gridcolor="lightgray",
            tickformat="%d-%m-%Y\n%H:%M",
            tickangle=0,
            dtick="M1",
            ticklabelmode="period",
        ),
    )

    return fig


def display_critical_periods_analysis(df, periods_df):
    """
    Viser analyse av kritiske perioder i Streamlit
    """
    if periods_df.empty:
        st.warning("Ingen kritiske perioder funnet i valgt tidsperiode.")
        return

    # Vis først oversiktsgrafen
    overview_fig = plot_critical_periods_overview(df, periods_df)
    if overview_fig is not None:
        st.plotly_chart(overview_fig, use_container_width=True)

    # Vis ekspanderbare detaljer for hver kritisk periode
    st.subheader("Detaljer for kritiske perioder")

    # Filtrer og sorter periodene
    critical_periods = periods_df[periods_df["max_risk_score"] > 0.65].sort_values(
        "start_time"
    )

    for i, period in critical_periods.iterrows():
        with st.expander(
            f"Periode {i} - {period['start_time'].strftime('%Y-%m-%d %H:%M')}"
        ):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Varighet", f"{period['duration']:.1f} timer")
            with col2:
                st.metric("Maks risiko", f"{period['max_risk_score']*100:.0f}")


def show_ml_optimization():
    """Viser ML-optimalisering seksjonen"""
    try:
        logger = logging.getLogger(__name__)

        optimizer = SnowDriftOptimizer()

        with st.spinner("Henter værdata..."):
            df = fetch_frost_data()
            logger.debug(f"Værdata hentet: {df.shape} rader")

        if df is not None:
            # Viktig: Bruk kun session state for parametre
            if "params" not in st.session_state:
                st.session_state["params"] = DEFAULT_PARAMS.copy()
                logger.debug("Initialiserte params i session state")

            current_params = st.session_state["params"]
            logger.debug(f"Nåværende parametre: {current_params}")

            df_risk, periods_df = calculate_snow_drift_risk(df, current_params)
            target = df_risk["risk_score"]

            with st.spinner("Optimaliserer parametre..."):
                results = optimizer.optimize_parameters(df, target)
                logger.debug(f"Optimalisering fullført. Resultater: {results}")

                col1, col2 = st.columns(2)

                with col1:
                    st.write("📊 **Modellytelse**")
                    st.metric(
                        "Gjennomsnittlig R² score", f"{results['mean_cv_score']:.3f}"
                    )

                    if results.get("feature_importance"):
                        st.write("🎯 **Viktigste faktorer**")
                        for feature, importance in sorted(
                            results["feature_importance"].items(),
                            key=lambda x: x[1],
                            reverse=True,
                        )[:5]:
                            st.write(f"- {feature}: {importance:.3f}")

                with col2:
                    if results.get("suggested_parameters"):
                        st.write("💡 **ML-foreslåtte parametre**")

                        # Vis sammenligning
                        st.write("Sammenligning av parametre:")
                        for param, value in results["suggested_parameters"].items():
                            current = current_params.get(param, "Ikke satt")
                            st.write(f"- {param}:")
                            st.write(f"  Nåværende: {current}")
                            st.write(f"  Foreslått: {value:.2f}")

                        if st.button("Bruk ML-foreslåtte parametre"):
                            # Behold min_duration
                            new_params = results["suggested_parameters"].copy()
                            new_params["min_duration"] = current_params.get(
                                "min_duration", 3
                            )

                            # Oppdater session state direkte
                            st.session_state["params"] = new_params
                            logger.debug(f"Nye parametre satt: {new_params}")

                            # Vis bekreftelse
                            st.success("Parametre oppdatert!")
                            st.json(new_params)

                            # Tving omberegning
                            st.rerun()

    except Exception as e:
        logger.exception("Feil i ML-optimalisering")
        st.error(f"Feil under ML-optimalisering: {str(e)}")


def show_main_analysis():
    """Viser hovedanalysen"""
    st.title("🌨️ Snøfokk-analyse")

    try:
        # Last inn værdata med debugging
        logger.info("Starter hovedanalyse")
        with st.spinner("Henter værdata fra Frost..."):
            logger.debug("Henter værdata...")
            df = fetch_frost_data()
            logger.debug(f"Værdata hentet: {df.shape if df is not None else 'None'}")

            # Debug værdata
            if df is not None:
                logger.debug("Værdata statistikk:")
                for col in df.columns:
                    logger.debug(f"{col}: {df[col].describe()}")

        if df is not None:
            # Hent oppdaterte parametre fra session state
            params = st.session_state.get("params", DEFAULT_PARAMS.copy())
            logger.debug(f"Aktive parametre: {params}")

            # Beregn risiko med debugging
            logger.debug("Starter risikoberegning...")
            df_risk, critical_periods = calculate_snow_drift_risk(df, params)
            logger.debug(
                f"Risikoberegning fullført. Kritiske perioder funnet: {len(critical_periods)}"
            )

            # Debug kritiske perioder
            if not critical_periods.empty:
                logger.debug("Kritiske perioder statistikk:")
                logger.debug(
                    f"Total varighet: {critical_periods['duration'].sum():.1f} timer"
                )
                logger.debug(
                    f"Gjennomsnittlig risiko: {critical_periods['max_risk_score'].mean():.2f}"
                )
                logger.debug(
                    f"Maks risiko: {critical_periods['max_risk_score'].max():.2f}"
                )

            # Kjør analyse av innstillingene
            logger.debug("Starter analyse av innstillinger...")
            analysis = analyze_settings(params, critical_periods)
            logger.debug("Analyse av innstillinger fullført")

            # Vis nøkkeltall øverst
            if not critical_periods.empty:
                st.subheader("📊 Nøkkeltall")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Kritiske perioder", len(critical_periods))
                with col2:
                    st.metric(
                        "Total varighet",
                        f"{critical_periods['duration'].sum():.1f} timer",
                    )
                with col3:
                    st.metric(
                        "Gjennomsnittlig risiko",
                        f"{critical_periods['max_risk_score'].mean():.1f}",
                    )

            # Vis hovedplot
            st.plotly_chart(plot_risk_analysis(df_risk), use_container_width=True)

            # Vis detaljert analyse
            if not critical_periods.empty:
                display_critical_periods_analysis(df_risk, critical_periods)

            # Vis lagringsmuligheter med analyse
            save_settings_ui(params, critical_periods, analysis)

    except Exception as e:
        logger.error(f"Feil i hovedanalyse: {str(e)}", exc_info=True)
        st.error(f"Feil i hovedanalyse: {str(e)}")
        st.exception(e)


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
            params = show_parameter_controls()

        # Vis valgt side
        if choice == "Hovedanalyse":
            show_main_analysis()
        elif choice == "ML-optimalisering":
            show_ml_optimization()
        elif choice == "Innstillinger":
            show_settings()

    except Exception as e:
        logger.error(f"Kritisk feil i hovedapplikasjon: {str(e)}", exc_info=True)
        st.error("En kritisk feil oppstod. Sjekk loggene for detaljer.")


if __name__ == "__main__":
    main()
