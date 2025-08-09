#!/usr/bin/env python3
"""
Slippery Road Pattern Analyzer - Analyserer værforhold som fører til glatte veier
"""
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from snofokk.config import settings
from snofokk.services import weather_service
from snofokk.models import WeatherData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SlipperyRoadEvent:
    """Dataklasse for glatt vei-hendelse"""
    start_time: datetime
    end_time: datetime
    duration_hours: float
    
    # Type glatte forhold
    event_type: str  # 'ice', 'frost', 'wet_ice', 'snow_ice'
    
    # Værforhold
    avg_temperature: float
    min_temperature: float
    avg_humidity: float
    precipitation: float
    dew_point: float
    
    # Risikofaktorer
    temperature_drop_rate: float  # °C per time
    freezing_transitions: int     # Antall ganger temp krysser 0°C
    
    risk_score: float
    confidence: float

@dataclass
class SlipperyRoadParameters:
    """Parametere for glatt vei-deteksjon"""
    
    # Temperaturterskler
    freezing_point: float = 0.0      # °C
    frost_threshold: float = 2.0     # °C - risiko for rim/frost
    ice_threshold: float = -2.0      # °C - definitt is
    
    # Luftfuktighet
    high_humidity: float = 85.0      # % - høy risiko
    frost_humidity: float = 90.0     # % - rimfrost-risiko
    
    # Nedbør
    light_rain: float = 0.1          # mm/h - lett regn
    moderate_rain: float = 1.0       # mm/h - moderat regn
    
    # Endringshastigheter
    rapid_temp_drop: float = 2.0     # °C/time - rask temperaturfall
    
    # Minimumskrav
    min_duration: int = 1            # timer
    
    # Vektinger for risk score
    temperature_weight: float = 0.4
    humidity_weight: float = 0.2
    precipitation_weight: float = 0.2
    transition_weight: float = 0.2

