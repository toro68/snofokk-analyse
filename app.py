import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px

from db_utils import (
    init_db, 
    save_settings, 
    get_saved_settings, 
    get_period_stats, 
    delete_settings,
    load_settings_parameters,
    analyze_settings,
    preprocess_critical_periods
)

# API konfigurasjon
CLIENT_ID = st.secrets["FROST_CLIENT_ID"]
STATION_ID = "SN46220"

# Standardparametre 
DEFAULT_PARAMS = {
    # Vindparametere
    'wind_strong': 8.0,
    'wind_moderate': 6.5,
    'wind_gust': 15.0,
    'wind_dir_change': 30.0,
    
    # Temperaturparametere
    'temp_cold': -2.0,
    'temp_cool': 0.0,
    
    # Snøparametere
    'snow_high': 1.5,
    'snow_moderate': 0.8,
    'snow_low': 0.3,
    
    # Vekting
    'wind_weight': 1.0,
    'temp_weight': 1.0,
    'snow_weight': 1.0,
    
    # Andre parametere
    'min_duration': 2
}

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
        analysis = analyze_settings(params, critical_periods, DEFAULT_PARAMS)
        
        if analysis:
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

def view_saved_settings():
    """Viser lagrede innstillinger"""
    try:
        # Hent alle lagrede innstillinger
        settings_df = get_saved_settings()
        
        if settings_df.empty:
            st.info("Ingen lagrede innstillinger ennå")
            return
            
        st.subheader("📋 Lagrede innstillinger")
        
        # Debug info
        st.write(f"Fant {len(settings_df)} innstillinger")
        
        # Vis hver innstilling
        for _, settings in settings_df.iterrows():
            container = st.container()
            container.markdown(f"### {settings['name']} ({settings['timestamp'][:10]})")
            
            col1, col2 = container.columns([3, 1])
            
            with col1:
                st.write("**Beskrivelse:**")
                st.write(settings['description'] if settings['description'] else "Ingen beskrivelse")
                
                st.write("**Endringer fra standard:**")
                if settings['changes']:
                    st.code("\n".join(settings['changes']))
                else:
                    st.write("Ingen endringer fra standard")
            
            with col2:
                st.metric("Kritiske perioder", settings['critical_periods'])
                st.metric("Total varighet", f"{settings['total_duration']}t")
                st.metric("Snittrisiko", f"{settings['avg_risk_score']:.1f}")
            
            # Hent periodestatistikk
            period_stats = get_period_stats(settings['id'])
            if not period_stats.empty:
                st.write("**Periodestatistikk:**")
                st.dataframe(
                    period_stats[[
                        'start_time', 'end_time', 'duration',
                        'max_risk_score', 'max_wind', 'min_temp'
                    ]].style.format({
                        'max_risk_score': '{:.1f}',
                        'max_wind': '{:.1f}',
                        'min_temp': '{:.1f}'
                    })
                )
            
            # Handlinger
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("🗑️ Slett", key=f"delete_{settings['id']}"):
                    success, message = delete_settings(settings['id'])
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
            
            with col2:
                if st.button("📥 Last inn", key=f"load_{settings['id']}"):
                    params = load_settings_parameters(settings['id'])
                    if params:
                        st.session_state.loaded_params = params
                        st.success("Innstillinger lastet inn! Oppdaterer...")
                        st.rerun()
            
            st.divider()
            
    except Exception as e:
        st.error(f"Feil ved visning av innstillinger: {str(e)}")
        import traceback
        st.error(traceback.format_exc())

