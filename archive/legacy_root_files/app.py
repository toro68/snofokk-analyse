import logging
import os
from datetime import datetime
from functools import lru_cache
from logging.handlers import RotatingFileHandler
from time import perf_counter

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import psutil

# Streamlit og plotting
import streamlit as st

# Lokale imports
from db_utils import (
    delete_settings,
    load_settings_parameters,
    save_settings,
)
from plotly.subplots import make_subplots

from config import DEFAULT_PARAMS, PARAM_RANGES
from snofokk import (
    analyze_settings,
    calculate_snow_drift_risk,
    fetch_frost_data,
)

# Opprett logs-mappe hvis den ikke eksisterer
os.makedirs('logs', exist_ok=True)

# Konfigurer logging med både fil og konsoll output
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Filhåndterer med mer detaljert format
file_handler = RotatingFileHandler(
    'logs/app.log',
    maxBytes=1024*1024,  # 1MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
file_handler.setLevel(logging.DEBUG)  # Sett fillogging til DEBUG
logger.addHandler(file_handler)

# Konsollhåndterer med mer informasjon
console_handler = logging.StreamHandler()
console_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
)
console_handler.setLevel(logging.DEBUG)  # Sett konsolllogging til DEBUG
logger.addHandler(console_handler)

# Sett logging nivå for andre biblioteker
logging.getLogger('urllib3').setLevel(logging.DEBUG)
logging.getLogger('streamlit').setLevel(logging.DEBUG)

@lru_cache(maxsize=32)
def get_cached_params():
    """Henter cached parametre"""
    return DEFAULT_PARAMS.copy()

def monitor_performance(func):
    """Dekoratør for å overvåke ytelse"""
    def wrapper(*args, **kwargs):
        start_time = perf_counter()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024

        result = func(*args, **kwargs)

        end_time = perf_counter()
        end_memory = psutil.Process().memory_info().rss / 1024 / 1024

        # Logg ytelsesdata
        perf_data = {
            'function': func.__name__,
            'execution_time': end_time - start_time,
            'memory_usage': end_memory - start_memory,
            'timestamp': datetime.now(),
            'success': result is not None
        }

        logger.info(
            f"{func.__name__}: "
            f"Tid={perf_data['execution_time']:.2f}s, "
            f"Minne=+{perf_data['memory_usage']:.1f}MB"
        )

        return result
    return wrapper

def get_param_help(param: str) -> str:
    """Returnerer hjelpetekst for hver parameter"""
    help_texts = {
        'wind_strong': "Vindstyrke som regnes som sterk vind (m/s)",
        'wind_moderate': "Vindstyrke som regnes som moderat vind (m/s)",
        'wind_gust': "Vindkast-terskel (m/s)",
        'wind_dir_change': "Betydelig endring i vindretning (grader)",
        'wind_weight': "Vekting av vindfaktoren i risikoberegningen",
        'temp_cold': "Temperatur som regnes som kald (°C)",
        'temp_cool': "Temperatur som regnes som kjølig (°C)",
        'temp_weight': "Vekting av temperaturfaktoren i risikoberegningen",
        'snow_high': "Stor endring i snødybde (m)",
        'snow_moderate': "Moderat endring i snødybde (m)",
        'snow_low': "Liten endring i snødybde (m)",
        'snow_weight': "Vekting av snøfaktoren i risikoberegningen",
        'min_duration': "Minimum varighet for en kritisk periode (timer)"
    }
    return help_texts.get(param, "Ingen hjelpetekst tilgjengelig")

