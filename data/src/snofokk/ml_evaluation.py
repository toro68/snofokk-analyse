# Fil: ml_evaluation.py
# Kategori: Machine Learning Evaluation Functions

import logging
import logging.handlers
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
import psutil

from .snow_constants import SnowDepthConfig


# Forbedret logging-oppsett
def setup_logging():
    """Konfigurerer logging med roterende filer og formattering"""
    logger = logging.getLogger(__name__)
    
    # Fjern eksisterende handlers for å unngå duplikater
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)
    
    logger.setLevel(logging.INFO)
    
    # Rotering av loggfiler
    file_handler = logging.handlers.RotatingFileHandler(
        "ml_evaluation.log",
        maxBytes=1024 * 1024,
        backupCount=5,
    )
    
    # Forbedret formattering
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Unngå propagering til root logger for å hindre duplikater
    logger.propagate = False
    
    return logger


logger = setup_logging()


class MLEvaluator:
    """
    Klasse for evaluering og visualisering av ML-modellresultater for snøfokk-analyse
    """

    def __init__(self):
        self.metrics = {}
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initialiserer MLEvaluator")
        self.grouped_features: Dict[str, List[str]] = {
            "temperature": ["air_temperature", "min_temp", "max_temp"],
            "wind": ["wind_speed", "max_wind"],
            "snow": ["snow_depth", "snow_change"],
        }

    def evaluate_model_performance(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        feature_importance: Optional[dict[str, float]] = None,
    ) -> dict[str, Any]:
        """
        Evaluerer modellens ytelse med flere metrikker

        Args:
            y_true: Faktiske verdier
            y_pred: Predikerte verdier
            feature_importance: Dict med feature importance verdier

        Returns:
            Dict med evalueringsmetrikker
        """
        self.logger.info("Starter modellevaluering")
        try:
            # Valider input
            if len(y_true) != len(y_pred):
                self.logger.error(
                    f"Dimensjonsfeil: y_true ({len(y_true)}) != y_pred ({len(y_pred)})"
                )
                raise ValueError("y_true og y_pred må ha samme lengde")
            if not feature_importance:
                logger.warning("Tomt feature_importance dict mottatt")
                feature_importance = {}

            # Beregn grunnleggende metrikker
            mse = np.mean((y_true - y_pred) ** 2)
            rmse = np.sqrt(mse)
            mae = np.mean(np.abs(y_true - y_pred))

            # Beregn mer avanserte metrikker
            results = {
                "basic_metrics": {
                    "mse": mse,
                    "rmse": rmse,
                    "mae": mae,
                },
                "feature_analysis": self._analyze_feature_importance(
                    feature_importance
                ),
                "prediction_quality": self._analyze_prediction_quality(y_true, y_pred),
                "prediction_stability": self._analyze_prediction_stability(y_pred),
            }

            self.metrics = results
            self.logger.info("Modellevaluering fullført vellykket")
            return results

        except Exception as e:
            self.logger.exception("Kritisk feil under modellevaluering")
            return {"error": str(e), "details": self._get_error_context()}

    def _analyze_feature_importance(
        self, feature_importance: dict[str, float]
    ) -> dict[str, Any]:
        """
        Analyserer feature importance med forbedret kategorisering
        """
        self.logger.info(
            f"Starter feature importance analyse for {len(feature_importance)} features"
        )
        try:
            # Mer detaljert feature gruppering
            grouped_features = {
                "wind": {"speed": {}, "direction": {}, "gust": {}},
                "temperature": {"absolute": {}, "change": {}},
                "snow": {"depth": {}, "change": {}},
                "temporal": {},
                "other": {},
            }

            # Forbedret feature kategorisering
            for feature, importance in feature_importance.items():
                if "wind" in feature.lower():
                    if "dir" in feature:
                        grouped_features["wind"]["direction"][feature] = importance
                    elif "gust" in feature:
                        grouped_features["wind"]["gust"][feature] = importance
                    else:
                        grouped_features["wind"]["speed"][feature] = importance
                elif "temp" in feature.lower():
                    if "absolute" in feature:
                        grouped_features["temperature"]["absolute"][
                            feature
                        ] = importance
                    elif "change" in feature:
                        grouped_features["temperature"]["change"][feature] = importance
                elif "snow" in feature.lower():
                    if "depth" in feature:
                        grouped_features["snow"]["depth"][feature] = importance
                    elif "change" in feature:
                        grouped_features["snow"]["change"][feature] = importance
                elif "temporal" in feature.lower():
                    grouped_features["temporal"][feature] = importance
                else:
                    grouped_features["other"][feature] = importance

            # Beregn total importance per gruppe
            group_importance = {
                group: sum(importances.values())
                for group, importances in grouped_features.items()
            }

            self.logger.debug(f"Grupperte features: {list(grouped_features.keys())}")
            self.logger.info("Feature importance analyse fullført med suksess")
            return {
                "grouped_features": grouped_features,
                "group_importance": group_importance,
                "recommendations": self._generate_feature_recommendations(
                    grouped_features
                ),
            }

        except Exception as e:
            self.logger.exception("Kritisk feil under feature importance analyse")
            return {"error": str(e)}

    def _analyze_prediction_quality(
        self, y_true: np.ndarray, y_pred: np.ndarray
    ) -> dict[str, Any]:
        """
        Analyserer prediksjonskvalitet med fokus på feiltyper
        """
        self.logger.info("Starter analyse av prediksjonskvalitet")
        try:
            # Beregn prediksjonsavvik
            errors = y_pred - y_true

            # Analyser feilfordeling
            error_distribution = {
                "mean_error": np.mean(errors),
                "std_error": np.std(errors),
                "max_overpredict": np.max(errors),
                "max_underpredict": np.min(errors),
                "error_quantiles": {
                    "25%": np.percentile(errors, 25),
                    "50%": np.percentile(errors, 50),
                    "75%": np.percentile(errors, 75),
                },
            }

            self.logger.debug(
                f"Beregnet feilstatistikk: mean={error_distribution['mean_error']:.3f}, std={error_distribution['std_error']:.3f}"
            )
            self.logger.info("Prediksjonskvalitet analyse fullført")
            return {
                "error_distribution": error_distribution,
                "error_patterns": self._analyze_error_patterns(y_true, y_pred, errors),
            }

        except Exception:
            self.logger.exception("Feil i analyse av prediksjonskvalitet")
            return {}

    def _analyze_error_patterns(
        self, y_true: np.ndarray, y_pred: np.ndarray, errors: np.ndarray
    ) -> dict[str, Any]:
        """
        Analyserer mønstre i prediksjonsfeil
        """
        try:
            # Identifiser systematiske feil
            systematic_errors = {
                "high_value_bias": np.mean(errors[y_true > np.percentile(y_true, 75)]),
                "low_value_bias": np.mean(errors[y_true < np.percentile(y_true, 25)]),
                "extreme_errors": len(errors[np.abs(errors) > 2 * np.std(errors)]),
            }

            return {
                "systematic_errors": systematic_errors,
                "error_severity": self._categorize_error_severity(errors),
            }

        except Exception as e:
            logger.error(f"Feil i analyse av feilmønstre: {str(e)}")
            return {}

    def _categorize_error_severity(self, errors: np.ndarray) -> dict[str, int]:
        """
        Kategoriserer alvorlighetsgraden av prediksjonsfeil
        """
        try:
            std_error = np.std(errors)

            severity_counts = {
                "minor": len(errors[np.abs(errors) <= std_error]),
                "moderate": len(
                    errors[
                        (np.abs(errors) > std_error) & (np.abs(errors) <= 2 * std_error)
                    ]
                ),
                "severe": len(errors[np.abs(errors) > 2 * std_error]),
            }

            return severity_counts

        except Exception as e:
            logger.error(f"Feil i kategorisering av feilalvorlighet: {str(e)}")
            return {}

    def _generate_feature_recommendations(
        self, group_importance: dict[str, float]
    ) -> list[dict[str, str]]:
        """
        Genererer anbefalinger basert på feature importance analyse
        """
        recommendations = []

        # Analyser viktighet og gi anbefalinger
        total_importance = sum(group_importance.values())

        for group, importance in group_importance.items():
            relative_importance = importance / total_importance

            if relative_importance > 0.4:
                recommendations.append(
                    {
                        "group": group,
                        "importance": f"{relative_importance:.1%}",
                        "recommendation": (
                            f"Høy viktighet for {group}-relaterte features. "
                            f"Vurder å øke vekting og forbedre datakvalitet."
                        ),
                    }
                )
            elif relative_importance < 0.1:
                recommendations.append(
                    {
                        "group": group,
                        "importance": f"{relative_importance:.1%}",
                        "recommendation": (
                            f"Lav viktighet for {group}-relaterte features. "
                            f"Vurder å forenkle eller fjerne mindre viktige features."
                        ),
                    }
                )

        return recommendations

    def _analyze_prediction_stability(
        self, y_pred: np.ndarray, window_size: int = 3
    ) -> dict[str, float]:
        """
        Analyserer stabiliteten i prediksjoner over tid
        """
        try:
            # Beregn rullende standardavvik
            rolling_std = pd.Series(y_pred).rolling(window=window_size).std()

            stability_metrics = {
                "mean_stability": rolling_std.mean(),
                "max_instability": rolling_std.max(),
                "stability_score": 1 - (rolling_std.mean() / np.std(y_pred)),
            }

            return stability_metrics

        except Exception as e:
            logger.error(f"Feil i stabilitetsanalyse: {str(e)}")
            return {}

    def evaluate_parameter_impact(
        self,
        df: pd.DataFrame,
        original_params: dict[str, float],
        optimized_params: dict[str, float],
    ) -> dict[str, Any]:
        """Evaluerer effekten av optimaliserte parametre mot originale parametre"""
        self.logger.info("Starter evaluering av parametereffekt")
        
        try:
            # Komplette snøfokk-parametre
            snow_params = {
                'wind_strong': 10.0,      # Sterk vindgrense
                'wind_moderate': 6.0,     # Moderat vindgrense
                'wind_gust': 15.0,        # Vindkast terskel
                'wind_dir_change': 30.0,  # Vindretningsendring
                'wind_weight': 0.4,       # Vindvekt
                'temp_cold': -10.0,       # Kald temperatur
                'temp_cool': -5.0,        # Kjølig temperatur
                'temp_weight': 0.3,       # Temperaturvekt
                'snow_high': 5.0,         # Høy snøendring
                'snow_moderate': 2.0,     # Moderat snøendring
                'snow_low': 0.5,          # Lav snøendring
                'snow_weight': 0.3,       # Snøvekt
                'min_duration': 2,        # Minimum varighet
                'temp_threshold': -1.0,   # Temperaturgrense
                'snow_depth_min': 10.0,   # Minimum snødybde
                'risk_threshold': 0.7     # Risikogrense
            }
            from snofokk import calculate_snow_drift_risk
            
            # Beregn risiko med standardparametre
            original_df, original_periods = calculate_snow_drift_risk(df, snow_params)
            
            # Juster parametre basert på ML-optimalisering
            adjusted_params = snow_params.copy()
            if 'n_estimators' in optimized_params:
                # Juster parametre basert på ML-optimalisering
                adjusted_params['wind_strong'] = 8.0 + (optimized_params['max_depth'] / 20.0) * 4.0
                adjusted_params['wind_moderate'] = 5.0 + (optimized_params['min_samples_split'] / 10.0) * 2.0
                adjusted_params['temp_threshold'] = -2.0 + (optimized_params['min_samples_leaf'] / 5.0)
                
            optimized_df, optimized_periods = calculate_snow_drift_risk(df, adjusted_params)
            
            return {
                "risk_scores": {
                    "original": {
                        "mean": original_df["risk_score"].mean(),
                        "max": original_df["risk_score"].max(),
                        "std": original_df["risk_score"].std(),
                    },
                    "optimized": {
                        "mean": optimized_df["risk_score"].mean(),
                        "max": optimized_df["risk_score"].max(),
                        "std": optimized_df["risk_score"].std(),
                    }
                },
                "parameters": {
                    "original": snow_params,
                    "optimized": adjusted_params
                }
            }
        except Exception as e:
            self.logger.error(f"Feil under evaluering av parametereffekt: {str(e)}")
            return None

    def _analyze_parameter_changes(
        self, parameter_changes: dict[str, dict]
    ) -> list[dict[str, str]]:
        """
        Analyserer parameterendringer og gir anbefalinger
        """
        recommendations = []

        for param, changes in parameter_changes.items():
            change_pct = changes["change_pct"]

            if abs(change_pct) > 20:
                recommendations.append(
                    {
                        "parameter": param,
                        "change": f"{change_pct:.1f}%",
                        "impact": "høy",
                        "recommendation": (
                            f"Betydelig endring i {param}. "
                            f"Vurder grundig testing før implementering."
                        ),
                    }
                )
            elif abs(change_pct) > 10:
                recommendations.append(
                    {
                        "parameter": param,
                        "change": f"{change_pct:.1f}%",
                        "impact": "moderat",
                        "recommendation": (
                            f"Moderat endring i {param}. " f"Overvåk effekten nøye."
                        ),
                    }
                )

        return recommendations

    def verify_model_parameters(
        self,
        model_path: str = "models/snow_drift_model.joblib",
        expected_params: dict[str, float] = None,
    ) -> dict[str, Any]:
        """
        Verifiserer at modellen bruker forventede parametre
        """
        self.logger.info(f"Starter verifisering av modellparametre fra {model_path}")
        try:
            # Last modellen
            model = joblib.load(model_path)

            # Hent faktiske parametre
            actual_params = getattr(model, "get_params", lambda: {})()

            # Sammenlign med forventede parametre hvis gitt
            if expected_params:
                matches = {}
                discrepancies = {}

                for param, expected_value in expected_params.items():
                    actual_value = actual_params.get(param)
                    if actual_value == expected_value:
                        matches[param] = actual_value
                    else:
                        discrepancies[param] = {
                            "expected": expected_value,
                            "actual": actual_value,
                        }

                verification_result = {
                    "status": "ok" if not discrepancies else "mismatch",
                    "matches": matches,
                    "discrepancies": discrepancies,
                    "model_path": model_path,
                    "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            else:
                verification_result = {
                    "status": "info",
                    "current_params": actual_params,
                    "model_path": model_path,
                    "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                }

            if discrepancies:
                self.logger.warning(f"Fant {len(discrepancies)} parameteravvik")
                for param, values in discrepancies.items():
                    self.logger.warning(
                        f"Parameter {param}: forventet {values['expected']}, faktisk {values['actual']}"
                    )
            else:
                self.logger.info("Alle parametre stemmer med forventede verdier")

            return verification_result

        except Exception as e:
            self.logger.exception("Feil under verifisering av modellparametre")
            return {
                "status": "error",
                "error": str(e),
                "model_path": model_path,
                "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

    def _get_error_context(self) -> dict[str, Any]:
        """Samler kontekstuell informasjon for feilsøking"""
        return {
            "metrics_state": bool(self.metrics),
            "timestamp": pd.Timestamp.now().isoformat(),
            "memory_usage": self._get_memory_usage(),
        }

    def _get_memory_usage(self) -> dict[str, float]:
        """Henter minnebruk for debugging"""
        process = psutil.Process()
        return {
            "memory_percent": process.memory_percent(),
            "memory_mb": process.memory_info().rss / 1024 / 1024,
        }

    def evaluate_parameters(
        self,
        actual_params: Dict[str, float],
        expected_params: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluerer parametere.

        Args:
            actual_params: Faktiske parametere
            expected_params: Forventede parametere (optional)

        Returns:
            Dictionary med evalueringsresultater
        """
        if expected_params is None:
            expected_params = {}

        results: Dict[str, Dict[str, Any]] = {}
        for param, actual_value in actual_params.items():
            results[param] = {
                "actual": actual_value,
                "expected": expected_params.get(param, actual_value),
                "difference": abs(
                    actual_value - expected_params.get(param, actual_value)
                ),
            }

        return {
            "discrepancies": results,
            "total_difference": sum(r["difference"] for r in results.values()),
        }
