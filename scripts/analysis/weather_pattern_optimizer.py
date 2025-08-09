#!/usr/bin/env python3
"""
Weather Pattern Optimizer - Hovedscript for optimalisering av snøfokk og glatt vei-parametere
"""
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging
import json

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from snofokk.config import settings

# Import våre analysere
try:
    from snow_drift_pattern_analyzer import SnowDriftAnalyzer, SnowDriftEvent, OptimalParameters
    from slippery_road_pattern_analyzer import SlipperyRoadAnalyzer, SlipperyRoadEvent, SlipperyRoadParameters
except ImportError:
    # Fallback imports hvis ikke i samme mappe
    import importlib.util
    import os
    
    # Last snow drift analyzer
    spec = importlib.util.spec_from_file_location(
        "snow_drift_pattern_analyzer", 
        os.path.join(os.path.dirname(__file__), "snow_drift_pattern_analyzer.py")
    )
    snow_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(snow_module)
    SnowDriftAnalyzer = snow_module.SnowDriftAnalyzer
    SnowDriftEvent = snow_module.SnowDriftEvent
    OptimalParameters = snow_module.OptimalParameters
    
    # Last slippery road analyzer
    spec = importlib.util.spec_from_file_location(
        "slippery_road_pattern_analyzer", 
        os.path.join(os.path.dirname(__file__), "slippery_road_pattern_analyzer.py")
    )
    slip_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(slip_module)
    SlipperyRoadAnalyzer = slip_module.SlipperyRoadAnalyzer
    SlipperyRoadEvent = slip_module.SlipperyRoadEvent
    SlipperyRoadParameters = slip_module.SlipperyRoadParameters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WeatherPatternOptimizer:
    """Hovedklasse for optimalisering av værmønster-parametere"""
    
    def __init__(self):
        self.snow_drift_analyzer = SnowDriftAnalyzer()
        self.slippery_road_analyzer = SlipperyRoadAnalyzer()
        
        # Resultater
        self.snow_drift_events: List[SnowDriftEvent] = []
        self.slippery_road_events: List[SlipperyRoadEvent] = []
        
        # Optimaliserte parametere
        self.optimal_snow_params: Optional[OptimalParameters] = None
        self.optimal_slippery_params: Optional[SlipperyRoadParameters] = None
    
    def analyze_historical_seasons(
        self, 
        start_year: int, 
        end_year: int,
        station: str = "SN46220"
    ) -> Dict:
        """Analyser flere vintersessonger for å finne mønstre"""
        
        logger.info(f"Analyserer vintersessonger {start_year}-{end_year}")
        
        all_snow_events = []
        all_slippery_events = []
        seasonal_stats = {}
        
        for year in range(start_year, end_year + 1):
            logger.info(f"\nAnalyserer vintersesong {year-1}/{year}...")
            
            # Definer sesong (november - mars)
            season_start = datetime(year - 1, 11, 1)
            season_end = datetime(year, 3, 31)
            
            # Analyser snøfokk
            snow_events = self.snow_drift_analyzer.analyze_historical_period(
                season_start, season_end, station
            )
            
            # Analyser glatte veier
            slippery_events = self.slippery_road_analyzer.analyze_period(
                season_start, season_end, station
            )
            
            # Samle statistikk for sesongen
            seasonal_stats[f"{year-1}/{year}"] = {
                'snow_drift_events': len(snow_events),
                'slippery_road_events': len(slippery_events),
                'total_snow_drift_hours': sum(e.duration_hours for e in snow_events),
                'total_slippery_hours': sum(e.duration_hours for e in slippery_events),
                'avg_snow_severity': np.mean([e.severity_score for e in snow_events]) if snow_events else 0,
                'avg_slippery_risk': np.mean([e.risk_score for e in slippery_events]) if slippery_events else 0
            }
            
            all_snow_events.extend(snow_events)
            all_slippery_events.extend(slippery_events)
        
        # Lagre resultater
        self.snow_drift_events = all_snow_events
        self.slippery_road_events = all_slippery_events
        
        logger.info("\nTotalt funnet:")
        logger.info(f"  - {len(all_snow_events)} snøfokk-hendelser")
        logger.info(f"  - {len(all_slippery_events)} glatt vei-hendelser")
        
        return {
            'seasonal_stats': seasonal_stats,
            'total_snow_events': len(all_snow_events),
            'total_slippery_events': len(all_slippery_events),
            'snow_events': all_snow_events,
            'slippery_events': all_slippery_events
        }
    
    def find_correlation_patterns(self) -> Dict:
        """Finn korrelasjoner mellom snøfokk og glatte vei-hendelser"""
        
        logger.info("Analyserer korrelasjoner mellom værfenomener...")
        
        correlations = {
            'temporal_overlap': 0,
            'close_proximity': 0,  # Hendelser innen 24 timer
            'shared_conditions': [],
            'temperature_patterns': {},
            'wind_patterns': {},
            'seasonal_distribution': {}
        }
        
        if not self.snow_drift_events or not self.slippery_road_events:
            logger.warning("Ikke nok data for korrelasjonsanalyse")
            return correlations
        
        # Analyser tidslig overlapp
        overlap_count = 0
        proximity_count = 0
        
        for snow_event in self.snow_drift_events:
            for slip_event in self.slippery_road_events:
                # Sjekk overlapp
                if (snow_event.start_time <= slip_event.end_time and 
                    snow_event.end_time >= slip_event.start_time):
                    overlap_count += 1
                
                # Sjekk nærhet (innen 24 timer)
                time_diff = abs((snow_event.start_time - slip_event.start_time).total_seconds() / 3600)
                if time_diff <= 24:
                    proximity_count += 1
        
        correlations['temporal_overlap'] = overlap_count
        correlations['close_proximity'] = proximity_count
        
        # Analyser værforhold
        correlations['temperature_patterns'] = self._analyze_temperature_patterns()
        correlations['wind_patterns'] = self._analyze_wind_patterns()
        correlations['seasonal_distribution'] = self._analyze_seasonal_distribution()
        
        logger.info("Korrelasjonsanalyse fullført:")
        logger.info(f"  - Overlappende hendelser: {overlap_count}")
        logger.info(f"  - Nære hendelser (24h): {proximity_count}")
        
        return correlations
    
    def _analyze_temperature_patterns(self) -> Dict:
        """Analyser temperaturmønstre"""
        
        snow_temps = [e.avg_temperature for e in self.snow_drift_events]
        slip_temps = [e.avg_temperature for e in self.slippery_road_events]
        
        return {
            'snow_avg_temp': np.mean(snow_temps) if snow_temps else 0,
            'snow_temp_range': [np.min(snow_temps), np.max(snow_temps)] if snow_temps else [0, 0],
            'slip_avg_temp': np.mean(slip_temps) if slip_temps else 0,
            'slip_temp_range': [np.min(slip_temps), np.max(slip_temps)] if slip_temps else [0, 0],
            'optimal_temp_range': self._find_optimal_temp_range()
        }
    
    def _analyze_wind_patterns(self) -> Dict:
        """Analyser vindmønstre"""
        
        snow_winds = [e.avg_wind_speed for e in self.snow_drift_events]
        
        return {
            'snow_avg_wind': np.mean(snow_winds) if snow_winds else 0,
            'snow_wind_range': [np.min(snow_winds), np.max(snow_winds)] if snow_winds else [0, 0],
            'high_wind_events': len([w for w in snow_winds if w > 10]) if snow_winds else 0
        }
    
    def _analyze_seasonal_distribution(self) -> Dict:
        """Analyser sesongfordeling"""
        
        snow_months = [e.start_time.month for e in self.snow_drift_events]
        slip_months = [e.start_time.month for e in self.slippery_road_events]
        
        return {
            'snow_by_month': {month: snow_months.count(month) for month in range(1, 13)},
            'slip_by_month': {month: slip_months.count(month) for month in range(1, 13)},
            'peak_snow_month': max(snow_months, key=snow_months.count) if snow_months else 0,
            'peak_slip_month': max(slip_months, key=slip_months.count) if slip_months else 0
        }
    
    def _find_optimal_temp_range(self) -> List[float]:
        """Finn optimal temperaturområde for begge fenomener"""
        
        all_temps = []
        all_temps.extend([e.avg_temperature for e in self.snow_drift_events])
        all_temps.extend([e.avg_temperature for e in self.slippery_road_events])
        
        if all_temps:
            return [np.percentile(all_temps, 10), np.percentile(all_temps, 90)]
        return [0, 0]
    
    def optimize_combined_parameters(self) -> Dict:
        """Optimaliser parametere for optimal deteksjon av begge fenomener"""
        
        logger.info("Optimaliserer kombinerte parametere...")
        
        # Analyser eksisterende hendelser for å finne beste terskler
        optimization_results = {
            'snow_drift_params': self._optimize_snow_drift_params(),
            'slippery_road_params': self._optimize_slippery_road_params(),
            'combined_thresholds': self._find_combined_thresholds(),
            'recommendations': self._generate_recommendations()
        }
        
        return optimization_results
    
    def _optimize_snow_drift_params(self) -> Dict:
        """Optimaliser snøfokk-parametere basert på funnet data"""
        
        if not self.snow_drift_events:
            return {}
        
        wind_speeds = [e.avg_wind_speed for e in self.snow_drift_events]
        temperatures = [e.avg_temperature for e in self.snow_drift_events]
        snow_variances = [e.snow_depth_variance for e in self.snow_drift_events]
        
        return {
            'optimal_wind_threshold': np.percentile(wind_speeds, 25),  # 25% kvartil
            'optimal_temp_threshold': np.percentile(temperatures, 75),  # 75% kvartil
            'optimal_snow_variance': np.percentile(snow_variances, 25),
            'recommended_min_duration': 2,  # timer
            'confidence_threshold': 70  # %
        }
    
    def _optimize_slippery_road_params(self) -> Dict:
        """Optimaliser glatt vei-parametere"""
        
        if not self.slippery_road_events:
            return {}
        
        temperatures = [e.avg_temperature for e in self.slippery_road_events]
        humidities = [e.avg_humidity for e in self.slippery_road_events]
        
        return {
            'optimal_temp_threshold': np.percentile(temperatures, 75),
            'optimal_humidity_threshold': np.percentile(humidities, 25),
            'recommended_min_duration': 1,  # timer
            'confidence_threshold': 60  # %
        }
    
    def _find_combined_thresholds(self) -> Dict:
        """Finn terskler som fungerer for begge fenomener"""
        
        # Kombiner temperaturdata
        all_temps = []
        all_temps.extend([e.avg_temperature for e in self.snow_drift_events])
        all_temps.extend([e.avg_temperature for e in self.slippery_road_events])
        
        return {
            'critical_temp_range': [np.percentile(all_temps, 10), np.percentile(all_temps, 90)] if all_temps else [0, 0],
            'high_risk_temp': np.percentile(all_temps, 25) if all_temps else 0,
            'monitoring_hours': [6, 22],  # Mest kritiske timer på døgnet
            'alert_threshold': 75  # Kombinert risikoscore
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generer anbefalinger basert på analysen"""
        
        recommendations = []
        
        if self.snow_drift_events:
            avg_snow_severity = np.mean([e.severity_score for e in self.snow_drift_events])
            recommendations.append(f"Snøfokk: Gjennomsnittlig alvorlighetsgrad er {avg_snow_severity:.1f}/100")
            
            peak_snow_month = max([e.start_time.month for e in self.snow_drift_events], 
                                key=[e.start_time.month for e in self.snow_drift_events].count)
            month_names = ["", "jan", "feb", "mar", "apr", "mai", "jun", 
                          "jul", "aug", "sep", "okt", "nov", "des"]
            recommendations.append(f"Mest snøfokk i {month_names[peak_snow_month]}")
        
        if self.slippery_road_events:
            ice_events = [e for e in self.slippery_road_events if e.event_type == 'ice']
            frost_events = [e for e in self.slippery_road_events if e.event_type == 'frost']
            
            recommendations.append(f"Glatte veier: {len(ice_events)} is-hendelser, {len(frost_events)} frost-hendelser")
        
        recommendations.append("Implementer varsling 2-6 timer før forventede hendelser")
        recommendations.append("Øk overvåking når temperatur er mellom -5°C og +2°C")
        
        return recommendations
    
    def save_results(self, output_file: str = None) -> None:
        """Lagre analyseresultater til fil"""
        
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"weather_pattern_analysis_{timestamp}.json"
        
        results = {
            'analysis_date': datetime.now().isoformat(),
            'total_snow_drift_events': len(self.snow_drift_events),
            'total_slippery_road_events': len(self.slippery_road_events),
            'correlations': self.find_correlation_patterns(),
            'optimization_results': self.optimize_combined_parameters(),
            'events_summary': {
                'snow_drift': [
                    {
                        'start_time': e.start_time.isoformat(),
                        'duration_hours': e.duration_hours,
                        'severity_score': e.severity_score,
                        'avg_wind_speed': e.avg_wind_speed,
                        'avg_temperature': e.avg_temperature
                    } for e in self.snow_drift_events[:10]  # De 10 første
                ],
                'slippery_road': [
                    {
                        'start_time': e.start_time.isoformat(),
                        'duration_hours': e.duration_hours,
                        'event_type': e.event_type,
                        'risk_score': e.risk_score,
                        'avg_temperature': e.avg_temperature
                    } for e in self.slippery_road_events[:10]  # De 10 første
                ]
            }
        }
        
        output_path = Path(settings.data_path) / "analyzed" / output_file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Resultater lagret til {output_path}")

def main():
    """Hovedfunksjon for værmønster-optimalisering"""
    
    logger.info("=== WEATHER PATTERN OPTIMIZER ===")
    
    optimizer = WeatherPatternOptimizer()
    
    # Analyser de siste 3 vintersesongene
    current_year = datetime.now().year
    start_year = current_year - 2
    end_year = current_year
    
    # Kjør historisk analyse
    historical_results = optimizer.analyze_historical_seasons(start_year, end_year)
    
    # Finn korrelasjoner
    correlations = optimizer.find_correlation_patterns()
    
    # Optimaliser parametere
    optimization = optimizer.optimize_combined_parameters()
    
    # Vis resultater
    logger.info("\n=== ANALYSERESULTATER ===")
    logger.info(f"Totalt {historical_results['total_snow_events']} snøfokk-hendelser")
    logger.info(f"Totalt {historical_results['total_slippery_events']} glatt vei-hendelser")
    logger.info(f"Overlappende hendelser: {correlations['temporal_overlap']}")
    logger.info(f"Nære hendelser (24h): {correlations['close_proximity']}")
    
    logger.info("\n=== ANBEFALINGER ===")
    for recommendation in optimization.get('recommendations', []):
        logger.info(f"- {recommendation}")
    
    # Lagre resultater
    optimizer.save_results()
    
    logger.info("\nAnalyse fullført!")

if __name__ == '__main__':
    main()
