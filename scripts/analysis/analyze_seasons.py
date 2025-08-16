import logging
from pathlib import Path

import pandas as pd

# Sett opp logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_winter_seasons():
    """Analyserer snøfokkperioder per vintersesong."""
    try:
        # Les snøfokkperiodene
        df = pd.read_csv('data/analyzed/snowdrift_periods.csv')
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Legg til vintersesong (f.eks. 2018-2019)
        df['winter_season'] = df['timestamp'].apply(
            lambda x: f'{x.year}-{x.year+1}' if x.month > 7
            else f'{x.year-1}-{x.year}'
        )

        # Grupper etter vintersesong og beregn statistikk
        winter_stats = df.groupby('winter_season').agg({
            'timestamp': 'count',
            'wind_speed': ['mean', 'max'],
            'air_temperature': ['mean', 'min'],
            'surface_snow_thickness': ['mean', 'max'],
            'risk_score': 'mean'
        }).round(1)

        # Skriv ut statistikk for hver vintersesong
        print('\nStatistikk per vintersesong:')
        print('=' * 80)

        for season, stats in winter_stats.iterrows():
            print(f'\nVinter {season}:')
            print(f'Antall timer med snøfokk: {stats[("timestamp", "count")]}')
            print(f'Gjennomsnittlig vindstyrke: {stats[("wind_speed", "mean")]} m/s '
                  f'(maks: {stats[("wind_speed", "max")]} m/s)')
            print(f'Gjennomsnittstemperatur: {stats[("air_temperature", "mean")]}°C '
                  f'(min: {stats[("air_temperature", "min")]}°C)')
            print(f'Gjennomsnittlig snødybde: '
                  f'{stats[("surface_snow_thickness", "mean")]} cm')
            print(f'Gjennomsnittlig risikoscore: {stats[("risk_score", "mean")]}')

        # Lagre statistikken til fil
        output_dir = Path('data/analyzed')
        output_dir.mkdir(parents=True, exist_ok=True)

        with open(output_dir / 'seasonal_summary.txt', 'w') as f:
            f.write('Statistikk per vintersesong\n')
            f.write('=' * 80 + '\n\n')

            for season, stats in winter_stats.iterrows():
                f.write(f'Vinter {season}:\n')
                f.write(f'Antall timer med snøfokk: '
                       f'{stats[("timestamp", "count")]}\n')
                f.write(f'Gjennomsnittlig vindstyrke: '
                       f'{stats[("wind_speed", "mean")]} m/s '
                       f'(maks: {stats[("wind_speed", "max")]} m/s)\n')
                f.write(f'Gjennomsnittstemperatur: '
                       f'{stats[("air_temperature", "mean")]}°C '
                       f'(min: {stats[("air_temperature", "min")]}°C)\n')
                f.write(f'Gjennomsnittlig snødybde: '
                       f'{stats[("surface_snow_thickness", "mean")]} cm\n')
                f.write(f'Gjennomsnittlig risikoscore: '
                       f'{stats[("risk_score", "mean")]}\n\n')

    except Exception as e:
        logger.error(f'En feil oppstod under analysen: {str(e)}')

if __name__ == '__main__':
    analyze_winter_seasons()
