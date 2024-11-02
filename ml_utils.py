# Standard biblioteker
import logging
from pathlib import Path
from typing import Any

import joblib

# Tredjeparts biblioteker
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.ensemble import (
    GradientBoostingRegressor,
    IsolationForest,
    RandomForestRegressor,
    VotingRegressor,
)
from sklearn.feature_selection import SelectFromModel
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from config import PARAMETER_BOUNDS
from snow_constants import SnowDepthConfig

logger = logging.getLogger(__name__)

# Lokale imports
# from snofokk import calculate_snow_drift_risk

# Logging oppsett
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SnowDriftOptimizer:
    """Maskinlæringsbasert optimalisering av snøfokk-parametre"""

    def __init__(self, data_path: str = "models"):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_importance = {}
        self.data_path = Path(data_path)
        self.data_path.mkdir(exist_ok=True)

    def create_feature_matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Lager feature matrix fra input data

        Args:
            df: DataFrame med værdata

        Returns:
            DataFrame med prosesserte features
        """
        try:
            features = pd.DataFrame(index=df.index)
            config = SnowDepthConfig.get_processing_config()

            # Sikre at alle nødvendige konfigurasjonsverdier finnes
            default_config = {
                "min_change": -10.0,
                "max_change": 10.0,
                "window": 3,
                "min_periods": 1,
            }

            # Oppdater config med standardverdier hvis noe mangler
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value

            # Vindretningsanalyse
            if "wind_from_direction" in df.columns and "wind_speed" in df.columns:
                wind_rad = np.deg2rad(df["wind_from_direction"])
                features["wind_dir_sin"] = np.sin(wind_rad)
                features["wind_dir_cos"] = np.cos(wind_rad)
                features["wind_speed"] = df["wind_speed"]

            # Temperaturanalyse
            if "air_temperature" in df.columns:
                features["temperature"] = df["air_temperature"]

            # Snødybdeanalyse med SnowDepthConfig
            if "surface_snow_thickness" in df.columns:
                snow_data = df["surface_snow_thickness"].copy()

                # Valider verdier med konfigurerte grenser
                invalid_mask = (snow_data < config["min_valid"]) | (
                    snow_data > config["max_valid"]
                )
                snow_data[invalid_mask] = np.nan

                # Prosesser snødybdedata med konfigurerte parametre
                features["snow_depth"] = (
                    snow_data.interpolate(
                        method=config["method"],
                        limit=config["interpolation_limit"],
                    )
                    .ffill(limit=config["ffill_limit"])
                    .bfill(limit=config["bfill_limit"])
                    .fillna(0)
                )
            else:
                features["snow_depth"] = 0.0
                logger.warning("Manglende snødybdedata - bruker nullverdier")

            # Beregn snøendringer med konfigurerte vinduer
            features["snow_change"] = (
                features["snow_depth"]
                .diff()
                .clip(lower=config["min_change"], upper=config["max_change"])
                .rolling(window=config["window"], min_periods=config["min_periods"])
                .mean()
                .fillna(0)
            )

            # Beregn raske snøendringer
            features["rapid_snow_change"] = (
                features["snow_change"]
                .abs()
                .rolling(window=config["window"], min_periods=config["min_periods"])
                .max()
                .fillna(0)
            )

            return features

        except Exception as exc:
            logger.exception(f"Kritisk feil i feature engineering: {str(exc)}")
            raise

    def optimize_parameters(
        self, df: pd.DataFrame, target: pd.Series
    ) -> dict[str, Any]:
        """
        Optimaliserer parametre basert på historiske data

        Args:
            df: DataFrame med værdata
            target: Faktisk risikoscore

        Returns:
            Dict med optimaliserte parametre og evalueringsmetrikker
        """
        try:
            # Lag feature matrix
            X = self.create_feature_matrix(df)
            y = target

            # Tidsserie-splitting
            tscv = TimeSeriesSplit(n_splits=5)

            # Initialiser resultater
            cv_scores = []
            feature_importance_list = []

            # Kjør cross-validation
            for train_idx, test_idx in tscv.split(X):
                X_train = X.iloc[train_idx]
                X_test = X.iloc[test_idx]
                y_train = y.iloc[train_idx]
                y_test = y.iloc[test_idx]

                # Skaler features
                X_train_scaled = self.scaler.fit_transform(X_train)
                X_test_scaled = self.scaler.transform(X_test)

                # Tren modell
                model = RandomForestRegressor(
                    n_estimators=100, max_depth=10, random_state=42
                )
                model.fit(X_train_scaled, y_train)

                # Evaluer
                y_pred = model.predict(X_test_scaled)
                score = r2_score(y_test, y_pred)
                cv_scores.append(score)

                # Lagre feature importance
                importance = dict(zip(X.columns, model.feature_importances_))
                feature_importance_list.append(importance)

            # Beregn gjennomsnittlig feature importance
            self.feature_importance = {
                feature: np.mean([imp[feature] for imp in feature_importance_list])
                for feature in X.columns
            }

            # Lagre beste modell
            self.model = model
            joblib.dump(self.model, self.data_path / "snow_drift_model.joblib")
            joblib.dump(self.scaler, self.data_path / "feature_scaler.joblib")

            # Generer parameterforslag basert på feature importance
            suggested_params = self.suggest_parameters()

            # Legg til min_duration optimalisering
            duration_results = self.optimize_min_duration(df)

            # Formater resultatene
            formatted_results = self.format_optimization_results(
                {
                    "cv_scores": cv_scores,
                    "mean_cv_score": np.mean(cv_scores),
                    "feature_importance": self.feature_importance,
                    "suggested_parameters": suggested_params,
                    "duration_analysis": duration_results,
                }
            )

            return formatted_results

        except Exception as exc:
            logger.error(f"Feil i parameteroptimalisering: {str(exc)}")
            raise

    def suggest_parameters(self) -> dict[str, float]:
        """
        Foreslår parameterinnstillinger basert på feature importance

        Returns:
            Dict med foreslåtte parametre
        """
        try:
            # Normaliser feature importance
            total_importance = sum(self.feature_importance.values())
            norm_importance = {
                k: v / total_importance for k, v in self.feature_importance.items()
            }

            # Beregn vekter basert på feature groups
            wind_importance = sum(
                v for k, v in norm_importance.items() if "wind" in k.lower()
            )
            temp_importance = sum(
                v for k, v in norm_importance.items() if "temp" in k.lower()
            )
            snow_importance = sum(
                v for k, v in norm_importance.items() if "snow" in k.lower()
            )
            temporal_importance = sum(
                v
                for k, v in norm_importance.items()
                if any(x in k.lower() for x in ["duration", "temporal", "period"])
            )

            # Juster parametre basert på relative viktigheter
            suggested_params = {
                "wind_weight": min(2.0, 1.0 + wind_importance),
                "temp_weight": min(2.0, 1.0 + temp_importance),
                "snow_weight": min(2.0, 1.0 + snow_importance),
                # Juster terskelverdier basert på feature importance
                "wind_strong": 8.0 * (1.0 + wind_importance * 0.5),
                "wind_moderate": 6.5 * (1.0 + wind_importance * 0.3),
                "wind_gust": 15.0 * (1.0 + wind_importance * 0.2),
                "wind_dir_change": 30.0 * (1.0 + wind_importance * 0.4),
                "temp_cold": -2.0 * (1.0 + temp_importance * 0.5),
                "temp_cool": 0.0 * (1.0 + temp_importance * 0.3),
                "snow_high": 1.5 * (1.0 + snow_importance * 0.5),
                "snow_moderate": 0.8 * (1.0 + snow_importance * 0.3),
                "snow_low": 0.3 * (1.0 + snow_importance * 0.2),
                # Legg til min_duration basert på temporal importance
                "min_duration": max(
                    1, min(12, round(3 * (1.0 + temporal_importance * 0.5)))
                ),
            }

            # Analyser vindretningseffekter
            wind_dir_features = [
                col for col in self.feature_importance if "wind_dir" in col
            ]
            dir_importance = sum(
                self.feature_importance.get(f, 0) for f in wind_dir_features
            )

            # Finn optimal primærretning basert på data
            if hasattr(self, "model") and self.model is not None:
                wind_dir_effects = pd.DataFrame(index=range(0, 360, 5))
                for direction in wind_dir_effects.index:
                    # Simuler effekt av ulike retninger
                    test_features = self.create_test_features(direction)
                    wind_dir_effects.loc[direction, "effect"] = self.model.predict(
                        test_features
                    ).mean()

                # Finn retningen med høyest effekt
                optimal_direction = wind_dir_effects["effect"].idxmax()

                # Beregn optimal toleranse basert på effektkurven
                effect_threshold = (
                    wind_dir_effects["effect"].max() * 0.8
                )  # 80% av maks effekt
                tolerance = min(
                    90,  # Maks 90 grader
                    wind_dir_effects[
                        wind_dir_effects["effect"] >= effect_threshold
                    ].index.size
                    * 5
                    // 2,
                )
            else:
                optimal_direction = 270  # Standard vestlig retning hvis ingen modell
                tolerance = 45  # Standard toleranse

            suggested_params.update(
                {
                    "wind_dir_primary": optimal_direction,
                    "wind_dir_tolerance": tolerance,
                    "wind_dir_weight": min(2.0, 1.0 + dir_importance * 2),
                }
            )

            return suggested_params

        except Exception as exc:
            logger.error(f"Feil i parameterforslag: {str(exc)}")
            raise

    def evaluate_parameters(
        self, df: pd.DataFrame, params: dict[str, float]
    ) -> dict[str, Any]:
        """
        Evaluerer et sett med parametre mot historiske data

        Args:
            df: DataFrame med værdata
            params: Dict med parametre å evaluere

        Returns:
            Dict med evalueringsmetrikker
        """
        try:
            # Sjekk om modell eksisterer
            model_path = self.data_path / "snow_drift_model.joblib"
            scaler_path = self.data_path / "feature_scaler.joblib"

            if not model_path.exists() or not scaler_path.exists():
                raise FileNotFoundError("Modell eller scaler filer mangler")

            # Importer calculate_snow_drift_risk lokalt for å unngå syklusimport
            try:
                from snofokk import calculate_snow_drift_risk
            except ImportError as exc:
                logger.error(f"Kunne ikke importere calculate_snow_drift_risk: {exc}")
                raise

            # Lag features for evaluering
            features = self.create_feature_matrix(df)

            if self.model is None:
                self.model = joblib.load(self.data_path / "snow_drift_model.joblib")
                self.scaler = joblib.load(self.data_path / "feature_scaler.joblib")

            # Prediker risikoscore
            X_scaled = self.scaler.transform(features)
            predicted_risk = self.model.predict(X_scaled)

            # Beregn faktisk risiko med nye parametre
            actual_df, periods_df = calculate_snow_drift_risk(df, params)

            # Beregn evalueringsmetrikker
            metrics = {
                "mse": mean_squared_error(actual_df["risk_score"], predicted_risk),
                "r2": r2_score(actual_df["risk_score"], predicted_risk),
                "num_critical_periods": len(periods_df),
                "avg_period_duration": (
                    periods_df["duration"].mean() if not periods_df.empty else 0
                ),
                "max_risk_score": actual_df["risk_score"].max(),
                "avg_risk_score": actual_df["risk_score"].mean(),
            }

            return metrics

        except Exception as exc:
            logger.exception(f"Kritisk feil i parameterevaluering: {str(exc)}")
            raise

    def optimize_min_duration(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Optimaliserer minimum varighet for kritiske perioder

        Args:
            df: DataFrame med værdata

        Returns:
            Dict med optimaliserte verdier og metrikker
        """
        try:
            # Sjekk om nødvendige kolonner eksisterer
            if not all(col in df.columns for col in ["wind_speed", "air_temperature"]):
                raise ValueError(
                    "Mangler nødvendige kolonner for varighet-optimalisering"
                )

            # Beregn risikoscore direkte her istedenfor å anta at den eksisterer
            risk_scores = df.apply(
                lambda row: (
                    (row["wind_speed"] > 10) * 1.0 + (row["air_temperature"] < -5) * 0.5
                ),
                axis=1,
            )

            # Test forskjellige varigheter
            durations = range(1, 13)  # 1-12 timer
            results = {}

            for duration in durations:
                # Finn perioder som varer minst 'duration' timer
                rolling_risk = risk_scores.rolling(window=duration).mean()
                critical_periods = rolling_risk[rolling_risk > 0.5]

                if len(critical_periods) > 0:
                    results[duration] = {
                        "num_periods": len(critical_periods),
                        "avg_risk": critical_periods.mean(),
                        "max_risk": critical_periods.max(),
                    }

            # Finn optimal varighet basert på balanse mellom antall perioder og risiko
            optimal_duration = min(
                results.keys(),
                key=lambda x: abs(results[x]["num_periods"] - 10),
            )

            # Legg til konfidensberegning
            confidence_score = 1.0 - (
                abs(results[optimal_duration]["num_periods"] - 10) / 10
            )

            return {
                "optimal_duration": optimal_duration,
                "duration_metrics": results,
                "confidence_score": confidence_score,
                "recommendation": f"Anbefalt minimum varighet: {optimal_duration} timer",
                "expected_impact": {
                    "num_periods": results[optimal_duration]["num_periods"],
                    "avg_risk": results[optimal_duration]["avg_risk"],
                },
            }

        except Exception as exc:
            logger.error(f"Feil i beregning: {str(exc)}")
            raise

    def format_optimization_results(self, results: dict[str, Any]) -> dict[str, Any]:
        """
        Formaterer optimeringsresultatene for presentasjon med bedre feilhåndtering
        """
        try:
            from config import DEFAULT_PARAMS

            # Beregn gjennomsnittlig CV score
            mean_cv_score = np.mean(results.get("cv_scores", [0]))

            # Sikre at vi har suggested_parameters
            suggested_params = results.get("suggested_parameters", {})
            if not suggested_params:
                # Bruk verdier fra config.DEFAULT_PARAMS hvis ingen forslag finnes
                suggested_params = DEFAULT_PARAMS.copy()
                logger.warning(
                    "Ingen foreslåtte parametre funnet, bruker verdier fra config.DEFAULT_PARAMS"
                )

            formatted = {
                "mean_cv_score": mean_cv_score,
                "model_performance": {
                    "r2_score": round(mean_cv_score, 3),
                    "stability": self._calculate_stability(
                        results.get("cv_scores", [])
                    ),
                },
                "feature_importance": results.get("feature_importance", {}),
                "suggested_parameters": suggested_params,
                "parameter_changes": {},
            }

            # Formater parameterendringer
            for param, value in results.get("suggested_parameters", {}).items():
                default = DEFAULT_PARAMS.get(param, value)
                pct_change = ((value - default) / default * 100) if default != 0 else 0

                formatted["parameter_changes"][param] = {
                    "value": round(value, 2),
                    "change": round(pct_change, 1),
                    "significance": (
                        "høy"
                        if abs(pct_change) > 5
                        else "moderat" if abs(pct_change) > 2 else "lav"
                    ),
                }

            # Legg til varighetsanalyse hvis tilgjengelig
            duration_analysis = results.get("duration_analysis", {})
            if duration_analysis:
                formatted["duration_analysis"] = {
                    "optimal": duration_analysis.get("min_duration", 3),
                    "confidence": round(
                        duration_analysis.get("confidence_score", 0.5), 2
                    ),
                    "impact": {
                        "num_periods": duration_analysis.get("expected_impact", {}).get(
                            "num_periods", 0
                        ),
                        "avg_risk": duration_analysis.get("expected_impact", {}).get(
                            "avg_risk", 0
                        ),
                    },
                }

            return formatted

        except Exception as exc:
            logger.error(f"Feil i beregning: {str(exc)}")
            raise

    def _calculate_stability(self, cv_scores: list[float]) -> str:
        """Beregner stabilitet basert på variasjon i CV scores"""
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
        """Lager test-features for vindretningsanalyse"""
        try:
            # Lag et enkelt datasett med vindretninger rundt test-retningen
            directions = np.arange(test_direction - 90, test_direction + 91, 5)
            test_df = pd.DataFrame(
                {
                    "wind_from_direction": directions,
                    "wind_speed": [10]
                    * len(directions),  # Standard vindstyrke for testing
                }
            )

            return self.create_feature_matrix(test_df)

        except Exception as exc:
            logger.error(f"Feil i beregning: {str(exc)}")
            raise


