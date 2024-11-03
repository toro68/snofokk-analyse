# 1. Imports først
import plotly.io as pio
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Set renderer for Colab environment
pio.renderers.default = 'colab'

# Andre imports
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import ipywidgets as widgets
from IPython.display import display, HTML

# Initialisering for plotly
from plotly.offline import init_notebook_mode
init_notebook_mode(connected=True)

# 3. Globale variabler og konstanter
client_id = "43fefca2-a26b-415b-954d-ba9af37e3e1f"
station_id = "SN46220"

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

# 4. Cache-variabler
_cached_data = None
_cached_timespan = None

def fetch_frost_data(start_date='2023-11-01', end_date='2024-04-30', use_cache=True):
    """Henter data fra Frost API med debugging"""
    global _cached_data, _cached_timespan

    try:
        # Debug-utskrift
        print("Starting fetch_frost_data...")
        print(f"Parameters: start_date={start_date}, end_date={end_date}, use_cache={use_cache}")

        # Sjekk cache først
        if use_cache and _cached_data is not None:
            if _cached_timespan == (start_date, end_date):
                print("Returning cached data...")
                return _cached_data.copy()

        # Hvis ikke, hent nye data
        print("Fetching new data from Frost API...")
        endpoint = 'https://frost.met.no/observations/v0.jsonld'
        elements = [
            "surface_snow_thickness",
            "wind_speed",
            "max(wind_speed_of_gust PT1H)",
            "wind_from_direction",
            "air_temperature",
            "sum(precipitation_amount PT1H)"
        ]

        parameters = {
            'sources': station_id,
            'elements': ','.join(elements),
            'referencetime': f'{start_date}/{end_date}',
            'timeresolutions': 'PT1H'
        }

        print("Making API request...")

        r = requests.get(endpoint, parameters, auth=(client_id, ''))
        print(f"API response status code: {r.status_code}")

        if r.status_code != 200:
            print("Error response from API:", r.text)
            r.raise_for_status()

        data = r.json()
        print(f"Received data with {len(data.get('data', []))} observations")

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

        # Cache dataene
        _cached_data = df.copy()
        _cached_timespan = (start_date, end_date)

        return df

    except Exception as e:
        print(f"Error in fetch_frost_data: {str(e)}")
        import traceback
        print("Full traceback:", traceback.format_exc())
        return None

def clear_cache():
    """Tømmer cached data"""
    global _cached_data, _cached_timespan
    _cached_data = None
    _cached_timespan = None
    print("Cache tømt.")

def calculate_snow_drift_risk(df, params):
    """Beregner snøfokk-risiko"""
    df = df.copy()

    # Grunnleggende beregninger
    df['snow_depth_change'] = df['surface_snow_thickness'].diff()
    df['sustained_wind'] = df['wind_speed'].rolling(window=2).mean()
    df['wind_dir_change'] = df['wind_from_direction'].diff().abs()
    df['recent_precip'] = df['sum(precipitation_amount PT1H)'].rolling(window=3).sum()

    # Beregn snøtilstand
    df['temp_last_24h'] = df['air_temperature'].rolling(window=24).mean()
    df['precip_last_24h'] = df['sum(precipitation_amount PT1H)'].rolling(window=24).sum()

    # Beregn forventet snødybdeendring
    df['expected_snow_change'] = df['recent_precip']
    df['unexplained_snow_change'] = df['snow_depth_change'].abs() - df['expected_snow_change']

    def calculate_risk_score(row):
        score = 0

        # Vindforhold som basis
        has_wind = False
        if row['sustained_wind'] >= params['wind_strong']:
            score += 30 * params['wind_weight']
            has_wind = True
        elif row['sustained_wind'] >= params['wind_moderate']:
            score += 20 * params['wind_weight']
            has_wind = True

        # Temperaturvilkår
        has_cold_temp = False
        if row['air_temperature'] <= params['temp_cold']:
            score += 20 * params['temp_weight']
            has_cold_temp = True
        elif row['air_temperature'] <= params['temp_cool']:
            score += 10 * params['temp_weight']
            has_cold_temp = True

        # Snøforhold
        snow_score = 0
        has_snow_conditions = False

        if row['unexplained_snow_change'] >= params['snow_high']:
            snow_score += 40 * params['snow_weight']
            has_snow_conditions = True
        elif row['unexplained_snow_change'] >= params['snow_moderate']:
            snow_score += 25 * params['snow_weight']
            has_snow_conditions = True
        elif row['unexplained_snow_change'] >= params['snow_low']:
            snow_score += 15 * params['snow_weight']
            has_snow_conditions = True

        # Legg til snøscore hvis vi har vind
        if has_wind:
            score += snow_score

        # Forsterkende faktorer
        if score > 30:
            if row['max(wind_speed_of_gust PT1H)'] >= params['wind_gust']:
                score *= 1.2
            if row['wind_dir_change'] >= params['wind_dir_change']:
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
        height=1200,
        showlegend=True
    )

    # Legg til y-akse titler
    fig.update_yaxes(title_text="Score", row=1, col=1)
    fig.update_yaxes(title_text="m/s", row=2, col=1)
    fig.update_yaxes(title_text="°C", row=3, col=1)
    fig.update_yaxes(title_text="cm", row=4, col=1)
    fig.update_yaxes(title_text="mm", row=5, col=1)

    return fig

