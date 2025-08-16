#!/usr/bin/env python3
"""
Utvidet WeatherService som utnytter alle tilgjengelige data fra Gullingen værstasjon.
Demonstrerer hvordan vi kan forbedre datautnyttelsen betydelig.
"""
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
from pathlib import Path
import sys

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from snofokk.config import settings


@dataclass
class EnhancedWeatherData:
    """Utvidet værdata med alle tilgjengelige elementer"""
    timestamp: datetime
    
    # Grunnleggende data
    air_temperature: Optional[float] = None
    surface_temperature: Optional[float] = None
    surface_snow_thickness: Optional[float] = None
    
    # Vind (utvidet)
    wind_speed: Optional[float] = None
    wind_from_direction: Optional[float] = None
    max_wind_speed_hourly: Optional[float] = None
    max_wind_gust_hourly: Optional[float] = None
    wind_direction_at_max_speed: Optional[float] = None
    
    # Nedbør (utvidet)
    precipitation_amount_hourly: Optional[float] = None
    precipitation_amount_10min: Optional[float] = None
    precipitation_duration_hourly: Optional[float] = None
    precipitation_duration_10min: Optional[float] = None
    accumulated_precipitation: Optional[float] = None
    
    # Fuktighet og duggpunkt
    relative_humidity: Optional[float] = None
    dew_point_temperature: Optional[float] = None
    
    # Beregnede verdier
    wind_chill: Optional[float] = None
    blowing_snow_risk: Optional[float] = None
    ice_formation_risk: Optional[float] = None
    visibility_estimate: Optional[float] = None


