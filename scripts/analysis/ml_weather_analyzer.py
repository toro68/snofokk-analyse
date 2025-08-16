#!/usr/bin/env python3
"""
Maskinlæringsbasert væranalyse for vinterværet 2018-2025.
Utvider eksisterende snøfokk-analyse med avanserte ML-teknikker.
"""

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
import joblib
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# Lokale imports
try:
    from data.src.snofokk.ml_utils import SnowDriftOptimizer
    from scripts.analysis.analyze_historical_data import analyze_data, fetch_weather_data
except ImportError as e:
    logging.warning(f"Import error: {e}")

# Logging oppsett
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/ml_weather_analysis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MLWeatherAnalyzer:
    """Maskinlæringsbasert analyse av vinterværet fra 2018 til nå."""

    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.weather_data = None
        self.features = [
            'air_temperature',
            'max(air_temperature PT1H)',      # Maks lufttemperatur per time - viktig for temperaturvariasjoner
            'min(air_temperature PT1H)',      # Min lufttemperatur per time - viktig for frost/is-forhold
            'wind_speed',
            'max(wind_speed_of_gust PT1H)',   # Vindkast - viktig for snøfokk
            'max(wind_speed PT1H)',           # Maks vindstyrke per time - alternativ vindkast-parameter
            'wind_from_direction',
            'surface_snow_thickness',
            'sum(precipitation_amount PT1H)',
            'relative_humidity'
        ]

        # Oprett nødvendige mapper
        os.makedirs('models', exist_ok=True)
        os.makedirs('data/analyzed', exist_ok=True)
        os.makedirs('logs', exist_ok=True)

    def load_historical_data(self, start_year: int = 2018, end_year: int = 2024) -> pd.DataFrame:
        """
        Laster historiske værdata fra spesifisert periode.
        
        Args:
            start_year: Startår for analyse
            end_year: Sluttår for analyse
            
        Returns:
            DataFrame med værdata
        """
        logger.info(f"Laster værdata fra {start_year} til {end_year}")

        all_data = []

        # Hent data for hver vintersesong
        for year in range(start_year, end_year + 1):
            try:
                # Vintersesong fra november til april
                winter_start = f"{year-1}-11-01"
                winter_end = f"{year}-04-30"

                logger.info(f"Henter data for vintersesong {year-1}-{year}")

                # Her ville vi normalt hente fra Frost API
                # For demonstrasjon bruker vi eksisterende cached data
                cached_file = f"data/cache/weather_data_{winter_start}_{winter_end}.pkl"

                if os.path.exists(cached_file):
                    season_data = pd.read_pickle(cached_file)
                    all_data.append(season_data)
                    logger.info(f"Lastet {len(season_data)} datapunkter for {year}")
                else:
                    logger.warning(f"Ingen cached data funnet for {year}")

            except Exception as e:
                logger.error(f"Feil ved lasting av data for {year}: {e}")
                continue

        if all_data:
            self.weather_data = pd.concat(all_data, ignore_index=True)
            logger.info(f"Totalt lastet {len(self.weather_data)} værdata-punkter")
            return self.weather_data
        else:
            logger.error("Ingen værdata lastet")
            return pd.DataFrame()

    def create_weather_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Lager utvidede features for maskinlæring.
        
        Args:
            df: Rå værdata
            
        Returns:
            DataFrame med features
        """
        logger.info("Lager features for maskinlæring")

        enhanced_df = df.copy()

        # Tidsbaserte features
        if 'time' in enhanced_df.columns:
            enhanced_df['hour'] = pd.to_datetime(enhanced_df['time']).dt.hour
            enhanced_df['day_of_year'] = pd.to_datetime(enhanced_df['time']).dt.dayofyear
            enhanced_df['month'] = pd.to_datetime(enhanced_df['time']).dt.month

        # Temperatur-features (utvidet)
        if 'max(air_temperature PT1H)' in enhanced_df.columns and 'min(air_temperature PT1H)' in enhanced_df.columns:
            # Temperaturvariasjoner innen timen
            enhanced_df['temp_range_1h'] = enhanced_df['max(air_temperature PT1H)'] - enhanced_df['min(air_temperature PT1H)']
            enhanced_df['temp_volatility'] = enhanced_df['temp_range_1h'].rolling(3).std().fillna(0)

            # Temperatur-trender
            enhanced_df['temp_rising'] = (enhanced_df['air_temperature'].diff() > 0).astype(int)
            enhanced_df['temp_falling'] = (enhanced_df['air_temperature'].diff() < 0).astype(int)

            # Frost-risiko indikatorer
            enhanced_df['near_freezing'] = (enhanced_df['air_temperature'].abs() <= 2.0).astype(int)
            enhanced_df['frost_risk'] = ((enhanced_df['min(air_temperature PT1H)'] <= 0) &
                                       (enhanced_df['air_temperature'] > -5)).astype(int)

        # Rullende gjennomsnittstrender
        for col in ['air_temperature', 'wind_speed', 'surface_snow_thickness']:
            if col in enhanced_df.columns:
                enhanced_df[f'{col}_3h_avg'] = enhanced_df[col].rolling(3).mean()
                enhanced_df[f'{col}_6h_avg'] = enhanced_df[col].rolling(6).mean()
                enhanced_df[f'{col}_change_1h'] = enhanced_df[col].diff()

        # Vindretningsfeatures
        if 'wind_from_direction' in enhanced_df.columns:
            # Konverter vindretning til sirkulære komponenter
            wind_rad = np.radians(enhanced_df['wind_from_direction'])
            enhanced_df['wind_x'] = np.cos(wind_rad)
            enhanced_df['wind_y'] = np.sin(wind_rad)
            enhanced_df['wind_dir_change'] = enhanced_df['wind_from_direction'].diff().abs()

        # Vindkast-features (forbedret)
        if 'max(wind_speed PT1H)' in enhanced_df.columns:
            # Bruk max(wind_speed PT1H) som vindkast hvis max(wind_speed_of_gust PT1H) ikke finnes
            enhanced_df['wind_gust'] = enhanced_df.get('max(wind_speed_of_gust PT1H)',
                                                      enhanced_df['max(wind_speed PT1H)'])

            # Beregn vindkast-ratio (hvor mye sterkere kastene er enn gjennomsnittsvind)
            enhanced_df['wind_gust_ratio'] = enhanced_df['wind_gust'] / enhanced_df['wind_speed'].replace(0, np.nan)

            # Vindkast-terskler som features
            enhanced_df['wind_gust_moderate'] = (enhanced_df['wind_gust'] >= 10.0).astype(int)
            enhanced_df['wind_gust_strong'] = (enhanced_df['wind_gust'] >= 15.0).astype(int)
            enhanced_df['wind_gust_extreme'] = (enhanced_df['wind_gust'] >= 20.0).astype(int)

        # Kombinerte værforhold
        if all(col in enhanced_df.columns for col in ['wind_speed', 'air_temperature']):
            enhanced_df['wind_chill'] = 13.12 + 0.6215 * enhanced_df['air_temperature'] - \
                                      11.37 * (enhanced_df['wind_speed'] ** 0.16) + \
                                      0.3965 * enhanced_df['air_temperature'] * (enhanced_df['wind_speed'] ** 0.16)

        # Snøfokk-indikatorer basert på eksisterende analyse (inkluderer vindkast)
        enhanced_df['potential_snowdrift'] = (
            (enhanced_df.get('wind_speed', 0) >= 6.0) &
            (enhanced_df.get('air_temperature', 10) <= -1.0) &
            (enhanced_df.get('surface_snow_thickness', 0) >= 3.0)
        ).astype(int)

        # Forbedret snøfokk-indikator som inkluderer vindkast
        enhanced_df['potential_snowdrift_with_gust'] = (
            ((enhanced_df.get('wind_speed', 0) >= 6.0) |
             (enhanced_df.get('wind_gust', 0) >= 10.0)) &
            (enhanced_df.get('air_temperature', 10) <= -1.0) &
            (enhanced_df.get('surface_snow_thickness', 0) >= 3.0)
        ).astype(int)

        # Ekstreme værforhold
        enhanced_df['extreme_wind'] = (enhanced_df.get('wind_speed', 0) >= 15.0).astype(int)
        enhanced_df['extreme_cold'] = (enhanced_df.get('air_temperature', 10) <= -15.0).astype(int)
        enhanced_df['heavy_snow'] = (enhanced_df.get('surface_snow_thickness', 0) >= 50.0).astype(int)

        return enhanced_df

    def train_snowdrift_classifier(self, df: pd.DataFrame) -> dict:
        """
        Trener en klassifikator for snøfokk-deteksjon.
        
        Args:
            df: DataFrame med værdata og features
            
        Returns:
            Dict med treningsresultater
        """
        logger.info("Trener snøfokk-klassifikator")

        # Forbered features
        feature_cols = [col for col in self.features if col in df.columns]

        # Legg til nye temperatur- og vindkast-features
        extended_features = ['hour', 'month', 'wind_x', 'wind_y', 'wind_chill',
                           'wind_gust', 'wind_gust_ratio', 'wind_gust_moderate',
                           'wind_gust_strong', 'wind_gust_extreme',
                           'temp_range_1h', 'temp_volatility', 'temp_rising',
                           'temp_falling', 'near_freezing', 'frost_risk']
        feature_cols.extend([col for col in extended_features if col in df.columns])
        feature_cols = [col for col in feature_cols if col in df.columns]

        X = df[feature_cols].fillna(0)
        y = df['potential_snowdrift'] if 'potential_snowdrift' in df.columns else np.zeros(len(df))

        # Normaliser features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Del opp i trenings- og testsett
        X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)

        # Tren Random Forest modell
        rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
        rf_model.fit(X_train, y_train)

        # Evaluer modell
        train_score = rf_model.score(X_train, y_train)
        test_score = rf_model.score(X_test, y_test)

        # Feature importance
        feature_importance = dict(zip(feature_cols, rf_model.feature_importances_, strict=False))
        sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)

        # Lagre modell
        self.models['snowdrift_classifier'] = rf_model
        self.scalers['snowdrift'] = scaler

        joblib.dump(rf_model, 'models/snowdrift_classifier.joblib')
        joblib.dump(scaler, 'models/snowdrift_scaler.joblib')

        results = {
            'train_accuracy': train_score,
            'test_accuracy': test_score,
            'feature_importance': sorted_features,
            'model_type': 'RandomForestClassifier',
            'features_used': feature_cols
        }

        logger.info(f"Modell trent - Test nøyaktighet: {test_score:.3f}")
        return results

    def cluster_weather_patterns(self, df: pd.DataFrame, n_clusters: int = 5) -> dict:
        """
        Utfører clustering for å identifisere værsmønstre.
        
        Args:
            df: DataFrame med værdata
            n_clusters: Antall clustere
            
        Returns:
            Dict med clustering-resultater
        """
        logger.info(f"Utfører clustering med {n_clusters} clustere")

        # Velg features for clustering
        cluster_features = ['air_temperature', 'wind_speed', 'surface_snow_thickness']
        cluster_features = [col for col in cluster_features if col in df.columns]

        X = df[cluster_features].fillna(0)

        # Normaliser data
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Utfør K-means clustering
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        clusters = kmeans.fit_predict(X_scaled)

        # Analyser clustere
        df_clustered = df.copy()
        df_clustered['cluster'] = clusters

        cluster_stats = {}
        for i in range(n_clusters):
            cluster_data = df_clustered[df_clustered['cluster'] == i]
            cluster_stats[f'cluster_{i}'] = {
                'size': len(cluster_data),
                'percentage': len(cluster_data) / len(df) * 100,
                'avg_temp': cluster_data['air_temperature'].mean() if 'air_temperature' in cluster_data.columns else None,
                'avg_wind': cluster_data['wind_speed'].mean() if 'wind_speed' in cluster_data.columns else None,
                'avg_snow': cluster_data['surface_snow_thickness'].mean() if 'surface_snow_thickness' in cluster_data.columns else None,
            }

        # Lagre clustering-modell
        joblib.dump(kmeans, 'models/weather_clusters.joblib')
        joblib.dump(scaler, 'models/cluster_scaler.joblib')

        results = {
            'n_clusters': n_clusters,
            'cluster_stats': cluster_stats,
            'features_used': cluster_features
        }

        logger.info("Clustering fullført")
        return results

    def analyze_long_term_trends(self, df: pd.DataFrame) -> dict:
        """
        Analyserer langtidstrender i værdata.
        
        Args:
            df: DataFrame med værdata
            
        Returns:
            Dict med trendanalyse
        """
        logger.info("Analyserer langtidstrender")

        if 'time' not in df.columns:
            logger.warning("Ingen tidsdata tilgjengelig for trendanalyse")
            return {}

        df['year'] = pd.to_datetime(df['time']).dt.year
        df['winter_season'] = df['year'].apply(lambda x: f"{x-1}-{x}" if pd.to_datetime(df[df['year']==x]['time']).dt.month.iloc[0] <= 6 else f"{x}-{x+1}")

        # Årlige gjennomsnitt
        yearly_stats = df.groupby('winter_season').agg({
            'air_temperature': ['mean', 'min', 'max'],
            'wind_speed': ['mean', 'max'],
            'surface_snow_thickness': ['mean', 'max'],
            'potential_snowdrift': 'sum' if 'potential_snowdrift' in df.columns else lambda x: 0
        }).round(2)

        # Trendberegning (lineær regresjon)
        trends = {}
        for param in ['air_temperature', 'wind_speed', 'surface_snow_thickness']:
            if param in df.columns:
                yearly_avg = df.groupby('winter_season')[param].mean()
                x = range(len(yearly_avg))
                trend_coef = np.polyfit(x, yearly_avg, 1)[0]
                trends[param] = {
                    'trend_per_year': trend_coef,
                    'direction': 'økende' if trend_coef > 0 else 'avtagende',
                    'significance': 'betydelig' if abs(trend_coef) > 0.1 else 'liten'
                }

        results = {
            'yearly_statistics': yearly_stats.to_dict(),
            'trends': trends,
            'analysis_period': f"{df['winter_season'].min()} til {df['winter_season'].max()}"
        }

        return results

    def run_comprehensive_analysis(self, start_year: int = 2018, end_year: int = 2024) -> dict:
        """
        Kjører komplett maskinlæringsanalyse av værdata.
        
        Args:
            start_year: Startår for analyse
            end_year: Sluttår for analyse
            
        Returns:
            Dict med alle analyseresultater
        """
        logger.info(f"Starter omfattende ML-analyse for {start_year}-{end_year}")

        results = {
            'analysis_period': f"{start_year}-{end_year}",
            'timestamp': datetime.now().isoformat(),
            'status': 'started'
        }

        try:
            # 1. Last værdata
            df = self.load_historical_data(start_year, end_year)
            if df.empty:
                raise ValueError("Ingen værdata tilgjengelig")

            results['data_points'] = len(df)

            # 2. Lag features
            df_enhanced = self.create_weather_features(df)

            # 3. Tren snøfokk-klassifikator
            classification_results = self.train_snowdrift_classifier(df_enhanced)
            results['snowdrift_classification'] = classification_results

            # 4. Cluster værsmønstre
            clustering_results = self.cluster_weather_patterns(df_enhanced)
            results['weather_clustering'] = clustering_results

            # 5. Analyser langtidstrender
            trend_results = self.analyze_long_term_trends(df_enhanced)
            results['long_term_trends'] = trend_results

            # 6. Generer sammendrag
            results['summary'] = self._generate_analysis_summary(results)
            results['status'] = 'completed'

            # Lagre resultater
            output_file = f"data/analyzed/ml_weather_analysis_{start_year}_{end_year}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                import json
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"Analyse fullført og lagret i {output_file}")

        except Exception as e:
            logger.error(f"Feil i ML-analyse: {e}")
            results['status'] = 'error'
            results['error'] = str(e)

        return results

    def _generate_analysis_summary(self, results: dict) -> dict:
        """Genererer sammendrag av analyseresultater."""

        summary = {
            'data_quality': 'høy' if results.get('data_points', 0) > 10000 else 'medium',
            'model_performance': 'god' if results.get('snowdrift_classification', {}).get('test_accuracy', 0) > 0.8 else 'moderat',
            'key_findings': []
        }

        # Nøkkelfunn basert på resultater
        if 'snowdrift_classification' in results:
            acc = results['snowdrift_classification'].get('test_accuracy', 0)
            summary['key_findings'].append(f"Snøfokk-klassifikator oppnår {acc:.1%} nøyaktighet")

        if 'weather_clustering' in results:
            n_clusters = results['weather_clustering'].get('n_clusters', 0)
            summary['key_findings'].append(f"Identifiserte {n_clusters} distinkte værsmønstre")

        if 'long_term_trends' in results:
            trends = results['long_term_trends'].get('trends', {})
            for param, trend_info in trends.items():
                direction = trend_info.get('direction', 'ukjent')
                summary['key_findings'].append(f"{param}: {direction} trend")

        return summary


def main():
    """Hovedfunksjon for å kjøre ML væranalyse."""

    print("🤖 MASKINLÆRING VÆRANALYSE 2018-2025")
    print("=" * 50)

    analyzer = MLWeatherAnalyzer()

    # Kjør analyse
    results = analyzer.run_comprehensive_analysis(start_year=2018, end_year=2024)

    if results['status'] == 'completed':
        print("\n✅ ANALYSE FULLFØRT")
        print(f"📊 Datapunkter analysert: {results.get('data_points', 0):,}")

        if 'summary' in results:
            print(f"🎯 Datakvalitet: {results['summary'].get('data_quality', 'ukjent')}")
            print(f"🤖 Modellytelse: {results['summary'].get('model_performance', 'ukjent')}")

            print("\n🔍 NØKKELFUNN:")
            for finding in results['summary'].get('key_findings', []):
                print(f"  • {finding}")

        print("\n💾 Resultater lagret i: data/analyzed/ml_weather_analysis_2018_2024.json")

    else:
        print(f"\n❌ ANALYSE FEILET: {results.get('error', 'Ukjent feil')}")


if __name__ == "__main__":
    main()
