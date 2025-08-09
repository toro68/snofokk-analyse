#!/usr/bin/env python3
"""Script for å analysere historiske værdata for vintermåneder."""

# Standard biblioteker
import os
import sys
import json
import logging
import argparse
from datetime import datetime, timedelta
from functools import lru_cache

# Legg til prosjektets rotmappe i Python-stien
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Tredjeparts biblioteker
import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Konfigurer logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/historical_analysis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Direkteimport av FROST API-nøkkel for å unngå streamlit-avhengighet
import os
from dotenv import load_dotenv

load_dotenv()
FROST_CLIENT_ID = os.getenv('FROST_CLIENT_ID')
if not FROST_CLIENT_ID:
    logger.error("FROST_CLIENT_ID ikke funnet i miljøvariabler")
    sys.exit(1)


def get_winter_periods(start_year, end_year):
    """
    Genererer liste over vinterperioder (1. november - 1. mai) for gitte år.
    
    Args:
        start_year (int): Startår
        end_year (int): Sluttår
        
    Returns:
        list: Liste med tupler av (start_date, end_date) for hver vinterperiode
    """
    periods = []
    for year in range(start_year, end_year + 1):
        # Vinterperiode starter 1. november året før og slutter 1. mai inneværende år
        winter_start = f"{year-1}-11-01"
        winter_end = f"{year}-05-01"
        periods.append((winter_start, winter_end))
    return periods


def split_period(start_date, end_date, chunk_days=30):
    """
    Deler opp en tidsperiode i mindre biter.
    
    Args:
        start_date (str): Startdato 'YYYY-MM-DD'
        end_date (str): Sluttdato 'YYYY-MM-DD'
        chunk_days (int): Antall dager per chunk
        
    Returns:
        list: Liste med tupler av (start_date, end_date) for hver chunk
    """
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    chunks = []
    
    current = start
    while current < end:
        chunk_end = min(current + timedelta(days=chunk_days), end)
        chunks.append((
            current.strftime('%Y-%m-%d'),
            chunk_end.strftime('%Y-%m-%d')
        ))
        current = chunk_end
    
    return chunks


def ensure_directories():
    """Oppretter nødvendige mapper hvis de ikke eksisterer."""
    for path in ['data/raw', 'data/processed', 'data/analyzed', 'logs']:
        os.makedirs(path, exist_ok=True)
    logger.info("Opprettet nødvendige mapper")