class EnhancedWeatherService:
    """Forbedret værservice som henter alle tilgjengelige data fra Gullingen"""
    
    # Element konstanter
    MAX_WIND_SPEED_1H = 'max(wind_speed PT1H)'
    MAX_WIND_GUST_1H = 'max(wind_speed_of_gust PT1H)'
    WIND_DIR_AT_MAX = 'max_wind_speed(wind_from_direction PT1H)'
    PRECIP_AMOUNT_1H = 'sum(precipitation_amount PT1H)'
    PRECIP_AMOUNT_10M = 'sum(precipitation_amount PT10M)'
    PRECIP_DURATION_1H = 'sum(duration_of_precipitation PT1H)'
    PRECIP_DURATION_10M = 'sum(duration_of_precipitation PT10M)'
    ACCUMULATED_PRECIP = 'accumulated(precipitation_amount)'
    
    def __init__(self):
        self.station_id = 'SN46220'
        self.base_url = 'https://frost.met.no/observations/v0.jsonld'
        
        # Alle tilgjengelige elementer med høy tidsoppløsning
        self.enhanced_elements = [
            # Grunnleggende elementer (høy oppløsning)
            'air_temperature',              # PT1H, PT10M
            'surface_temperature',          # PT1H, PT10M
            'surface_snow_thickness',       # PT1H, PT10M
            'relative_humidity',            # PT1H
            'dew_point_temperature',        # PT1H
            
            # Vind (alle aspekter)
            'wind_speed',                   # PT1H
            'wind_from_direction',          # PT1H
            self.MAX_WIND_SPEED_1H,         # Maksimal vindstyrke per time
            self.MAX_WIND_GUST_1H,          # Maksimal vindkast per time
            self.WIND_DIR_AT_MAX,           # Retning ved maks vind
            
            # Nedbør (detaljert)
            self.PRECIP_AMOUNT_1H,          # Timeakkumulert
            self.PRECIP_AMOUNT_10M,         # 10-min akkumulert
            self.PRECIP_DURATION_1H,        # Nedbørvarighet per time
            self.PRECIP_DURATION_10M,       # Nedbørvarighet per 10 min
            self.ACCUMULATED_PRECIP,        # Akkumulert total
            
            # Temperaturdetaljer
            'min(air_temperature PT1H)',    # Min temp per time
            'max(air_temperature PT1H)',    # Max temp per time
        ]
    
    async def get_enhanced_weather_data(
        self, 
        start_time: datetime, 
        end_time: datetime,
        time_resolution: str = 'PT1H'
    ) -> List[EnhancedWeatherData]:
        """Hent utvidet værdata med alle tilgjengelige elementer"""
        
        async with aiohttp.ClientSession() as session:
            # Hent data for alle elementer
            all_data = {}
            
            # Grupper elementer for effektive API-kall
            element_groups = self._group_elements_by_resolution()
            
            for resolution, elements in element_groups.items():
                if resolution == time_resolution or time_resolution == 'ALL':
                    data = await self._fetch_element_group(
                        session, elements, start_time, end_time, resolution
                    )
                    all_data.update(data)
            
            # Kombiner til EnhancedWeatherData objekter
            return self._combine_to_enhanced_data(all_data, start_time, end_time)
    
    async def get_real_time_conditions(self) -> Dict[str, float]:
        """Hent sanntids værforhold med alle tilgjengelige detaljer"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=2)
        
        data = await self.get_enhanced_weather_data(start_time, end_time)
        
        if not data:
            return {}
        
        latest = data[-1]
        
        # Beregn risikoindikatorer
        conditions = {
            'timestamp': latest.timestamp.isoformat(),
            
            # Grunnleggende
            'air_temperature': latest.air_temperature,
            'surface_temperature': latest.surface_temperature,
            'snow_depth': latest.surface_snow_thickness,
            'humidity': latest.relative_humidity,
            
            # Vind (detaljert)
            'wind_speed': latest.wind_speed,
            'wind_direction': latest.wind_from_direction,
            'max_wind_speed': latest.max_wind_speed_hourly,
            'max_wind_gust': latest.max_wind_gust_hourly,
            'wind_direction_at_max': latest.wind_direction_at_max_speed,
            
            # Nedbør (detaljert)
            'precipitation_hourly': latest.precipitation_amount_hourly,
            'precipitation_duration': latest.precipitation_duration_hourly,
            'accumulated_precipitation': latest.accumulated_precipitation,
            
            # Risikoindikatorer
            'wind_chill': latest.wind_chill,
            'blowing_snow_risk': latest.blowing_snow_risk,
            'ice_formation_risk': latest.ice_formation_risk,
            'visibility_estimate': latest.visibility_estimate,
        }
        
        return {k: v for k, v in conditions.items() if v is not None}
    
    async def analyze_snowdrift_conditions(
        self, 
        hours_back: int = 6
    ) -> Dict[str, any]:
        """Detaljert snøfokk-analyse med alle tilgjengelige data"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours_back)
        
        data = await self.get_enhanced_weather_data(start_time, end_time)
        
        if not data:
            return {'error': 'Ingen data tilgjengelig'}
        
        # Konverter til DataFrame for analyse
        df = pd.DataFrame([
            {
                'timestamp': d.timestamp,
                'wind_speed': d.wind_speed,
                'max_wind_gust': d.max_wind_gust_hourly,
                'wind_direction': d.wind_from_direction,
                'air_temp': d.air_temperature,
                'surface_temp': d.surface_temperature,
                'snow_depth': d.surface_snow_thickness,
                'humidity': d.relative_humidity,
                'precipitation': d.precipitation_amount_hourly,
                'wind_chill': d.wind_chill,
                'blowing_snow_risk': d.blowing_snow_risk
            } for d in data
        ])
        
        # Detaljert analyse
        analysis = {
            'period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'hours': hours_back,
                'data_points': len(df)
            },
            
            # Vindforhold
            'wind_analysis': {
                'avg_speed': df['wind_speed'].mean(),
                'max_speed': df['wind_speed'].max(),
                'max_gust': df['max_wind_gust'].max(),
                'speed_consistency': df['wind_speed'].std(),
                'direction_variability': df['wind_direction'].std(),
                'hours_above_threshold': (df['wind_speed'] > 8).sum(),
                'gust_factor': df['max_wind_gust'].max() / df['wind_speed'].mean() if df['wind_speed'].mean() > 0 else 0
            },
            
            # Temperaturforhold
            'temperature_analysis': {
                'avg_air_temp': df['air_temp'].mean(),
                'avg_surface_temp': df['surface_temp'].mean(),
                'temp_range': df['air_temp'].max() - df['air_temp'].min(),
                'surface_air_diff': (df['surface_temp'] - df['air_temp']).mean(),
                'freezing_hours': (df['air_temp'] <= 0).sum(),
                'wind_chill_avg': df['wind_chill'].mean()
            },
            
            # Snøforhold
            'snow_analysis': {
                'avg_depth': df['snow_depth'].mean(),
                'depth_change': df['snow_depth'].iloc[-1] - df['snow_depth'].iloc[0] if len(df) > 1 else 0,
                'snow_available': df['snow_depth'].mean() > 5,
                'new_snow': (df['precipitation'] > 0).sum()
            },
            
            # Risikovurdering
            'risk_assessment': {
                'blowing_snow_hours': (df['blowing_snow_risk'] > 0.5).sum(),
                'combined_risk_score': self._calculate_combined_risk(df),
                'visibility_impact': self._estimate_visibility_impact(df),
                'road_condition_risk': self._assess_road_conditions(df)
            },
            
            # Prediksjoner
            'predictions': {
                'next_hour_risk': self._predict_next_hour_risk(df),
                'deterioration_trend': self._calculate_deterioration_trend(df),
                'recommended_action': self._recommend_action(df)
            }
        }
        
        return analysis
    
    def _group_elements_by_resolution(self) -> Dict[str, List[str]]:
        """Grupper elementer etter tidsoppløsning for effektive API-kall"""
        return {
            'PT1H': [
                'air_temperature', 'surface_temperature', 'surface_snow_thickness',
                'wind_speed', 'wind_from_direction', 'relative_humidity',
                'dew_point_temperature', self.MAX_WIND_SPEED_1H,
                self.MAX_WIND_GUST_1H, self.PRECIP_AMOUNT_1H,
                self.PRECIP_DURATION_1H, 'min(air_temperature PT1H)',
                'max(air_temperature PT1H)', self.WIND_DIR_AT_MAX
            ],
            'PT10M': [
                'air_temperature', 'surface_temperature', 'surface_snow_thickness',
                self.PRECIP_AMOUNT_10M, self.PRECIP_DURATION_10M,
                self.ACCUMULATED_PRECIP
            ]
        }
    
    async def _fetch_element_group(
        self, 
        session: aiohttp.ClientSession,
        elements: List[str],
        start_time: datetime,
        end_time: datetime,
        resolution: str
    ) -> Dict[str, pd.DataFrame]:
        """Hent en gruppe elementer fra Frost API"""
        
        params = {
            'sources': self.station_id,
            'elements': ','.join(elements),
            'referencetime': f"{start_time.isoformat()}/{end_time.isoformat()}",
            'timeresolutions': resolution
        }
        
        headers = {'Accept': 'application/json'}
        auth = aiohttp.BasicAuth(settings.frost_client_id, '')
        
        try:
            async with session.get(self.base_url, params=params, headers=headers, auth=auth) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_frost_response(data)
                else:
                    print(f"API-feil {response.status} for elementer: {elements[:3]}...")
                    return {}
        
        except Exception as e:
            print(f"Feil ved henting av {elements[:3]}...: {e}")
            return {}
    
    def _parse_frost_response(self, response_data: Dict) -> Dict[str, pd.DataFrame]:
        """Parse Frost API response til strukturert data"""
        observations = response_data.get('data', [])
        
        element_data = {}
        
        for obs in observations:
            element_id = obs.get('elementId')
            timestamp = pd.to_datetime(obs.get('referenceTime'))
            value = obs.get('observations', [{}])[0].get('value')
            
            if element_id not in element_data:
                element_data[element_id] = []
            
            element_data[element_id].append({
                'timestamp': timestamp,
                'value': float(value) if value is not None else None
            })
        
        # Konverter til DataFrames
        result = {}
        for element_id, data_list in element_data.items():
            if data_list:
                df = pd.DataFrame(data_list)
                df = df.sort_values('timestamp').reset_index(drop=True)
                result[element_id] = df
        
        return result
    
    def _combine_to_enhanced_data(
        self, 
        all_data: Dict[str, pd.DataFrame],
        start_time: datetime,
        end_time: datetime
    ) -> List[EnhancedWeatherData]:
        """Kombiner alle dataelementer til EnhancedWeatherData objekter"""
        
        # Opprett tidsindex
        time_range = pd.date_range(start_time, end_time, freq='1H')
        
        result = []
        
        for timestamp in time_range:
            # Hent verdier for hvert element på dette tidspunktet
            data_point = EnhancedWeatherData(timestamp=timestamp)
            
            # Map elementnavn til attributter
            element_mapping = {
                'air_temperature': 'air_temperature',
                'surface_temperature': 'surface_temperature',
                'surface_snow_thickness': 'surface_snow_thickness',
                'wind_speed': 'wind_speed',
                'wind_from_direction': 'wind_from_direction',
                self.MAX_WIND_SPEED_1H: 'max_wind_speed_hourly',
                self.MAX_WIND_GUST_1H: 'max_wind_gust_hourly',
                self.WIND_DIR_AT_MAX: 'wind_direction_at_max_speed',
                self.PRECIP_AMOUNT_1H: 'precipitation_amount_hourly',
                self.PRECIP_AMOUNT_10M: 'precipitation_amount_10min',
                self.PRECIP_DURATION_1H: 'precipitation_duration_hourly',
                self.PRECIP_DURATION_10M: 'precipitation_duration_10min',
                self.ACCUMULATED_PRECIP: 'accumulated_precipitation',
                'relative_humidity': 'relative_humidity',
                'dew_point_temperature': 'dew_point_temperature'
            }
            
            # Sett verdier fra data
            for element_id, attr_name in element_mapping.items():
                if element_id in all_data:
                    df = all_data[element_id]
                    # Finn nærmeste verdi i tid
                    closest_idx = (df['timestamp'] - timestamp).abs().idxmin()
                    value = df.loc[closest_idx, 'value']
                    setattr(data_point, attr_name, value)
            
            # Beregn utledede verdier
            data_point.wind_chill = self._calculate_wind_chill(
                data_point.air_temperature, data_point.wind_speed
            )
            data_point.blowing_snow_risk = self._calculate_blowing_snow_risk(data_point)
            data_point.ice_formation_risk = self._calculate_ice_formation_risk(data_point)
            data_point.visibility_estimate = self._estimate_visibility(data_point)
            
            result.append(data_point)
        
        return result
    
    def _calculate_wind_chill(self, temp: Optional[float], wind: Optional[float]) -> Optional[float]:
        """Beregn vindavkjøling"""
        if temp is None or wind is None:
            return None
        return temp - (wind * 0.5)
    
    def _calculate_blowing_snow_risk(self, data: EnhancedWeatherData) -> Optional[float]:
        """Beregn risiko for snøfokk basert på alle tilgjengelige faktorer"""
        if (data.wind_speed is None or data.surface_snow_thickness is None or 
            data.air_temperature is None):
            return None
        
        risk = 0.0
        
        # Vindstyrke (hovedfaktor)
        if data.wind_speed > 8:
            risk += 0.4
        elif data.wind_speed > 5:
            risk += 0.2
        
        # Vindkast
        if data.max_wind_gust_hourly and data.max_wind_gust_hourly > 12:
            risk += 0.2
        
        # Snødybde
        if data.surface_snow_thickness > 10:
            risk += 0.3
        elif data.surface_snow_thickness > 5:
            risk += 0.15
        
        # Temperatur (tørr snø blåser lettere)
        if data.air_temperature < -5:
            risk += 0.1
        elif data.air_temperature > 2:
            risk -= 0.2  # Våt snø blåser mindre
        
        return min(max(risk, 0.0), 1.0)
    
    def _calculate_ice_formation_risk(self, data: EnhancedWeatherData) -> Optional[float]:
        """Beregn risiko for isdannelse"""
        if (data.air_temperature is None or data.surface_temperature is None or 
            data.relative_humidity is None):
            return None
        
        risk = 0.0
        
        # Temperatur nær frysepunktet
        if data.air_temperature <= 0 and data.air_temperature > -3:
            risk += 0.4
        
        # Overflatetemperatur under lufttemperatur
        if data.surface_temperature < data.air_temperature:
            risk += 0.3
        
        # Høy fuktighet
        if data.relative_humidity > 85:
            risk += 0.3
        
        return min(risk, 1.0)
    
    def _estimate_visibility(self, data: EnhancedWeatherData) -> Optional[float]:
        """Estimer siktbarhet basert på værforhold"""
        if data.wind_speed is None:
            return None
        
        # Start med god sikt
        visibility = 10.0  # km
        
        # Reduser for snøfokk
        if data.blowing_snow_risk and data.blowing_snow_risk > 0.3:
            visibility *= (1 - data.blowing_snow_risk)
        
        # Reduser for nedbør
        if data.precipitation_amount_hourly and data.precipitation_amount_hourly > 2:
            visibility *= 0.7
        
        return max(visibility, 0.1)
    
    def _calculate_combined_risk(self, df: pd.DataFrame) -> float:
        """Beregn kombinert risikoscore"""
        if df.empty:
            return 0.0
        
        return (df['blowing_snow_risk'].fillna(0).mean() * 0.6 + 
                (df['wind_speed'].fillna(0) > 10).mean() * 0.4)
    
    def _estimate_visibility_impact(self, df: pd.DataFrame) -> str:
        """Estimer påvirkning på siktbarhet"""
        avg_risk = df['blowing_snow_risk'].fillna(0).mean()
        
        if avg_risk > 0.7:
            return 'Kraftig redusert sikt (<500m)'
        elif avg_risk > 0.4:
            return 'Moderat redusert sikt (500-2000m)'
        else:
            return 'Minimal påvirkning på sikt'
    
    def _assess_road_conditions(self, df: pd.DataFrame) -> str:
        """Vurder veiforhold"""
        wind_avg = df['wind_speed'].fillna(0).mean()
        temp_avg = df['air_temp'].fillna(0).mean()
        
        if wind_avg > 10 and temp_avg < 0:
            return 'Kritiske forhold - snøfokk og is'
        elif wind_avg > 8:
            return 'Utfordrende forhold - snøfokk'
        elif temp_avg < 0:
            return 'Glatte forhold - is'
        else:
            return 'Akseptable forhold'
    
    def _predict_next_hour_risk(self, df: pd.DataFrame) -> float:
        """Prediker risiko neste time basert på trend"""
        if len(df) < 2:
            return 0.0
        
        recent_trend = df['blowing_snow_risk'].fillna(0).tail(3).mean()
        wind_trend = df['wind_speed'].fillna(0).diff().tail(3).mean()
        
        # Øk risiko hvis vind øker
        adjustment = wind_trend * 0.1 if wind_trend > 0 else 0
        
        return min(recent_trend + adjustment, 1.0)
    
    def _calculate_deterioration_trend(self, df: pd.DataFrame) -> str:
        """Beregn om forholdene forverres"""
        if len(df) < 3:
            return 'Utilstrekkelig data'
        
        wind_trend = df['wind_speed'].fillna(0).tail(5).diff().mean()
        risk_trend = df['blowing_snow_risk'].fillna(0).tail(5).diff().mean()
        
        if wind_trend > 1 or risk_trend > 0.1:
            return 'Forverring - økende risiko'
        elif wind_trend < -1 or risk_trend < -0.1:
            return 'Forbedring - avtakende risiko'
        else:
            return 'Stabile forhold'
    
    def _recommend_action(self, df: pd.DataFrame) -> str:
        """Anbefal tiltak basert på analyse"""
        risk_avg = df['blowing_snow_risk'].fillna(0).mean()
        wind_max = df['wind_speed'].fillna(0).max()
        
        if risk_avg > 0.7 or wind_max > 15:
            return 'HØYPRIORITET: Kontinuerlig brøyting anbefalt'
        elif risk_avg > 0.4 or wind_max > 10:
            return 'MEDIUM: Økt brøytefrikevens anbefalt'
        else:
            return 'LAV: Normal brøyteplan tilstrekkelig'


