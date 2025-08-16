#!/usr/bin/env python3
"""
ML-basert klassifikator for slush og glatt vei kriterier.
Inkluderer innsikten at nysnø fungerer som naturlig strøing.
"""

import json
import os
from datetime import datetime

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler


class SlushSlipperyMLClassifier:
    """ML-klassifikator for slush og glatt vei basert på værforhold og vedlikeholdsdata."""

    def __init__(self):
        self.slush_model = None
        self.slippery_model = None
        self.scaler = StandardScaler()
        self.feature_importance = {}

        # Viktige innsikter fra domain ekspertise
        self.domain_rules = {
            'fresh_snow_protection': True,  # Nysnø beskytter mot glatthet
            'salt_only_effective_on_ice': True,  # Strøing kun effektivt på is
            'slush_temperature_range': (-1, 4),  # Ideelt temperaturområde for slush
            'fresh_snow_threshold_mm': 2.0  # Minimum nysnø for beskyttende effekt
        }

    def load_training_data(self, maintenance_file: str) -> pd.DataFrame:
        """Last treningsdata fra vedlikeholdsanalyse."""
        print("Laster treningsdata...")

        # Last korrelerte data
        base_name = maintenance_file.replace('.csv', '')
        correlation_file = f"{base_name}.csv"

        if os.path.exists(correlation_file):
            df = pd.read_csv(correlation_file)
            print(f"Lastet {len(df)} treningsobservasjoner")
            return df
        else:
            print(f"Finner ikke korrelasjonsdata: {correlation_file}")
            return pd.DataFrame()

    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Lag feature engineering med fokus på slush og glatt vei."""
        print("Utfører feature engineering...")

        features_df = df.copy()

        # Grunnleggende værfeatures
        features_df['temp_range'] = features_df['temp_max'] - features_df['temp_min']
        features_df['around_freezing'] = (
            (features_df['temp_min'] <= 2) & (features_df['temp_max'] >= -2)
        ).astype(int)

        # Slush-relaterte features
        features_df['slush_temp_range'] = (
            (features_df['temp_mean'] >= self.domain_rules['slush_temperature_range'][0]) &
            (features_df['temp_mean'] <= self.domain_rules['slush_temperature_range'][1])
        ).astype(int)

        features_df['precip_with_mild_temp'] = (
            features_df['precip_total'] * features_df['slush_temp_range']
        )

        # Nysnø-beskyttelse (VIKTIG INNSIKT)
        features_df['recent_snowfall'] = (
            (features_df['temp_mean'] < 1) &
            (features_df['precip_total'] > self.domain_rules['fresh_snow_threshold_mm'])
        ).astype(int)

        # Freeze-thaw sykluser (farlig for isdannelse)
        features_df['freeze_thaw_cycle'] = (
            (features_df['temp_max'] > 2) & (features_df['temp_min'] < -1)
        ).astype(int)

        # Regn på snø (kritisk for glatthet)
        features_df['rain_on_snow_risk'] = (
            (features_df['temp_mean'] > 0) &
            (features_df['temp_mean'] < 3) &
            (features_df['precip_total'] > 1) &
            (features_df['snow_depth_cm'] > 0)
        ).astype(int)

        # Vindeffekt (øker avkjøling og isdannelse)
        features_df['wind_chill_factor'] = np.where(
            features_df['wind_max'] > 5,
            features_df['temp_mean'] - (features_df['wind_max'] * 0.2),
            features_df['temp_mean']
        )

        # Vedlikehold-baserte labels (fra observerte episoder)
        features_df['needs_salting'] = features_df['likely_maintenance_purpose'].str.contains(
            'strøing|slush|glatt|regn_på_snø|tining_frysing', na=False, case=False
        ).astype(int)

        features_df['is_slush_episode'] = features_df['likely_maintenance_purpose'].str.contains(
            'slush', na=False, case=False
        ).astype(int)

        return features_df

    def create_labels(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
        """Lag labels basert på observerte vedlikeholdsepisoder."""

        # SLUSH LABELS - basert på observerte episoder og værforhold
        slush_conditions = (
            (df['slush_temp_range'] == 1) &
            (df['precip_total'] > 0) &
            (df['recent_snowfall'] == 0)  # Nysnø beskytter mot slush
        )

        # Kombiner med observerte slush-episoder
        observed_slush = df['is_slush_episode'] == 1
        slush_labels = (slush_conditions | observed_slush).astype(int)

        # GLATT VEI LABELS - når strøing var nødvendig
        glatt_vei_conditions = (
            (df['freeze_thaw_cycle'] == 1) |
            (df['rain_on_snow_risk'] == 1) |
            ((df['temp_mean'] < 0) & (df['precip_total'] > 0) & (df['recent_snowfall'] == 0))
        )

        # Kombiner med observerte strøingsepisoder
        observed_salting = df['needs_salting'] == 1
        slippery_labels = (glatt_vei_conditions | observed_salting).astype(int)

        # VIKTIG: Reduser glatt vei-risiko når det er nysnø
        slippery_labels = np.where(
            df['recent_snowfall'] == 1,
            0,  # Nysnø beskytter mot glatthet
            slippery_labels
        )

        return df, pd.Series(slush_labels), pd.Series(slippery_labels)

    def train_models(self, features_df: pd.DataFrame, slush_labels: pd.Series, slippery_labels: pd.Series):
        """Tren ML-modeller for slush og glatt vei."""
        print("Trener ML-modeller...")

        # Velg feature-kolonner
        feature_cols = [
            'temp_mean', 'temp_min', 'temp_max', 'temp_range',
            'precip_total', 'precip_max_hourly',
            'wind_max', 'wind_chill_factor',
            'around_freezing', 'slush_temp_range', 'precip_with_mild_temp',
            'recent_snowfall', 'freeze_thaw_cycle', 'rain_on_snow_risk'
        ]

        # Fjern rader med NaN i features
        clean_mask = features_df[feature_cols].notna().all(axis=1)
        X = features_df[clean_mask][feature_cols]
        y_slush = slush_labels[clean_mask]
        y_slippery = slippery_labels[clean_mask]

        print(f"Trener på {len(X)} rene observasjoner")
        print(f"Slush-episoder: {y_slush.sum()}/{len(y_slush)} ({y_slush.mean()*100:.1f}%)")
        print(f"Glatt vei-episoder: {y_slippery.sum()}/{len(y_slippery)} ({y_slippery.mean()*100:.1f}%)")

        # Standardiser features
        X_scaled = self.scaler.fit_transform(X)

        # Tren slush-modell
        self.slush_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=10,
            random_state=42,
            class_weight='balanced'
        )

        # Tren glatt vei-modell
        self.slippery_model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42
        )

        # Cross-validation
        if y_slush.sum() > 5:  # Kun hvis vi har nok positive eksempler
            slush_scores = cross_val_score(self.slush_model, X_scaled, y_slush, cv=5)
            print(f"Slush-modell CV score: {slush_scores.mean():.3f} ± {slush_scores.std():.3f}")

        if y_slippery.sum() > 5:
            slippery_scores = cross_val_score(self.slippery_model, X_scaled, y_slippery, cv=5)
            print(f"Glatt vei-modell CV score: {slippery_scores.mean():.3f} ± {slippery_scores.std():.3f}")

        # Fit modellene
        self.slush_model.fit(X_scaled, y_slush)
        self.slippery_model.fit(X_scaled, y_slippery)

        # Feature importance
        self.feature_importance = {
            'slush': dict(zip(feature_cols, self.slush_model.feature_importances_, strict=False)),
            'slippery': dict(zip(feature_cols, self.slippery_model.feature_importances_, strict=False))
        }

        print("Modeller trent!")
        return X, y_slush, y_slippery

    def derive_criteria(self) -> dict:
        """Utled kriterier fra trente modeller."""
        print("Utleder kriterier fra ML-modeller...")

        criteria = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'based_on_ml': True,
                'domain_rules_applied': True
            },
            'domain_insights': {
                'fresh_snow_protection': "Nysnø (>2mm ved temp <1°C) fungerer som naturlig strøing",
                'salt_effectiveness': "Strøing kun effektivt på klink is, ikke på snø",
                'slush_formation': "Slush dannes i temperaturområde -1°C til 4°C med nedbør"
            }
        }

        # Slush-kriterier basert på feature importance
        slush_importance = self.feature_importance['slush']
        criteria['slush_criteria'] = {
            'primary_conditions': {
                'temperature_range': {
                    'min_temp': self.domain_rules['slush_temperature_range'][0],
                    'max_temp': self.domain_rules['slush_temperature_range'][1],
                    'importance': slush_importance.get('slush_temp_range', 0)
                },
                'precipitation_threshold': {
                    'min_mm': 1.0,
                    'importance': slush_importance.get('precip_total', 0)
                }
            },
            'protective_factors': {
                'fresh_snow': {
                    'threshold_mm': self.domain_rules['fresh_snow_threshold_mm'],
                    'temp_threshold': 1.0,
                    'protection_effect': "Reduserer slush-risiko betydelig"
                }
            }
        }

        # Glatt vei-kriterier
        slippery_importance = self.feature_importance['slippery']
        criteria['slippery_road_criteria'] = {
            'high_risk_scenarios': {
                'freeze_thaw_cycle': {
                    'condition': "Temp max > 2°C og temp min < -1°C",
                    'importance': slippery_importance.get('freeze_thaw_cycle', 0),
                    'mechanism': "Tining følgt av frysing skaper klink is"
                },
                'rain_on_snow': {
                    'condition': "Regn (>1mm) på eksisterende snø ved 0-3°C",
                    'importance': slippery_importance.get('rain_on_snow_risk', 0),
                    'mechanism': "Regn smelter snø og fryser til is"
                }
            },
            'protective_factors': {
                'fresh_snowfall': {
                    'threshold': f"{self.domain_rules['fresh_snow_threshold_mm']}mm ved temp <1°C",
                    'effect': "Naturlig strøing - reduserer behov for salt",
                    'importance': slippery_importance.get('recent_snowfall', 0)
                }
            },
            'salting_effectiveness': {
                'most_effective': "På klink is (temp -5°C til 2°C)",
                'not_effective': "På nysnø eller tykk snødekke",
                'timing': "Må skje før isdannelse for beste effekt"
            }
        }

        return criteria

    def generate_thresholds(self, X: pd.DataFrame, y_slush: pd.Series, y_slippery: pd.Series) -> dict:
        """Generer optimale terskelverdier basert på modellenes prediksjoner."""

        # Prediker sannsynligheter
        X_scaled = self.scaler.transform(X)
        slush_probs = self.slush_model.predict_proba(X_scaled)[:, 1]
        slippery_probs = self.slippery_model.predict_proba(X_scaled)[:, 1]

        # Finn optimale terskler (maksimerer F1-score)
        def find_optimal_threshold(y_true, y_probs):
            thresholds = np.arange(0.1, 0.9, 0.05)
            best_f1 = 0
            best_threshold = 0.5

            for threshold in thresholds:
                y_pred = (y_probs >= threshold).astype(int)
                if y_pred.sum() > 0 and y_true.sum() > 0:
                    from sklearn.metrics import f1_score
                    f1 = f1_score(y_true, y_pred)
                    if f1 > best_f1:
                        best_f1 = f1
                        best_threshold = threshold

            return best_threshold, best_f1

        slush_threshold, slush_f1 = find_optimal_threshold(y_slush, slush_probs)
        slippery_threshold, slippery_f1 = find_optimal_threshold(y_slippery, slippery_probs)

        thresholds = {
            'slush_model': {
                'probability_threshold': slush_threshold,
                'f1_score': slush_f1,
                'interpretation': f"Slush-risiko når modell predikerer >{slush_threshold:.2f}"
            },
            'slippery_road_model': {
                'probability_threshold': slippery_threshold,
                'f1_score': slippery_f1,
                'interpretation': f"Glatt vei-risiko når modell predikerer >{slippery_threshold:.2f}"
            }
        }

        return thresholds

    def visualize_results(self, features_df: pd.DataFrame, output_dir: str = "data/analyzed"):
        """Lag visualiseringer av ML-resultatene."""
        print("Lager visualiseringer...")

        os.makedirs(output_dir, exist_ok=True)

        # Feature importance plot
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

        # Slush feature importance
        slush_features = list(self.feature_importance['slush'].keys())
        slush_importance = list(self.feature_importance['slush'].values())

        ax1.barh(slush_features, slush_importance)
        ax1.set_title('Slush-kriterier: Feature Importance')
        ax1.set_xlabel('Importance')

        # Slippery road feature importance
        slippery_features = list(self.feature_importance['slippery'].keys())
        slippery_importance = list(self.feature_importance['slippery'].values())

        ax2.barh(slippery_features, slippery_importance)
        ax2.set_title('Glatt vei-kriterier: Feature Importance')
        ax2.set_xlabel('Importance')

        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, f"ml_feature_importance_{datetime.now().strftime('%Y%m%d_%H%M')}.png"),
                   dpi=300, bbox_inches='tight')
        plt.close()

        # Scatter plot: temperatur vs nedbør med klassifikasjoner
        fig, ax = plt.subplots(figsize=(10, 8))

        # Plot alle punkter
        ax.scatter(features_df['temp_mean'], features_df['precip_total'],
                  alpha=0.5, c='lightgray', label='Andre episoder')

        # Highlight slush-episoder
        slush_episodes = features_df[features_df['is_slush_episode'] == 1]
        ax.scatter(slush_episodes['temp_mean'], slush_episodes['precip_total'],
                  c='orange', s=50, label='Slush-episoder')

        # Highlight strøingsepisoder
        salting_episodes = features_df[features_df['needs_salting'] == 1]
        ax.scatter(salting_episodes['temp_mean'], salting_episodes['precip_total'],
                  c='red', s=30, alpha=0.7, label='Strøingsepisoder')

        # Highlight nysnø-beskyttelse
        fresh_snow = features_df[features_df['recent_snowfall'] == 1]
        ax.scatter(fresh_snow['temp_mean'], fresh_snow['precip_total'],
                  c='blue', s=30, alpha=0.7, label='Nysnø (beskyttelse)')

        ax.set_xlabel('Temperatur (°C)')
        ax.set_ylabel('Nedbør (mm)')
        ax.set_title('ML-baserte kriterier for slush og glatt vei')
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.savefig(os.path.join(output_dir, f"ml_criteria_scatter_{datetime.now().strftime('%Y%m%d_%H%M')}.png"),
                   dpi=300, bbox_inches='tight')
        plt.close()

        print("Visualiseringer lagret")

    def save_models_and_criteria(self, criteria: dict, thresholds: dict, output_dir: str = "data/analyzed"):
        """Lagre modeller og kriterier."""
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M')

        # Lagre modeller
        model_file = os.path.join(output_dir, f"ml_slush_slippery_models_{timestamp}.joblib")
        joblib.dump({
            'slush_model': self.slush_model,
            'slippery_model': self.slippery_model,
            'scaler': self.scaler,
            'feature_importance': self.feature_importance
        }, model_file)

        # Lagre kriterier
        criteria_file = os.path.join(output_dir, f"ml_slush_slippery_criteria_{timestamp}.json")
        with open(criteria_file, 'w', encoding='utf-8') as f:
            json.dump(criteria, f, indent=2, ensure_ascii=False)

        # Lagre terskelverdier
        thresholds_file = os.path.join(output_dir, f"ml_optimal_thresholds_{timestamp}.json")
        with open(thresholds_file, 'w', encoding='utf-8') as f:
            json.dump(thresholds, f, indent=2, ensure_ascii=False)

        print(f"ML-modeller lagret: {model_file}")
        print(f"Kriterier lagret: {criteria_file}")
        print(f"Terskelverdier lagret: {thresholds_file}")

def main():
    """Hovedfunksjon for ML-basert kriterieanalyse."""
    print("=== ML-BASERT ANALYSE AV SLUSH OG GLATT VEI ===")
    print("Inkluderer innsikt: Nysnø fungerer som naturlig strøing\n")

    classifier = SlushSlipperyMLClassifier()

    # Last treningsdata fra vedlikeholdsanalyse
    maintenance_file = "data/analyzed/maintenance_weather_data_20250810_0839.csv"

    if not os.path.exists(maintenance_file):
        print(f"ERROR: Finner ikke treningsdata: {maintenance_file}")
        print("Kjør først: python scripts/analysis/correlate_maintenance_weather.py")
        return

    # Last og forbered data
    df = classifier.load_training_data(maintenance_file)

    if df.empty:
        print("Ingen treningsdata tilgjengelig")
        return

    # Feature engineering
    features_df = classifier.engineer_features(df)

    # Lag labels basert på observerte episoder
    features_df, slush_labels, slippery_labels = classifier.create_labels(features_df)

    # Tren modeller
    X, y_slush, y_slippery = classifier.train_models(features_df, slush_labels, slippery_labels)

    # Utled kriterier
    criteria = classifier.derive_criteria()

    # Generer optimale terskelverdier
    thresholds = classifier.generate_thresholds(X, y_slush, y_slippery)

    # Kombiner alt i en rapport
    final_criteria = {**criteria, 'optimal_thresholds': thresholds}

    # Lagre resultater
    classifier.save_models_and_criteria(final_criteria, thresholds)

    # Lag visualiseringer
    classifier.visualize_results(features_df)

    print("\n=== SAMMENDRAG ===")
    print(f"Analyserte {len(features_df)} vedlikeholdsepisoder")
    print(f"Identifiserte {slush_labels.sum()} slush-episoder")
    print(f"Identifiserte {slippery_labels.sum()} glatt vei-episoder")
    print("\nViktige innsikter implementert:")
    print("- Nysnø (>2mm ved <1°C) reduserer glatt vei-risiko")
    print("- Strøing kun effektivt på klink is")
    print("- Slush dannes ved -1°C til 4°C med nedbør")
    print("\nML-baserte kriterier generert!")

if __name__ == "__main__":
    main()
