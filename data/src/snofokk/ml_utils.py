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
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from xgboost import XGBRegressor
from joblib import dump, load

# Lokale imports
try:
    from .snofokk import calculate_snow_drift_risk
    from .config import DEFAULT_PARAMS
except ImportError:
    from data.src.snofokk.snofokk import calculate_snow_drift_risk
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
            # Beregn baseline risk_score med initielle parametre
            df_baseline = df.copy()
            df_baseline, _ = calculate_snow_drift_risk(df_baseline, params=self.initial_params)
            baseline_risk = df_baseline['risk_score'].copy()

            def objective(trial):
                # Optimaliser snøfokk-parametre
                params = {
                    'wind_strong': trial.suggest_float('wind_strong', 10.0, 25.0),
                    'wind_moderate': trial.suggest_float('wind_moderate', 5.0, 15.0),
                    'wind_gust': trial.suggest_float('wind_gust', 10.0, 30.0),
                    'wind_dir_change': trial.suggest_float('wind_dir_change', 0.0, 180.0),
                    'wind_weight': trial.suggest_float('wind_weight', 0.0, 2.0),
                    'temp_cold': trial.suggest_float('temp_cold', -20.0, -5.0),
                    'temp_cool': trial.suggest_float('temp_cool', -5.0, 2.0),
                    'temp_weight': trial.suggest_float('temp_weight', 0.0, 2.0),
                    'snow_high': trial.suggest_float('snow_high', 2.0, 10.0),
                    'snow_moderate': trial.suggest_float('snow_moderate', 1.0, 5.0),
                    'snow_low': trial.suggest_float('snow_low', 0.0, 2.0),
                    'snow_weight': trial.suggest_float('snow_weight', 0.0, 2.0)
                }
                
                # Beregn risk_score med de foreslåtte parametrene
                df_temp = df.copy()
                df_temp, _ = calculate_snow_drift_risk(df_temp, params=params)
                
                # Evaluer resultatet mot baseline
                if target == 'r2_score':
                    score = r2_score(baseline_risk, df_temp['risk_score'])
                elif target == 'mean_squared_error':
                    score = -mean_squared_error(baseline_risk, df_temp['risk_score'])
                else:  # mean_absolute_error
                    score = -mean_absolute_error(baseline_risk, df_temp['risk_score'])
                    
                return -score  # Negativ fordi Optuna minimerer

            # Kjør optimalisering
            study = optuna.create_study(direction='minimize')
            study.optimize(objective, n_trials=50)

            # Hent beste parametre og beregn endelig score
            best_params = study.best_params
            df_best = df.copy()
            df_best, _ = calculate_snow_drift_risk(df_best, params=best_params)
            
            if target == 'r2_score':
                best_score = r2_score(baseline_risk, df_best['risk_score'])
                current_score = 1.0
            else:
                best_score = -study.best_value
                current_score = 0.0

            return {
                'status': 'success',
                'best_params': best_params,
                'best_score': best_score,
                'current_score': current_score,
                'optimization_history': study.trials_dataframe().to_dict('records')
            }

        except Exception as e:
            logger.error(f"Feil i parameteroptimalisering: {str(e)}", exc_info=True)
            return {'status': 'error', 'error': str(e)}
