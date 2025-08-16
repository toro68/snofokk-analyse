#!/usr/bin/env python3
"""
Enhanced Snowdrift Detection - Forbedret snøfokk-deteksjon basert på fysiske realiteter
"""
import asyncio
import json
import sys
from datetime import date, datetime
from pathlib import Path

import aiohttp

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

class EnhancedSnowdriftDetector:
    """Forbedret snøfokk-detektor som tar hensyn til alle fysiske realiteter"""

    def __init__(self):
        self.station_id = 'SN46220'  # Gullingen Skisenter
        self.load_frost_key()

    def load_frost_key(self):
        """Last Frost API-nøkkel"""
        env_file = Path(__file__).parent.parent.parent / '.env'
        if env_file.exists():
            with open(env_file, encoding='utf-8') as f:
                for line in f:
                    if line.startswith('FROST_CLIENT_ID='):
                        self.client_id = line.split('=', 1)[1].strip()
                        break
        else:
            raise FileNotFoundError("❌ .env fil ikke funnet")

    async def get_comprehensive_weather_data(self, start_date, end_date):
        """Hent omfattende værdata med alle relevante parametre"""

        # Viktige element-IDer basert på tilgjengelige data
        critical_elements = [
            'wind_speed',                    # Primær: Vindstyrke (PT1H)
            'max(wind_speed_of_gust PT1H)',  # Primær: Vindkast
            'wind_from_direction',           # Sekundær: Vindretning
            'air_temperature',               # Primær: Temperatur (PT1H)
            'surface_snow_thickness',        # Primær: Snødybde (PT1H)
            'sum(precipitation_amount PT1H)', # Sekundær: Aktiv nedbør
            'relative_humidity',             # Sekundær: Luftfuktighet
            'surface_temperature'            # Tillegg: Overflatetemperatur
        ]

        url = "https://frost.met.no/observations/v0.jsonld"

        params = {
            'sources': self.station_id,
            'elements': ','.join(critical_elements),
            'referencetime': f"{start_date}/{end_date}",
            'fields': 'sourceId,referenceTime,elementId,value,unit,timeOffset',
            'timeoffsets': 'PT0H',
            'timeresolutions': 'PT1H'  # Timeoppløsning
        }

        headers = {
            'User-Agent': 'snofokk-analyse/1.0'
        }

        auth = aiohttp.BasicAuth(self.client_id, '')

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, auth=auth) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"❌ API-feil: {response.status}")
                    return None

    def organize_weather_data(self, raw_data):
        """Organiser værdata etter tidspunkt og parameter"""

        observations = raw_data.get('data', [])

        # Grupper etter tidspunkt
        time_series = {}

        for obs in observations:
            ref_time = obs.get('referenceTime', '')
            element_id = obs.get('elementId', '')
            value = obs.get('value', None)

            if ref_time not in time_series:
                time_series[ref_time] = {}

            time_series[ref_time][element_id] = value

        # Konverter til sortert liste
        organized_data = []
        for timestamp in sorted(time_series.keys()):
            data_point = {
                'timestamp': timestamp,
                **time_series[timestamp]
            }
            organized_data.append(data_point)

        return organized_data

    def detect_enhanced_snowdrift_events(self, weather_data):
        """Forbedret snøfokk-deteksjon basert på fysiske realiteter"""

        events = []
        current_event = None

        print(f"🔍 ANALYSERER {len(weather_data)} DATAPUNKTER")
        print("=" * 60)

        for i, point in enumerate(weather_data):

            # Hent verdier med fallback
            wind_speed = point.get('wind_speed', 0) or 0
            wind_gust = point.get('max(wind_speed_of_gust PT1H)', 0) or 0
            wind_direction = point.get('wind_from_direction', 0)
            temperature = point.get('air_temperature', 0)
            snow_depth = point.get('surface_snow_thickness', 0)
            precipitation = point.get('sum(precipitation_amount PT1H)', 0) or 0
            humidity = point.get('relative_humidity', 0)
            surface_temp = point.get('surface_temperature', None)

            # Beregn snødybde-endring (hvis mulig)
            snow_change = 0
            if i > 0:
                prev_snow = weather_data[i-1].get('surface_snow_thickness', 0) or 0
                if snow_depth and prev_snow:
                    snow_change = snow_depth - prev_snow

            # FORBEDRET SNØFOKK-LOGIKK basert på dine observasjoner

            # 1. PRIMÆRE INDIKATORER (må være oppfylt)
            primary_conditions = self.check_primary_conditions(
                wind_speed, wind_gust, temperature, snow_depth
            )

            # 2. SEKUNDÆRE INDIKATORER (styrker sannsynlighet)
            secondary_score = self.calculate_secondary_score(
                wind_direction, humidity, precipitation, surface_temp
            )

            # 3. SPESIELLE TILSTANDER basert på snødybde-endring
            drift_type = self.classify_drift_type(
                snow_change, wind_speed, temperature, snow_depth
            )

            # Samlet risikovurdering
            risk_assessment = self.assess_snowdrift_risk(
                primary_conditions, secondary_score, drift_type, point
            )

            # Beslutningstaking
            if risk_assessment['is_snowdrift']:

                if current_event is None:
                    # Start ny hendelse
                    current_event = {
                        'start_time': point['timestamp'],
                        'end_time': point['timestamp'],
                        'duration_hours': 1,
                        'max_wind_speed': wind_speed,
                        'max_wind_gust': wind_gust,
                        'min_temperature': temperature,
                        'snow_depth_start': snow_depth,
                        'snow_depth_end': snow_depth,
                        'total_snow_change': snow_change,
                        'drift_type': drift_type,
                        'risk_score': risk_assessment['risk_score'],
                        'confidence': risk_assessment['confidence'],
                        'evidence': risk_assessment['evidence']
                    }
                else:
                    # Fortsett eksisterende hendelse
                    current_event['end_time'] = point['timestamp']
                    current_event['duration_hours'] += 1
                    current_event['max_wind_speed'] = max(current_event['max_wind_speed'], wind_speed)
                    current_event['max_wind_gust'] = max(current_event['max_wind_gust'], wind_gust)
                    current_event['min_temperature'] = min(current_event['min_temperature'], temperature)
                    current_event['snow_depth_end'] = snow_depth
                    current_event['total_snow_change'] += snow_change
                    current_event['risk_score'] = max(current_event['risk_score'], risk_assessment['risk_score'])

                    # Oppdater drift-type hvis vi finner sterkere evidens
                    if risk_assessment['confidence'] > current_event['confidence']:
                        current_event['drift_type'] = drift_type
                        current_event['confidence'] = risk_assessment['confidence']
                        current_event['evidence'] = risk_assessment['evidence']

            else:
                # Avslutt pågående hendelse hvis den finnes
                if current_event is not None:
                    if current_event['duration_hours'] >= 1:  # Minimum varighet
                        events.append(current_event)
                    current_event = None

        # Avslutt siste hendelse hvis nødvendig
        if current_event is not None:
            if current_event['duration_hours'] >= 1:
                events.append(current_event)

        return events

    def check_primary_conditions(self, wind_speed, wind_gust, temperature, snow_depth):
        """Sjekk primære betingelser for snøfokk"""

        conditions = {
            'sufficient_wind': False,
            'cold_enough': False,
            'available_snow': False
        }

        # Vindkrav (bruk optimaliserte verdier)
        if wind_speed >= 9.0 or wind_gust >= 12.0:
            conditions['sufficient_wind'] = True

        # Temperaturkrav (optimalisert)
        if temperature <= -3.1:
            conditions['cold_enough'] = True

        # Snøtilgjengelighet (optimalisert + fleksibilitet)
        if snow_depth >= 8.3:
            conditions['available_snow'] = True
        elif snow_depth >= 3.0 and wind_speed >= 12.0:
            # Mindre snø OK hvis vinden er sterk nok
            conditions['available_snow'] = True

        return conditions

    def calculate_secondary_score(self, wind_direction, humidity, precipitation, surface_temp):
        """Beregn sekundær risikoscore"""

        score = 0

        # Vedvarende vindretning (indikerer stabil snøfokk)
        if wind_direction is not None:
            score += 0.2

        # Lav luftfuktighet (tørr snø blåser lettere)
        if humidity and humidity < 80:
            score += 0.3

        # Ingen aktiv nedbør (omblåsing vs. snøfall)
        if precipitation == 0:
            score += 0.2

        # Kald overflate (snø fester seg ikke)
        if surface_temp and surface_temp < -2:
            score += 0.3

        return min(score, 1.0)  # Maksimum 1.0

    def classify_drift_type(self, snow_change, wind_speed, temperature, snow_depth):
        """Klassifiser type snøfokk basert på snødybde-endring"""

        if abs(snow_change) < 0.5:
            # USYNLIG SNØFOKK - mest farlig for veier!
            return {
                'type': 'invisible_drift',
                'description': 'Snøtransport uten akkumulering',
                'road_danger': 'HIGH',
                'explanation': 'Snø blåser forbi/gjennom måleområde - kan fylle veier!'
            }

        elif snow_change > 0.5:
            # AKKUMULERENDE SNØFOKK
            return {
                'type': 'accumulating_drift',
                'description': 'Snøoppbygging ved målestasjon',
                'road_danger': 'MEDIUM',
                'explanation': 'Snø samles ved stasjon - mindre på veier'
            }

        elif snow_change < -0.5:
            # ERODERENDE SNØFOKK
            return {
                'type': 'eroding_drift',
                'description': 'Snø blåses vekk fra målestasjon',
                'road_danger': 'HIGH',
                'explanation': 'Snø fra stasjon kan blåse til veier'
            }

        return {
            'type': 'unknown',
            'description': 'Ukjent drift-type',
            'road_danger': 'MEDIUM',
            'explanation': 'Ikke tilstrekkelig data for klassifisering'
        }

    def assess_snowdrift_risk(self, primary_conditions, secondary_score, drift_type, point):
        """Samlet risikovurdering"""

        # Tell oppfylte primærbetingelser
        primary_score = sum(primary_conditions.values()) / len(primary_conditions)

        # Samlet risikoscore
        risk_score = (primary_score * 0.7) + (secondary_score * 0.3)

        # Juster for drift-type
        if drift_type['road_danger'] == 'HIGH':
            risk_score = min(risk_score + 0.2, 1.0)

        # Beslutningstaking
        is_snowdrift = risk_score >= 0.6  # Senket terskel for å fange "usynlig" drift

        # Konfidensbasert på tilgjengelige data
        confidence = self.calculate_confidence(primary_conditions, secondary_score, point)

        # Evidens for beslutning
        evidence = []
        for condition, met in primary_conditions.items():
            if met:
                evidence.append(f"✅ {condition.replace('_', ' ').title()}")
            else:
                evidence.append(f"❌ {condition.replace('_', ' ').title()}")

        evidence.append(f"📊 Sekundær score: {secondary_score:.2f}")
        evidence.append(f"🎯 Drift-type: {drift_type['type']}")

        return {
            'is_snowdrift': is_snowdrift,
            'risk_score': risk_score,
            'confidence': confidence,
            'evidence': evidence
        }

    def calculate_confidence(self, primary_conditions, secondary_score, point):
        """Beregn konfidensgrad basert på datatilgjengelighet"""

        available_params = 0
        total_params = 8  # Antall kritiske parametre

        if point.get('wind_speed') is not None:
            available_params += 1
        if point.get('max(wind_speed_of_gust PT1H)') is not None:
            available_params += 1
        if point.get('wind_from_direction') is not None:
            available_params += 1
        if point.get('air_temperature') is not None:
            available_params += 1
        if point.get('surface_snow_thickness') is not None:
            available_params += 1
        if point.get('sum(precipitation_amount PT1H)') is not None:
            available_params += 1
        if point.get('relative_humidity') is not None:
            available_params += 1
        if point.get('surface_temperature') is not None:
            available_params += 1

        return available_params / total_params

    async def run_enhanced_analysis(self, start_date, end_date):
        """Kjør forbedret snøfokk-analyse"""

        print("🚀 FORBEDRET SNØFOKK-ANALYSE")
        print("=" * 60)
        print("Basert på fysiske realiteter:")
        print("• Snøfokk kan øke snødybden (akkumulering)")
        print("• Snøfokk kan redusere snødybden (erosjon)")
        print("• 'Usynlig' snøfokk (ingen snødybde-endring)")
        print("• Alle typer kan blokkere veier!")
        print()

        # Hent værdata
        print(f"📊 Henter værdata: {start_date} til {end_date}")
        raw_data = await self.get_comprehensive_weather_data(start_date, end_date)

        if not raw_data:
            print("❌ Ingen værdata mottatt")
            return

        # Organiser data
        weather_data = self.organize_weather_data(raw_data)
        print(f"✅ Organisert {len(weather_data)} tidspunkter")

        # Detekter snøfokk-hendelser
        events = self.detect_enhanced_snowdrift_events(weather_data)

        # Presenter resultater
        self.present_enhanced_results(events, start_date, end_date)

        # Lagre resultater
        await self.save_enhanced_results(events, start_date, end_date, weather_data)

        return events

    def present_enhanced_results(self, events, start_date, end_date):
        """Present forbedrede resultater"""

        print("\n🎯 FORBEDREDE RESULTATER")
        print("=" * 60)
        print(f"Periode: {start_date} til {end_date}")
        print(f"Totalt: {len(events)} snøfokk-hendelser")

        if not events:
            print("✅ Ingen snøfokk-hendelser oppdaget")
            return

        # Kategoriser etter drift-type
        drift_types = {}
        total_hours = 0

        for event in events:
            drift_type = event['drift_type']['type']
            if drift_type not in drift_types:
                drift_types[drift_type] = []
            drift_types[drift_type].append(event)
            total_hours += event['duration_hours']

        print(f"Total varighet: {total_hours} timer")
        print()

        for drift_type, type_events in drift_types.items():
            count = len(type_events)
            hours = sum(e['duration_hours'] for e in type_events)
            danger = type_events[0]['drift_type']['road_danger']

            print(f"🏷️ {drift_type.replace('_', ' ').upper()}:")
            print(f"   Hendelser: {count}")
            print(f"   Timer: {hours}")
            print(f"   Veifare: {danger}")
            print(f"   Beskrivelse: {type_events[0]['drift_type']['description']}")
            print()

        # Vis de mest kritiske hendelsene
        print("🚨 MEST KRITISKE HENDELSER:")
        critical_events = sorted(events, key=lambda x: x['risk_score'], reverse=True)[:5]

        for i, event in enumerate(critical_events, 1):
            print(f"\n{i}. {event['start_time'][:16]} - {event['end_time'][11:16]}")
            print(f"   Varighet: {event['duration_hours']} timer")
            print(f"   Risikoscore: {event['risk_score']:.2f}")
            print(f"   Type: {event['drift_type']['type']}")
            print(f"   Veifare: {event['drift_type']['road_danger']}")
            print(f"   Vind: {event['max_wind_speed']:.1f} m/s (kast: {event['max_wind_gust']:.1f})")
            print(f"   Temp: {event['min_temperature']:.1f}°C")
            print(f"   Snøendring: {event['total_snow_change']:+.1f} cm")

    async def save_enhanced_results(self, events, start_date, end_date, weather_data):
        """Lagre forbedrede resultater"""

        output_file = Path(__file__).parent.parent.parent / 'data' / 'analyzed' / 'enhanced_snowdrift_analysis.json'

        # Beregn statistikker
        statistics = {
            'total_events': len(events),
            'total_hours': sum(e['duration_hours'] for e in events),
            'drift_types': {},
            'risk_distribution': {'low': 0, 'medium': 0, 'high': 0},
            'confidence_stats': {
                'high': len([e for e in events if e['confidence'] >= 0.8]),
                'medium': len([e for e in events if 0.6 <= e['confidence'] < 0.8]),
                'low': len([e for e in events if e['confidence'] < 0.6])
            }
        }

        # Drift-type statistikk
        for event in events:
            drift_type = event['drift_type']['type']
            if drift_type not in statistics['drift_types']:
                statistics['drift_types'][drift_type] = {'count': 0, 'hours': 0}
            statistics['drift_types'][drift_type]['count'] += 1
            statistics['drift_types'][drift_type]['hours'] += event['duration_hours']

            # Risikodistribusjon
            if event['risk_score'] >= 0.8:
                statistics['risk_distribution']['high'] += 1
            elif event['risk_score'] >= 0.6:
                statistics['risk_distribution']['medium'] += 1
            else:
                statistics['risk_distribution']['low'] += 1

        result_data = {
            'analysis_type': 'enhanced_snowdrift_detection',
            'analysis_date': datetime.now().isoformat(),
            'period': {'start': str(start_date), 'end': str(end_date)},
            'station': {'id': self.station_id, 'name': 'Gullingen Skisenter'},
            'methodology': {
                'primary_conditions': ['sufficient_wind', 'cold_enough', 'available_snow'],
                'secondary_factors': ['wind_direction', 'humidity', 'precipitation', 'surface_temp'],
                'drift_classification': ['invisible_drift', 'accumulating_drift', 'eroding_drift'],
                'risk_threshold': 0.6
            },
            'statistics': statistics,
            'events': events,
            'data_quality': {
                'total_datapoints': len(weather_data),
                'parameters_used': 8,
                'coverage': len(weather_data) / ((end_date - start_date).days * 24) if weather_data else 0
            }
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Forbedrede resultater lagret i {output_file}")

async def main():
    detector = EnhancedSnowdriftDetector()

    # Test med vinterperiode
    start_date = date(2025, 1, 1)
    end_date = date(2025, 1, 31)

    await detector.run_enhanced_analysis(start_date, end_date)

if __name__ == '__main__':
    asyncio.run(main())