def analyze_seasonal_patterns(df: pd.DataFrame) -> dict[str, Any]:
    """
    Analyserer sesongmessige mønstre i værdata

    Args:
        df: DataFrame med værdata
    Returns:
        Dict med sesonganalyse
    """
    if df.empty or not all(
        col in df.columns for col in ["wind_speed", "air_temperature"]
    ):
        return {}

    analysis = {}

    # Legg til sesonginfo
    df = df.copy()
    df["month"] = df.index.month
    df["hour"] = df.index.hour
    df["season"] = pd.cut(
        df.index.month,
        bins=[0, 3, 6, 9, 12],
        labels=["Vinter", "Vår", "Sommer", "Høst"],
    )

    # Analyser sesongvariasjoner
    season_stats = (
        df.groupby("season")
        .agg(
            {
                "wind_speed": ["mean", "max"],
                "air_temperature": ["mean", "min"],
                "surface_snow_thickness": ["mean", "std"],
            }
        )
        .round(2)
    )

    # Analyser døgnvariasjoner
    hourly_stats = (
        df.groupby("hour")
        .agg({"wind_speed": "mean", "air_temperature": "mean"})
        .round(2)
    )

    # Finn typiske mønstre
    patterns = []

    # Vindmønstre
    wind_pattern = (
        df.groupby(["season", "hour"])["wind_speed"].mean().unstack().idxmax(axis=1)
    )
    patterns.append(
        {
            "type": "wind",
            "description": "Tidspunkt for høyest vind per sesong",
            "data": wind_pattern.to_dict(),
        }
    )

    # Temperaturmønstre
    temp_pattern = (
        df.groupby(["season", "hour"])["air_temperature"]
        .mean()
        .unstack()
        .idxmin(axis=1)
    )
    patterns.append(
        {
            "type": "temperature",
            "description": "Tidspunkt for lavest temperatur per sesong",
            "data": temp_pattern.to_dict(),
        }
    )

    analysis["season_stats"] = season_stats
    analysis["hourly_stats"] = hourly_stats
    analysis["patterns"] = patterns

    return analysis


