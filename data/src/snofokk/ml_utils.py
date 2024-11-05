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
    def __init__(self) -> None:
        self.scaler: StandardScaler = StandardScaler()
        self.data_path: Path = Path("")
        self.current_params: Dict[str, float] = DEFAULT_PARAMS.copy()
        self.best_params: Optional[Dict[str, float]] = None
        self.best_score: float = float("-inf")
        self.history: List[Dict[str, Any]] = []
        self.model: Optional[ModelType] = None
        self.feature_importance: Dict[str, float] = {}

        # Initialiser optimaliserings-strategi
        self.strategy = optuna.create_study(
            direction="maximize", sampler=optuna.samplers.TPESampler()
        )

    def _calculate_stability(self, cv_scores: List[float]) -> str:
        """Beregner stabilitet basert på variasjon i CV scores."""
        variation = np.std(cv_scores) / np.mean(cv_scores)
        if variation < 0.05:
            return "Svært stabil"
        elif variation < 0.10:
            return "Stabil"
        elif variation < 0.15:
            return "Moderat stabil"
        else:
            return "Ustabil"

    def create_test_features(self, test_direction: float) -> pd.DataFrame:
        """Lager test-features for vindretningsanalyse."""
        try:
            directions = np.arange(test_direction - 90, test_direction + 91, 5)
            test_df = pd.DataFrame(
                {
                    "wind_from_direction": directions,
                    "wind_speed": [10.0] * len(directions),  # Endret til float
                }
            )
            return self.create_feature_matrix(test_df)
        except Exception as exc:
            logger.error(f"Feil i beregning: {str(exc)}")
            raise

    def process_datetime_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prosesserer datetime-features."""
        df = df.copy()
        if not df.index.empty and isinstance(df.index, pd.DatetimeIndex):
            df["month"] = df.index.month
            df["hour"] = df.index.hour
            df["month_bin"] = pd.cut(
                pd.Series(df.index.month),  # Konvertert til Series først
                bins=[0, 3, 6, 9, 12],
                labels=["winter", "spring", "summer", "fall"],
            )
        return df

    def fillna_with_defaults(self, series: pd.Series, default_value: Any) -> pd.Series:
        """Fyller NA-verdier med standardverdier."""
        return series.fillna(default_value)

    def suggest_parameters(self):
        """Parametere basert på data."""
        # Opprett dataframe for vindretningseffekter
        wind_dir_effects = pd.DataFrame(index=range(0, 360, 10), columns=["effect"])
        # Opprett standard feature-sett
        base_features = {
            "wind_speed": self.current_params["wind_strong"],
            "wind_gust": self.current_params["wind_gust"],
            "temperature": self.current_params["temp_cold"],
            "snow_depth": self.current_params["snow_high"],
            "snow_change": 0.5,  # Standard endringsverdi
            "wind_dir_diff": 0,  # Legg til manglende feature
            "wind_direction": 0,  # Vil bli oppdatert i løkken
        }

        # Beregn effekter for hver vindretning
        for direction in wind_dir_effects.index:
            features = base_features.copy()
            features["wind_direction"] = direction

            # Konverter til DataFrame med riktig format
            X = pd.DataFrame([features])

            try:
                wind_dir_effects.loc[direction, "effect"] = self.model.predict(X)[0]
            except Exception as e:
                logging.error(f"Feil ved prediksjon for retning {direction}: {str(e)}")
                wind_dir_effects.loc[direction, "effect"] = 0
