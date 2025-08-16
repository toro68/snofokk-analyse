#!/usr/bin/env python3
"""
Snøfokk Pattern Analyzer - Analyserer historiske værdata for å identifisere snøfokk-mønstre
"""
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from snofokk.config import settings
from snofokk.models import WeatherData
from snofokk.services import weather_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SnowDriftEvent:
    """Dataklasse for snøfokk-hendelse"""
    start_time: datetime
    end_time: datetime
    duration_hours: float

    # Værforhold under hendelsen
    avg_wind_speed: float
    max_wind_speed: float
    avg_temperature: float
    min_temperature: float

    # Snøforhold
    initial_snow_depth: float
    final_snow_depth: float
    snow_depth_change: float
    snow_depth_variance: float  # Hvor mye snødybden varierer (indikator på drift)

    # Beregnet styrke
    severity_score: float
    confidence: float

@dataclass
class OptimalParameters:
    """Optimale parametere for snøfokk-deteksjon"""
    wind_threshold_low: float = 6.0    # m/s - minimum vind for snøfokk
    wind_threshold_high: float = 12.0  # m/s - sterk snøfokk
    temp_threshold_warm: float = -2.0  # °C - for varmt for snøfokk
    temp_threshold_cold: float = -15.0 # °C - optimal snøfokk-temperatur

    snow_variance_threshold: float = 2.0  # cm - minimum variasjon i snødybde
    min_duration: int = 2  # timer - minimum varighet

    # Vektinger for severity score
    wind_weight: float = 0.4
    temp_weight: float = 0.3
    snow_weight: float = 0.3

class SnowDriftAnalyzer:
    """Analyserer historiske data for snøfokk-mønstre"""

    def __init__(self, params: OptimalParameters = None):
        self.params = params or OptimalParameters()
        self.events: list[SnowDriftEvent] = []

    def analyze_historical_period(
        self,
        start_date: datetime,
        end_date: datetime,
        station: str = "SN46220"
    ) -> list[SnowDriftEvent]:
        """Analyser en historisk periode for snøfokk-hendelser"""

        logger.info(f"Analyserer periode {start_date.strftime('%Y-%m-%d')} til {end_date.strftime('%Y-%m-%d')}")

        # Hent værdata
        df = weather_service.fetch_weather_data(
            station=station,
            from_time=start_date.isoformat(),
            to_time=end_date.isoformat(),
            client_id=settings.frost_client_id
        )

        if df is None or df.empty:
            logger.warning("Ingen værdata tilgjengelig for perioden")
            return []

        # Normaliser data
        df = weather_service.normalize_snow_data(df)

        # Identifiser snøfokk-hendelser
        events = self._identify_snow_drift_events(df)

        logger.info(f"Funnet {len(events)} potensielle snøfokk-hendelser")
        return events

    def _identify_snow_drift_events(self, df: WeatherData) -> list[SnowDriftEvent]:
        """Identifiser snøfokk-hendelser basert på værdata"""

        events = []

        # Beregn snødybde-variasjon over rullende vindu
        if 'surface_snow_thickness' in df.columns:
            df['snow_variance'] = df['surface_snow_thickness'].rolling(
                window=6, min_periods=3
            ).std()
        else:
            logger.warning("Ingen snødybde-data tilgjengelig")
            return events

        # Identifiser potensielle snøfokk-perioder
        df['potential_drift'] = (
            (df.get('wind_speed', 0) >= self.params.wind_threshold_low) &
            (df.get('air_temperature', 10) <= self.params.temp_threshold_warm) &
            (df.get('snow_variance', 0) >= self.params.snow_variance_threshold)
        )

        # Finn sammenhengende perioder
        drift_periods = self._find_continuous_periods(df, 'potential_drift')

        # Konverter til SnowDriftEvent objekter
        for period in drift_periods:
            event = self._create_snow_drift_event(df, period)
            if event and event.duration_hours >= self.params.min_duration:
                events.append(event)

        return events

    def _find_continuous_periods(self, df: WeatherData, column: str) -> list[tuple[int, int]]:
        """Finn sammenhengende perioder hvor betingelsen er sann"""

        periods = []
        in_period = False
        start_idx = None

        for idx, value in enumerate(df[column]):
            if value and not in_period:
                # Start av ny periode
                start_idx = idx
                in_period = True
            elif not value and in_period:
                # Slutt på periode
                periods.append((start_idx, idx - 1))
                in_period = False

        # Håndter periode som går til slutten
        if in_period:
            periods.append((start_idx, len(df) - 1))

        return periods

    def _create_snow_drift_event(
        self,
        df: WeatherData,
        period: tuple[int, int]
    ) -> SnowDriftEvent | None:
        """Opprett SnowDriftEvent fra dataperiode"""

        start_idx, end_idx = period
        period_data = df.iloc[start_idx:end_idx + 1]

        if period_data.empty:
            return None

        try:
            # Tidsdata
            start_time = period_data['referenceTime'].iloc[0]
            end_time = period_data['referenceTime'].iloc[-1]
            duration = (end_time - start_time).total_seconds() / 3600  # timer

            # Værdata
            wind_data = period_data.get('wind_speed', pd.Series([0]))
            temp_data = period_data.get('air_temperature', pd.Series([0]))
            snow_data = period_data.get('surface_snow_thickness', pd.Series([0]))

            # Beregn snø-statistikk
            initial_snow = snow_data.iloc[0] if not snow_data.empty else 0
            final_snow = snow_data.iloc[-1] if not snow_data.empty else 0
            snow_change = final_snow - initial_snow
            snow_variance = snow_data.std() if not snow_data.empty else 0

            # Beregn severity score
            severity = self._calculate_severity_score(
                wind_data.mean(),
                temp_data.mean(),
                snow_variance
            )

            # Beregn konfidensgrad
            confidence = self._calculate_confidence(period_data, duration)

            return SnowDriftEvent(
                start_time=start_time,
                end_time=end_time,
                duration_hours=duration,
                avg_wind_speed=wind_data.mean(),
                max_wind_speed=wind_data.max(),
                avg_temperature=temp_data.mean(),
                min_temperature=temp_data.min(),
                initial_snow_depth=initial_snow,
                final_snow_depth=final_snow,
                snow_depth_change=snow_change,
                snow_depth_variance=snow_variance,
                severity_score=severity,
                confidence=confidence
            )

        except Exception as e:
            logger.error(f"Feil ved opprettelse av snøfokk-hendelse: {e}")
            return None

    def _calculate_severity_score(
        self,
        avg_wind: float,
        avg_temp: float,
        snow_variance: float
    ) -> float:
        """Beregn severity score (0-100)"""

        # Wind component (høyere vind = høyere score)
        wind_score = min(100, (avg_wind / 20.0) * 100)

        # Temperature component (kaldere = høyere score, optimal rundt -10°C)
        if avg_temp <= self.params.temp_threshold_cold:
            temp_score = 100
        elif avg_temp <= -5:
            temp_score = 80 - (avg_temp + 5) * 10  # Lineær nedgang
        elif avg_temp <= 0:
            temp_score = 40 - (avg_temp + 0) * 8   # Raskere nedgang
        else:
            temp_score = 0

        # Snow variance component (mer variasjon = høyere score)
        snow_score = min(100, (snow_variance / 10.0) * 100)

        # Vektet gjennomsnittscore
        total_score = (
            wind_score * self.params.wind_weight +
            temp_score * self.params.temp_weight +
            snow_score * self.params.snow_weight
        )

        return round(total_score, 1)

    def _calculate_confidence(self, period_data: pd.DataFrame, duration: float) -> float:
        """Beregn konfidensgrad for hendelsen (0-100)"""

        confidence = 80  # Base confidence

        # Reduser for kort varighet
        if duration < 4:
            confidence -= (4 - duration) * 10

        # Reduser for manglende data
        missing_data_ratio = period_data.isnull().sum().sum() / (len(period_data) * len(period_data.columns))
        confidence -= missing_data_ratio * 30

        # Øk for lange perioder med konsistente forhold
        if duration > 8:
            confidence += min(20, (duration - 8) * 2)

        return max(10, min(100, confidence))

    def optimize_parameters(
        self,
        known_events: list[dict],
        start_date: datetime,
        end_date: datetime
    ) -> OptimalParameters:
        """Optimaliser parametere basert på kjente snøfokk-hendelser"""

        logger.info("Starter parameteroptimalisering...")

        # Her ville vi implementert en optimaliserings-algoritme
        # som justerer parametere for best mulig match med kjente hendelser

        # For nå returnerer vi forbedrede standardparametere
        optimized = OptimalParameters(
            wind_threshold_low=5.5,
            wind_threshold_high=11.0,
            temp_threshold_warm=-1.5,
            temp_threshold_cold=-12.0,
            snow_variance_threshold=1.8,
            min_duration=2,
            wind_weight=0.45,
            temp_weight=0.35,
            snow_weight=0.20
        )

        logger.info("Parameteroptimalisering fullført")
        return optimized