def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Håndterer snødybdedata:
    - Konverterer negative verdier til 0
    - Interpolerer korte perioder med manglende data
    - Fyller lengre perioder med forrige kjente verdi
    """
    if "surface_snow_thickness" in df.columns:
        # Logg originale negative verdier hvis de finnes
        neg_values = df[df["surface_snow_thickness"] < 0]["surface_snow_thickness"]
        if not neg_values.empty:
            logger.warning(
                f"Fant {len(neg_values)} negative snødybdeverdier. Konverterer til 0."
            )

        # Konverter negative verdier til 0
        df["surface_snow_thickness"] = df["surface_snow_thickness"].clip(lower=0)

        # Tell antall påfølgende NaN-verdier
        null_periods = (
            df["surface_snow_thickness"]
            .isnull()
            .astype(int)
            .groupby(df["surface_snow_thickness"].notnull().cumsum())
            .cumsum()
        )

        # Interpoler korte perioder (f.eks. mindre enn 6 timer)
        kort_periode = 6
        mask_kort = null_periods <= kort_periode
        df.loc[mask_kort, "surface_snow_thickness"] = df[
            "surface_snow_thickness"
        ].interpolate(method="linear", limit=kort_periode, limit_direction="both")

        # For lengre perioder, bruk ffill med en maksgrense
        lang_periode = 24  # maksimalt 24 timer med ffill
        df["surface_snow_thickness"] = df["surface_snow_thickness"].fillna(
            method="ffill", limit=lang_periode
        )

        # Gjenstående NaN settes til 0
        manglende_data = df["surface_snow_thickness"].isnull().sum()
        if manglende_data > 0:
            logger.warning(
                f"Setter {manglende_data} verdier til 0 etter {lang_periode} "
                "timer uten gyldige målinger"
            )
            df["surface_snow_thickness"] = df["surface_snow_thickness"].fillna(0)

        logger.info(
            f"Snødybde-statistikk etter preprocessing: \n"
            f"Min: {df['surface_snow_thickness'].min():.2f}, "
            f"Max: {df['surface_snow_thickness'].max():.2f}, "
            f"Gjennomsnitt: {df['surface_snow_thickness'].mean():.2f}"
        )

    return df


def _is_numeric(value: Any) -> bool:
    """Sjekker om en verdi er numerisk (int eller float, men ikke bool)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_parameters(params: dict[str, float]) -> tuple[bool, str]:
    """
    Validerer parametre før de brukes i beregninger.

    Sjekker:
    - At alle påkrevde parametre eksisterer
    - At verdiene er innenfor definerte grenser
    - At verdiene er numeriske
    - At verdiene har logiske relasjoner til hverandre

    Args:
        params: Dict med parametre som skal valideres

    Returns:
        tuple[bool, str]: (Er valid, Feilmelding hvis ikke valid)
    """
    try:
        # Sjekk at alle påkrevde parametre finnes og er numeriske
        for param, (min_val, max_val) in PARAMETER_BOUNDS.items():
            if param not in params:
                logger.error(f"Mangler parameter: {param}")
                return False, f"Mangler parameter: {param}"

            if not _is_numeric(params[param]):
                logger.error(f"Parameter {param} er ikke numerisk: {params[param]}")
                return False, f"Parameter {param} må være et tall"

            if not min_val <= params[param] <= max_val:
                logger.error(
                    f"Parameter {param} = {params[param]} er utenfor gyldig område: {min_val}-{max_val}"
                )
                return (
                    False,
                    f"Parameter {param} utenfor gyldig område: {min_val}-{max_val}",
                )

        # Valider logiske relasjoner mellom parametre
        validations = [
            (
                params["wind_strong"] > params["wind_moderate"],
                "wind_strong må være større enn wind_moderate",
            ),
            (
                params["wind_gust"] > params["wind_strong"],
                "wind_gust må være større enn wind_strong",
            ),
            (
                params["temp_cold"] < params["temp_cool"],
                "temp_cold må være lavere enn temp_cool",
            ),
            (
                params["snow_high"] > params["snow_moderate"] > params["snow_low"],
                "Snøverdier må være i rekkefølge: high > moderate > low",
            ),
            (
                all(
                    0 <= params[p] <= 2
                    for p in ["wind_weight", "temp_weight", "snow_weight"]
                ),
                "Vekter må være mellom 0 og 2",
            ),
        ]

        for condition, error_message in validations:
            if not condition:
                logger.error(error_message)
                return False, error_message

        logger.debug("Parametervalidering vellykket")
        return True, ""

    except Exception as exc:
        error_msg = f"Uventet feil i parametervalidering: {str(exc)}"
        logger.exception(error_msg)
        return False, error_msg