def main():
    """Hovedfunksjon for Streamlit-applikasjonen"""
    st.set_page_config(
        page_title="Snøfokk Analyse",
        page_icon="❄️",
        layout="wide"
    )

    st.title("Snøfokk Analyse 🌨️")
    st.write("Analyserer værdata for å identifisere perioder med risiko for snøfokk.")

    # Velg vinterperiode
    years = list(range(2018, 2025))
    selected_year = st.selectbox("Velg vinterperiode", years, index=len(years)-2)

    # Sett faste datoer for vinterperioden
    start_date = datetime(selected_year, 11, 1).date()
    end_date = datetime(selected_year + 1, 4, 30).date()

    # Debug info for datoer
    logger.debug(f"Valgt år: {selected_year}")
    logger.debug(f"Startdato: {start_date} ({type(start_date)})")
    logger.debug(f"Sluttdato: {end_date} ({type(end_date)})")

    st.info(f"Viser data for vinterperioden {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}")

    # Initialiser parametre
    new_params = DEFAULT_PARAMS.copy()

    try:
        # Hent data
        st.write("Starter datahenting...")
        df = fetch_frost_data(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )

        if df is not None and not df.empty:
            logger.info(f"Data hentet: {len(df)} rader fra {df.index[0]} til {df.index[-1]}")

            # Filtrer data basert på valgt tidsperiode
            mask = (df.index.date >= start_date) & (df.index.date <= end_date)
            df = df[mask]

            if len(df) == 0:
                st.warning("Ingen data funnet for valgt tidsperiode")
                return

            # Håndter snødybdedata
            df['surface_snow_thickness'] = df['surface_snow_thickness'].replace(-1, np.nan)
            df['surface_snow_thickness'] = df['surface_snow_thickness'].fillna(method='ffill')

            # Logg snødybdestatistikk
            valid_snow = df['surface_snow_thickness'].dropna()
            logger.info("Snødybdestatistikk:")
            logger.info(f"Total antall målinger: {len(df)}")
            logger.info(f"Gyldige snødybdemålinger: {len(valid_snow)}")
            logger.info(f"Gjennomsnittlig snødybde: {valid_snow.mean():.1f} cm")

            # Beregn risiko med gjeldende parametre
            risk_df, periods_df = calculate_snow_drift_risk(df, new_params)

            # Vis data
            st.subheader("Snødybde og Temperatur")
            fig1 = make_subplots(specs=[[{"secondary_y": True}]])

            # Snødybde
            fig1.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['surface_snow_thickness'],
                    name="Snødybde (cm)",
                    line=dict(color='blue')
                ),
                secondary_y=False
            )

            # Temperatur
            fig1.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['air_temperature'],
                    name="Temperatur (°C)",
                    line=dict(color='red')
                ),
                secondary_y=True
            )

            fig1.update_layout(
                title="Snødybde og Temperatur over tid",
                xaxis_title="Dato",
                yaxis_title="Snødybde (cm)",
                yaxis2_title="Temperatur (°C)",
                height=400
            )
            st.plotly_chart(fig1, use_container_width=True)

            st.subheader("Vind og Risiko")
            fig2 = make_subplots(specs=[[{"secondary_y": True}]])

            # Vindstyrke
            fig2.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['wind_speed'],
                    name="Vindstyrke (m/s)",
                    line=dict(color='green')
                ),
                secondary_y=False
            )

            # Risikoscore
            fig2.add_trace(
                go.Scatter(
                    x=risk_df.index,
                    y=risk_df['risk_score'],
                    name="Risikoscore",
                    line=dict(color='orange')
                ),
                secondary_y=True
            )

            fig2.update_layout(
                title="Vindstyrke og Risikoscore over tid",
                xaxis_title="Dato",
                yaxis_title="Vindstyrke (m/s)",
                yaxis2_title="Risikoscore",
                showlegend=True,
                height=400
            )
            st.plotly_chart(fig2, use_container_width=True)

        else:
            st.error("Kunne ikke hente data fra Frost API.")
            return

    except Exception as e:
        logger.exception("Feil ved datahenting")
        st.error(f"En feil oppstod: {str(e)}")
        return

    # Sidepanel for parameterinnstillinger
    with st.sidebar:
        st.header("Parameterinnstillinger")

        # Last inn lagrede innstillinger
        saved_settings = load_settings_parameters('default')
        current_params = DEFAULT_PARAMS.copy()
        if saved_settings:
            current_params.update(saved_settings)

        # Initialiser new_params
        new_params = {}

        # Vindparametre
        st.subheader("Vindparametre")
        wind_params = ['wind_strong', 'wind_moderate', 'wind_gust', 'wind_dir_change', 'wind_weight']
        for param in wind_params:
            param_range = PARAM_RANGES.get(param, (0.0, 1.0))
            step = 0.1
            new_params[param] = st.slider(
                param.replace('_', ' ').title(),
                min_value=float(param_range[0]),
                max_value=float(param_range[1]),
                value=float(current_params[param]),
                step=step,
                help=get_param_help(param)
            )

        # Temperaturparametre
        st.subheader("Temperaturparametre")
        temp_params = ['temp_cold', 'temp_cool', 'temp_weight']
        for param in temp_params:
            param_range = PARAM_RANGES.get(param, (0.0, 1.0))
            step = 0.1
            new_params[param] = st.slider(
                param.replace('_', ' ').title(),
                min_value=float(param_range[0]),
                max_value=float(param_range[1]),
                value=float(current_params[param]),
                step=step,
                help=get_param_help(param)
            )

        # Snøparametre
        st.subheader("Snøparametre")
        snow_params = ['snow_high', 'snow_moderate', 'snow_low', 'snow_weight']
        for param in snow_params:
            param_range = PARAM_RANGES.get(param, (0.0, 1.0))
            step = 0.1
            new_params[param] = st.slider(
                param.replace('_', ' ').title(),
                min_value=float(param_range[0]),
                max_value=float(param_range[1]),
                value=float(current_params[param]),
                step=step,
                help=get_param_help(param)
            )

        # Andre parametre
        st.subheader("Andre parametre")
        other_params = ['min_duration']
        for param in other_params:
            param_range = PARAM_RANGES.get(param, (0.0, 1.0))
            step = 1.0 if param == 'min_duration' else 0.1
            new_params[param] = st.slider(
                param.replace('_', ' ').title(),
                min_value=float(param_range[0]),
                max_value=float(param_range[1]),
                value=float(current_params[param]),
                step=step,
                help=get_param_help(param)
            )

        # Knapper for å lagre/tilbakestille innstillinger
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Lagre Innstillinger"):
                save_settings(new_params, 'default')
                st.success("Innstillinger lagret!")

        with col2:
            if st.button("Tilbakestill"):
                delete_settings('default')
                new_params = DEFAULT_PARAMS.copy()
                st.success("Innstillinger tilbakestilt!")

    # Parameteroptimalisering (flyttet ut av sidebar)
    st.markdown("---")
    st.header("Parameteroptimalisering")

    st.write("""
    Denne seksjonen hjelper deg med å finne optimale parametere basert på historiske data.
    Velg hvilke kriterier som er viktigst for din analyse:
    """)

    # Vektlegging av optimaliseringskriterier
    col1, col2, col3 = st.columns(3)
    with col1:
        weights = {}
        weights['antall_perioder'] = st.slider(
            "Vekt: Antall kritiske perioder",
            min_value=0.0,
            max_value=1.0,
            value=0.3,
            step=0.1,
            help="Høyere verdi gir flere kritiske perioder"
        )
    with col2:
        weights['varighet'] = st.slider(
            "Vekt: Gjennomsnittlig varighet",
            min_value=0.0,
            max_value=1.0,
            value=0.3,
            step=0.1,
            help="Høyere verdi favoriserer lengre perioder"
        )
    with col3:
        weights['risiko_score'] = st.slider(
            "Vekt: Maksimal risikoscore",
            min_value=0.0,
            max_value=1.0,
            value=0.4,
            step=0.1,
            help="Høyere verdi gir høyere risikoscore"
        )

    # Normaliser vektene
    total_weight = sum(weights.values())
    if total_weight > 0:
        weights = {k: v/total_weight for k, v in weights.items()}

    if st.button("Optimaliser Parametere"):
        with st.spinner("Optimaliserer parametere..."):
            try:
                # Hent data hvis ikke allerede hentet
                st.write("Starter datahenting...")
                logger.debug(f"Forsøker å hente data for perioden {start_date} til {end_date}")
                logger.debug(f"API-parametre: start_date={start_date.strftime('%Y-%m-%d')}, end_date={end_date.strftime('%Y-%m-%d')}")

                df = fetch_frost_data(
                    start_date=start_date.strftime('%Y-%m-%d'),
                    end_date=end_date.strftime('%Y-%m-%d')
                )

                if df is not None:
                    logger.debug(f"Data mottatt: {len(df)} rader")
                    logger.debug(f"Tidsperiode: {df.index[0]} til {df.index[-1]}")
                    logger.debug(f"Kolonner: {df.columns.tolist()}")

                    # Filtrer data basert på valgt tidsperiode
                    logger.debug("Filtrerer data basert på valgt tidsperiode")
                    mask = (df.index.date >= start_date) & (df.index.date <= end_date)
                    df = df[mask]
                    logger.debug(f"Filtrerte data: {len(df)} rader")

                    if len(df) == 0:
                        logger.warning("Ingen data funnet etter filtrering")
                        st.warning("Ingen data funnet for valgt tidsperiode")
                        return

                    logger.debug("Korrigerer negative snødybdeverdier")
                    df['surface_snow_thickness'] = df['surface_snow_thickness'].replace(-1, 0)

                    logger.info(f"Data hentet: {len(df)} rader fra {df.index[0]} til {df.index[-1]}")
                    logger.debug(f"Kolonner i datasettet: {list(df.columns)}")

                    # Beregn risiko
                    risk_df, periods_df = calculate_snow_drift_risk(df, new_params)
                    logger.debug(f"Antall kritiske perioder funnet: {len(periods_df)}")

                    # Sjekk for manglende data
                    missing_snow = df['surface_snow_thickness'].isna().sum()
                    if missing_snow > 0:
                        logger.warning(f"Fant {missing_snow} manglende snødybdeverdier")

                    # Analyser innstillingene hvis knappen er trykket
                    if st.button("Analyser Innstillinger"):
                        analysis = analyze_settings(new_params, periods_df)
                        st.write("Analyse av innstillinger:")
                        for key, value in analysis.items():
                            st.write(f"{key}: {value}")

                    # Vis data
                    st.subheader("Snødybde og Temperatur")
                    fig1 = make_subplots(specs=[[{"secondary_y": True}]])

                    # Snødybde
                    fig1.add_trace(
                        go.Scatter(
                            x=df.index,
                            y=df['surface_snow_thickness'],
                            name="Snødybde (cm)",
                            line=dict(color='blue')
                        ),
                        secondary_y=False
                    )

                    # Temperatur
                    fig1.add_trace(
                        go.Scatter(
                            x=df.index,
                            y=df['air_temperature'],
                            name="Temperatur (°C)",
                            line=dict(color='red')
                        ),
                        secondary_y=True
                    )

                    fig1.update_layout(
                        title="Snødybde og Temperatur over tid",
                        xaxis_title="Dato",
                        yaxis_title="Snødybde (cm)",
                        yaxis2_title="Temperatur (°C)",
                        height=400
                    )
                    st.plotly_chart(fig1, use_container_width=True)

                    st.subheader("Vind og Risiko")
                    fig2 = make_subplots(specs=[[{"secondary_y": True}]])

                    # Vindstyrke
                    fig2.add_trace(
                        go.Scatter(
                            x=df.index,
                            y=df['wind_speed'],
                            name="Vindstyrke (m/s)",
                            line=dict(color='green')
                        ),
                        secondary_y=False
                    )

                    # Risikoscore
                    fig2.add_trace(
                        go.Scatter(
                            x=risk_df.index,
                            y=risk_df['risk_score'],
                            name="Risikoscore",
                            line=dict(color='orange')
                        ),
                        secondary_y=True
                    )

                    # Legg til fargede områder for kritiske perioder
                    if not periods_df.empty:
                        for _, period in periods_df.iterrows():
                            color = 'rgba(255,0,0,0.2)' if period['risk_level'] == 'Høy' else 'rgba(255,165,0,0.1)'
                            fig2.add_vrect(
                                x0=period['start_time'],
                                x1=period['end_time'],
                                fillcolor=color,
                                layer="below",
                                line_width=0,
                                annotation_text=f"Risiko: {period['risk_level']}" if period['risk_level'] == 'Høy' else None,
                                annotation_position="top left"
                            )

                    fig2.update_layout(
                        title="Vindstyrke og Risikoscore over tid",
                        xaxis_title="Dato",
                        yaxis_title="Vindstyrke (m/s)",
                        yaxis2_title="Risikoscore",
                        showlegend=True,
                        height=400
                    )
                    st.plotly_chart(fig2, use_container_width=True)

                    # Vis statistikk for periodene
                    if not periods_df.empty:
                        st.markdown("### Statistikk for kritiske perioder")

                        # Grunnleggende statistikk
                        høy_risiko = len(periods_df[periods_df['risk_level'] == 'Høy'])
                        moderat_risiko = len(periods_df[periods_df['risk_level'] == 'Moderat'])

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Høy risiko perioder", høy_risiko)
                        with col2:
                            st.metric("Moderat risiko perioder", moderat_risiko)
                        with col3:
                            st.metric("Total varighet (timer)", periods_df['duration'].sum())

                        # Detaljert statistikk
                        st.markdown("#### Detaljert Statistikk")
                        stats_df = pd.DataFrame({
                            'Metrikk': [
                                'Gjennomsnittlig varighet (timer)',
                                'Lengste periode (timer)',
                                'Høyeste risikoscore',
                                'Gjennomsnittlig risikoscore',
                                'Høyeste vindstyrke (m/s)',
                                'Laveste temperatur (°C)',
                                'Perioder per måned',
                                'Dekningsgrad (%)'
                            ],
                            'Verdi': [
                                f"{periods_df['duration'].mean():.1f}",
                                f"{periods_df['duration'].max():.0f}",
                                f"{periods_df['max_risk_score'].max():.2f}",
                                f"{periods_df['avg_risk_score'].mean():.2f}",
                                f"{periods_df['max_wind'].max():.1f}",
                                f"{periods_df['min_temp'].min():.1f}",
                                f"{len(periods_df) / (len(df) / (24 * 30)):.1f}",
                                f"{len(risk_df[risk_df['risk_score'] > 0]) / len(risk_df) * 100:.1f}"
                            ]
                        })
                        st.dataframe(stats_df, hide_index=True)

                        # Månedlig fordeling
                        st.markdown("#### Månedlig Fordeling")
                        periods_df['month'] = pd.to_datetime(periods_df['start_time']).dt.strftime('%B')
                        monthly_dist = periods_df.groupby('month').size().reset_index()
                        monthly_dist.columns = ['Måned', 'Antall perioder']
                        st.dataframe(monthly_dist, hide_index=True)

                        # Risikoscore distribusjon
                        st.markdown("#### Risikoscore Distribusjon")
                        fig_dist = go.Figure()
                        fig_dist.add_trace(go.Histogram(
                            x=periods_df['max_risk_score'],
                            nbinsx=20,
                            name='Maksimal risikoscore'
                        ))
                        fig_dist.update_layout(
                            title="Fordeling av maksimal risikoscore",
                            xaxis_title="Risikoscore",
                            yaxis_title="Antall perioder",
                            height=300
                        )
                        st.plotly_chart(fig_dist, use_container_width=True)

                    # Vis kritiske perioder
                    st.subheader("Kritiske Perioder")
                    if not periods_df.empty:
                        periods_df['start_time'] = pd.to_datetime(periods_df['start_time'])
                        periods_df['end_time'] = pd.to_datetime(periods_df['end_time'])

                        # Grupper periodene etter risiko-nivå
                        st.markdown("#### Høy Risiko Perioder")
                        høy_risiko_df = periods_df[periods_df['risk_level'] == 'Høy'].sort_values('start_time', ascending=False)
                        if not høy_risiko_df.empty:
                            st.dataframe(
                                høy_risiko_df[[
                                    'start_time', 'end_time', 'duration',
                                    'max_risk_score', 'avg_risk_score',
                                    'max_wind', 'min_temp'
                                ]]
                            )
                        else:
                            st.info("Ingen perioder med høy risiko funnet.")

                        st.markdown("#### Moderat Risiko Perioder")
                        moderat_risiko_df = periods_df[periods_df['risk_level'] == 'Moderat'].sort_values('start_time', ascending=False)
                        if not moderat_risiko_df.empty:
                            st.dataframe(
                                moderat_risiko_df[[
                                    'start_time', 'end_time', 'duration',
                                    'max_risk_score', 'avg_risk_score',
                                    'max_wind', 'min_temp'
                                ]]
                            )
                        else:
                            st.info("Ingen perioder med moderat risiko funnet.")
                    else:
                        st.info("Ingen kritiske perioder funnet i dette tidsrommet.")

                else:
                    st.error("Kunne ikke hente data fra Frost API.")

            except Exception as e:
                logger.exception("Feil ved henting av data")
                st.error(f"En feil oppstod: {str(e)}")

if __name__ == "__main__":
    main()
