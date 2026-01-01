"""Test av maskinlæring for snøfokk, glatte veier og slaps"""

import logging
import sys
from pathlib import Path
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# Lokale imports
from data.src.snofokk.config import FROST_CLIENT_ID, DEFAULT_PARAMS
from data.src.snofokk.ml_utils import SnowDriftOptimizer

# Forbedret logging oppsett
def setup_logging():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
    # Opprett en fil handler
    fh = logging.FileHandler('ml_test.log')
    fh.setLevel(logging.DEBUG)
    
    # Opprett en konsoll handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    # Opprett en formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    # Legg til handlers
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger

logger = setup_logging()

class WeatherDataFetcher:
    """Henter værdata direkte fra Frost API"""
    
    def __init__(self):
        self.client_id = FROST_CLIENT_ID
        
    def fetch_data(self, start_date, end_date, required_elements):
        """Henter data fra Frost API basert på spesifiserte elementer"""
        try:
            logger.debug(f"Henter data fra {start_date} til {end_date}")
            params = {
                'sources': 'SN46220',
                'elements': ','.join(required_elements),
                'referencetime': f'{start_date}/{end_date}',
            }
            
            endpoint = 'https://frost.met.no/observations/v0.jsonld'
            r = requests.get(endpoint, params=params, auth=(self.client_id, ''))
            
            logger.debug(f"API respons status: {r.status_code}")
            
            if r.status_code == 200:
                data = pd.DataFrame()
                for item in r.json()['data']:
                    row = {obs['elementId']: obs['value'] for obs in item['observations']}
                    row['referenceTime'] = item['referenceTime']
                    data = pd.concat([data, pd.DataFrame([row])], ignore_index=True)
                
                data.set_index('referenceTime', inplace=True)
                data.index = pd.to_datetime(data.index)
                
                logger.debug(f"Data hentet: {len(data)} rader, {len(data.columns)} kolonner")
                logger.debug(f"Kolonner: {data.columns.tolist()}")
                
                return data
            else:
                logger.error(f"Feil ved API-kall: {r.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Feil i fetch_data: {str(e)}", exc_info=True)
            return None

