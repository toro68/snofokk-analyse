import numpy as np
import pandas as pd
try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import TimeSeriesSplit 
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_squared_error, r2_score
except ImportError:
    logging.error("Kunne ikke importere sklearn. Vennligst installer scikit-learn pakken.")
    raise
import logging
from typing import Dict, List, Tuple, Any
from datetime import datetime
import joblib
from pathlib import Path

# Sett opp logging
logging.basicConfig(level=logging.INFO)
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
        Lager avanserte features for maskinlæring
        
        Args:
            df: DataFrame med værdata
        Returns:
            DataFrame med beregnede features
        """
        try:
            features = pd.DataFrame(index=df.index)
            
            # Vindstabilitet og variabilitet
            features['wind_speed'] = df['wind_speed']
            features['wind_gust'] = df['max(wind_speed_of_gust PT1H)']
            features['wind_variability'] = df['wind_speed'].rolling(3).std()
            
            # Beregn vindretningsstabilitet
            if 'wind_from_direction' in df.columns:
                wind_dir = df['wind_from_direction']
                # Konverter til radianer for sirkulær statistikk
                wind_rad = np.deg2rad(wind_dir)
                # Beregn gjennomsnittlig retning over 3 timer
                sin_avg = np.sin(wind_rad).rolling(3).mean()
                cos_avg = np.cos(wind_rad).rolling(3).mean()
                dir_stability = np.sqrt(sin_avg**2 + cos_avg**2)
                features['wind_dir_stability'] = dir_stability
            
            # Temperaturgradienter og stabilitet
            features['temperature'] = df['air_temperature']
            features['temp_gradient'] = df['air_temperature'].diff()
            features['temp_variability'] = df['air_temperature'].rolling(3).std()
            
            if 'surface_temperature' in df.columns:
                features['temp_surface_gradient'] = (
                    df['air_temperature'] - df['surface_temperature']
                )
            
            # Snøendring og akkumulering
            if 'surface_snow_thickness' in df.columns:
                features['snow_depth'] = df['surface_snow_thickness']
                features['snow_change'] = df['surface_snow_thickness'].diff()
                features['snow_change_rate'] = features['snow_change'].rolling(3).mean()
            
            # Sesong- og døgnvariasjoner
            features['hour'] = df.index.hour
            features['month'] = df.index.month
            features['day_of_year'] = df.index.dayofyear
            
            # Legg til sinus-transformerte tidsverdier for sykliske mønstre
            features['hour_sin'] = np.sin(2 * np.pi * features['hour'] / 24)
            features['month_sin'] = np.sin(2 * np.pi * features['month'] / 12)
            
            # Kombinerte features
            features['wind_temp_interaction'] = (
                features['wind_speed'] * features['temperature'].abs()
            )
            
            # Fyll manglende verdier
            features = features.fillna(method='ffill').fillna(method='bfill')
            
            return features
            
        except Exception as e:
            logger.error(f"Feil i feature engineering: {str(e)}")
            raise
    
    def optimize_parameters(self, 
                          df: pd.DataFrame, 
                          target: pd.Series,
                          n_splits: int = 5) -> Dict[str, Any]:
        """
        Optimaliserer parametre basert på historiske data
        
        Args:
            df: DataFrame med værdata
            target: Faktisk risikoscore
            n_splits: Antall splitt for tidsserie-validering
        
        Returns:
            Dict med optimaliserte parametre og evalueringsmetrikker
        """
        try:
            # Lag feature matrix
            X = self.create_feature_matrix(df)
            y = target
            
            # Tidsserie-splitting
            tscv = TimeSeriesSplit(n_splits=n_splits)
            
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
                    n_estimators=100,
                    max_depth=10,
                    random_state=42
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
            
            return {
                'cv_scores': cv_scores,
                'mean_cv_score': np.mean(cv_scores),
                'feature_importance': self.feature_importance,
                'suggested_parameters': suggested_params
            }
            
        except Exception as e:
            logger.error(f"Feil i parameteroptimalisering: {str(e)}")
            raise
    
    def suggest_parameters(self) -> Dict[str, float]:
        """
        Foreslår parameterinnstillinger basert på feature importance
        
        Returns:
            Dict med foreslåtte parametre
        """
        try:
            # Normaliser feature importance
            total_importance = sum(self.feature_importance.values())
            norm_importance = {
                k: v/total_importance 
                for k, v in self.feature_importance.items()
            }
            
            # Beregn vekter basert på feature groups
            wind_importance = sum(
                v for k, v in norm_importance.items() 
                if 'wind' in k.lower()
            )
            temp_importance = sum(
                v for k, v in norm_importance.items() 
                if 'temp' in k.lower()
            )
            snow_importance = sum(
                v for k, v in norm_importance.items() 
                if 'snow' in k.lower()
            )
            
            # Juster parametre basert på relative viktigheter
            suggested_params = {
                'wind_weight': min(2.0, 1.0 + wind_importance),
                'temp_weight': min(2.0, 1.0 + temp_importance),
                'snow_weight': min(2.0, 1.0 + snow_importance),
                
                # Juster terskelverdier basert på feature importance
                'wind_strong': 8.0 * (1.0 + wind_importance * 0.5),
                'wind_moderate': 6.5 * (1.0 + wind_importance * 0.3),
                'wind_gust': 15.0 * (1.0 + wind_importance * 0.2),
                'wind_dir_change': 30.0 * (1.0 + wind_importance * 0.4),
                
                'temp_cold': -2.0 * (1.0 + temp_importance * 0.5),
                'temp_cool': 0.0 * (1.0 + temp_importance * 0.3),
                
                'snow_high': 1.5 * (1.0 + snow_importance * 0.5),
                'snow_moderate': 0.8 * (1.0 + snow_importance * 0.3),
                'snow_low': 0.3 * (1.0 + snow_importance * 0.2)
            }
            
            return suggested_params
            
        except Exception as e:
            logger.error(f"Feil i parameterforslag: {str(e)}")
            raise
    
    def evaluate_parameters(self, 
                          df: pd.DataFrame, 
                          params: Dict[str, float]) -> Dict[str, Any]:
        """
        Evaluerer et sett med parametre mot historiske data
        
        Args:
            df: DataFrame med værdata
            params: Dict med parametre å evaluere
            
        Returns:
            Dict med evalueringsmetrikker
        """
        try:
            # Lag features for evaluering
            features = self.create_feature_matrix(df)
            
            if self.model is None:
                self.model = joblib.load(self.data_path / "snow_drift_model.joblib")
                self.scaler = joblib.load(self.data_path / "feature_scaler.joblib")
            
            # Prediker risikoscore
            X_scaled = self.scaler.transform(features)
            predicted_risk = self.model.predict(X_scaled)
            
            # Beregn faktisk risiko med nye parametre
            from db_utils import calculate_snow_drift_risk
            actual_df, periods_df = calculate_snow_drift_risk(df, params)
            
            # Beregn evalueringsmetrikker
            metrics = {
                'mse': mean_squared_error(
                    actual_df['risk_score'], 
                    predicted_risk
                ),
                'r2': r2_score(
                    actual_df['risk_score'], 
                    predicted_risk
                ),
                'num_critical_periods': len(periods_df),
                'avg_period_duration': periods_df['duration'].mean()
                if not periods_df.empty else 0,
                'max_risk_score': actual_df['risk_score'].max(),
                'avg_risk_score': actual_df['risk_score'].mean()
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Feil i parameterevaluering: {str(e)}")
            raise

def analyze_seasonal_patterns(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyserer sesongmessige mønstre i værdata
    
    Args:
        df: DataFrame med værdata
    Returns:
        Dict med sesonganalyse
    """
    try:
        analysis = {}
        
        # Legg til sesonginfo
        df = df.copy()
        df['month'] = df.index.month
        df['hour'] = df.index.hour
        df['season'] = pd.cut(
            df.index.month, 
            bins=[0, 3, 6, 9, 12],
            labels=['Vinter', 'Vår', 'Sommer', 'Høst']
        )
        
        # Analyser sesongvariasjoner
        season_stats = df.groupby('season').agg({
            'wind_speed': ['mean', 'max'],
            'air_temperature': ['mean', 'min'],
            'surface_snow_thickness': ['mean', 'std']
        }).round(2)
        
        # Analyser døgnvariasjoner
        hourly_stats = df.groupby('hour').agg({
            'wind_speed': 'mean',
            'air_temperature': 'mean'
        }).round(2)
        
        # Finn typiske mønstre
        patterns = []
        
        # Vindmønstre
        wind_pattern = (
            df.groupby(['season', 'hour'])['wind_speed']
            .mean()
            .unstack()
            .idxmax(axis=1)
        )
        patterns.append({
            'type': 'wind',
            'description': 'Tidspunkt for høyest vind per sesong',
            'data': wind_pattern.to_dict()
        })
        
        # Temperaturmønstre
        temp_pattern = (
            df.groupby(['season', 'hour'])['air_temperature']
            .mean()
            .unstack()
            .idxmin(axis=1)
        )
        patterns.append({
            'type': 'temperature',
            'description': 'Tidspunkt for lavest temperatur per sesong',
            'data': temp_pattern.to_dict()
        })
        
        analysis['season_stats'] = season_stats
        analysis['hourly_stats'] = hourly_stats
        analysis['patterns'] = patterns
        
        return analysis
        
    except Exception as e:
        logger.error(f"Feil i sesonganalyse: {str(e)}")
        return {} 