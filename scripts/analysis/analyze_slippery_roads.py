import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import logging
import json
from datetime import datetime
import os

# Sett opp logging
logging.basicConfig(level=logging.INFO,
                   format='%(message)s')
logger = logging.getLogger(__name__)

# Logg tidspunkt ved start
logger.info(f"\n=== ANALYSE STARTET {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

def load_config():
    """Last inn konfigurasjon fra JSON-fil."""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(script_dir)
        config_path = os.path.join(base_dir, 'config', 'alert_config.json')
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Kunne ikke laste konfigurasjonsfil: {str(e)}")
        raise

def load_data(start_date=None, end_date=None):
    """Last inn historiske data med valgfri datofiltrering."""
    logger.info("Laster inn historiske data...")
    
    # Last inn data
    df = pd.read_csv('data/raw/historical_data.csv')
    
    # Konverter timestamp til datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Filtrer på dato hvis spesifisert
    if start_date:
        df = df[df['timestamp'] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df['timestamp'] <= pd.to_datetime(end_date)]
    
    # Fyll NaN-verdier med 0 for nedbør og snødybde
    df['precipitation_amount'] = df['precipitation_amount'].fillna(0)
    df['surface_snow_thickness'] = df['surface_snow_thickness'].fillna(0)
    
    # Beregn endring i snødybde (positiv verdi betyr nysnø)
    df['snow_change'] = df['surface_snow_thickness'].diff()
    df['snow_change'] = df['snow_change'].fillna(0)
    
    # Beregn total nedbør siste 3 timer (rullende sum)
    df['precip_3h'] = df['precipitation_amount'].rolling(
        window=3, min_periods=1).sum()
    
    logger.info(f"Lastet inn {len(df)} observasjoner fra {df['timestamp'].min()} til {df['timestamp'].max()}")
    return df


def is_slippery_conditions(row, config):
    """
    Vurderer om forholdene tilsier glatte veier basert på konfigurasjon.
    """
    params = config['slippery_roads']
    
    melting_temp = params['temp_min'] <= row['air_temperature'] <= params['temp_max']
    high_humidity = row['relative_humidity'] >= params['humidity_min']
    significant_precip = row['precip_3h'] >= params['precip_3h_min']
    enough_snow = row['surface_snow_thickness'] >= params['snow_depth_min']
    snow_melting = row['snow_change'] < params['snow_change_max']
    no_fresh_snow = row['precipitation_amount'] < params['fresh_snow_max']
    
    return (enough_snow and 
            melting_temp and 
            high_humidity and
            significant_precip and
            snow_melting and
            no_fresh_snow)


def find_slippery_periods(df, config):
    """Finn sammenhengende perioder med risiko for glatte veier."""
    logger.info("\nAnalyserer perioder med risiko for glatte veier...")
    
    params = config['slippery_roads']
    cooldown_hours = params['cooldown_hours']
    
    df = df.sort_values('timestamp')
    df['slippery_risk'] = df.apply(lambda row: is_slippery_conditions(row, config), axis=1)
    
    # Beregn tid siden forrige observasjon
    df['hours_since_last'] = (
        df['timestamp'] - df['timestamp'].shift()
    ).dt.total_seconds() / 3600
    
    # Finn perioder med risiko
    risk_periods = []
    last_alert = None
    
    for idx, row in df[df['slippery_risk']].iterrows():
        current_time = row['timestamp']
        
        if last_alert is None or (current_time - last_alert).total_seconds() / 3600 >= cooldown_hours:
            last_alert = current_time
            # Finn data for de neste 3 timene
            end_time = current_time + pd.Timedelta(hours=3)
            period_data = df[
                (df['timestamp'] >= current_time) & 
                (df['timestamp'] <= end_time)
            ]
            
            risk_periods.append({
                'start': current_time,
                'end': end_time,
                'data': period_data
            })
    
    # Konverter perioder til DataFrame format
    periods = []
    for period in risk_periods:
        period_data = period['data']
        if len(period_data) > 0:
            duration = (period['end'] - period['start']).total_seconds() / 3600
            
            if (duration >= params['min_duration'] and 
                duration <= params['max_duration']):
                periods.append({
                    'start': period['start'],
                    'end': period['end'],
                    'duration_hours': duration,
                    'max_snow': period_data['surface_snow_thickness'].max(),
                    'min_temp': period_data['air_temperature'].min(),
                    'max_temp': period_data['air_temperature'].max(),
                    'avg_humidity': period_data['relative_humidity'].mean(),
                    'snow_change': period_data['snow_change'].sum(),
                    'total_precip': period_data['precipitation_amount'].sum(),
                    'max_3h_precip': period_data['precip_3h'].max()
                })
    
    periods_df = pd.DataFrame(periods)
    logger.info(f"Fant {len(periods_df)} separate perioder med risiko for glatte veier")
    logger.info(f"(Med {cooldown_hours} timers nedkjølingstid mellom varsler)")
    return periods_df


def analyze_slippery_conditions(df, config):
    """Analyser forhold som kan føre til glatte veier."""
    logger.info("\nStarter detaljert analyse...")
    
    # Opprett output-mappe hvis den ikke eksisterer
    output_dir = Path('data/analyzed')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Finn perioder med glatte veier
    periods_df = find_slippery_periods(df, config)
    
    # Lagre perioder til CSV
    output_file = output_dir / 'slippery_periods.csv'
    periods_df.to_csv(output_file, index=False)
    logger.info(f"Lagret periodeliste til {output_file}")
    
    # Legg til en kolonne for glatte forhold
    df['slippery_risk'] = df.apply(lambda row: is_slippery_conditions(row, config), axis=1)
    
    # 1. Månedlig distribusjon av risiko for glatte veier
    plt.figure(figsize=(12, 6))
    monthly_counts = (df[df['slippery_risk']]
                     .groupby(df['timestamp'].dt.month)
                     .size())
    monthly_counts.plot(kind='bar')
    plt.title('Månedlig fordeling av risiko for glatte veier')
    plt.xlabel('Måned')
    plt.ylabel('Antall tilfeller')
    output_file = output_dir / 'slippery_monthly.png'
    plt.savefig(output_file)
    plt.close()
    logger.info(f"Lagret månedsfordeling til {output_file}")
    
    # 2. Forhold mellom temperatur og luftfuktighet
    plt.figure(figsize=(10, 6))
    sns.scatterplot(
        data=df,
        x='air_temperature',
        y='relative_humidity',
        hue='slippery_risk',
        alpha=0.5
    )
    plt.title('Forhold mellom temperatur og luftfuktighet')
    output_file = output_dir / 'temp_humidity_relationship.png'
    plt.savefig(output_file)
    plt.close()
    logger.info(f"Lagret temperatur/fuktighet-analyse til {output_file}")
    
    # Lagre oppsummerende statistikk
    output_file = output_dir / 'slippery_roads_summary.txt'
    with open(output_file, 'w') as f:
        f.write('Analyse av risiko for glatte veier\n')
        f.write('================================\n\n')
        
        f.write(f'Analyseperiode: {df["timestamp"].min()} til {df["timestamp"].max()}\n\n')
        
        params = config['slippery_roads']
        f.write('Kriterier for glatte veier:\n')
        f.write(f'- Minst {params["snow_depth_min"]} cm snø på bakken\n')
        f.write(f'- Temperatur mellom {params["temp_min"]}°C og {params["temp_max"]}°C\n')
        f.write(f'- Høy luftfuktighet (>{params["humidity_min"]}%)\n')
        f.write(f'- Minst {params["precip_3h_min"]}mm nedbør siste 3 timer\n')
        f.write(f'- Betydelig minkende snødybde (<{params["snow_change_max"]} cm/t)\n')
        f.write(f'- Ikke betydelig nysnø (<{params["fresh_snow_max"]} mm/t)\n\n')
        
        f.write(f'Total antall observasjoner: {len(df)}\n')
        f.write(
            f'Antall tilfeller med risiko for glatte veier: '
            f'{df["slippery_risk"].sum()}\n'
        )
        f.write(
            f'Antall separate perioder med risiko: {len(periods_df)}\n'
        )
        f.write(
            f'Gjennomsnittlig varighet av perioder: '
            f'{periods_df["duration_hours"].mean():.1f} timer\n\n'
        )
        
        # Beregn statistikk for ikke-NaN verdier
        temp_stats = df[df['slippery_risk']]['air_temperature'].dropna()
        humid_stats = df[df['slippery_risk']]['relative_humidity'].dropna()
        snow_stats = df[df['slippery_risk']]['surface_snow_thickness'].dropna()
        
        f.write('Statistikk for perioder med risiko:\n')
        f.write(
            f'- Temperatur: {temp_stats.mean():.1f}°C '
            f'(min: {temp_stats.min():.1f}°C, '
            f'max: {temp_stats.max():.1f}°C)\n'
        )
        f.write(
            f'- Luftfuktighet: {humid_stats.mean():.1f}% '
            f'(min: {humid_stats.min():.1f}%, '
            f'max: {humid_stats.max():.1f}%)\n'
        )
        f.write(
            f'- Snødybde: {snow_stats.mean():.1f} cm '
            f'(min: {snow_stats.min():.1f} cm, '
            f'max: {snow_stats.max():.1f} cm)\n\n'
        )
        
        # Skriv ut de 5 lengste periodene
        f.write('\nDe 5 lengste periodene med risiko:\n')
        f.write('--------------------------------\n')
        top_periods = periods_df.nlargest(5, 'duration_hours')
        for _, period in top_periods.iterrows():
            f.write(
                f'Fra: {period["start"].strftime("%Y-%m-%d %H:%M")}\n'
                f'Til: {period["end"].strftime("%Y-%m-%d %H:%M")}\n'
                f'Varighet: {period["duration_hours"]:.1f} timer\n'
                f'Maks snødybde: {period["max_snow"]:.1f} cm\n'
                f'Temperatur: {period["min_temp"]:.1f}°C til '
                f'{period["max_temp"]:.1f}°C\n'
                f'Endring i snødybde: {period["snow_change"]:.1f} cm\n'
                f'Total nedbør: {period["total_precip"]:.1f} mm\n'
                f'Maks 3-timers nedbør: {period["max_3h_precip"]:.1f} mm\n\n'
            )
    
    logger.info(f"Lagret oppsummerende statistikk til {output_file}")


def main():
    """Hovedfunksjon for analyse av historiske data."""
    try:
        # Last konfigurasjon
        config = load_config()
        
        # Last inn data for vinteren 2023/2024
        df = load_data(
            start_date="2023-11-01",
            end_date="2024-05-01"
        )
        
        # Analyser data
        analyze_slippery_conditions(df, config)
        
        logger.info("\nAnalyse fullført. Se resultater i data/analyzed/")
        
    except Exception as e:
        logger.error(f"Feil under analyse: {str(e)}")


if __name__ == "__main__":
    main() 