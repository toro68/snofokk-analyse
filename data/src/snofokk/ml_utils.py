# Standard biblioteker
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, Union

# Tredjeparts biblioteker
import numpy as np
import optuna
import pandas as pd
from sklearn.ensemble import (
    GradientBoostingRegressor,
    RandomForestRegressor,
    VotingRegressor,
)
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor
from joblib import dump, load

# Lokale imports
try:
    from .config import DEFAULT_PARAMS
except ImportError:
    from data.src.snofokk.config import DEFAULT_PARAMS

# Type aliases
T = TypeVar("T")
ModelType = Union[
    RandomForestRegressor, GradientBoostingRegressor, XGBRegressor, VotingRegressor
]

# Logging oppsett
logger = logging.getLogger(__name__)


class SnowDriftOptimizer:
    def __init__(self, initial_params: Dict = None):
        # Sikre at vi har alle nødvendige parametre
        self.initial_params = initial_params if initial_params is not None else DEFAULT_PARAMS.copy()
        
        # ML-spesifikke parametre med oppdatert max_features
        self.ml_params = {
            'n_estimators': 100,
            'max_depth': None,
            'min_samples_split': 2,
            'min_samples_leaf': 1,
            'max_features': 'sqrt'  # Endret fra 'auto' til 'sqrt'
        }
        
        self.model = RandomForestRegressor(**self.ml_params, random_state=42)
        self.scaler = StandardScaler()
        
    def prepare_features(self, df: pd.DataFrame) -> np.ndarray:
        """Forbereder features for ML-modellen"""
        logger.info("Forbereder features for ML")
        features = [
            'wind_speed', 
            'wind_from_direction', 
            'air_temperature', 
            'surface_snow_thickness', 
            'relative_humidity'
        ]
        
        # Sjekk om alle features finnes
        if not all(feature in df.columns for feature in features):
            missing = [f for f in features if f not in df.columns]
            logger.error(f"Mangler følgende kolonner: {missing}")
            raise ValueError(f"Mangler nødvendige kolonner: {missing}")
            
        return self.scaler.fit_transform(df[features])
        
    def train(self, df: pd.DataFrame, target: str = 'risk_score'):
        """Trener modellen"""
        X = self.prepare_features(df)
        y = df[target]
        self.model.fit(X, y)
        
    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Gjør prediksjoner"""
        X = self.prepare_features(df)
        return self.model.predict(X)
        
    def save_model(self, path: str = 'models/'):
        """Lagrer modellen"""
        dump(self.model, f'{path}snow_drift_model.joblib')
        dump(self.scaler, f'{path}feature_scaler.joblib')
        
    def load_model(self, path: str = 'models/'):
        """Laster modellen"""
        self.model = load(f'{path}snow_drift_model.joblib')
        self.scaler = load(f'{path}feature_scaler.joblib')
        
    def optimize_parameters(self, df: pd.DataFrame, target: str = 'r2_score') -> Dict[str, Any]:
        """Optimaliserer modellparametre"""
        logger.info("Starter parameteroptimalisering")
        try:
            # Beregn risk_score med snøfokk-parametre hvis den ikke finnes
            if 'risk_score' not in df.columns:
                from .snofokk import calculate_snow_drift_risk
                df, _ = calculate_snow_drift_risk(df, params=self.initial_params)
            
            X = self.prepare_features(df)
            y = df['risk_score'].values
            
            # Tren modellen først med nåværende parametre
            logger.info("Trener initial modell")
            self.model.fit(X, y)
            
            # Beregn current_score med trent modell
            if target == 'r2_score':
                current_score = self.model.score(X, y)
            elif target == 'mean_squared_error':
                pred = self.model.predict(X)
                current_score = -np.mean((y - pred) ** 2)
            else:  # mean_absolute_error
                pred = self.model.predict(X)
                current_score = -np.mean(np.abs(y - pred))
            
            logger.info(f"Initial score: {-current_score}")
            
            def objective(trial):
                params = {
                    'n_estimators': trial.suggest_int('n_estimators', 50, 300),
                    'max_depth': trial.suggest_int('max_depth', 3, 20),
                    'min_samples_split': trial.suggest_int('min_samples_split', 2, 10),
                    'min_samples_leaf': trial.suggest_int('min_samples_leaf', 1, 5),
                    'max_features': trial.suggest_categorical('max_features', ['sqrt', 'log2'])
                }
                
                model = RandomForestRegressor(**params, random_state=42)
                model.fit(X, y)
                
                if target == 'r2_score':
                    score = model.score(X, y)
                elif target == 'mean_squared_error':
                    pred = model.predict(X)
                    score = -np.mean((y - pred) ** 2)
                else:  # mean_absolute_error
                    pred = model.predict(X)
                    score = -np.mean(np.abs(y - pred))
                    
                return -score  # Negativ fordi Optuna minimerer
                
            study = optuna.create_study(direction='minimize')
            study.optimize(objective, n_trials=50)
            
            if study.best_params and study.best_value is not None:
                self.model = RandomForestRegressor(**study.best_params, random_state=42)
                self.model.fit(X, y)
                
                # Konverter numpy typer til Python native typer
                best_params = {
                    k: v.item() if hasattr(v, 'item') else v 
                    for k, v in study.best_params.items()
                }
                
                return {
                    'status': 'success',
                    'best_params': best_params,  # Bruk konverterte parametre
                    'best_score': float(-study.best_value),  # Konverter til float
                    'current_score': float(-current_score),  # Konverter til float
                    'optimization_history': [
                        {k: v.item() if hasattr(v, 'item') else v for k, v in trial.items()}
                        for trial in study.trials_dataframe().to_dict('records')
                    ],
                    'n_trials': len(study.trials)
                }
            else:
                raise ValueError("Ingen gyldige parametre funnet under optimalisering")
                
        except Exception as e:
            logger.error(f"Feil under parameteroptimalisering: {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'best_params': None,
                'best_score': None
            }