class WeatherConditionTester:
    """Tester værforhold med maskinlæring"""
    
    def __init__(self):
        self.data = None
        # Definer spesifikke features for hver tilstand
        self.features = {
            'snow_drift': [
                'air_temperature',
                'wind_speed',
                'wind_from_direction',
                'max(wind_speed_of_gust PT1H)',
                'surface_snow_thickness',
                'sum(precipitation_amount PT1H)',
                'relative_humidity'
            ],
            'icy_road': [
                'air_temperature',
                'surface_temperature',
                'dew_point_temperature',
                'relative_humidity',
                'sum(precipitation_amount PT1H)',
                'surface_snow_thickness'
            ],
            'slush': [
                'air_temperature',
                'surface_temperature',
                'surface_snow_thickness',
                'sum(precipitation_amount PT1H)',
                'relative_humidity',
                'sum(duration_of_precipitation PT1H)'
            ]
        }
    
    def fetch_test_data(self):
        """Henter testdata"""
        try:
            logger.info("Henter testdata...")
            fetcher = WeatherDataFetcher()
            start_date = "2024-01-01"
            end_date = "2024-01-31"
            
            # Samle alle unike features som trengs
            all_features = set()
            for feature_list in self.features.values():
                all_features.update(feature_list)
            
            self.data = fetcher.fetch_data(start_date, end_date, list(all_features))
            if self.data is not None:
                logger.info(f"Hentet {len(self.data)} rader med data")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Feil ved henting av data: {str(e)}", exc_info=True)
            return False

    def calculate_derived_features(self):
        """Beregner avledede features"""
        try:
            logger.debug("Starter beregning av avledede features")
            df = self.data.copy()
            
            # Snøfokk-spesifikke
            df['wind_dir_change'] = df['wind_from_direction'].diff().abs()
            df['sustained_wind'] = df['wind_speed'].rolling(window=2).mean()
            
            # Glatte veier-spesifikke
            df['temp_gradient'] = df['air_temperature'] - df['surface_temperature']
            df['dew_point_diff'] = df['air_temperature'] - df['dew_point_temperature']
            df['frost_risk'] = ((df['surface_temperature'] < 0) & 
                              (df['air_temperature'] > 0)).astype(int)
            
            # Slaps-spesifikke
            df['melting_condition'] = ((df['air_temperature'] > 0) & 
                                     (df['surface_snow_thickness'] > 0)).astype(int)
            df['precip_intensity'] = (
                df['sum(precipitation_amount PT1H)'] / 
                df['sum(duration_of_precipitation PT1H)'].clip(lower=0.1)
            )
            
            self.data = df
            logger.info("Avledede features beregnet")
            logger.debug(f"Nye kolonner: {[col for col in df.columns if col not in self.data.columns]}")
            return True
            
        except Exception as e:
            logger.error(f"Feil ved beregning av features: {str(e)}", exc_info=True)
            return False

    def test_condition(self, condition_type):
        try:
            logger.info(f"\n=== Testing {condition_type} ===")
            
            # Logg tilgjengelige features
            logger.debug(f"Tilgjengelige features i datasettet: {self.data.columns.tolist()}")
            
            # Hent features for denne tilstanden
            required_features = self.features[condition_type]
            logger.debug(f"Påkrevde features for {condition_type}: {required_features}")
            
            # Sjekk manglende features
            missing_features = [f for f in required_features if f not in self.data.columns]
            if missing_features:
                logger.error(f"Mangler følgende features for {condition_type}: {missing_features}")
                return None
                
            # Velg kun de spesifiserte features
            df_features = self.data[required_features].copy()
            logger.debug(f"Faktiske features som brukes: {df_features.columns.tolist()}")
            logger.debug(f"Antall features valgt: {len(df_features.columns)}")
            
            # Håndter manglende verdier
            df_features = df_features.ffill().bfill()
            
            # Beregn target basert på tilstand
            if condition_type == 'snow_drift':
                target = ((df_features['wind_speed'] > 5) & 
                         (df_features['surface_snow_thickness'] > 0) &
                         (df_features['air_temperature'] < 0)).astype(int)
            elif condition_type == 'icy_road':
                target = ((df_features['air_temperature'] < 0) &
                         (df_features['surface_temperature'] < 0) &
                         (df_features['relative_humidity'] > 80)).astype(int)
            else:  # slush
                target = ((df_features['air_temperature'] > 0) &
                         (df_features['surface_snow_thickness'] > 0)).astype(int)
            
            logger.debug(f"Target distribution: {target.value_counts()}")
            
            # Del opp data
            X_train, X_test, y_train, y_test = train_test_split(
                df_features, target, test_size=0.2, random_state=42
            )
            
            logger.debug(f"Training features shape: {X_train.shape}")
            logger.debug(f"Testing features shape: {X_test.shape}")
            
            # Tren og evaluer modell
            optimizer = SnowDriftOptimizer()
            optimizer.train(X_train, y_train)
            
            predictions = optimizer.predict(X_test)
            
            return {
                'condition': condition_type,
                'score': optimizer.model.score(X_test, y_test),
                'feature_importance': dict(zip(required_features, optimizer.model.feature_importances_)),
                'data_points': len(df_features),
                'classification_report': classification_report(y_test, predictions)
            }
            
        except Exception as e:
            logger.error(f"Feil ved testing av {condition_type}: {str(e)}", exc_info=True)
            return None

def run_all_tests():
    """Kjører alle tester"""
    logger.info("=== STARTER ML-TESTING ===")
    
    tester = WeatherConditionTester()
    
    if not tester.fetch_test_data():
        logger.error("Kunne ikke hente testdata")
        return
    
    if not tester.calculate_derived_features():
        logger.error("Kunne ikke beregne avledede features")
        return
    
    results = {}
    for condition in ['snow_drift', 'icy_road', 'slush']:
        result = tester.test_condition(condition)
        if result:
            results[condition] = result
            
            logger.info(f"\nResultater for {condition}:")
            logger.info(f"Score: {result['score']:.4f}")
            logger.info("Viktigste features:")
            sorted_features = sorted(
                result['feature_importance'].items(),
                key=lambda x: x[1],
                reverse=True
            )
            for feature, importance in sorted_features[:3]:
                logger.info(f"  {feature}: {importance:.4f}")
            logger.info(f"Klassifikasjonsrapport:\n{result['classification_report']}")
    
    return results

if __name__ == "__main__":
    results = run_all_tests()
    if results:
        logger.info("\n=== OPPSUMMERING ===")
        for condition, result in results.items():
            logger.info(f"\n{condition.upper()}:")
            logger.info(f"Score: {result['score']:.4f}")
            logger.info(f"Antall datapunkter: {result['data_points']}")
    logger.info("\n=== TEST FULLFØRT ===")