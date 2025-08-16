#!/usr/bin/env python3
"""
ML-basert grenseverdi-optimalisering for snøfokk-deteksjon.
Bruker maskinlæring til å automatisk fastsette optimale terskelverdier
og identifisere kritiske værkombinasjoner.
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Legg til prosjektets rotmappe i Python-stien
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Maskinlæring biblioteker
from sklearn.ensemble import RandomForestClassifier

# For threshold optimization
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier, export_text

# Logging oppsett
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/ml_threshold_optimization.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MLThresholdOptimizer:
    """ML-basert optimalisering av grenseverdier for snøfokk-deteksjon."""

    def __init__(self):
        self.models = {}
        self.thresholds = {}
        self.rules = {}
        self.feature_boundaries = {}

    def load_weather_data(self) -> pd.DataFrame:
        """Laster inn værdata fra cache."""
        try:
            # Prøv å laste fra cache først
            cache_files = [
                "data/cache/weather_data_2023-11-01_2024-04-30.pkl",
                "data/cache/weather_data_gullingen_2018_2024.pkl",
                "data/cache/weather_data_2018_2024.pkl",
                "data/cache/weather_gullingen.pkl"
            ]

            for cache_file in cache_files:
                if os.path.exists(cache_file):
                    logger.info(f"Laster værdata fra {cache_file}")
                    df = pd.read_pickle(cache_file)
                    logger.info(f"Lastet {len(df)} værobservasjoner")
                    return df

            raise FileNotFoundError("Ingen cached værdata funnet")

        except Exception as e:
            logger.error(f"Feil ved lasting av værdata: {e}")
            return pd.DataFrame()

    def create_enhanced_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Lager utvidede features inkludert vindkast og temperatur-features."""
        logger.info("Lager utvidede weather features...")

        df_enhanced = df.copy()

        # Håndter datetime-kolonne
        time_col = None
        for col in ['referenceTime', 'time', 'timestamp']:
            if col in df.columns:
                time_col = col
                break

        # Grunnleggende vindkast-features
        if 'wind_speed' in df.columns:
            df_enhanced['wind_chill'] = self._calculate_wind_chill(
                df['air_temperature'], df['wind_speed']
            )

        # Temperatur-features
        if 'air_temperature' in df.columns:
            df_enhanced['frost_risk'] = (df['air_temperature'] <= 0).astype(int)
            df_enhanced['near_freezing'] = (
                (df['air_temperature'] >= -2) & (df['air_temperature'] <= 2)
            ).astype(int)

        # Time-based features
        if time_col and time_col in df.columns:
            time_series = pd.to_datetime(df[time_col])
            df_enhanced['hour'] = time_series.dt.hour
            df_enhanced['month'] = time_series.dt.month
            df_enhanced['is_winter'] = df_enhanced['month'].isin([11, 12, 1, 2, 3]).astype(int)
            # Dropp den originale datetime-kolonnen for ML
            df_enhanced = df_enhanced.drop(columns=[time_col])

        # Snøfokk-risiko target (dummy for demonstrasjon)
        # I praksis bør dette komme fra observasjoner eller ekspertklassifisering
        df_enhanced['snowdrift_risk'] = self._calculate_snowdrift_risk(df_enhanced)

        logger.info(f"Opprettet {len(df_enhanced.columns)} features")
        return df_enhanced

    def _calculate_wind_chill(self, temp: pd.Series, wind: pd.Series) -> pd.Series:
        """Beregner vindkjøling."""
        # Wind chill formula (kun for temp <= 10°C og wind >= 4.8 km/h)
        mask = (temp <= 10) & (wind >= 1.34)  # 4.8 km/h = 1.34 m/s

        wind_chill = temp.copy()
        wind_chill[mask] = (
            13.12 + 0.6215 * temp[mask] -
            11.37 * (wind[mask] * 3.6) ** 0.16 +
            0.3965 * temp[mask] * (wind[mask] * 3.6) ** 0.16
        )

        return wind_chill

    def _calculate_snowdrift_risk(self, df: pd.DataFrame) -> pd.Series:
        """
        Beregner snøfokk-risiko basert på heuristikker.
        Denne funksjonen bør erstattes med faktiske observasjoner.
        """
        risk = pd.Series(0, index=df.index)

        # Høy risiko hvis:
        # - Vindstyrke > 7 m/s OG temperatur < 0°C OG snø på bakken
        high_wind = df.get('wind_speed', 0) > 7
        freezing = df.get('air_temperature', 10) < 0
        snow_present = df.get('surface_snow_thickness', 0) > 0.01

        # Medium risiko hvis noen av kriteriene er oppfylt
        medium_conditions = (
            (df.get('wind_speed', 0) > 5) |
            (df.get('air_temperature', 10) < -5) |
            (df.get('wind_speed', 0) > 4) & (df.get('surface_snow_thickness', 0) > 0.05)
        )

        # Høy risiko
        risk[high_wind & freezing & snow_present] = 2

        # Medium risiko
        risk[medium_conditions & ~(high_wind & freezing & snow_present)] = 1

        return risk

    def optimize_feature_thresholds(self, df: pd.DataFrame, target_col: str = 'snowdrift_risk') -> dict:
        """Optimaliserer terskelverdier for hver feature ved hjelp av ML."""
        logger.info("Optimaliserer feature-terskelverdier...")

        # Forbered data - fjern non-numeric og datetime kolonner
        excluded_cols = [target_col, 'time', 'referenceTime', 'timestamp']
        feature_cols = [col for col in df.columns if col not in excluded_cols]

        # Sikre at alle features er numeriske
        X = df[feature_cols].select_dtypes(include=[np.number]).fillna(0)
        y = df[target_col]

        logger.info(f"Bruker {len(X.columns)} numeriske features: {list(X.columns)}")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # Tren Decision Tree for regel-ekstrahering
        dt_model = DecisionTreeClassifier(
            max_depth=10,
            min_samples_split=50,
            min_samples_leaf=20,
            random_state=42
        )
        dt_model.fit(X_train, y_train)

        # Ekstrahér regler fra decision tree
        tree_rules = export_text(dt_model, feature_names=list(X.columns))

        # Analyser decision boundaries for hver feature
        thresholds = {}
        for feature in X.columns:
            feature_thresholds = self._extract_feature_thresholds(
                dt_model, X_train, y_train, feature, list(X.columns)
            )
            thresholds[feature] = feature_thresholds

        # Evaluer modell
        train_score = dt_model.score(X_train, y_train)
        test_score = dt_model.score(X_test, y_test)

        results = {
            'model_performance': {
                'train_accuracy': train_score,
                'test_accuracy': test_score,
                'feature_count': len(X.columns)
            },
            'feature_thresholds': thresholds,
            'decision_rules': tree_rules,
            'feature_importance': dict(zip(X.columns, dt_model.feature_importances_, strict=False))
        }

        # Lagre modell
        self.models['decision_tree'] = dt_model
        self.thresholds = thresholds

        logger.info(f"Threshold optimization fullført. Test accuracy: {test_score:.3f}")
        return results

    def _extract_feature_thresholds(self, model, X, y, feature_name: str, feature_names: list[str]) -> dict:
        """Ekstraherer optimale terskelverdier for en spesifikk feature."""
        feature_idx = feature_names.index(feature_name)

        # Hent feature-verdier
        feature_values = X.iloc[:, feature_idx]

        # Analyser decision tree nodes
        tree = model.tree_
        thresholds_found = []

        def traverse_tree(node_id, depth=0):
            if tree.feature[node_id] == feature_idx:
                threshold = tree.threshold[node_id]
                thresholds_found.append(threshold)

            # Fortsett til venstre og høyre barn
            if tree.children_left[node_id] != -1:
                traverse_tree(tree.children_left[node_id], depth + 1)
            if tree.children_right[node_id] != -1:
                traverse_tree(tree.children_right[node_id], depth + 1)

        traverse_tree(0)

        # Analyser feature-distribusjonen
        low_risk_values = feature_values[y == 0]
        medium_risk_values = feature_values[y == 1]
        high_risk_values = feature_values[y == 2] if (y == 2).any() else pd.Series()

        return {
            'decision_tree_thresholds': sorted(set(thresholds_found)),
            'statistical_thresholds': {
                'low_risk_median': low_risk_values.median() if len(low_risk_values) > 0 else None,
                'medium_risk_median': medium_risk_values.median() if len(medium_risk_values) > 0 else None,
                'high_risk_median': high_risk_values.median() if len(high_risk_values) > 0 else None,
                'overall_25th': feature_values.quantile(0.25),
                'overall_75th': feature_values.quantile(0.75),
                'overall_90th': feature_values.quantile(0.90)
            },
            'range': {
                'min': feature_values.min(),
                'max': feature_values.max(),
                'mean': feature_values.mean(),
                'std': feature_values.std()
            }
        }

    def extract_weather_combination_rules(self, df: pd.DataFrame, target_col: str = 'snowdrift_risk') -> dict:
        """Ekstraherer regler for værkombinationer som fører til snøfokk."""
        logger.info("Ekstraherer værkombinasjon-regler...")

        # Forbered data - fjern non-numeric og datetime kolonner
        excluded_cols = [target_col, 'time', 'referenceTime', 'timestamp']
        feature_cols = [col for col in df.columns if col not in excluded_cols]

        # Sikre at alle features er numeriske
        X = df[feature_cols].select_dtypes(include=[np.number]).fillna(0)
        y = df[target_col]

        # Tren Random Forest for feature interactions
        rf_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=15,
            min_samples_split=20,
            min_samples_leaf=10,
            random_state=42
        )
        rf_model.fit(X, y)

        # Analyser feature interactions
        feature_interactions = self._analyze_feature_interactions(rf_model, X, y, list(X.columns))

        # Generer kombinasjonsregler
        combination_rules = self._generate_combination_rules(df, target_col)

        # Valider regler mot data
        rule_validation = self._validate_rules(df, combination_rules, target_col)

        results = {
            'random_forest_performance': {
                'train_accuracy': rf_model.score(X, y),
                'feature_importance': dict(zip(X.columns, rf_model.feature_importances_, strict=False))
            },
            'feature_interactions': feature_interactions,
            'combination_rules': combination_rules,
            'rule_validation': rule_validation
        }

        self.models['random_forest'] = rf_model
        self.rules = combination_rules

        return results

    def _analyze_feature_interactions(self, model, X, y, feature_names: list[str]) -> dict:
        """Analyserer feature interactions i Random Forest."""
        # Enkel feature interaction analyse basert på co-occurrence i splits
        interactions = {}

        # Analyser hvor ofte features dukker opp sammen i trees
        for tree in model.estimators_:
            tree_features = []
            def get_tree_features(node_id):
                if tree.tree_.feature[node_id] != -2:  # Ikke leaf node
                    tree_features.append(feature_names[tree.tree_.feature[node_id]])
                    if tree.tree_.children_left[node_id] != -1:
                        get_tree_features(tree.tree_.children_left[node_id])
                    if tree.tree_.children_right[node_id] != -1:
                        get_tree_features(tree.tree_.children_right[node_id])

            get_tree_features(0)

            # Telle co-occurrences
            for i, feat1 in enumerate(tree_features):
                for feat2 in tree_features[i+1:]:
                    pair = tuple(sorted([feat1, feat2]))
                    interactions[pair] = interactions.get(pair, 0) + 1

        # Sorter etter hyppighet
        sorted_interactions = sorted(interactions.items(), key=lambda x: x[1], reverse=True)

        return {
            'top_interactions': sorted_interactions[:20],
            'total_interactions_found': len(interactions)
        }

    def _generate_combination_rules(self, df: pd.DataFrame, target_col: str) -> dict:
        """Genererer eksplisitte kombinasjonsregler basert på data-analyse."""
        rules = {}

        # Analyser høy-risiko situasjoner
        high_risk_data = df[df[target_col] == 2] if (df[target_col] == 2).any() else pd.DataFrame()
        medium_risk_data = df[df[target_col] == 1]
        low_risk_data = df[df[target_col] == 0]

        if not high_risk_data.empty:
            # Regel 1: Høy vindstyrke + frost + snø
            rules['high_wind_frost_snow'] = {
                'conditions': {
                    'wind_speed': f"> {high_risk_data['wind_speed'].quantile(0.25):.1f} m/s",
                    'air_temperature': f"< {high_risk_data['air_temperature'].quantile(0.75):.1f}°C",
                    'surface_snow_thickness': f"> {high_risk_data['surface_snow_thickness'].quantile(0.25):.3f} m"
                },
                'risk_level': 'HIGH',
                'frequency': len(high_risk_data),
                'confidence': self._calculate_rule_confidence(df, {
                    'wind_speed': ('>', high_risk_data['wind_speed'].quantile(0.25)),
                    'air_temperature': ('<', high_risk_data['air_temperature'].quantile(0.75)),
                    'surface_snow_thickness': ('>', high_risk_data['surface_snow_thickness'].quantile(0.25))
                }, target_col, 2)
            }

        # Regel 2: Medium vindstyrke kombinasjoner
        if not medium_risk_data.empty:
            rules['medium_wind_combinations'] = {
                'conditions': {
                    'wind_speed': f"{medium_risk_data['wind_speed'].quantile(0.25):.1f} - {medium_risk_data['wind_speed'].quantile(0.75):.1f} m/s",
                    'air_temperature': f"< {medium_risk_data['air_temperature'].quantile(0.75):.1f}°C"
                },
                'risk_level': 'MEDIUM',
                'frequency': len(medium_risk_data),
                'confidence': self._calculate_rule_confidence(df, {
                    'wind_speed': ('between', medium_risk_data['wind_speed'].quantile(0.25), medium_risk_data['wind_speed'].quantile(0.75)),
                    'air_temperature': ('<', medium_risk_data['air_temperature'].quantile(0.75))
                }, target_col, 1)
            }

        # Regel 3: Vindkjøling-baserte regler
        if 'wind_chill' in df.columns:
            extreme_chill = df[df['wind_chill'] < df['wind_chill'].quantile(0.10)]
            if not extreme_chill.empty:
                rules['extreme_wind_chill'] = {
                    'conditions': {
                        'wind_chill': f"< {df['wind_chill'].quantile(0.10):.1f}°C"
                    },
                    'risk_level': 'HIGH',
                    'frequency': len(extreme_chill),
                    'confidence': self._calculate_rule_confidence(df, {
                        'wind_chill': ('<', df['wind_chill'].quantile(0.10))
                    }, target_col, 2)
                }

        return rules

    def _calculate_rule_confidence(self, df: pd.DataFrame, conditions: dict, target_col: str, target_value: int) -> float:
        """Beregner confidence for en regel."""
        mask = pd.Series(True, index=df.index)

        for feature, condition in conditions.items():
            if feature not in df.columns:
                continue

            if isinstance(condition, tuple):
                if condition[0] == '>':
                    mask &= df[feature] > condition[1]
                elif condition[0] == '<':
                    mask &= df[feature] < condition[1]
                elif condition[0] == 'between':
                    mask &= (df[feature] >= condition[1]) & (df[feature] <= condition[2])

        matching_rows = df[mask]
        if len(matching_rows) == 0:
            return 0.0

        correct_predictions = len(matching_rows[matching_rows[target_col] == target_value])
        return correct_predictions / len(matching_rows)

    def _validate_rules(self, df: pd.DataFrame, rules: dict, target_col: str) -> dict:
        """Validerer kombinasjonsregler mot data."""
        validation = {}

        for rule_name, rule_info in rules.items():
            # Test regelen mot datasettet
            total_matches = 0
            correct_matches = 0

            # Her ville vi implementere regelvalidering
            # For nå returnerer vi grunnleggende statistikk
            validation[rule_name] = {
                'total_applicable_cases': rule_info.get('frequency', 0),
                'confidence': rule_info.get('confidence', 0.0),
                'coverage': rule_info.get('frequency', 0) / len(df) if len(df) > 0 else 0.0
            }

        return validation

    def run_threshold_optimization(self) -> dict:
        """Kjører komplett threshold optimization analyse."""
        logger.info("Starter ML-basert threshold optimization...")

        try:
            # 1. Last værdata
            df = self.load_weather_data()
            if df.empty:
                raise ValueError("Ingen værdata tilgjengelig")

            # 2. Lag features
            df_enhanced = self.create_enhanced_features(df)

            # 3. Optimaliser terskelverdier
            threshold_results = self.optimize_feature_thresholds(df_enhanced)

            # 4. Ekstrahér kombinasjonsregler
            combination_results = self.extract_weather_combination_rules(df_enhanced)

            # 5. Generer finale anbefalinger
            recommendations = self._generate_threshold_recommendations(
                threshold_results, combination_results
            )

            # Kombiner alle resultater
            final_results = {
                'timestamp': datetime.now().isoformat(),
                'data_summary': {
                    'total_observations': len(df_enhanced),
                    'features_analyzed': len([col for col in df_enhanced.columns if col not in ['snowdrift_risk', 'time']]),
                    'risk_distribution': df_enhanced['snowdrift_risk'].value_counts().to_dict()
                },
                'threshold_optimization': threshold_results,
                'combination_analysis': combination_results,
                'recommendations': recommendations,
                'status': 'completed'
            }

            # Lagre resultater
            output_file = "data/analyzed/ml_threshold_optimization_results.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(final_results, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"Threshold optimization fullført og lagret i {output_file}")
            return final_results

        except Exception as e:
            logger.error(f"Feil i threshold optimization: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def _generate_threshold_recommendations(self, threshold_results: dict, combination_results: dict) -> dict:
        """Genererer finale anbefalinger for grenseverdier og kombinasjoner."""

        recommendations = {
            'critical_thresholds': {},
            'warning_thresholds': {},
            'combination_rules': {},
            'implementation_guidance': {}
        }

        # Analyser feature importance for å prioritere
        feature_importance = threshold_results.get('feature_importance', {})
        sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)

        # Top 5 viktigste features
        top_features = sorted_features[:5]

        for feature, importance in top_features:
            if feature in threshold_results.get('feature_thresholds', {}):
                thresholds = threshold_results['feature_thresholds'][feature]

                # Kritiske terskelverdier (90th percentile)
                critical_threshold = thresholds['statistical_thresholds'].get('overall_90th')
                if critical_threshold is not None:
                    recommendations['critical_thresholds'][feature] = {
                        'value': critical_threshold,
                        'importance': importance,
                        'description': f"Kritisk grense for {feature}"
                    }

                # Advarselsterskelverdier (75th percentile)
                warning_threshold = thresholds['statistical_thresholds'].get('overall_75th')
                if warning_threshold is not None:
                    recommendations['warning_thresholds'][feature] = {
                        'value': warning_threshold,
                        'importance': importance,
                        'description': f"Advarselsgrense for {feature}"
                    }

        # Kombinasjonsregler
        combo_rules = combination_results.get('combination_rules', {})
        for rule_name, rule_info in combo_rules.items():
            if rule_info.get('confidence', 0) > 0.7:  # Kun høy-confidence regler
                recommendations['combination_rules'][rule_name] = {
                    'conditions': rule_info['conditions'],
                    'risk_level': rule_info['risk_level'],
                    'confidence': rule_info['confidence']
                }

        # Implementeringsguide
        recommendations['implementation_guidance'] = {
            'monitoring_priority': [feat for feat, _ in top_features],
            'alert_system_config': {
                'use_combinations': True,
                'confidence_threshold': 0.7,
                'require_multiple_conditions': True
            },
            'validation_needed': [
                "Test mot historiske hendelser",
                "Kalibrere mot lokale forhold",
                "Justere for sesongvariasjoner"
            ]
        }

        return recommendations