@st.cache_data(ttl=3600)  # Cache data for 1 time
def fetch_frost_data(start_date='2023-11-01', end_date='2024-04-30'):
    """
    Henter utvidet værdatasett fra Frost API
    
    Nye elementer inkluderer:
    - Bakketemperatur for bedre snøforholdsanalyse
    - Luftfuktighet for snøkonsistens
    - Utvidet temperatur- og vinddata
    - Nedbørsvarighet for intensitetsberegning
    """
    try:
        endpoint = 'https://frost.met.no/observations/v0.jsonld'
        elements = [
            # Eksisterende elementer
            "surface_snow_thickness",
            "wind_speed",
            "max(wind_speed_of_gust PT1H)",
            "wind_from_direction",
            "air_temperature",
            "sum(precipitation_amount PT1H)",
            
            # Nye elementer
            "surface_temperature",          # Bakketemperatur
            "min(air_temperature PT1H)",    # Minimum lufttemperatur
            "max(air_temperature PT1H)",    # Maksimum lufttemperatur
            "relative_humidity",            # Luftfuktighet
            "dew_point_temperature",        # Duggpunkt
            "sum(duration_of_precipitation PT1H)",  # Nedbørsvarighet
            "max(wind_speed PT1H)"         # Maksimal vindhastighet
        ]
        
        parameters = {
            'sources': STATION_ID,
            'elements': ','.join(elements),
            'referencetime': f'{start_date}/{end_date}',
            'timeresolutions': 'PT1H'
        }
        
        r = requests.get(endpoint, parameters, auth=(CLIENT_ID, ''))
        
        if r.status_code != 200:
            st.error(f"Feil ved henting av data: {r.text}")
            return None
            
        data = r.json()
        
        observations = []
        for item in data['data']:
            timestamp = item['referenceTime']
            obs_data = {'timestamp': timestamp}
            for obs in item['observations']:
                obs_data[obs['elementId']] = float(obs['value']) if obs['value'] is not None else None
            observations.append(obs_data)
        
        df = pd.DataFrame(observations)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        # Legg til beregnede kolonner
        df['temp_gradient'] = df['air_temperature'] - df['surface_temperature']
        df['precip_intensity'] = df['sum(precipitation_amount PT1H)'] / df['sum(duration_of_precipitation PT1H)'].replace(0, np.nan)
        
        return df
        
    except Exception as e:
        st.error(f"Feil i fetch_frost_data: {str(e)}")
        return None

# Fil: app.py
# Kategori: Analysis Functions

def calculate_snow_drift_risk(df, params):
    """
    Forbedret snøfokk-risikoberegning med utvidede værparametere
    """
    df = df.copy()
    
    # Grunnleggende beregninger (eksisterende)
    df['snow_depth_change'] = df['surface_snow_thickness'].diff()
    df['sustained_wind'] = df['wind_speed'].rolling(window=2).mean()
    df['wind_dir_change'] = df['wind_from_direction'].diff().abs()
    
    # Nye beregninger med utvidede data
    df['temp_stability'] = df['air_temperature'] - df['min(air_temperature PT1H)']
    df['surface_cooling'] = df['air_temperature'] - df['surface_temperature']
    df['humidity_factor'] = (df['relative_humidity'] > 90).astype(int)
    
    def calculate_risk_score(row):
        score = 0
        
        # Vindforhold (utvidet)
        has_wind = False
        if row['sustained_wind'] >= params['wind_strong']:
            score += 30 * params['wind_weight']
            has_wind = True
        elif row['sustained_wind'] >= params['wind_moderate']:
            score += 20 * params['wind_weight']
            has_wind = True
            
        # Temperaturforhold (forbedret)
        has_cold_temp = False
        if row['air_temperature'] <= params['temp_cold']:
            score += 20 * params['temp_weight']
            # Øk score hvis bakken er kaldere enn lufta
            if row['surface_cooling'] > 2:
                score += 5 * params['temp_weight']
            has_cold_temp = True
        elif row['air_temperature'] <= params['temp_cool']:
            score += 10 * params['temp_weight']
            has_cold_temp = True
        
        # Snøforhold (utvidet)
        snow_score = 0
        has_snow_conditions = False
        
        if abs(row['snow_depth_change']) >= params['snow_high']:
            snow_score += 40 * params['snow_weight']
            has_snow_conditions = True
        elif abs(row['snow_depth_change']) >= params['snow_moderate']:
            snow_score += 25 * params['snow_weight']
            has_snow_conditions = True
        elif abs(row['snow_depth_change']) >= params['snow_low']:
            snow_score += 15 * params['snow_weight']
            has_snow_conditions = True
            
        # Legg til snøscore hvis vi har vind
        if has_wind:
            score += snow_score
        
        # Nye forsterkende faktorer
        if score > 30:
            # Vindkast
            if row['max(wind_speed_of_gust PT1H)'] >= params['wind_gust']:
                score *= 1.2
            # Vindretningsendring
            if row['wind_dir_change'] >= params['wind_dir_change']:
                score *= 1.1
            # Høy luftfuktighet
            if row['humidity_factor'] == 1:
                score *= 1.1
            # Ustabil temperatur
            if row['temp_stability'] > 3:
                score *= 1.1
        
        # Reduser score hvis ikke alle forhold er til stede
        if not (has_wind and (has_cold_temp or has_snow_conditions)):
            score *= 0.5
        
        return min(100, score)
    
    # Beregn risikoscore og nivåer
    df['risk_score'] = df.apply(calculate_risk_score, axis=1)
    df['risk_level'] = pd.cut(df['risk_score'], 
                             bins=[-np.inf, 30, 50, 70, np.inf],
                             labels=['Lav', 'Moderat', 'Høy', 'Kritisk'])
    
    # Identifiser perioder
    periods_df = identify_risk_periods(df, min_duration=params['min_duration'])
    
    return df, periods_df