def get_frost_session():
    """
    Oppretter en requests-sesjon med retry-mekanisme.
    
    Returns:
        requests.Session: Konfgurert sesjon med retry-mekanisme
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.auth = (FROST_CLIENT_ID, '')
    session.headers.update({'Accept': 'application/json'})
    return session


@lru_cache(maxsize=100)
def get_cached_data_filename(start_date, end_date):
    """
    Genererer et filnavn for caching av værdata.
    
    Args:
        start_date (str): Startdato 'YYYY-MM-DD'
        end_date (str): Sluttdato 'YYYY-MM-DD'
        
    Returns:
        str: Filnavn for caching
    """
    return f"data/processed/frost_data_{start_date}_to_{end_date}.csv"


def fetch_frost_data(start_date, end_date, use_cache=True):
    """
    Henter værdata fra Frost API for en gitt tidsperiode.
    
    Args:
        start_date (str): Startdato på format 'YYYY-MM-DD'
        end_date (str): Sluttdato på format 'YYYY-MM-DD'
        use_cache (bool): Om caching skal brukes
        
    Returns:
        pandas.DataFrame: DataFrame med værdata
    """
    # Elementer som skal hentes fra Frost API
    elements = [
        'air_temperature',
        'surface_snow_thickness',
        'wind_speed',
        'wind_from_direction',
        'relative_humidity',
        'max(wind_speed_of_gust PT1H)',
        'max(wind_speed PT1H)',
        'min(air_temperature PT1H)',
        'max(air_temperature PT1H)',
        'sum(duration_of_precipitation PT1H)',
        'sum(precipitation_amount PT1H)',
        'dew_point_temperature'
    ]
    
    cache_file = get_cached_data_filename(start_date, end_date)
    
    # Sjekk om dataen finnes i cache
    if use_cache and os.path.exists(cache_file):
        try:
            logger.info(f"Bruker cachet data for {start_date} til {end_date}")
            return pd.read_csv(cache_file, parse_dates=['timestamp'], index_col='timestamp')
        except Exception as e:
            logger.warning(
                f"Kunne ikke lese fra cache ({cache_file}): {str(e)}. Henter på nytt."
            )
    
    try:
        logger.info(f"Henter data fra {start_date} til {end_date}")
        
        session = get_frost_session()
        endpoint = 'https://frost.met.no/observations/v0.jsonld'
        parameters = {
            'sources': 'SN46220',
            'referencetime': f'{start_date}/{end_date}',
            'elements': ','.join(elements),
            'timeresolutions': 'PT1H'
        }
        
        r = session.get(endpoint, params=parameters)
        
        if r.status_code == 200:
            data = r.json()
            
            if not data.get('data'):
                logger.error("Ingen data mottatt fra API")
                return None
                
            # Konverter til DataFrame med forbedret formatering
            records = []
            for item in data['data']:
                record = {
                    'timestamp': datetime.fromisoformat(
                        item['referenceTime'].rstrip('Z')
                    )
                }
                
                # Samle alle verdier fra observasjoner
                for obs in item['observations']:
                    key = obs['elementId']
                    
                    # Forenkle kolonnenavn
                    if key.startswith('max('):
                        key = 'max_' + key.split('(')[1].split(' ')[0]
                    elif key.startswith('min('):
                        key = 'min_' + key.split('(')[1].split(' ')[0]
                    elif key.startswith('sum('):
                        key = key.split('(')[1].split(' ')[0]
                    
                    # Erstatt kompliserte navn med enklere
                    key = key.replace('wind_speed_of_gust', 'wind_gust')
                    # Erstatt langere navn med kortere
                    key = key.replace(
                        'duration_of_precipitation', 'precip_duration'
                    )
                    key = key.replace(
                        'precipitation_amount', 'precip_amount'
                    )
                    
                    record[key] = obs['value']
                
                records.append(record)
            
            if not records:
                logger.warning("Ingen data kunne konverteres")
                return None
                
            # Opprett DataFrame
            df = pd.DataFrame(records)
            df.set_index('timestamp', inplace=True)
            
            # Valider og reparer data
            for col in df.columns:
                # Konverter -1 verdier til NaN for snødybde
                if col == 'surface_snow_thickness':
                    df[col] = df[col].replace(-1, np.nan)
            
            # Lagre til cache hvis cache er aktivert
            if use_cache:
                try:
                    df.to_csv(cache_file)
                    logger.info(f"Data cachet til {cache_file}")
                except Exception as e:
                    logger.warning(f"Kunne ikke cache data: {str(e)}")
            
            return df
            
        else:
            logger.error(
                f"API-feil {r.status_code}: {r.text}"
            )
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Nettverksfeil ved henting av data: {str(e)}")
        return None
    except ValueError as e:
        logger.error(f"Verdifeil ved prosessering av data: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Uventet feil ved henting av data: {str(e)}")
        return None


def analyze_data(df):
    """
    Foretar grunnleggende analyse av værdata.
    
    Args:
        df (pandas.DataFrame): DataFrame med værdata
        
    Returns:
        dict: Analyseresultater
    """
    if df is None or df.empty:
        logger.warning("Ingen data å analysere")
        return {}
    
    # Grunnleggende statistikk
    results = {
        'periode_start': df.index.min().strftime('%Y-%m-%d'),
        'periode_slutt': df.index.max().strftime('%Y-%m-%d'),
        'antall_dager': (df.index.max() - df.index.min()).days,
        'antall_målinger': len(df),
        'temperatur': {
            'min': float(df['air_temperature'].min()),
            'max': float(df['air_temperature'].max()),
            'gjennomsnitt': float(df['air_temperature'].mean())
        },
        'vind': {
            'max_vindkast': float(df.get('max_wind_gust', df.get('wind_gust', pd.Series())).max()),
            'gjennomsnitt': float(df['wind_speed'].mean())
        }
    }
    
    # Legg til snøstatistikk hvis tilgjengelig
    if 'surface_snow_thickness' in df.columns:
        snow_data = df['surface_snow_thickness'].dropna()
        if not snow_data.empty:
            results['snø'] = {
                'max_dybde': float(snow_data.max()),
                'gjennomsnitt': float(snow_data.mean()),
                'dager_med_snø': int((snow_data > 0).sum())
            }
    
    return results


def convert_numpy_types(obj):
    """
    Konverterer NumPy-datatyper til standard Python-datatyper for JSON-serialisering.
    
    Args:
        obj: Objektet som skal konverteres
        
    Returns:
        Konvertert objekt som kan serialiseres til JSON
    """
    if isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return convert_numpy_types(obj.tolist())
    elif isinstance(obj, pd.Series):
        return convert_numpy_types(obj.tolist())
    elif isinstance(obj, pd.DataFrame):
        return convert_numpy_types(obj.to_dict('records'))
    else:
        return obj


def parse_arguments():
    """
    Håndterer kommandolinjeargumenter.
    
    Returns:
        argparse.Namespace: Parsede argumenter
    """
    parser = argparse.ArgumentParser(
        description="Analyserer historiske værdata for vintermåneder"
    )
    parser.add_argument(
        '--start-year',
        type=int,
        default=2018,
        help="Startår for analyse (standard: 2018)"
    )
    parser.add_argument(
        '--end-year',
        type=int,
        default=datetime.now().year,
        help="Sluttår for analyse (standard: inneværende år)"
    )
    parser.add_argument(
        '--no-cache',
        action='store_true',
        help="Ikke bruk caching av API-data"
    )
    parser.add_argument(
        '--output',
        default='data/analyzed/historical_analysis.json',
        help="Sti til JSON-resultatfil"
    )
    
    return parser.parse_args()


def main():
    """Hovedfunksjon for historisk analyse."""
    try:
        args = parse_arguments()
        ensure_directories()
        
        logger.info(
            f"Starter analyse av vinterperioder fra {args.start_year} til {args.end_year}"
        )
        
        # Få liste over vinterperioder
        winter_periods = get_winter_periods(args.start_year, args.end_year)
        
        all_data = []
        analysis_results = []
        
        # Hent data for hver vinterperiode i mindre biter
        for winter_start, winter_end in winter_periods:
            logger.info(f"Prosesserer vinterperiode {winter_start} til {winter_end}")
            
            # Del opp perioden i 30-dagers biter
            chunks = split_period(winter_start, winter_end, chunk_days=30)
            period_data = []
            
            for chunk_start, chunk_end in chunks:
                df = fetch_frost_data(
                    chunk_start, 
                    chunk_end, 
                    use_cache=not args.no_cache
                )
                
                if df is not None:
                    period_data.append(df)
                    logger.info(
                        f"Hentet data for periode {chunk_start} til {chunk_end}"
                    )
                else:
                    logger.warning(
                        f"Kunne ikke hente data for {chunk_start} til {chunk_end}"
                    )
            
            if period_data:
                # Kombiner data for perioden
                period_df = pd.concat(period_data)
                winter_label = f"Vinter {winter_start[:4]}-{winter_end[:4]}"
                
                # Analyser vinterperioden
                period_results = analyze_data(period_df)
                period_results['periode_navn'] = winter_label
                analysis_results.append(period_results)
                
                all_data.append(period_df)
                logger.info(f"Fullført analyse av {winter_label}")
            else:
                logger.error(f"Ingen data for perioden {winter_start} til {winter_end}")
        
        if all_data:
            # Kombiner alle dataframes
            final_df = pd.concat(all_data)
            
            # Lagre rådata
            raw_data_path = 'data/raw/historical_data.csv'
            final_df.to_csv(raw_data_path)
            logger.info(f"Rådata lagret til {raw_data_path}")
            
            # Lagre analyseresultater
            with open(args.output, 'w', encoding='utf-8') as f:
                # Konverter NumPy-datatyper før serialisering
                converted_results = convert_numpy_types(analysis_results)
                json.dump(converted_results, f, indent=2, ensure_ascii=False)
            logger.info(f"Analyseresultater lagret til {args.output}")
            
        else:
            logger.error("Ingen data ble hentet")
            
    except Exception as e:
        logger.error(f"En feil oppstod: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main() 