def create_test_widgets():
    """Oppretter interaktive kontroller for parametertest"""

    layout = widgets.Layout(width='auto', height='40px')
    style = {'description_width': '150px'}

    params = {
        # Vindparametere
        'wind_strong': widgets.FloatSlider(
            value=8.0, min=5.0, max=15.0, step=0.5,
            description='Sterk vind (m/s)',
            style=style, layout=layout
        ),
        'wind_moderate': widgets.FloatSlider(
            value=6.5, min=4.0, max=10.0, step=0.5,
            description='Moderat vind (m/s)',
            style=style, layout=layout
        ),
        'wind_gust': widgets.FloatSlider(
            value=15.0, min=10.0, max=25.0, step=0.5,
            description='Vindkast terskel (m/s)',
            style=style, layout=layout
        ),
        'wind_dir_change': widgets.FloatSlider(
            value=30.0, min=10.0, max=60.0, step=5.0,
            description='Vindretningsendring (°)',
            style=style, layout=layout
        ),

        # Temperaturparametere
        'temp_cold': widgets.FloatSlider(
            value=-2.0, min=-5.0, max=0.0, step=0.5,
            description='Kald temp (°C)',
            style=style, layout=layout
        ),
        'temp_cool': widgets.FloatSlider(
            value=0.0, min=-3.0, max=2.0, step=0.5,
            description='Kjølig temp (°C)',
            style=style, layout=layout
        ),

        # Snøparametere
        'snow_high': widgets.FloatSlider(
            value=1.5, min=0.5, max=3.0, step=0.1,
            description='Høy snøendring (cm)',
            style=style, layout=layout
        ),
        'snow_moderate': widgets.FloatSlider(
            value=0.8, min=0.3, max=2.0, step=0.1,
            description='Moderat snøendring (cm)',
            style=style, layout=layout
        ),
        'snow_low': widgets.FloatSlider(
            value=0.3, min=0.1, max=1.0, step=0.1,
            description='Lav snøendring (cm)',
            style=style, layout=layout
        ),

        # Vekting
        'wind_weight': widgets.FloatSlider(
            value=1.0, min=0.5, max=2.0, step=0.1,
            description='Vindvekt',
            style=style, layout=layout
        ),
        'temp_weight': widgets.FloatSlider(
            value=1.0, min=0.5, max=2.0, step=0.1,
            description='Temperaturvekt',
            style=style, layout=layout
        ),
        'snow_weight': widgets.FloatSlider(
            value=1.0, min=0.5, max=2.0, step=0.1,
            description='Snøvekt',
            style=style, layout=layout
        ),

        # Andre parametere
        'min_duration': widgets.IntSlider(
            value=2, min=1, max=6, step=1,
            description='Min varighet (t)',
            style=style, layout=layout
        )
    }

    # Organiser widgets i kategorier
    categories = {
        'Vindparametere': ['wind_strong', 'wind_moderate', 'wind_gust', 'wind_dir_change'],
        'Temperaturparametere': ['temp_cold', 'temp_cool'],
        'Snøparametere': ['snow_high', 'snow_moderate', 'snow_low'],
        'Vekting': ['wind_weight', 'temp_weight', 'snow_weight'],
        'Andre': ['min_duration']
    }

    accordion = widgets.Accordion(children=[])

    for category, param_names in categories.items():
        category_widgets = [params[name] for name in param_names]
        box = widgets.VBox(category_widgets)
        accordion.children += (box,)

    for i, (category, _) in enumerate(categories.items()):
        accordion.set_title(i, category)

    return params, accordion

