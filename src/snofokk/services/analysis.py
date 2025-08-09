"""
Analysis service for processing weather data and identifying snow drift risks
"""
import pandas as pd
import numpy as np
from typing import List
from datetime import datetime
import logging

from ..config import settings
from ..models import WeatherData, SnowAnalysis

logger = logging.getLogger(__name__)

class AnalysisService:
    """Service for analyzing weather data and snow drift conditions"""
    
    def analyze_snow_conditions(self, df: WeatherData) -> List[SnowAnalysis]:
        """Analyze snow conditions and detect changes"""
        analyses = []
        
        if 'surface_snow_thickness' not in df.columns or df.empty:
            logger.warning("No snow thickness data available for analysis")
            return analyses
        
        snow_data = df['surface_snow_thickness'].dropna()
        
        if len(snow_data) < 2:
            logger.warning("Insufficient snow data for analysis")
            return analyses
        
        for i in range(1, len(snow_data)):
            prev_depth = snow_data.iloc[i-1]
            curr_depth = snow_data.iloc[i]
            
            if pd.isna(prev_depth) or pd.isna(curr_depth):
                continue
            
            # Calculate change
            change = curr_depth - prev_depth
            
            # Determine change type
            if abs(change) < settings.snow_change_threshold:
                change_type = 'steady'
            elif change > 0:
                change_type = 'increase'
            else:
                change_type = 'decrease'
            
            # Calculate confidence based on data quality
            confidence = self._calculate_confidence(curr_depth, change)
            
            analysis = SnowAnalysis(
                raw_depth=curr_depth,
                normalized_depth=curr_depth,  # Already normalized in weather service
                confidence=confidence,
                is_valid=not pd.isna(curr_depth) and curr_depth >= 0,
                change_type=change_type
            )
            
            analyses.append(analysis)
        
        return analyses
    
    def _calculate_confidence(self, depth: float, change: float) -> float:
        """Calculate confidence score for snow analysis"""
        # Base confidence
        confidence = 0.8
        
        # Reduce confidence for extreme values
        if depth > 200:  # Very deep snow
            confidence -= 0.2
        if abs(change) > 20:  # Very large change
            confidence -= 0.3
        
        return max(0.1, confidence)
    
    def detect_risk_periods(self, df: WeatherData) -> pd.DataFrame:
        """Detect periods with high snow drift risk"""
        
        if df.empty:
            return pd.DataFrame()
        
        # Initialize risk score
        df = df.copy()
        df['risk_score'] = 0.0
        
        # Wind risk component
        if 'wind_speed' in df.columns:
            wind_risk = np.where(
                df['wind_speed'] >= 15.0, 1.0,
                np.where(df['wind_speed'] >= settings.wind_impact_threshold, 0.6, 0.0)
            )
            df['risk_score'] += wind_risk * 0.4
        
        # Temperature risk component (cold temperatures increase drift risk)
        if 'air_temperature' in df.columns:
            temp_risk = np.where(
                df['air_temperature'] <= -10.0, 0.8,
                np.where(df['air_temperature'] <= settings.temperature_snow_threshold, 0.4, 0.0)
            )
            df['risk_score'] += temp_risk * 0.3
        
        # Snow change component
        if 'surface_snow_thickness' in df.columns:
            snow_change = df['surface_snow_thickness'].diff().abs()
            snow_risk = np.where(
                snow_change >= 5.0, 0.8,
                np.where(snow_change >= settings.snow_change_threshold, 0.4, 0.0)
            )
            df['risk_score'] += snow_risk * 0.3
        
        # Identify high-risk periods (risk_score > 0.6)
        df['is_high_risk'] = df['risk_score'] > 0.6
        
        # Find continuous periods
        periods = self._identify_continuous_periods(df)
        
        return periods
    
    def _identify_continuous_periods(self, df: pd.DataFrame, min_duration: int = 2) -> pd.DataFrame:
        """Identify continuous high-risk periods"""
        
        if 'is_high_risk' not in df.columns or df['is_high_risk'].sum() == 0:
            return pd.DataFrame(columns=[
                'start_time', 'end_time', 'duration', 'max_risk_score', 'avg_risk_score'
            ])
        
        # Find period boundaries
        risk_changes = df['is_high_risk'].astype(int).diff()
        period_starts = df.index[risk_changes == 1]
        period_ends = df.index[risk_changes == -1]
        
        # Handle edge cases
        if df['is_high_risk'].iloc[0]:
            period_starts = pd.Index([df.index[0]]).union(period_starts)
        if df['is_high_risk'].iloc[-1]:
            period_ends = period_ends.union(pd.Index([df.index[-1]]))
        
        periods = []
        for start_idx, end_idx in zip(period_starts, period_ends):
            period_df = df.loc[start_idx:end_idx]
            duration = len(period_df)
            
            if duration >= min_duration:
                periods.append({
                    'start_time': period_df['referenceTime'].iloc[0] if 'referenceTime' in period_df else start_idx,
                    'end_time': period_df['referenceTime'].iloc[-1] if 'referenceTime' in period_df else end_idx,
                    'duration': duration,
                    'max_risk_score': period_df['risk_score'].max(),
                    'avg_risk_score': period_df['risk_score'].mean()
                })
        
        return pd.DataFrame(periods)

# Global analysis service instance
analysis_service = AnalysisService()
