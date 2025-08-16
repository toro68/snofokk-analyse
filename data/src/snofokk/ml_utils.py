# Standard biblioteker
import logging
from typing import Any, TypeVar, Union

# Tredjeparts biblioteker
import numpy as np
import optuna
import pandas as pd
from joblib import dump, load
from sklearn.ensemble import (
    GradientBoostingRegressor,
    RandomForestRegressor,
    VotingRegressor,
)
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

# Lokale imports
try:
    from .config import DEFAULT_PARAMS
    from .snofokk import calculate_snow_drift_risk
except ImportError:
    from data.src.snofokk.config import DEFAULT_PARAMS
    from data.src.snofokk.snofokk import calculate_snow_drift_risk

# Type aliases
T = TypeVar("T")
ModelType = Union[
    RandomForestRegressor, GradientBoostingRegressor, XGBRegressor, VotingRegressor
]

# Logging oppsett
logger = logging.getLogger(__name__)


class SnowDriftOptimizer:
    def __init__(self, initial_params: dict = None):
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

    def optimize_parameters(self, df: pd.DataFrame, target: str = 'r2_score') -> dict[str, Any]:
        """
        Optimaliserer modellparametre med forbedret søkestrategi og validering
        
        Args:
            df: DataFrame med værdata
            target: Målemetrikk ('r2_score', 'mean_squared_error', eller 'mean_absolute_error')
            
        Returns:
            Dict med optimaliseringsresultater
        """
        logger.info("Starter parameteroptimalisering med forbedret strategi")

        try:
            # Beregn baseline med nåværende parametre
            df_baseline = df.copy()
            df_baseline, _ = calculate_snow_drift_risk(df_baseline, params=self.initial_params)
            baseline_risk = df_baseline['risk_score'].copy()

            def objective(trial):
                # Definer parameterrom med mer fornuftige grenser
                params = {
                    'wind_strong': trial.suggest_float('wind_strong', 12.0, 20.0),
                    'wind_moderate': trial.suggest_float('wind_moderate', 6.0, 12.0),
                    'wind_gust': trial.suggest_float('wind_gust', 15.0, 25.0),
                    'wind_dir_change': trial.suggest_float('wind_dir_change', 20.0, 90.0),
                    'wind_weight': trial.suggest_float('wind_weight', 0.3, 0.6),
                    'temp_cold': trial.suggest_float('temp_cold', -15.0, -8.0),
                    'temp_cool': trial.suggest_float('temp_cool', -5.0, 0.0),
                    'temp_weight': trial.suggest_float('temp_weight', 0.2, 0.4),
                    'snow_high': trial.suggest_float('snow_high', 3.0, 8.0),
                    'snow_moderate': trial.suggest_float('snow_moderate', 1.5, 4.0),
                    'snow_low': trial.suggest_float('snow_low', 0.5, 1.5),
                    'snow_weight': trial.suggest_float('snow_weight', 0.2, 0.4)
                }

                # Valider parameterrelasjoner
                if params['wind_moderate'] >= params['wind_strong']:
                    return float('inf')
                if params['snow_low'] >= params['snow_moderate']:
                    return float('inf')
                if params['snow_moderate'] >= params['snow_high']:
                    return float('inf')

                # Beregn score
                df_temp = df.copy()
                df_temp, _ = calculate_snow_drift_risk(df_temp, params=params)

                if target == 'r2_score':
                    score = r2_score(baseline_risk, df_temp['risk_score'])
                    return -score  # Negativ siden Optuna minimerer
                elif target == 'mean_squared_error':
                    return mean_squared_error(baseline_risk, df_temp['risk_score'])
                else:
                    return mean_absolute_error(baseline_risk, df_temp['risk_score'])

            # Kjør optimalisering med flere forsøk
            study = optuna.create_study(direction='minimize')
            study.optimize(objective, n_trials=100)  # Økt antall forsøk

            # Evaluer resultater
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
                'optimization_history': study.trials_dataframe().to_dict('records'),
                'parameter_importance': self.calculate_parameter_importance(study)
            }

        except Exception as e:
            logger.error(f"Feil i parameteroptimalisering: {str(e)}", exc_info=True)
            return {'status': 'error', 'error': str(e)}

    def calculate_parameter_importance(self, study) -> dict[str, float]:
        """
        Beregner parameter importance basert på korrelasjon mellom parameterverdi og score
        
        Args:
            study: Optuna study objekt
        
        Returns:
            Dict med parameter importance scores
        """
        trials_df = study.trials_dataframe()

        # Hvis vi ikke har nok trials, returner tom dict
        if len(trials_df) < 2:
            return {}

        importance_scores = {}

        # Beregn korrelasjon mellom hver parameter og verdien
        for param in study.best_params.keys():
            if param in trials_df.columns:
                # Bruk absoluttverdi av korrelasjonen som importance score
                correlation = abs(trials_df[param].corr(trials_df['value']))
                importance_scores[param] = correlation if not np.isnan(correlation) else 0.0

        # Normaliser scores
        total = sum(importance_scores.values())
        if total > 0:
            importance_scores = {k: v/total for k, v in importance_scores.items()}

        return importance_scores