def identify_risk_periods(df, min_duration=3):
    """Identifiserer sammenhengende risikoperioder"""
    df = df.copy()
    
    # Marker start på nye perioder
    df['new_period'] = (
        ((df['risk_score'] > 30) & (df['risk_score'].shift() <= 30)) |
        ((df['risk_score'] > 30) & (df['risk_score'].shift().isna()))
    ).astype(int)
    
    # Gi hver periode et unikt nummer
    df['period_id'] = df['new_period'].cumsum()
    
    # Fjern periode_id hvor risk_score er lav
    df.loc[df['risk_score'] <= 30, 'period_id'] = np.nan
    
    # Grupper sammenhengende perioder
    periods = []
    for period_id in df['period_id'].dropna().unique():
        period_data = df[df['period_id'] == period_id].copy()
        
        if len(period_data) >= min_duration:
            period_info = {
                'start_time': period_data.index[0],
                'end_time': period_data.index[-1],
                'duration': len(period_data),
                'max_risk_score': period_data['risk_score'].max(),
                'avg_risk_score': period_data['risk_score'].mean(),
                'max_wind': period_data['sustained_wind'].max(),
                'max_gust': period_data['max(wind_speed_of_gust PT1H)'].max(),
                'min_temp': period_data['air_temperature'].min(),
                'total_precip': period_data['sum(precipitation_amount PT1H)'].sum(),
                'max_snow_change': period_data['snow_depth_change'].abs().max(),
                'risk_level': period_data['risk_level'].mode()[0],
                'period_id': period_id
            }
            
            wind_dirs = period_data['wind_from_direction'].dropna()
            if not wind_dirs.empty:
                rad = np.deg2rad(wind_dirs)
                avg_sin = np.mean(np.sin(rad))
                avg_cos = np.mean(np.cos(rad))
                avg_dir = np.rad2deg(np.arctan2(avg_sin, avg_cos)) % 360
                period_info['wind_direction'] = avg_dir
            
            periods.append(period_info)
    
    return pd.DataFrame(periods)

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
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df['sustained_wind'],
            name='Vedvarende vind',
            line=dict(color='blue')
        ),
        row=2, col=1
    )
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
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df['surface_snow_thickness'],
            name='Snødybde',
            line=dict(color='purple')
        ),
        row=4, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df['snow_depth_change'],
            name='Endring i snødybde',
            line=dict(color='magenta', dash='dot')
        ),
        row=4, col=1
    )
    
    # Nedbør
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df['sum(precipitation_amount PT1H)'],
            name='Nedbør',
            marker_color='lightblue'
        ),
        row=5, col=1
    )
    
    # Oppdater layout
    fig.update_layout(
        title='Snøfokk-risikoanalyse',
        showlegend=True,
        height=1200  # Flyttet hit fra make_subplots
    )
    
    # Legg til y-akse titler
    fig.update_yaxes(title_text="Score", row=1, col=1)
    fig.update_yaxes(title_text="m/s", row=2, col=1)
    fig.update_yaxes(title_text="°C", row=3, col=1)
    fig.update_yaxes(title_text="cm", row=4, col=1)
    fig.update_yaxes(title_text="mm", row=5, col=1)
    
    return fig

# Fil: app.py
# Kategori: Visualization Functions