async def test_enhanced_service():
    """Test den utvidede værservicen"""
    service = EnhancedWeatherService()
    
    print("🌟 UTVIDET VÆRSERVICE - DEMONSTRASJON")
    print("=" * 50)
    
    try:
        # Test sanntids data
        print("\n📡 SANNTIDS VÆRFORHOLD:")
        current = await service.get_real_time_conditions()
        
        for key, value in current.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")
        
        # Test snøfokk-analyse
        print("\n❄️ SNØFOKK-ANALYSE (siste 6 timer):")
        analysis = await service.analyze_snowdrift_conditions(hours_back=6)
        
        if 'error' not in analysis:
            print(f"  Dataperiode: {analysis['period']['hours']} timer ({analysis['period']['data_points']} punkter)")
            
            wind = analysis['wind_analysis']
            print(f"  Gjennomsnittlig vind: {wind['avg_speed']:.1f} m/s")
            print(f"  Maksimal vindkast: {wind['max_gust']:.1f} m/s")
            print(f"  Timer over terskel: {wind['hours_above_threshold']}")
            
            risk = analysis['risk_assessment']
            print(f"  Kombinert risikoscore: {risk['combined_risk_score']:.2f}")
            print(f"  Siktpåvirkning: {risk['visibility_impact']}")
            print(f"  Veiforhold: {risk['road_condition_risk']}")
            
            pred = analysis['predictions']
            print(f"  Anbefaling: {pred['recommended_action']}")
            print(f"  Trend: {pred['deterioration_trend']}")
        
        print("\n✅ Utvidet værservice fungerer!")
        
    except Exception as e:
        print(f"❌ Feil under testing: {e}")


if __name__ == '__main__':
    asyncio.run(test_enhanced_service())