def main():
    """Hovedfunksjon for threshold optimization."""

    print("🎯 ML-BASERT GRENSEVERDI-OPTIMALISERING")
    print("=" * 50)

    optimizer = MLThresholdOptimizer()

    # Kjør optimization
    results = optimizer.run_threshold_optimization()

    if results['status'] == 'completed':
        print("\n✅ THRESHOLD OPTIMIZATION FULLFØRT")

        # Vis datasammendrag
        data_summary = results.get('data_summary', {})
        print(f"📊 Analyserte observasjoner: {data_summary.get('total_observations', 0):,}")
        print(f"🎛️ Features analysert: {data_summary.get('features_analyzed', 0)}")

        # Vis nøkkelresultater
        recommendations = results.get('recommendations', {})

        print("\n🎯 KRITISKE GRENSEVERDIER:")
        for feature, info in recommendations.get('critical_thresholds', {}).items():
            print(f"  • {feature}: {info['value']:.2f} (viktighet: {info['importance']:.3f})")

        print("\n⚠️ ADVARSELSGRENSER:")
        for feature, info in recommendations.get('warning_thresholds', {}).items():
            print(f"  • {feature}: {info['value']:.2f} (viktighet: {info['importance']:.3f})")

        print("\n🔗 KOMBINASJONSREGLER:")
        for rule_name, rule_info in recommendations.get('combination_rules', {}).items():
            print(f"  • {rule_name}: {rule_info['risk_level']} risiko")
            print(f"    Confidence: {rule_info['confidence']:.1%}")

        print("\n💾 Resultater lagret i: data/analyzed/ml_threshold_optimization_results.json")

    else:
        print(f"\n❌ OPTIMIZATION FEILET: {results.get('error', 'Ukjent feil')}")


if __name__ == "__main__":
    main()