def main(params=DEFAULT_PARAMS):
    """Hovedfunksjon for å kjøre analysen"""
    try:
        print("Starting main function...")

        # Hent data
        df = fetch_frost_data()
        if df is None:
            return None, None, None

        # Kjør risikoanalyse
        df, periods_df = calculate_snow_drift_risk(df, params)
        if periods_df.empty:
            print("No risk periods identified")
            return df, periods_df, None

        return df, periods_df, None

    except Exception as e:
        print(f"Error in main function: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None, None, None

def run_test_analysis():
    """Kjører interaktiv test av snøfokk-analyse"""
    try:
        # Create widgets
        params, accordion = create_test_widgets()

        # Create outputs
        status_output = widgets.Output(
            layout=widgets.Layout(
                width='100%',
                min_height='200px',
                border='1px solid #ccc',
                padding='10px'
            )
        )

        plot_output = widgets.Output(
            layout=widgets.Layout(
                width='100%',
                min_height='600px',
                border='1px solid #ccc',
                padding='10px'
            )
        )

        def run_analysis(b):
            """Handler for running the analysis"""
            with status_output:
                status_output.clear_output(wait=True)
                print("Kjører analyse med nye parametere...")

                try:
                    # Get current parameters
                    current_params = {}
                    for name, widget in params.items():
                        current_params[name] = widget.value

                    # Run analysis
                    df, periods_df, _ = main(current_params)

                    if df is not None and periods_df is not None:
                        print("\nAnalysen er fullført!")
                        print(f"Antall identifiserte perioder: {len(periods_df)}")

                        if not periods_df.empty:
                            print("\nRisikofordeling:")
                            print(periods_df['risk_level'].value_counts())

                            # Generate and display plots
                            with plot_output:
                                plot_output.clear_output(wait=True)
                                fig = plot_risk_analysis(df)
                                display(fig)
                    else:
                        print("Analysis failed - check error messages above")

                except Exception as e:
                    print(f"Error during analysis: {str(e)}")
                    import traceback
                    print(traceback.format_exc())

        # Create buttons
        run_button = widgets.Button(
            description='Kjør analyse',
            button_style='success',
            layout=widgets.Layout(width='200px', height='40px', margin='10px')
        )

        clear_cache_button = widgets.Button(
            description='Tøm cache',
            button_style='warning',
            layout=widgets.Layout(width='200px', height='40px', margin='10px')
        )

        # Connect button handlers
        run_button.on_click(run_analysis)
        clear_cache_button.on_click(lambda b: clear_cache())

        # Create interface
        interface = widgets.VBox([
            widgets.HTML("<h2 style='margin: 20px 0;'>Snøfokk-analyse Testpanel</h2>"),
            widgets.Box([accordion], layout=widgets.Layout(margin='20px 0')),
            widgets.HBox([run_button, clear_cache_button],
                        layout=widgets.Layout(justify_content='flex-start', margin='10px 0')),
            widgets.HTML("<h3 style='margin: 20px 0;'>Status:</h3>"),
            status_output,
            widgets.HTML("<h3 style='margin: 20px 0;'>Plots:</h3>"),
            plot_output
        ], layout=widgets.Layout(width='100%', padding='20px'))

        # Display the interface
        display(interface)

        # Initialize data cache
        print("Initializing data cache...")
        fetch_frost_data(use_cache=True)

    except Exception as e:
        print(f"Error in run_test_analysis: {str(e)}")
        import traceback
        print(traceback.format_exc())

# Kjør analysen
if __name__ == "__main__":
    try:
        print("Initializing analysis tool...")
        run_test_analysis()
    except Exception as e:
        print(f"Error initializing tool: {str(e)}")
        import traceback
        print(traceback.format_exc())
