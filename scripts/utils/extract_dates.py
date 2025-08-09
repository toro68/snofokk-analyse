import pandas as pd
import logging
from pathlib import Path

# Sett opp logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_snowdrift_dates():
    """Trekker ut datoer for snøfokkperioder og lagrer i ny CSV."""
    try:
        # Les snøfokkperiodene
        df = pd.read_csv('data/analyzed/snowdrift_periods.csv')
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Sorter etter tidspunkt
        df = df.sort_values('timestamp')
        
        # Lag en ny DataFrame med bare nødvendig informasjon
        dates_df = pd.DataFrame({
            'dato': df['timestamp'].dt.strftime('%Y-%m-%d'),
            'klokkeslett': df['timestamp'].dt.strftime('%H:%M'),
            'vindstyrke': df['wind_speed'].round(1),
            'temperatur': df['air_temperature'].round(1),
            'snødybde': df['surface_snow_thickness'].round(1),
            'risikoscore': df['risk_score'].round(2)
        })
        
        # Lagre til CSV
        output_file = 'data/analyzed/snowdrift_dates.csv'
        dates_df.to_csv(output_file, index=False)
        
        logger.info(f"Lagret {len(dates_df)} snøfokkperioder til {output_file}")
        
        # Vis de første radene
        print("\nEksempel på innhold:")
        print(dates_df.head().to_string())
        
    except Exception as e:
        logger.error(f"En feil oppstod: {str(e)}")

if __name__ == '__main__':
    extract_snowdrift_dates() 