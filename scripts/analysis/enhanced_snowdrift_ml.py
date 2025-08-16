#!/usr/bin/env python3
"""
Utvidet ML-basert snøfokk-detektor som inkluderer snødybde-endringer.
Kombinerer vindbaserte indikatorer med direkte observasjoner av snøtransport.
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
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

# Logging oppsett
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnhancedSnowDriftDetector:
    """
    Utvidet ML-basert snøfokk-detektor som inkluderer snødybde-endringer
    som en kritisk indikator på aktiv snøfokk.
    """

    def __init__(self):
        self.model = None
        self.feature_importance = {}
        self.thresholds = {}

    def load_weather_data(self) -> pd.DataFrame:
        """Laster værdata med alle tilgjengelige parametre."""
        try:
            cache_file = "data/cache/weather_data_2023-11-01_2024-04-30.pkl"
            if os.path.exists(cache_file):
                logger.info(f"Laster værdata fra {cache_file}")
                df = pd.read_pickle(cache_file)

                # Konverter datetime
                if 'referenceTime' in df.columns:
                    df['time'] = pd.to_datetime(df['referenceTime'])
                    df = df.drop(columns=['referenceTime'])

                # Sorter etter tid
                df = df.sort_values('time').reset_index(drop=True)

                logger.info(f"Lastet {len(df)} værobservasjoner")
                return df

        except Exception as e:
            logger.error(f"Feil ved lasting av værdata: {e}")
            return pd.DataFrame()

    def create_enhanced_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Lager utvidede features inkludert snødybde-endringer."""
        logger.info("Lager utvidede features med snødybde-analyse...")

        df_enhanced = df.copy()

        # === SNØDYBDE-FEATURES (NYE) ===

        # Beregn snødybde-endringer over forskjellige tidsperioder
        df_enhanced['snow_depth_change_10min'] = df['surface_snow_thickness'].diff()
        df_enhanced['snow_depth_change_1h'] = df['surface_snow_thickness'].diff(periods=6)  # 6 x 10min
        df_enhanced['snow_depth_change_3h'] = df['surface_snow_thickness'].diff(periods=18)  # 18 x 10min

        # Snødybde-volatilitet (indikator på aktiv transport)
        df_enhanced['snow_depth_volatility_1h'] = df['surface_snow_thickness'].rolling(window=6).std()
        df_enhanced['snow_depth_volatility_3h'] = df['surface_snow_thickness'].rolling(window=18).std()

        # Uforklarte snødybde-endringer (ikke fra nedbør)
        df_enhanced['unexplained_snow_increase'] = (
            (df_enhanced['snow_depth_change_1h'] > 0.010) &  # >10mm økning
            (df['sum(precipitation_amount PT1H)'] < 0.002)   # <2mm nedbør
        ).astype(int)

        df_enhanced['unexplained_snow_decrease'] = (
            (df_enhanced['snow_depth_change_1h'] < -0.010) &  # >10mm reduksjon
            (df['sum(precipitation_amount PT1H)'] < 0.002)    # <2mm nedbør
        ).astype(int)

        # Kraftige snødybde-endringer (direkte snøfokk-indikator)
        df_enhanced['rapid_snow_change'] = (
            abs(df_enhanced['snow_depth_change_1h']) > 0.015  # >15mm på 1h
        ).astype(int)

        # Snø-transportretning indikator
        df_enhanced['snow_transport_direction'] = np.where(
            df_enhanced['snow_depth_change_1h'] > 0.010, 1,  # Akkumulasjon
            np.where(df_enhanced['snow_depth_change_1h'] < -0.010, -1, 0)  # Erosjon
        )

        # === VIND-FEATURES (EKSISTERENDE) ===

        # Vindkjøling
        if 'wind_speed' in df.columns and 'air_temperature' in df.columns:
            df_enhanced['wind_chill'] = self._calculate_wind_chill(
                df['air_temperature'], df['wind_speed']
            )

        # === TEMPERATUR-FEATURES ===

        if 'air_temperature' in df.columns:
            df_enhanced['frost_risk'] = (df['air_temperature'] <= 0).astype(int)
            df_enhanced['near_freezing'] = (
                (df['air_temperature'] >= -2) & (df['air_temperature'] <= 2)
            ).astype(int)

        # === KOMBINERTE INDIKATORER ===

        # Aktiv snøfokk-indikator (kombinerer snødybde + vind)
        df_enhanced['active_snowdrift_indicator'] = (
            (df_enhanced['rapid_snow_change'] == 1) &
            (df.get('wind_speed', 0) > 3.0) &
            (df['sum(precipitation_amount PT1H)'] < 0.003)
        ).astype(int)

        # Snøtransport-risiko score
        df_enhanced['snow_transport_risk_score'] = (
            df_enhanced['unexplained_snow_increase'] +
            df_enhanced['unexplained_snow_decrease'] +
            df_enhanced['rapid_snow_change'] +
            (df_enhanced['snow_depth_volatility_1h'] > 0.020).astype(int)
        )

        # === TIME-BASED FEATURES ===

        if 'time' in df.columns:
            time_series = pd.to_datetime(df['time'])
            df_enhanced['hour'] = time_series.dt.hour
            df_enhanced['month'] = time_series.dt.month
            df_enhanced['is_winter'] = df_enhanced['month'].isin([11, 12, 1, 2, 3]).astype(int)

        # === TARGET VARIABLE (FORBEDRET) ===

        # Snøfokk-risiko basert på flere indikatorer
        df_enhanced['snowdrift_risk'] = self._calculate_enhanced_snowdrift_risk(df_enhanced)

        logger.info(f"Opprettet {len(df_enhanced.columns)} features (inkl. {8} snødybde-features)")
        return df_enhanced

    def _calculate_wind_chill(self, temp: pd.Series, wind: pd.Series) -> pd.Series:
        """Beregner vindkjøling."""
        mask = (temp <= 10) & (wind >= 1.34)  # 4.8 km/h = 1.34 m/s

        wind_chill = temp.copy()
        wind_chill[mask] = (
            13.12 + 0.6215 * temp[mask] -
            11.37 * (wind[mask] * 3.6) ** 0.16 +
            0.3965 * temp[mask] * (wind[mask] * 3.6) ** 0.16
        )

        return wind_chill

    def _calculate_enhanced_snowdrift_risk(self, df: pd.DataFrame) -> pd.Series:
        """
        Beregner snøfokk-risiko basert på kombinasjon av indikatorer.
        Fokuserer spesielt på snødybde-endringer som direktebevis.
        """
        risk = pd.Series(0, index=df.index)

        # HØYESTE RISIKO: Direkte observasjon av snøtransport
        direct_snowdrift = (
            (df.get('active_snowdrift_indicator', 0) == 1) |
            (df.get('snow_transport_risk_score', 0) >= 3)
        )
        risk[direct_snowdrift] = 3  # EKSTREM risiko

        # HØY RISIKO: Kraftige værforhold + noe snøaktivitet
        high_risk_conditions = (
            (df.get('wind_speed', 0) > 8) &
            (df.get('air_temperature', 10) < -1) &
            (df.get('surface_snow_thickness', 0) > 0.02) &
            (df.get('snow_transport_risk_score', 0) >= 1)
        )
        risk[high_risk_conditions & (risk == 0)] = 2  # HØY risiko

        # MEDIUM RISIKO: Moderate forhold med noen indikatorer
        medium_risk_conditions = (
            (df.get('wind_speed', 0) > 4) &
            (df.get('air_temperature', 10) < 0) &
            (
                (df.get('unexplained_snow_increase', 0) == 1) |
                (df.get('unexplained_snow_decrease', 0) == 1) |
                (df.get('wind_chill', 10) < 0)
            )
        )
        risk[medium_risk_conditions & (risk == 0)] = 1  # MEDIUM risiko

        return risk

    def train_enhanced_model(self, df: pd.DataFrame) -> dict:
        """Trener utvidet ML-modell med snødybde-features."""
        logger.info("Trener utvidet ML-modell med snødybde-features...")

        # Forbered features
        excluded_cols = ['snowdrift_risk', 'time']
        feature_cols = [col for col in df.columns if col not in excluded_cols]

        # Sikre numeriske data
        X = df[feature_cols].select_dtypes(include=[np.number]).fillna(0)
        y = df['snowdrift_risk']

        logger.info(f"Bruker {len(X.columns)} features: {list(X.columns)}")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # Tren Random Forest modell
        self.model = RandomForestClassifier(
            n_estimators=200,
            max_depth=20,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42,
            class_weight='balanced'  # Håndter ubalanserte klasser
        )

        self.model.fit(X_train, y_train)

        # Evaluer modell
        train_score = self.model.score(X_train, y_train)
        test_score = self.model.score(X_test, y_test)

        # Feature importance
        self.feature_importance = dict(zip(X.columns, self.model.feature_importances_, strict=False))

        # Sorter features etter viktighet
        sorted_features = sorted(self.feature_importance.items(), key=lambda x: x[1], reverse=True)

        # Predictions for detailed analysis
        y_pred = self.model.predict(X_test)

        results = {
            'model_performance': {
                'train_accuracy': train_score,
                'test_accuracy': test_score,
                'feature_count': len(X.columns)
            },
            'feature_importance': self.feature_importance,
            'top_features': sorted_features[:15],
            'classification_report': classification_report(y_test, y_pred, output_dict=True),
            'risk_distribution': y.value_counts().to_dict()
        }

        logger.info(f"Modell trent. Test accuracy: {test_score:.3f}")
        return results

    def analyze_snow_depth_impact(self, results: dict) -> dict:
        """Analyserer påvirkningen av snødybde-features på modellen."""

        # Identifiser snødybde-relaterte features
        snow_features = [feature for feature in self.feature_importance.keys()
                        if 'snow' in feature.lower()]

        # Beregn samlet viktighet av snødybde-features
        snow_importance_total = sum(self.feature_importance[f] for f in snow_features)

        # Sammenlign med andre feature-kategorier
        wind_features = [f for f in self.feature_importance.keys()
                        if 'wind' in f.lower() or 'chill' in f.lower()]
        wind_importance_total = sum(self.feature_importance[f] for f in wind_features)

        temp_features = [f for f in self.feature_importance.keys()
                        if 'temperature' in f.lower() or 'frost' in f.lower() or 'freezing' in f.lower()]
        temp_importance_total = sum(self.feature_importance[f] for f in temp_features)

        analysis = {
            'snow_features': {
                'features': snow_features,
                'total_importance': snow_importance_total,
                'individual_importance': {f: self.feature_importance[f] for f in snow_features}
            },
            'wind_features': {
                'total_importance': wind_importance_total,
                'feature_count': len(wind_features)
            },
            'temperature_features': {
                'total_importance': temp_importance_total,
                'feature_count': len(temp_features)
            },
            'feature_category_ranking': [
                ('Snow depth features', snow_importance_total),
                ('Wind features', wind_importance_total),
                ('Temperature features', temp_importance_total)
            ]
        }

        # Sorter kategorier etter viktighet
        analysis['feature_category_ranking'].sort(key=lambda x: x[1], reverse=True)

        return analysis

    def run_enhanced_analysis(self) -> dict:
        """Kjører komplett analyse med snødybde-features."""
        logger.info("Starter utvidet snøfokk-analyse med snødybde-features...")

        try:
            # 1. Last data
            df = self.load_weather_data()
            if df.empty:
                raise ValueError("Ingen værdata tilgjengelig")

            # 2. Lag utvidede features
            df_enhanced = self.create_enhanced_features(df)

            # 3. Tren ML-modell
            ml_results = self.train_enhanced_model(df_enhanced)

            # 4. Analyser snødybde-påvirkning
            snow_analysis = self.analyze_snow_depth_impact(ml_results)

            # 5. Kombiner resultater
            final_results = {
                'timestamp': datetime.now().isoformat(),
                'data_summary': {
                    'total_observations': len(df_enhanced),
                    'features_created': len(df_enhanced.columns),
                    'snow_depth_features': len(snow_analysis['snow_features']['features'])
                },
                'ml_results': ml_results,
                'snow_depth_analysis': snow_analysis,
                'status': 'completed'
            }

            # Lagre resultater
            output_file = "data/analyzed/enhanced_snowdrift_ml_results.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(final_results, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"Utvidet analyse fullført og lagret i {output_file}")
            return final_results

        except Exception as e:
            logger.error(f"Feil i utvidet analyse: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


def main():
    """Hovedfunksjon for utvidet snøfokk-analyse."""

    print("🌨️ UTVIDET ML-ANALYSE MED SNØDYBDE-FEATURES")
    print("=" * 55)

    detector = EnhancedSnowDriftDetector()

    # Kjør analyse
    results = detector.run_enhanced_analysis()

    if results['status'] == 'completed':
        print("\n✅ UTVIDET ANALYSE FULLFØRT")

        # Vis datasammendrag
        data_summary = results.get('data_summary', {})
        print(f"📊 Analyserte observasjoner: {data_summary.get('total_observations', 0):,}")
        print(f"🎛️ Totale features: {data_summary.get('features_created', 0)}")
        print(f"❄️ Snødybde-features: {data_summary.get('snow_depth_features', 0)}")

        # Vis ML-resultater
        ml_results = results.get('ml_results', {})
        perf = ml_results.get('model_performance', {})
        print(f"🤖 Modell-nøyaktighet: {perf.get('test_accuracy', 0)*100:.2f}%")

        # Vis top features
        top_features = ml_results.get('top_features', [])[:10]
        print("\n🏆 TOP 10 VIKTIGSTE FEATURES:")
        for i, (feature, importance) in enumerate(top_features, 1):
            print(f"  {i:2d}. {feature:<25} {importance:.3f}")

        # Vis snødybde-analyse
        snow_analysis = results.get('snow_depth_analysis', {})
        print("\n❄️ SNØDYBDE-FEATURES PÅVIRKNING:")
        snow_total = snow_analysis.get('snow_features', {}).get('total_importance', 0)
        print(f"   • Total viktighet: {snow_total:.3f} ({snow_total*100:.1f}%)")

        # Vis kategori-ranking
        ranking = snow_analysis.get('feature_category_ranking', [])
        print("\n📊 FEATURE-KATEGORI RANKING:")
        for i, (category, importance) in enumerate(ranking, 1):
            print(f"  {i}. {category}: {importance:.3f} ({importance*100:.1f}%)")

        print("\n💾 Resultater lagret i: data/analyzed/enhanced_snowdrift_ml_results.json")

    else:
        print(f"\n❌ ANALYSE FEILET: {results.get('error', 'Ukjent feil')}")


if __name__ == "__main__":
    main()
