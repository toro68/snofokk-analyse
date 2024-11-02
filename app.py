import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px
import logging
from typing import Tuple, Dict, Any

# Lokale imports
from ml_utils import SnowDriftOptimizer, analyze_seasonal_patterns
from db_utils import (
    init_db,
    save_settings,
    get_saved_settings,
    delete_settings
)
from snofokk import (
    fetch_frost_data,
    calculate_snow_drift_risk,
    analyze_settings,
    create_rolling_stats,
    identify_risk_periods,
    analyze_wind_directions
)
from config import (
    FROST_CLIENT_ID,
    FROST_STATION_ID,
    DEFAULT_PARAMS
)

def format_settings_summary(params, num_critical_periods):
    """
    Formatterer en lesbar oppsummering av innstillingene
    """
    return {
        'wind': {
            'strong': params['wind_strong'],
            'moderate': params['wind_moderate'],
            'gust': params['wind_gust']
        },
        'temp': {
            'cold': params['temp_cold'],
            'cool': params['temp_cool']
        },
        'snow': {
            'high': params['snow_high'],
            'moderate': params['snow_moderate'],
            'low': params['snow_low']
        },
        'weights': {
            'wind': params['wind_weight'],
            'temp': params['temp_weight'],
            'snow': params['snow_weight']
        },
        'critical_periods': num_critical_periods
    }
    
def save_settings_ui(params, critical_periods):
    """UI-komponent for å lagre vellykkede innstillinger"""
    st.divider()
    st.subheader("📊 Analyse av gjeldende innstillinger")
    
    # Analyser innstillinger (fjernet DEFAULT_PARAMS argument)
    analysis = analyze_settings(params, critical_periods)
    
    # Vis antall kritiske perioder og total varighet
    total_duration = critical_periods['duration'].sum()
    avg_risk = critical_periods['max_risk_score'].mean()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Kritiske perioder", len(critical_periods))
    with col2:
        st.metric("Total varighet", f"{total_duration} timer")
    with col3:
        st.metric("Gjennomsnittlig risiko", f"{avg_risk:.1f}")
    
    # Vis alle gjeldende innstillinger i en egen seksjon
    st.write("🔧 **Gjeldende innstillinger**")
    
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
    
    # Legg til AI-analyse
    with st.expander("🤖 AI-analyse av innstillingene"):
        # Vis parameterendringer
        if analysis['parameter_changes']:
            st.write("**📊 Vesentlige endringer fra standard:**")
            for change in analysis['parameter_changes']:
                st.write(f"- {change['description']}")
        else:
            st.info("Ingen vesentlige endringer fra standardinnstillinger")

        # Vis påvirkningsanalyse
        if analysis['impact_analysis']:
            st.write("**🎯 Viktigste påvirkningsfaktorer:**")
            for factor in analysis['impact_analysis']:
                st.write(f"- {factor['description']}")

        # Vis forslag til forbedringer
        if analysis['suggestions']:
            st.write("**💡 Forslag til justeringer:**")
            for suggestion in analysis['suggestions']:
                st.write(f"- {suggestion}")

        # Vis meteorologisk kontekst
        if analysis['meteorological_context']:
            st.write("**🌤️ Meteorologisk kontekst:**")
            for context in analysis['meteorological_context']:
                st.write(context)
    
    # Lagringsseksjon
    st.divider()
    st.write("💾 **Lagre disse innstillingene**")
    
    with st.form("save_settings_form"):
        settings_name = st.text_input(
            "Navn på innstillingene",
            placeholder="F.eks. 'Vinter 2024 - Høy sensitivitet'"
        )
        
        settings_desc = st.text_area(
            "Beskrivelse",
            placeholder="Beskriv hvorfor disse innstillingene fungerer bra...",
            help="Legg gjerne til informasjon om værforhold, sesong, etc."
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
                'name': settings_name,
                'description': settings_desc,
                'timestamp': datetime.now().isoformat(),
                'parameters': format_settings_summary(params, len(critical_periods)),
                'changes': changes
            }
            
            # Lagre til database
            success, message = save_settings(settings_data, critical_periods)
            if success:
                st.success(message)
            else:
                st.error(message)