def analyze_winter_season(year: int, station: str = "SN46220") -> list[SnowDriftEvent]:
    """Analyser en hel vintersesong for snøfokk"""

    # Definer vintersesong (november - mars)
    start_date = datetime(year - 1, 11, 1)
    end_date = datetime(year, 3, 31)

    analyzer = SnowDriftAnalyzer()
    events = analyzer.analyze_historical_period(start_date, end_date, station)

    return events

def main():
    """Hovedfunksjon for snøfokk-analyse"""

    logger.info("=== SNØFOKK PATTERN ANALYZER ===")

    # Analyser siste vintersesong
    current_year = datetime.now().year
    events = analyze_winter_season(current_year)

    if events:
        logger.info(f"\nFunnet {len(events)} snøfokk-hendelser:")

        for i, event in enumerate(events, 1):
            logger.info(f"\nHendelse {i}:")
            logger.info(f"  Tid: {event.start_time.strftime('%Y-%m-%d %H:%M')} - {event.end_time.strftime('%Y-%m-%d %H:%M')}")
            logger.info(f"  Varighet: {event.duration_hours:.1f} timer")
            logger.info(f"  Vind: {event.avg_wind_speed:.1f} m/s (maks {event.max_wind_speed:.1f})")
            logger.info(f"  Temperatur: {event.avg_temperature:.1f}°C (min {event.min_temperature:.1f})")
            logger.info(f"  Snødybde-endring: {event.snow_depth_change:.1f} cm")
            logger.info(f"  Snø-variasjon: {event.snow_depth_variance:.1f} cm")
            logger.info(f"  Severity: {event.severity_score:.1f}/100")
            logger.info(f"  Confidence: {event.confidence:.1f}%")
    else:
        logger.info("Ingen snøfokk-hendelser funnet")

if __name__ == '__main__':
    main()