class SlipperyRoadAnalyzer:
    """Analyserer værdata for glatt vei-forhold"""
    
    def __init__(self, params: SlipperyRoadParameters = None):
        self.params = params or SlipperyRoadParameters()
        self.events: List[SlipperyRoadEvent] = []
    
    def analyze_period(
        self,
        start_date: datetime,
        end_date: datetime,
        station: str = "SN46220"
    ) -> List[SlipperyRoadEvent]:
        """Analyser periode for glatt vei-hendelser"""
        
        logger.info(f"Analyserer glatt vei-forhold {start_date.strftime('%Y-%m-%d')} til {end_date.strftime('%Y-%m-%d')}")
        
        # Hent værdata
        df = weather_service.fetch_weather_data(
            station=station,
            from_time=start_date.isoformat(),
            to_time=end_date.isoformat(),
            client_id=settings.frost_client_id
        )
        
        if df is None or df.empty:
            logger.warning("Ingen værdata tilgjengelig")
            return []
        
        # Preprosesser data for glatt vei-analyse
        df = self._preprocess_for_slippery_analysis(df)
        
        # Identifiser glatt vei-hendelser
        events = self._identify_slippery_events(df)
        
        logger.info(f"Funnet {len(events)} potensielle glatt vei-hendelser")
        return events
    
    def _preprocess_for_slippery_analysis(self, df: WeatherData) -> WeatherData:
        """Preprosesser data for glatt vei-analyse"""
        
        df = df.copy()
        
        # Beregn temperaturdropphastighet
        if 'air_temperature' in df.columns:
            df['temp_drop_rate'] = -df['air_temperature'].diff()  # Negativt = fall
            df['temp_drop_rate_per_hour'] = df['temp_drop_rate'] # Antar timedata
        
        # Tell frysepunktoverganger
        if 'air_temperature' in df.columns:
            df['below_freezing'] = df['air_temperature'] <= self.params.freezing_point
            df['freezing_transition'] = df['below_freezing'].astype(int).diff().abs()
        
        # Beregn duggpunkt (forenklet estimat)
        if 'air_temperature' in df.columns and 'relative_humidity' in df.columns:
            df['dew_point'] = self._calculate_dew_point(
                df['air_temperature'], 
                df['relative_humidity']
            )
        
        # Identifiser risikoperioder
        df['ice_risk'] = self._calculate_ice_risk(df)
        df['frost_risk'] = self._calculate_frost_risk(df)
        df['wet_ice_risk'] = self._calculate_wet_ice_risk(df)
        
        # Samlet glatt vei-risiko
        df['slippery_risk'] = (
            df.get('ice_risk', 0) | 
            df.get('frost_risk', 0) | 
            df.get('wet_ice_risk', 0)
        )
        
        return df
    
    def _calculate_dew_point(self, temp: pd.Series, humidity: pd.Series) -> pd.Series:
        """Beregn duggpunkt (Magnus-formel, forenklet)"""
        
        # Magnus-formel konstanter
        a = 17.27
        b = 237.7
        
        def magnus_formula(T, RH):
            alpha = ((a * T) / (b + T)) + np.log(RH / 100.0)
            return (b * alpha) / (a - alpha)
        
        return temp.combine(humidity, magnus_formula)
    
    def _calculate_ice_risk(self, df: pd.DataFrame) -> pd.Series:
        """Beregn risiko for isdannelse"""
        
        temp_risk = df.get('air_temperature', 10) <= self.params.ice_threshold
        humidity_risk = df.get('relative_humidity', 0) >= self.params.high_humidity
        
        return temp_risk & humidity_risk
    
    def _calculate_frost_risk(self, df: pd.DataFrame) -> pd.Series:
        """Beregn risiko for rimfrost"""
        
        temp_in_range = (
            (df.get('air_temperature', 10) <= self.params.frost_threshold) &
            (df.get('air_temperature', 10) > self.params.ice_threshold)
        )
        high_humidity = df.get('relative_humidity', 0) >= self.params.frost_humidity
        clear_sky = df.get('sum(precipitation_amount PT1H)', 1) < 0.1  # Lite/ingen nedbør
        
        return temp_in_range & high_humidity & clear_sky
    
    def _calculate_wet_ice_risk(self, df: pd.DataFrame) -> pd.Series:
        """Beregn risiko for våt is (underkjølt regn)"""
        
        temp_below_freezing = df.get('air_temperature', 10) <= self.params.freezing_point
        precipitation = df.get('sum(precipitation_amount PT1H)', 0) >= self.params.light_rain
        rapid_cooling = df.get('temp_drop_rate_per_hour', 0) >= self.params.rapid_temp_drop
        
        return temp_below_freezing & precipitation & rapid_cooling
    
    def _identify_slippery_events(self, df: WeatherData) -> List[SlipperyRoadEvent]:
        """Identifiser glatt vei-hendelser"""
        
        events = []
        
        # Finn perioder med glatt vei-risiko
        risk_periods = self._find_risk_periods(df, 'slippery_risk')
        
        for period in risk_periods:
            event = self._create_slippery_event(df, period)
            if event and event.duration_hours >= self.params.min_duration:
                events.append(event)
        
        return events
    
    def _find_risk_periods(self, df: WeatherData, column: str) -> List[Tuple[int, int]]:
        """Finn perioder med kontinuerlig risiko"""
        
        periods = []
        in_period = False
        start_idx = None
        
        for idx, value in enumerate(df[column]):
            if value and not in_period:
                start_idx = idx
                in_period = True
            elif not value and in_period:
                periods.append((start_idx, idx - 1))
                in_period = False
        
        if in_period:
            periods.append((start_idx, len(df) - 1))
        
        return periods
    
    def _create_slippery_event(
        self, 
        df: WeatherData, 
        period: Tuple[int, int]
    ) -> Optional[SlipperyRoadEvent]:
        """Opprett SlipperyRoadEvent fra dataperiode"""
        
        start_idx, end_idx = period
        period_data = df.iloc[start_idx:end_idx + 1]
        
        if period_data.empty:
            return None
        
        try:
            # Tidsdata
            start_time = period_data['referenceTime'].iloc[0]
            end_time = period_data['referenceTime'].iloc[-1]
            duration = (end_time - start_time).total_seconds() / 3600
            
            # Identifiser hendelsestype
            event_type = self._determine_event_type(period_data)
            
            # Beregn statistikk
            temp_data = period_data.get('air_temperature', pd.Series([0]))
            humidity_data = period_data.get('relative_humidity', pd.Series([0]))
            precip_data = period_data.get('sum(precipitation_amount PT1H)', pd.Series([0]))
            dew_point_data = period_data.get('dew_point', pd.Series([0]))
            temp_drop_data = period_data.get('temp_drop_rate_per_hour', pd.Series([0]))
            
            # Tell frysepunktoverganger
            freezing_transitions = period_data.get('freezing_transition', pd.Series([0])).sum()
            
            # Beregn risikoscore
            risk_score = self._calculate_risk_score(period_data)
            confidence = self._calculate_event_confidence(period_data, duration)
            
            return SlipperyRoadEvent(
                start_time=start_time,
                end_time=end_time,
                duration_hours=duration,
                event_type=event_type,
                avg_temperature=temp_data.mean(),
                min_temperature=temp_data.min(),
                avg_humidity=humidity_data.mean(),
                precipitation=precip_data.sum(),
                dew_point=dew_point_data.mean(),
                temperature_drop_rate=temp_drop_data.max(),
                freezing_transitions=int(freezing_transitions),
                risk_score=risk_score,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Feil ved opprettelse av glatt vei-hendelse: {e}")
            return None
    
    def _determine_event_type(self, period_data: pd.DataFrame) -> str:
        """Bestem type glatt vei-hendelse"""
        
        has_ice_risk = period_data.get('ice_risk', pd.Series([False])).any()
        has_frost_risk = period_data.get('frost_risk', pd.Series([False])).any()
        has_wet_ice_risk = period_data.get('wet_ice_risk', pd.Series([False])).any()
        
        if has_wet_ice_risk:
            return 'wet_ice'
        elif has_ice_risk:
            return 'ice'
        elif has_frost_risk:
            return 'frost'
        else:
            return 'unknown'
    
    def _calculate_risk_score(self, period_data: pd.DataFrame) -> float:
        """Beregn risikoscore for glatt vei-hendelse"""
        
        # Temperaturkomponent
        min_temp = period_data.get('air_temperature', pd.Series([10])).min()
        if min_temp <= -5:
            temp_score = 100
        elif min_temp <= 0:
            temp_score = 80 + (min_temp * 4)  # Linear fra 80 til 100
        elif min_temp <= 2:
            temp_score = 40 + ((2 - min_temp) * 20)  # Fra 40 til 80
        else:
            temp_score = 20
        
        # Fuktighetskomponent
        avg_humidity = period_data.get('relative_humidity', pd.Series([0])).mean()
        humidity_score = min(100, avg_humidity)
        
        # Nedbørkomponent
        total_precip = period_data.get('sum(precipitation_amount PT1H)', pd.Series([0])).sum()
        if total_precip > 5:
            precip_score = 100
        elif total_precip > 1:
            precip_score = 60 + (total_precip * 8)
        else:
            precip_score = total_precip * 60
        
        # Overgangskomponent
        transitions = period_data.get('freezing_transition', pd.Series([0])).sum()
        transition_score = min(100, transitions * 25)
        
        # Vektet score
        total_score = (
            temp_score * self.params.temperature_weight +
            humidity_score * self.params.humidity_weight +
            precip_score * self.params.precipitation_weight +
            transition_score * self.params.transition_weight
        )
        
        return round(total_score, 1)
    
    def _calculate_event_confidence(self, period_data: pd.DataFrame, duration: float) -> float:
        """Beregn konfidensgrad"""
        
        confidence = 70  # Base confidence
        
        # Øk for lengre varighet
        if duration > 6:
            confidence += min(20, (duration - 6) * 2)
        
        # Reduser for manglende data
        missing_ratio = period_data.isnull().sum().sum() / (len(period_data) * len(period_data.columns))
        confidence -= missing_ratio * 30
        
        # Øk for flere risikotyper samtidig
        risk_types = [
            period_data.get('ice_risk', pd.Series([False])).any(),
            period_data.get('frost_risk', pd.Series([False])).any(),
            period_data.get('wet_ice_risk', pd.Series([False])).any()
        ]
        active_risks = sum(risk_types)
        confidence += active_risks * 10
        
        return max(20, min(100, confidence))

def analyze_winter_slippery_conditions(year: int, station: str = "SN46220") -> List[SlipperyRoadEvent]:
    """Analyser vintersesong for glatte vei-forhold"""
    
    start_date = datetime(year - 1, 10, 1)  # Oktober til april
    end_date = datetime(year, 4, 30)
    
    analyzer = SlipperyRoadAnalyzer()
    events = analyzer.analyze_period(start_date, end_date, station)
    
    return events

def main():
    """Hovedfunksjon for glatt vei-analyse"""
    
    logger.info("=== SLIPPERY ROAD PATTERN ANALYZER ===")
    
    current_year = datetime.now().year
    events = analyze_winter_slippery_conditions(current_year)
    
    if events:
        logger.info(f"\nFunnet {len(events)} glatt vei-hendelser:")
        
        # Grupper etter type
        event_types = {}
        for event in events:
            if event.event_type not in event_types:
                event_types[event.event_type] = []
            event_types[event.event_type].append(event)
        
        for event_type, type_events in event_types.items():
            logger.info(f"\n{event_type.upper()} hendelser ({len(type_events)}):")
            
            for i, event in enumerate(type_events[:5], 1):  # Vis de 5 første
                logger.info(f"\n  Hendelse {i}:")
                logger.info(f"    Tid: {event.start_time.strftime('%Y-%m-%d %H:%M')} - {event.end_time.strftime('%Y-%m-%d %H:%M')}")
                logger.info(f"    Varighet: {event.duration_hours:.1f} timer")
                logger.info(f"    Temperatur: {event.avg_temperature:.1f}°C (min {event.min_temperature:.1f})")
                logger.info(f"    Luftfuktighet: {event.avg_humidity:.1f}%")
                logger.info(f"    Nedbør: {event.precipitation:.1f} mm")
                logger.info(f"    Frysepunktoverganger: {event.freezing_transitions}")
                logger.info(f"    Risikoscore: {event.risk_score:.1f}/100")
                logger.info(f"    Confidence: {event.confidence:.1f}%")
    else:
        logger.info("Ingen glatt vei-hendelser funnet")

if __name__ == '__main__':
    main()