def show_settings():
    """Viser og håndterer innstillinger"""
    st.header("⚙️ Innstillinger")
    
    # Hent lagrede innstillinger
    settings_df = get_saved_settings()
    
    if not settings_df.empty:
        st.subheader("📋 Lagrede innstillinger")
        
        for _, settings in settings_df.iterrows():
            with st.expander(f"📊 {settings['name']} ({settings['timestamp'].strftime('%Y-%m-%d %H:%M')})"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Beskrivelse:**")
                    st.write(settings['description'])
                    
                    if settings.get('critical_periods'):
                        st.metric("Antall kritiske perioder", settings['critical_periods'])
                        st.metric("Total varighet", f"{settings.get('total_duration', 0)} timer")
                        st.metric("Gjennomsnittlig risiko", f"{settings.get('avg_risk_score', 0):.1f}")
                
                with col2:
                    if settings.get('changes'):
                        st.write("**Endringer fra standard:**")
                        for change in settings['changes']:
                            st.write(f"- {change}")
                    
                    if settings.get('parameters'):
                        st.write("**Parameterinnstillinger:**")
                        st.json(settings['parameters'])
                
                # Handlingsknapper
                col3, col4 = st.columns(2)
                with col3:
                    if st.button("🔄 Last inn", key=f"load_{settings['id']}"):
                        params = load_settings_parameters(settings['id'])
                        if params:
                            st.session_state['params'] = params
                            st.success("Innstillinger lastet inn!")
                            st.rerun()
                
                with col4:
                    if st.button("🗑️ Slett", key=f"delete_{settings['id']}"):
                        success, message = delete_settings(settings['id'])
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
    else:
        st.info("Ingen lagrede innstillinger funnet")

def plot_risk_analysis(df):
    """Lager interaktiv visualisering av risikoanalysen"""
    fig = make_subplots(
        rows=5, cols=1,
        subplot_titles=(
            'Risikoscore og Nivå',
            'Vind og Vindkast',
            'Temperatur',
            'Snødybde og Endring',
            'Nedbør'
        ),
        vertical_spacing=0.08
    )
    
    # Risikoscore
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df['risk_score'],
            name='Risikoscore',
            line=dict(color='red')
        ),
        row=1, col=1
    )
    
    # Vind
    if 'sustained_wind' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['sustained_wind'],
                name='Vedvarende vind',
                line=dict(color='blue')
            ),
            row=2, col=1
        )
    
    if 'max(wind_speed_of_gust PT1H)' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['max(wind_speed_of_gust PT1H)'],
                name='Vindkast',
                line=dict(color='lightblue', dash='dash')
            ),
            row=2, col=1
        )
    
    # Temperatur
    if 'air_temperature' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['air_temperature'],
                name='Temperatur',
                line=dict(color='green')
            ),
            row=3, col=1
        )
    
    # Snødybde og endring
    if 'surface_snow_thickness' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['surface_snow_thickness'],
                name='Snødybde',
                line=dict(color='purple')
            ),
            row=4, col=1
        )
    
    if 'snow_depth_change' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['snow_depth_change'],
                name='Endring i snødybde',
                line=dict(color='magenta', dash='dot')
            ),
            row=4, col=1
        )
    
    # Nedbør - med riktig kolonnenavn for nedbørsvarighet
    if 'sum(duration_of_precipitation PT1H)' in df.columns:
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df['sum(duration_of_precipitation PT1H)'],
                name='Nedbørsvarighet',  # Oppdatert navn
                marker_color='lightblue'
            ),
            row=5, col=1
        )
    elif 'precipitation_amount' in df.columns:  # Sjekk alternativt kolonnenavn
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df['precipitation_amount'],
                name='Nedbør',
                marker_color='lightblue'
            ),
            row=5, col=1
        )
    else:
        # Legg til en tom trace for å beholde subplot-strukturen
        fig.add_trace(
            go.Bar(
                x=[df.index[0]],
                y=[0],
                name='Nedbør (ingen data)',
                marker_color='lightgray'
            ),
            row=5, col=1
        )
    
    # Oppdater layout
    fig.update_layout(
        title='Snøfokk-risikoanalyse',
        showlegend=True,
        height=1200
    )
    
    # Legg til y-akse titler
    fig.update_yaxes(title_text="Score", row=1, col=1)
    fig.update_yaxes(title_text="m/s", row=2, col=1)
    fig.update_yaxes(title_text="°C", row=3, col=1)
    fig.update_yaxes(title_text="cm", row=4, col=1)
    fig.update_yaxes(title_text="Nedbørsvarighet (min)", row=5, col=1)  # Endret enhet til minutter
    
    return fig

