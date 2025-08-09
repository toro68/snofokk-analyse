#!/usr/bin/env python3
"""
Snøfokk Pattern Analyzer - Analyserer historiske værdata for å finne snøfokk-mønstre
"""
import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from snofokk.services.weather import WeatherService
from snofokk.services.analysis import AnalysisService
from snofokk.config import settings

# Sett opp logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SnowDriftPatternAnalyzer:
    """Analyserer snøfokk-mønstre i historiske værdata"""
    
    def __init__(self):
        self.weather_service = WeatherService()
        self.analysis_service = AnalysisService()
        
        # Snøfokk-kriterier (basert på meteorologisk forskning)
        self.snowdrift_criteria = {
            'min_wind_speed': 6.0,        # m/s - minimum vindstyrke
            'optimal_wind_speed': 12.0,   # m/s - optimal vindstyrke for snøfokk
            'max_temperature': -2.0,      # °C - maksimal temperatur
            'optimal_temperature': -8.0,  # °C - optimal temperatur
            'min_snow_depth': 3.0,        # cm - minimum snødybde
            'snow_change_threshold': 2.0, # cm - signifikant endring i snødybde
            'duration_hours': 2           # timer - minimum varighet
        }
    
    def fetch_historical_data(self, start_date: datetime, end_date: datetime, station: str = None) -> pd.DataFrame:
        """Hent historiske værdata fra Frost API"""
        if station is None:
            station = settings.weather_station
            
        logger.info(f"Henter værdata fra {start_date.strftime('%Y-%m-%d')} til {end_date.strftime('%Y-%m-%d')}")
        
        data = self.weather_service.fetch_weather_data(
            station=station,
            from_time=start_date.strftime('%Y-%m-%dT%H:%M:%S'),
            to_time=end_date.strftime('%Y-%m-%dT%H:%M:%S'),
            client_id=settings.frost_client_id
        )
        
        if data is None or data.empty:
            logger.error("Ingen værdata hentet")
            return pd.DataFrame()
        
        logger.info(f"Hentet {len(data)} datapunkter")
        return data
    
    def detect_snowdrift_conditions(self, df: pd.DataFrame) -> pd.DataFrame:
        """Identifiser potensielle snøfokk-forhold"""
        if df.empty:
            return pd.DataFrame()
        
        # Normaliser snødata først
        df_normalized = self.weather_service.normalize_snow_data(df.copy())
        
        # Beregn snøfokk-sannsynlighet for hver rad
        df_normalized['snowdrift_score'] = 0.0
        df_normalized['snowdrift_factors'] = ''
        
        # 1. Vindkomponent (40% av score)
        if 'wind_speed' in df_normalized.columns:
            wind_score = np.where(
                df_normalized['wind_speed'] >= self.snowdrift_criteria['optimal_wind_speed'], 1.0,
                np.where(
                    df_normalized['wind_speed'] >= self.snowdrift_criteria['min_wind_speed'], 
                    (df_normalized['wind_speed'] - self.snowdrift_criteria['min_wind_speed']) / 
                    (self.snowdrift_criteria['optimal_wind_speed'] - self.snowdrift_criteria['min_wind_speed']),
                    0.0
                )
            )
            df_normalized['snowdrift_score'] += wind_score * 0.4
        
        # 2. Temperaturkomponent (30% av score) 
        if 'air_temperature' in df_normalized.columns:
            temp_score = np.where(
                df_normalized['air_temperature'] <= self.snowdrift_criteria['optimal_temperature'], 1.0,
                np.where(
                    df_normalized['air_temperature'] <= self.snowdrift_criteria['max_temperature'],
                    1.0 - (df_normalized['air_temperature'] - self.snowdrift_criteria['optimal_temperature']) / 
                    (self.snowdrift_criteria['max_temperature'] - self.snowdrift_criteria['optimal_temperature']),
                    0.0
                )
            )
            df_normalized['snowdrift_score'] += temp_score * 0.3
        
        # 3. Snødybdekomponent (20% av score)
        if 'surface_snow_thickness' in df_normalized.columns:
            snow_score = np.where(
                df_normalized['surface_snow_thickness'] >= self.snowdrift_criteria['min_snow_depth'], 1.0, 0.0
            )
            df_normalized['snowdrift_score'] += snow_score * 0.2
        
        # 4. Snøendring (10% av score) - indikerer aktiv snøfokk
        if 'surface_snow_thickness' in df_normalized.columns:
            snow_change = df_normalized['surface_snow_thickness'].diff().abs()
            change_score = np.where(
                snow_change >= self.snowdrift_criteria['snow_change_threshold'], 1.0, 0.0
            )
            df_normalized['snowdrift_score'] += change_score * 0.1
        
        # Identifiser høy-risiko perioder (score > 0.6)
        df_normalized['high_snowdrift_risk'] = df_normalized['snowdrift_score'] > 0.6
        
        return df_normalized
    
    def find_snowdrift_events(self, df: pd.DataFrame) -> pd.DataFrame:
        """Finn kontinuerlige snøfokk-hendelser"""
        if df.empty or 'high_snowdrift_risk' not in df.columns:
            return pd.DataFrame()
        
        # Finn start og slutt på risiko-perioder
        risk_changes = df['high_snowdrift_risk'].astype(int).diff()
        event_starts = df.index[risk_changes == 1]
        event_ends = df.index[risk_changes == -1]
        
        # Håndter kanttilfeller
        if df['high_snowdrift_risk'].iloc[0]:
            event_starts = pd.Index([df.index[0]]).union(event_starts)
        if df['high_snowdrift_risk'].iloc[-1]:
            event_ends = event_ends.union(pd.Index([df.index[-1]]))
        
        events = []
        for start_idx, end_idx in zip(event_starts, event_ends):
            event_data = df.loc[start_idx:end_idx]
            
            # Beregn hendelsesstatistikk
            if 'referenceTime' in event_data.columns:
                start_time = event_data['referenceTime'].iloc[0]
                end_time = event_data['referenceTime'].iloc[-1]
                duration = len(event_data)
            else:
                start_time = start_idx
                end_time = end_idx
                duration = len(event_data)
            
            # Kun ta med hendelser som varer lenge nok
            if duration >= self.snowdrift_criteria['duration_hours']:
                event_stats = {
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration_hours': duration,
                    'max_snowdrift_score': event_data['snowdrift_score'].max(),
                    'avg_snowdrift_score': event_data['snowdrift_score'].mean(),
                    'max_wind_speed': event_data['wind_speed'].max() if 'wind_speed' in event_data else 0,
                    'avg_wind_speed': event_data['wind_speed'].mean() if 'wind_speed' in event_data else 0,
                    'min_temperature': event_data['air_temperature'].min() if 'air_temperature' in event_data else 0,
                    'avg_temperature': event_data['air_temperature'].mean() if 'air_temperature' in event_data else 0,
                    'snow_depth_start': event_data['surface_snow_thickness'].iloc[0] if 'surface_snow_thickness' in event_data else 0,
                    'snow_depth_end': event_data['surface_snow_thickness'].iloc[-1] if 'surface_snow_thickness' in event_data else 0,
                    'snow_depth_change': (event_data['surface_snow_thickness'].iloc[-1] - event_data['surface_snow_thickness'].iloc[0]) if 'surface_snow_thickness' in event_data else 0
                }
                events.append(event_stats)
        
        return pd.DataFrame(events)
    
    def analyze_snowdrift_patterns(self, events_df: pd.DataFrame) -> dict:
        """Analyser mønstre i snøfokk-hendelser"""
        if events_df.empty:
            return {
                'total_events': 0,
                'total_duration': 0,
                'patterns': {},
                'recommendations': []
            }
        
        analysis = {
            'total_events': len(events_df),
            'total_duration': events_df['duration_hours'].sum(),
            'avg_duration': events_df['duration_hours'].mean(),
            'max_duration': events_df['duration_hours'].max(),
            'patterns': {},
            'recommendations': []
        }
        
        # Vindmønstre
        analysis['patterns']['wind'] = {
            'avg_max_wind': events_df['max_wind_speed'].mean(),
            'optimal_wind_range': f"{events_df['max_wind_speed'].quantile(0.25):.1f}-{events_df['max_wind_speed'].quantile(0.75):.1f} m/s"
        }
        
        # Temperaturmønstre  
        analysis['patterns']['temperature'] = {
            'avg_min_temp': events_df['min_temperature'].mean(),
            'optimal_temp_range': f"{events_df['min_temperature'].quantile(0.75):.1f} til {events_df['min_temperature'].quantile(0.25):.1f}°C"
        }
        
        # Snømønstre
        analysis['patterns']['snow'] = {
            'avg_depth_at_start': events_df['snow_depth_start'].mean(),
            'avg_depth_change': events_df['snow_depth_change'].mean()
        }
        
        # Generer anbefalinger
        if analysis['patterns']['wind']['avg_max_wind'] > 15:
            analysis['recommendations'].append("Høy vindstyrke er hoveddriver - fokuser på vindvarsel")
        
        if analysis['patterns']['temperature']['avg_min_temp'] < -10:
            analysis['recommendations'].append("Svært kalde forhold øker risiko - vær ekstra oppmerksom ved temperaturer under -10°C")
        
        if analysis['patterns']['snow']['avg_depth_change'] < -1:
            analysis['recommendations'].append("Snødybde reduseres under hendelser - snøfokk fører snøen bort")
        
        return analysis
    
    def run_analysis(self, days_back: int = 30, station: str = None) -> dict:
        """Kjør komplett snøfokk-analyse"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        logger.info(f"=== SNØFOKK PATTERN ANALYSE ===")
        logger.info(f"Periode: {start_date.strftime('%Y-%m-%d')} til {end_date.strftime('%Y-%m-%d')}")
        
        # 1. Hent historiske data
        weather_data = self.fetch_historical_data(start_date, end_date, station)
        if weather_data.empty:
            return {'error': 'Ingen værdata tilgjengelig'}
        
        # 2. Identifiser snøfokk-forhold
        logger.info("Analyserer snøfokk-forhold...")
        data_with_scores = self.detect_snowdrift_conditions(weather_data)
        
        # 3. Finn hendelser
        logger.info("Identifiserer snøfokk-hendelser...")
        events = self.find_snowdrift_events(data_with_scores)
        
        # 4. Analyser mønstre
        logger.info("Analyserer mønstre...")
        patterns = self.analyze_snowdrift_patterns(events)
        
        # 5. Lag sammendrag
        summary = {
            'analysis_period': f"{start_date.strftime('%Y-%m-%d')} til {end_date.strftime('%Y-%m-%d')}",
            'data_points': len(weather_data),
            'high_risk_periods': (data_with_scores['high_snowdrift_risk'] == True).sum() if not data_with_scores.empty else 0,
            'snowdrift_events': patterns,
            'raw_events': events.to_dict('records') if not events.empty else []
        }
        
        return summary

def main():
    """Hovedfunksjon"""
    analyzer = SnowDriftPatternAnalyzer()
    
    # Kjør analyse for siste 30 dager
    try:
        results = analyzer.run_analysis(days_back=30)
        
        if 'error' in results:
            logger.error(f"Analyse feilet: {results['error']}")
            return
        
        # Skriv ut resultater
        print(f"\n{'='*60}")
        print(f"SNØFOKK PATTERN ANALYSE - RESULTATER")
        print(f"{'='*60}")
        print(f"Periode: {results['analysis_period']}")
        print(f"Totalt antall datapunkter: {results['data_points']}")
        print(f"Høyrisiko-perioder: {results['high_risk_periods']}")
        
        events = results['snowdrift_events']
        print(f"\nSNØFOKK-HENDELSER:")
        print(f"  Totalt: {events['total_events']}")
        print(f"  Total varighet: {events['total_duration']:.1f} timer")
        
        if events['total_events'] > 0:
            print(f"  Gjennomsnittlig varighet: {events['avg_duration']:.1f} timer")
            print(f"  Lengste hendelse: {events['max_duration']:.1f} timer")
            
            print(f"\nMØNSTRE:")
            wind = events['patterns']['wind']
            print(f"  Vind: Gjennomsnitt {wind['avg_max_wind']:.1f} m/s, optimal range {wind['optimal_wind_range']}")
            
            temp = events['patterns']['temperature']
            print(f"  Temperatur: Gjennomsnitt {temp['avg_min_temp']:.1f}°C, optimal range {temp['optimal_temp_range']}")
            
            snow = events['patterns']['snow']
            print(f"  Snø: Start-dybde {snow['avg_depth_at_start']:.1f} cm, endring {snow['avg_depth_change']:.1f} cm")
            
            print(f"\nANBEFALINGER:")
            for rec in events['recommendations']:
                print(f"  • {rec}")
        
        # Lagre detaljerte resultater
        output_file = Path(__file__).parent.parent.parent / 'data' / 'analyzed' / 'snowdrift_pattern_analysis.json'
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        import json
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"Detaljerte resultater lagret i {output_file}")
        
    except Exception as e:
        logger.error(f"Feil under analyse: {e}")
        raise

if __name__ == '__main__':
    main()