def plot_critical_periods(df, periods_df):
    """
    Lager en detaljert visualisering av kritiske snøfokkperioder for Streamlit
    
    Args:
        df: DataFrame med alle værdata og risikoberegninger
        periods_df: DataFrame med identifiserte perioder
    """
    # Finn kritiske perioder
    critical_periods = periods_df[periods_df['risk_level'] == 'Kritisk'].copy()

    if critical_periods.empty:
        st.warning("Ingen kritiske perioder funnet i valgt tidsperiode")
        return None

    # Opprett subplots med fokus på kritiske perioder
    fig = make_subplots(
        rows=6, cols=1,
        subplot_titles=(
            'Risikoscore',
            'Vindforhold under kritiske perioder',
            'Temperatur under kritiske perioder',
            'Snødybde og endring under kritiske perioder',
            'Nedbør under kritiske perioder',
            'Oversikt over kritiske perioder'
        ),
        vertical_spacing=0.05,
        shared_xaxes=True,
        row_heights=[0.2, 0.2, 0.15, 0.15, 0.15, 0.15]
    )

    # Marker kritiske perioder med rød bakgrunn
    for _, period in critical_periods.iterrows():
        for row in range(1, 7):
            fig.add_vrect(
                x0=period['start_time'],
                x1=period['end_time'],
                fillcolor="rgba(255, 0, 0, 0.1)",
                layer="below",
                line_width=0,
                row=row, col=1
            )

    # Risikoscore med fremhevet kritisk nivå
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

    # Vindforhold med terskelverdi
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df['sustained_wind'],
            name='Vedvarende vind',
            line=dict(color='blue')
        ),
        row=2, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df['max(wind_speed_of_gust PT1H)'],
            name='Vindkast',
            line=dict(color='lightblue', dash='dash')
        ),
        row=2, col=1
    )
    fig.add_hline(y=8.0, line_dash="dash", line_color="gray", row=2, col=1,
                 annotation=dict(text="Sterk vind (8.0 m/s)", x=0))

    # Temperatur med frysepunkt
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
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df['surface_snow_thickness'],
            name='Snødybde',
            line=dict(color='purple')
        ),
        row=4, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df['snow_depth_change'],
            name='Endring i snødybde',
            line=dict(color='magenta', dash='dot')
        ),
        row=4, col=1
    )

    # Nedbør
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df['sum(precipitation_amount PT1H)'],
            name='Nedbør',
            marker_color='lightblue'
        ),
        row=5, col=1
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
            row=6, col=1
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
        height=1400,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    # Legg til y-akse titler med enheter
    fig.update_yaxes(title_text="Risikoscore", row=1, col=1)
    fig.update_yaxes(title_text="Vindstyrke (m/s)", row=2, col=1)
    fig.update_yaxes(title_text="Temperatur (°C)", row=3, col=1)
    fig.update_yaxes(title_text="Snødybde (cm)", row=4, col=1)
    fig.update_yaxes(title_text="Nedbør (mm)", row=5, col=1)
    fig.update_yaxes(title_text="Risikoscore", row=6, col=1)

    # Forbedret x-akse format
    fig.update_xaxes(tickformat="%d-%m-%Y\n%H:%M")

    return fig, critical_periods

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