def plot_critical_periods(df: pd.DataFrame, periods_df: pd.DataFrame) -> Tuple[go.Figure, pd.DataFrame]:
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
        critical_periods = periods_df[periods_df['risk_level'] == 'Kritisk'].copy()

        if critical_periods.empty:
            st.warning("Ingen kritiske perioder funnet i valgt tidsperiode")
            return None, critical_periods

        # Opprett subplots
        fig = make_subplots(
            rows=5, cols=1,  # Redusert til 5 rader siden vi ikke trenger nedbør
            subplot_titles=(
                'Risikoscore',
                'Vindforhold under kritiske perioder',
                'Temperatur under kritiske perioder',
                'Snødybde og endring under kritiske perioder',
                'Oversikt over kritiske perioder'
            ),
            vertical_spacing=0.05,
            shared_xaxes=True,
            row_heights=[0.2, 0.2, 0.2, 0.2, 0.2]
        )

        # Marker kritiske perioder
        for _, period in critical_periods.iterrows():
            for row in range(1, 6):  # Oppdatert til 5 rader
                fig.add_vrect(
                    x0=period['start_time'],
                    x1=period['end_time'],
                    fillcolor="rgba(255, 0, 0, 0.1)",
                    layer="below",
                    line_width=0,
                    row=row, col=1
                )

        # Risikoscore
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['risk_score'],
                name='Risikoscore',
                line=dict(color='red', width=1)
            ),
            row=1, col=1
        )
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=1, col=1,
                     annotation=dict(text="Kritisk nivå (70)", x=0))

        # Vindforhold
        if 'sustained_wind' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['sustained_wind'],
                    name='Vedvarende vind',
                    line=dict(color='blue')
                ),
                row=2, col=1
            )
        
        if 'max(wind_speed_of_gust PT1H)' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['max(wind_speed_of_gust PT1H)'],
                    name='Vindkast',
                    line=dict(color='lightblue', dash='dash')
                ),
                row=2, col=1
            )

        # Temperatur
        if 'air_temperature' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['air_temperature'],
                    name='Temperatur',
                    line=dict(color='green')
                ),
                row=3, col=1
            )
            fig.add_hline(y=0, line_dash="dash", line_color="gray", row=3, col=1,
                         annotation=dict(text="Frysepunkt", x=0))

        # Snødybde og endring
        if 'surface_snow_thickness' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['surface_snow_thickness'],
                    name='Snødybde',
                    line=dict(color='purple')
                ),
                row=4, col=1
            )
        
        if 'snow_depth_change' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['snow_depth_change'],
                    name='Endring i snødybde',
                    line=dict(color='magenta', dash='dot')
                ),
                row=4, col=1
            )

        # Fokusert visning av kritiske perioder
        for _, period in critical_periods.iterrows():
            period_data = df[period['start_time']:period['end_time']]
            fig.add_trace(
                go.Scatter(
                    x=period_data.index,
                    y=period_data['risk_score'],
                    name=f"Kritisk periode {int(period['period_id'])}",
                    mode='lines+markers',
                    line=dict(width=3),
                    marker=dict(size=8)
                ),
                row=5, col=1
            )

        # Oppdater layout
        fig.update_layout(
            title={
                'text': 'Detaljert analyse av kritiske snøfokkperioder',
                'y':0.95,
                'x':0.5,
                'xanchor': 'center',
                'yanchor': 'top'
            },
            height=1200,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
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

def display_critical_periods_analysis(df, periods_df):
    """
    Viser analyse av kritiske perioder i Streamlit
    """
    fig, critical_periods = plot_critical_periods(df, periods_df)
    
    if fig is not None:
        # Vis nøkkelstatistikk
        st.subheader("Statistikk for kritiske perioder")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Antall kritiske perioder", len(critical_periods))
        with col2:
            avg_duration = critical_periods['duration'].mean()
            st.metric("Gjennomsnittlig varighet", f"{avg_duration:.1f} timer")
        with col3:
            max_risk = critical_periods['max_risk_score'].max()
            st.metric("Høyeste risikoscore", f"{max_risk:.1f}")

        # Vis detaljert plot
        st.plotly_chart(fig, use_container_width=True)

        # Vis detaljer for hver kritisk periode
        st.subheader("Detaljer for kritiske perioder")
        for _, period in critical_periods.iterrows():
            with st.expander(f"Periode {int(period['period_id'])} - {period['start_time'].strftime('%Y-%m-%d %H:%M')}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"Varighet: {period['duration']} timer")
                    st.write(f"Maks risikoscore: {period['max_risk_score']:.1f}")
                    st.write(f"Maks vindstyrke: {period['max_wind']:.1f} m/s")
                    st.write(f"Maks vindkast: {period['max_gust']:.1f} m/s")
                with col2:
                    st.write(f"Min temperatur: {period['min_temp']:.1f}°C")
                    st.write(f"Maks snøendring: {period['max_snow_change']:.1f} cm")
                    st.write(f"Total nedbør: {period['total_precip']:.1f} mm")

def show_ml_optimization():
    """Viser ML-optimalisering seksjonen"""
    st.subheader("🤖 Maskinlæringsbasert Parameteroptimalisering")
    
    # Legg til forklarende tekst
    st.markdown("""
    ### Om Maskinlæringsmodellen
    
    Denne siden bruker maskinlæring for å optimalisere parametrene som brukes i snøfokk-analysen. 
    Modellen er en Random Forest Regressor som er trent på historiske værdata og analyserer 
    sammenhengen mellom ulike værfaktorer.

    #### 🎯 Modellens Hovedfunn
    Analysen viser at snøfokk-risiko best kan predikeres med følgende vekting:
    - **Vindforhold** (59.0%): Den klart viktigste faktoren
    - **Temperatur** (19.0%): Nest viktigste faktor
    - **Snøforhold** (14.3%): Tredje viktigste faktor
    - **Andre faktorer** (7.7%): Inkluderer vindretningsstabilitet og snødybde

    #### 📊 Modellytelse
    - Modellen oppnår en R² score på 0.932-0.933
    - Dette betyr at modellen forklarer 93.2-93.3% av variasjonen i snøfokk-risiko
    - De optimaliserte parametrene er stabile med minimale svingninger

    #### 💡 Praktisk Betydning
    De optimaliserte parametrene gir:
    - Mer presis deteksjon av kritiske perioder
    - Sterkere vekting av vindforhold (1.65)
    - Moderat vekting av temperatur (1.20)
    - Balansert vekting av snøforhold (1.15)
    
    #### 🔄 Kontinuerlig Læring
    Modellen kan kjøres på nytt for å:
    - Tilpasse seg nye værforhold
    - Validere eksisterende parametre
    - Foreslå justeringer basert på nye data
    """)
    
    try:
        # Initialiser optimizer
        optimizer = SnowDriftOptimizer()
        
        # Last inn data
        with st.spinner('Henter værdata...'):
            df = fetch_frost_data()
        
        if df is not None:
            # Beregn risikoscore med nåværende parametre
            current_params = st.session_state.get('params', DEFAULT_PARAMS)
            df_risk, periods_df = calculate_snow_drift_risk(df, current_params)
            target = df_risk['risk_score']
            
            # Kjør optimalisering
            with st.spinner('Optimaliserer parametre...'):
                results = optimizer.optimize_parameters(df, target)
                
                # Vis resultater
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("📊 **Modellytelse**")
                    st.metric("Gjennomsnittlig R² score", f"{results['mean_cv_score']:.3f}")
                    
                    if results.get('feature_importance'):
                        st.write("🎯 **Viktigste faktorer**")
                        for feature, importance in sorted(
                            results['feature_importance'].items(), 
                            key=lambda x: x[1], 
                            reverse=True
                        )[:5]:
                            st.write(f"- {feature}: {importance:.3f}")
                
                with col2:
                    st.write("💡 **Foreslåtte parametre**")
                    if results.get('suggested_parameters'):
                        for param, value in results['suggested_parameters'].items():
                            current = current_params[param]
                            
                            # Sikker beregning av prosentvis endring
                            if current == 0:
                                if value == 0:
                                    change = 0
                                else:
                                    change = 100  # Indikerer en endring fra 0
                            else:
                                change = ((value - current) / abs(current)) * 100
                            
                            # Formater endringen
                            if change != 0:
                                change_str = f"({'↑' if change > 0 else '↓'}{abs(change):.1f}%)"
                            else:
                                change_str = "(uendret)"
                            
                            st.write(f"- {param}: {value:.2f} {change_str}")
                
                # Legg til knapp for å bruke optimaliserte parametre
                if st.button("Bruk optimaliserte parametre"):
                    st.session_state['params'] = results['suggested_parameters']
                    st.success("Parametre oppdatert! Analysen vil nå bruke de optimaliserte verdiene.")
                    st.rerun()
    
    except Exception as e:
        st.error(f"Feil under optimalisering: {str(e)}")
        st.exception(e)

def show_main_analysis():
    """Viser hovedanalysen"""
    st.title("🌨️ Snøfokk-analyse")
    
    try:
        # Last inn værdata
        with st.spinner('Henter værdata fra Frost...'):
            df = fetch_frost_data()
            
        if df is not None:
            # Hent eller initialiser parametre
            params = st.session_state.get('params', DEFAULT_PARAMS.copy())
            
            # Sikre at alle parameterverdier er float
            for key in params:
                if isinstance(params[key], (list, tuple)):
                    params[key] = float(params[key][0])
                elif not isinstance(params[key], (int, float)):
                    params[key] = float(DEFAULT_PARAMS[key])
            
            # Beregn risiko og få kritiske perioder
            df_risk, critical_periods = calculate_snow_drift_risk(df, params)
            
            # Vis parameterinnstillinger i sidebar
            st.sidebar.subheader("⚙️ Parameterinnstillinger")
            
            # Vindparametere
            st.sidebar.write("**Vindparametere**")
            params['wind_strong'] = st.sidebar.slider("Sterk vind (m/s)", 10.0, 25.0, float(params['wind_strong']), step=0.5)
            params['wind_moderate'] = st.sidebar.slider("Moderat vind (m/s)", 5.0, 15.0, float(params['wind_moderate']), step=0.5)
            params['wind_gust'] = st.sidebar.slider("Vindkast terskel (m/s)", 10.0, 30.0, float(params['wind_gust']), step=0.5)
            params['wind_dir_change'] = st.sidebar.slider("Vindretningsendring (grader)", 0.0, 180.0, float(params['wind_dir_change']), step=0.5)
            params['wind_weight'] = st.sidebar.slider("Vindvekt", 0.0, 2.0, float(params['wind_weight']), step=0.1)
            
            # Temperaturparametere
            st.sidebar.write("**Temperaturparametere**")
            params['temp_cold'] = st.sidebar.slider("Kald temperatur (°C)", -20.0, -5.0, float(params['temp_cold']), step=0.5)
            params['temp_cool'] = st.sidebar.slider("Kjølig temperatur (°C)", -5.0, 2.0, float(params['temp_cool']), step=0.5)
            params['temp_weight'] = st.sidebar.slider("Temperaturvekt", 0.0, 2.0, float(params['temp_weight']), step=0.1)
            
            # Snøparametere
            st.sidebar.write("**Snøparametere**")
            params['snow_high'] = st.sidebar.slider("Høy snøendring (cm)", 5.0, 20.0, float(params['snow_high']), step=0.5)
            params['snow_moderate'] = st.sidebar.slider("Moderat snøendring (cm)", 2.0, 10.0, float(params['snow_moderate']), step=0.5)
            params['snow_low'] = st.sidebar.slider("Lav snøendring (cm)", 0.0, 5.0, float(params['snow_low']), step=0.5)
            params['snow_weight'] = st.sidebar.slider("Snøvekt", 0.0, 2.0, float(params['snow_weight']), step=0.1)
            
            # Oppdater session state
            st.session_state['params'] = params
            
            # Vis nøkkeltall øverst
            if not critical_periods.empty:
                st.subheader("📊 Nøkkeltall")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Kritiske perioder", len(critical_periods))
                with col2:
                    st.metric("Total varighet", f"{critical_periods['duration'].sum():.1f} timer")
                with col3:
                    st.metric("Gjennomsnittlig risiko", f"{critical_periods['max_risk_score'].mean():.1f}")
                
                # Legg til litt mellomrom
                st.write("")
            
            # Vis hovedplot i full bredde
            st.plotly_chart(plot_risk_analysis(df_risk), use_container_width=True)
            
            # Vis detaljert analyse av kritiske perioder
            if not critical_periods.empty:
                display_critical_periods_analysis(df_risk, critical_periods)
            
            # Vis lagringsmuligheter
            save_settings_ui(params, critical_periods)
            
        else:
            st.error("Kunne ikke laste værdata. Sjekk tilkobling og prøv igjen.")
            
    except Exception as e:
        st.error(f"Feil i hovedanalyse: {str(e)}")
        st.exception(e)

# Oppdater main() funksjonen
def main():
    st.set_page_config(page_title="Snøfokk-analyse", layout="wide")
    
    # Initialiser database
    init_db()
    
    # Legg til menyvalg
    menu = ["Hovedanalyse", "ML-optimalisering", "Innstillinger"]
    choice = st.sidebar.selectbox("Velg analyse", menu)
    
    if choice == "Hovedanalyse":
        show_main_analysis()  # Kall show_main_analysis funksjonen
    elif choice == "ML-optimalisering":
        show_ml_optimization()
    elif choice == "Innstillinger":
        show_settings()

if __name__ == "__main__":
    main()  