class OutlierRemover(BaseEstimator, TransformerMixin):
    """Tilpasset transformer for fjerning av utliggere"""

    def __init__(self, contamination=0.1):
        self.contamination = contamination
        self.detector = IsolationForest(contamination=contamination)

    def fit(self, X, y=None):
        self.detector.fit(X)
        return self

    def transform(self, X):
        mask = self.detector.predict(X) == 1
        return X[mask]


def improve_model_robustness(
    optimizer: SnowDriftOptimizer, cv_folds: int = 5, random_state: int = 42
) -> tuple[bool, dict[str, Any]]:
    """
    Forbedrer modellrobusthet med ensemble-metoder og feature selection

    Args:
        optimizer: SnowDriftOptimizer instans
        cv_folds: Antall kryss-validering folder
        random_state: Random seed for reproduserbarhet

    Returns:
        tuple[bool, Dict]: (Suksess status, Metrics dict)
    """
    try:
        logger.info("Starter modellforbedringstiltak...")

        # Konfigurer base modeller med standardiserte parametere
        base_models = {
            "rf": RandomForestRegressor(
                n_estimators=100, max_depth=10, random_state=random_state
            ),
            "gbm": GradientBoostingRegressor(
                n_estimators=100, learning_rate=0.1, random_state=random_state
            ),
            "xgb": XGBRegressor(
                n_estimators=100, learning_rate=0.1, random_state=random_state
            ),
        }

        # Opprett ensemble med vekting
        voting_ensemble = VotingRegressor(
            [(name, model) for name, model in base_models.items()]
        )

        # Konfigurer feature selection med terskel
        selector = SelectFromModel(
            estimator=RandomForestRegressor(random_state=random_state),
            threshold="median",  # Bruk median som terskel
        )

        # Opprett robust pipeline
        pipeline = Pipeline(
            [
                ("outlier_removal", OutlierRemover(contamination=0.1)),
                ("feature_selection", selector),
                ("ensemble", voting_ensemble),
            ]
        )

        # Oppdater optimizer modell
        optimizer.model = pipeline

        # Samle metrics
        metrics = {
            "pipeline_steps": [step[0] for step in pipeline.steps],
            "base_models": list(base_models.keys()),
            "feature_selection_threshold": "median",
            "outlier_removal_contamination": 0.1,
        }

        logger.info("Modellforbedringstiltak fullført vellykket")
        return True, metrics

    except Exception as exc:
        logger.error(f"Kritisk feil i modellforbedrning: {str(exc)}", exc_info=True)
        return False, {"error": str(exc)}


# Dette skal være helt nederst i filen
__all__ = ["SnowDriftOptimizer", "analyze_seasonal_patterns"]