# Hovedapplikasjon
def main():
    st.set_page_config(page_title="Snøfokk-analyse", layout="wide")
    
    # Initialiser database
    init_db()
    
    # Sjekk om vi har lagrede parametre som skal lastes
    if 'loaded_params' in st.session_state:
        params = st.session_state.loaded_params
        del st.session_state.loaded_params
    else:
        params = DEFAULT_PARAMS.copy()
        
    # Sidepanel for parametre
    with st.sidebar:
        st.title("Parametre")
        
        # Datovelgere
        start_date = st.date_input(
            "Fra dato",
            value=datetime(2023, 11, 1).date(),
            min_value=datetime(2023, 1, 1).date(),
            max_value=datetime(2024, 12, 31).date()
        )
        
        end_date = st.date_input(
            "Til dato",
            value=datetime(2024, 4, 30).date(),
            min_value=start_date,
            max_value=datetime(2024, 12, 31).date()
        )
        
        # Ekspander-boks for avanserte innstillinger
        with st.expander("Avanserte innstillinger"):
            params = DEFAULT_PARAMS.copy()
            
            st.subheader("Vindparametere")
            params['wind_strong'] = st.slider(
                "Sterk vind (m/s)", 
                5.0, 15.0, 
                DEFAULT_PARAMS['wind_strong'], 
                0.5
            )
            st.markdown("""
            <small>🌬️ Vindstyrke som regnes som sterk nok til å kunne forårsake betydelig snøtransport.
            Verdier over dette gir høy risikoscore.</small>
            """, unsafe_allow_html=True)

            params['wind_moderate'] = st.slider(
                "Moderat vind (m/s)", 
                4.0, 10.0, 
                DEFAULT_PARAMS['wind_moderate'], 
                0.5
            )
            st.markdown("""
            <small>🍃 Vindstyrke som kan føre til noe snøtransport. 
            Verdier over dette gir moderat risikoscore.</small>
            """, unsafe_allow_html=True)

            params['wind_gust'] = st.slider(
                "Vindkast terskel (m/s)", 
                10.0, 25.0, 
                DEFAULT_PARAMS['wind_gust'], 
                0.5
            )
            st.markdown("""
            <small>💨 Grense for vindkast som kan forårsake plutselig økt snøtransport.
            Verdier over dette øker risikoscoren med 20%.</small>
            """, unsafe_allow_html=True)

            params['wind_dir_change'] = st.slider(
                "Vindretningsendring (°)", 
                10.0, 60.0, 
                DEFAULT_PARAMS['wind_dir_change'], 
                5.0
            )
            st.markdown("""
            <small>🔄 Betydelig endring i vindretning som kan påvirke snøtransporten.
            Verdier over dette øker risikoscoren med 10%.</small>
            """, unsafe_allow_html=True)
            
            st.subheader("Temperaturparametere")
            params['temp_cold'] = st.slider(
                "Kald temperatur (°C)", 
                -5.0, 0.0, 
                DEFAULT_PARAMS['temp_cold'], 
                0.5
            )
            st.markdown("""
            <small>❄️ Temperaturer under dette regnes som kalde forhold.
            Gir høy vekting i risikoberegningen.</small>
            """, unsafe_allow_html=True)

            params['temp_cool'] = st.slider(
                "Kjølig temperatur (°C)", 
                -3.0, 2.0, 
                DEFAULT_PARAMS['temp_cool'], 
                0.5
            )
            st.markdown("""
            <small>🌡️ Temperaturer under dette regnes som kjølige forhold.
            Gir moderat vekting i risikoberegningen.</small>
            """, unsafe_allow_html=True)
            
            st.subheader("Snøparametere")
            params['snow_high'] = st.slider(
                "Høy snøendring (cm)", 
                0.5, 3.0, 
                DEFAULT_PARAMS['snow_high'], 
                0.1
            )
            st.markdown("""
            <small>🏔️ Betydelig endring i snødybde som indikerer kraftig snøtransport.
            Verdier over dette gir høy risikoscore når kombinert med vind.</small>
            """, unsafe_allow_html=True)

            params['snow_moderate'] = st.slider(
                "Moderat snøendring (cm)", 
                0.3, 2.0, 
                DEFAULT_PARAMS['snow_moderate'], 
                0.1
            )
            st.markdown("""
            <small>🌨️ Moderat endring i snødybde som kan indikere snøtransport.
            Verdier over dette gir moderat risikoscore når kombinert med vind.</small>
            """, unsafe_allow_html=True)

            params['snow_low'] = st.slider(
                "Lav snøendring (cm)", 
                0.1, 1.0, 
                DEFAULT_PARAMS['snow_low'], 
                0.1
            )
            st.markdown("""
            <small>❄️ Minimal endring i snødybde som kan indikere lett snøtransport.
            Verdier over dette gir lav risikoscore når kombinert med vind.</small>
            """, unsafe_allow_html=True)
            
            st.subheader("Vekting")
            params['wind_weight'] = st.slider(
                "Vindvekt", 
                0.5, 2.0, 
                DEFAULT_PARAMS['wind_weight'], 
                0.1
            )
            st.markdown("""
            <small>🎚️ Justerer hvor stor innvirkning vindforhold har på total risikoscore.
            Høyere verdi gir mer vekt til vindparameterne.</small>
            """, unsafe_allow_html=True)

            params['temp_weight'] = st.slider(
                "Temperaturvekt", 
                0.5, 2.0, 
                DEFAULT_PARAMS['temp_weight'], 
                0.1
            )
            st.markdown("""
            <small>🎚️ Justerer hvor stor innvirkning temperaturforhold har på total risikoscore.
            Høyere verdi gir mer vekt til temperaturparameterne.</small>
            """, unsafe_allow_html=True)

            params['snow_weight'] = st.slider(
                "Snøvekt", 
                0.5, 2.0, 
                DEFAULT_PARAMS['snow_weight'], 
                0.1
            )
            st.markdown("""
            <small>🎚️ Justerer hvor stor innvirkning snøforhold har på total risikoscore.
            Høyere verdi gir mer vekt til snøparameterne.</small>
            """, unsafe_allow_html=True)
            
            st.subheader("Andre parametere")
            params['min_duration'] = st.slider(
                "Minimum varighet (timer)", 
                1, 6, 
                DEFAULT_PARAMS['min_duration'], 
                1
            )
            st.markdown("""
            <small>🖖 Minimum antall sammenhengende timer med forhøyet risiko før det regnes som en risikoperiode.
            Høyere verdi filtrerer bort kortvarige hendelser.</small>
            """, unsafe_allow_html=True)

            # Info-boks med generell forklaring
            st.info("""
            💡 **Hvordan parameterne påvirker risikoberegningen:**
            
            - Risikoscore beregnes på en skala fra 0-100
            - Vind er grunnleggende for snøfokk og må være tilstede
            - Temperatur og snøforhold forsterker risikoen
            - Vektingen lar deg justere betydningen av hver faktor
            
            Juster parameterne basert på lokale forhold og erfaringer.
            """)
    
    # Hovedinnhold
    st.title("Snøfokk-risikoanalyse")
    
    try:
        # Last inn data
        with st.spinner('Henter data fra Frost...'):
            df = fetch_frost_data(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            
        if df is not None:
            # Kjør analyse
            with st.spinner('Analyserer data...'):
                df, critical_periods = calculate_snow_drift_risk(df, params)
                
                # Preprocess kritiske perioder
                if critical_periods is not None and not critical_periods.empty:
                    critical_periods = preprocess_critical_periods(critical_periods)
                else:
                    critical_periods = pd.DataFrame()  # Tom DataFrame hvis ingen perioder funnet
                
                # Fortsett med analyse
                analysis_results = analyze_settings(params, critical_periods, DEFAULT_PARAMS)
                
                # Vis resultater
                if not critical_periods.empty:
                    st.subheader("Identifiserte risikoperioder")
                    
                    # Vis standardstatistikk og tabell som før
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Antall perioder", len(critical_periods))
                    with col2:
                        st.metric("Gjennomsnittlig varighet", 
                                 f"{critical_periods['duration'].mean():.1f} timer")
                    with col3:
                        st.metric("Høyeste risikoscore", 
                                 f"{critical_periods['max_risk_score'].max():.1f}")
                    
                    # Vis perioder i tabell
                    st.dataframe(
                        critical_periods[[
                            'start_time', 'end_time', 'duration', 
                            'risk_level', 'max_risk_score', 'max_wind',
                            'min_temp', 'max_snow_change'
                        ]].style.format({
                            'max_risk_score': '{:.1f}',
                            'max_wind': '{:.1f}',
                            'min_temp': '{:.1f}',
                            'max_snow_change': '{:.1f}'
                        })
                    )
                    
                    # Legg til valgmulighet for visualisering
                    viz_type = st.radio(
                        "Velg visualiseringstype",
                        ["Fokus på kritiske perioder", "Standard visualisering"],
                        index=0,
                        horizontal=True
                    )
                    
                    if viz_type == "Fokus på kritiske perioder":
                        # Vis kritiske perioder
                        display_critical_periods_analysis(df, critical_periods)
                        
                        # Hvis vi har kritiske perioder, vis lagringsmulighet
                        critical_periods_high = critical_periods[critical_periods['risk_level'] == 'Kritisk']
                        if not critical_periods_high.empty:
                            save_settings_ui(params, critical_periods_high)
                    else:
                        # Vis standard plot
                        st.plotly_chart(plot_risk_analysis(df), use_container_width=True)
                    
                    # Legg til en seksjon for å vise lagrede innstillinger
                    with st.expander("🔍 Se lagrede innstillinger"):
                        view_saved_settings()
                else:
                    st.info("Ingen risikoperioder identifisert i valgt tidsperiode.")
        else:
            st.error("Kunne ikke hente data fra Frost API. Sjekk feilmeldinger ovenfor.")
            
    except Exception as e:
        st.error(f"Feil i hovedfunksjonen: {str(e)}")
        import traceback
        st.error(traceback.format_exc())

if __name__ == "__main__":
    main()
