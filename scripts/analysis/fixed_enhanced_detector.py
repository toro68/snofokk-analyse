#!/usr/bin/env python3
"""
Fixed Enhanced Snowdrift Detector - Bruker samme metode som fungerende WeatherService
"""
import asyncio
import json
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))


class FixedEnhancedSnowdriftDetector:
    """Forbedret snøfokk-detektor med korrekt data-henting"""

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

    def fetch_weather_data_pandas(self, start_date, end_date):
        """Hent værdata med samme metode som fungerende WeatherService"""

        # Samme elementer som fungerende service
        elements = [
            'air_temperature',
            'relative_humidity',
            'wind_speed',
            'wind_from_direction',
            'surface_snow_thickness',
            'sum(precipitation_amount PT1H)',
            'max(wind_speed PT1H)',
            'min(air_temperature PT1H)',
            'max(air_temperature PT1H)'
        ]

        params = {
            'sources': self.station_id,
            'elements': ','.join(elements),
            'referencetime': f"{start_date}/{end_date}"
        }

        try:
            response = requests.get(
                'https://frost.met.no/observations/v0.jsonld',
                params=params,
                auth=(self.client_id, ''),
                timeout=30,
                headers={'User-Agent': 'Snofokk-Analyse/2.0.0'}
            )

            response.raise_for_status()
            data = response.json()

            if not data.get('data'):
                print("❌ Ingen data mottatt fra Frost API")
                return None

            print(f"✅ Mottatt {len(data['data'])} datapunkter fra API")

            # Konverter til DataFrame med samme metode som fungerer
            df = pd.json_normalize(
                data['data'],
                ['observations'],
                ['referenceTime']
            )

            if df.empty:
                print("❌ Tom DataFrame etter normalisering")
                return None

            print(f"📊 DataFrame form etter normalisering: {df.shape}")
            print(f"Kolonner: {list(df.columns)}")

            # Pivot til riktig format
            df = df.pivot_table(
                index='referenceTime',
                columns='elementId',
                values='value',
                aggfunc='first'
            ).reset_index()

            print(f"📊 DataFrame form etter pivot: {df.shape}")
            print(f"Kolonner etter pivot: {list(df.columns)}")

            # Konverter tid
            df['referenceTime'] = pd.to_datetime(df['referenceTime'])

            # Vis eksempel data
            print("\n🔍 EKSEMPEL DATA (første 3 rader):")
            for col in df.columns:
                if col != 'referenceTime':
                    valid_values = df[col].dropna()
                    if len(valid_values) > 0:
                        print(f"   {col}: {valid_values.iloc[0]:.2f} (første gyldig verdi)")
                    else:
                        print(f"   {col}: Ingen gyldige verdier")

            return df

        except requests.exceptions.RequestException as e:
            print(f"❌ API request feilet: {e}")
            return None
        except Exception as e:
            print(f"❌ Feil ved prosessering: {e}")
            return None

    def detect_enhanced_snowdrift_events_pandas(self, df):
        """Forbedret snøfokk-deteksjon med pandas DataFrame"""

        if df is None or df.empty:
            return []

        events = []
        current_event = None

        print(f"\n🔍 ANALYSERER {len(df)} DATAPUNKTER MED PANDAS")
        print("=" * 60)

        # Sjekk tilgjengelige kolonner
        available_cols = {
            'wind_speed': 'wind_speed' in df.columns,
            'wind_gust': 'max(wind_speed PT1H)' in df.columns,
            'wind_direction': 'wind_from_direction' in df.columns,
            'temperature': 'air_temperature' in df.columns,
            'snow_depth': 'surface_snow_thickness' in df.columns,
            'precipitation': 'sum(precipitation_amount PT1H)' in df.columns,
            'humidity': 'relative_humidity' in df.columns
        }

        print("📋 Tilgjengelige kolonner:")
        for param, available in available_cols.items():
            status = "✅" if available else "❌"
            print(f"   {status} {param}")

        # Beregn snødybde-endringer
        if available_cols['snow_depth']:
            df['snow_change'] = df['surface_snow_thickness'].diff()
        else:
            df['snow_change'] = 0

        # Analyser hver rad
        for idx, row in df.iterrows():

            # Hent verdier (med fallback til 0 hvis None)
            wind_speed = row.get('wind_speed', 0) or 0
            wind_gust = row.get('max(wind_speed PT1H)', 0) or 0
            temperature = row.get('air_temperature', 0) or 0
            snow_depth = row.get('surface_snow_thickness', 0) or 0
            snow_change = row.get('snow_change', 0) or 0
            humidity = row.get('relative_humidity', 50) or 50
            precipitation = row.get('sum(precipitation_amount PT1H)', 0) or 0

            # FORBEDRET SNØFOKK-LOGIKK basert på dine observasjoner

            # 1. Primære betingelser (justerte terskler)
            wind_ok = wind_speed >= 6.0 or wind_gust >= 8.0  # Senket fra 9.0
            temp_ok = temperature <= -1.0  # Senket fra -3.1
            snow_ok = snow_depth >= 3.0  # Senket fra 8.3

            # 2. Sekundære faktorer
            secondary_score = 0
            if humidity < 80:
                secondary_score += 0.3
            if precipitation == 0:
                secondary_score += 0.2
            if abs(snow_change) > 0.1:  # Enhver snøendring
                secondary_score += 0.5

            # 3. Risikoscore
            primary_score = sum([wind_ok, temp_ok, snow_ok]) / 3
            total_risk = (primary_score * 0.7) + (secondary_score * 0.3)

            # 4. Spesiell håndtering av "usynlig snøfokk"
            invisible_drift_risk = False
            if wind_ok and temp_ok and snow_ok and abs(snow_change) < 0.5:
                invisible_drift_risk = True
                total_risk = min(total_risk + 0.3, 1.0)  # Boost for usynlig drift

            # Beslutningstaking
            is_snowdrift = total_risk >= 0.5  # Senket terskel

            if is_snowdrift:
                # Klassifiser drift-type
                if abs(snow_change) < 0.5:
                    drift_type = 'invisible_drift'
                    road_danger = 'HIGH'
                elif snow_change > 0.5:
                    drift_type = 'accumulating_drift'
                    road_danger = 'MEDIUM'
                elif snow_change < -0.5:
                    drift_type = 'eroding_drift'
                    road_danger = 'HIGH'
                else:
                    drift_type = 'unknown'
                    road_danger = 'MEDIUM'

                if current_event is None:
                    # Start ny hendelse
                    current_event = {
                        'start_time': str(row['referenceTime']),
                        'end_time': str(row['referenceTime']),
                        'duration_hours': 1,
                        'max_wind_speed': wind_speed,
                        'max_wind_gust': wind_gust,
                        'min_temperature': temperature,
                        'snow_depth_start': snow_depth,
                        'snow_depth_end': snow_depth,
                        'total_snow_change': snow_change,
                        'drift_type': {
                            'type': drift_type,
                            'road_danger': road_danger
                        },
                        'risk_score': total_risk,
                        'invisible_drift': invisible_drift_risk,
                        'conditions': {
                            'wind_ok': wind_ok,
                            'temp_ok': temp_ok,
                            'snow_ok': snow_ok,
                            'secondary_score': secondary_score
                        }
                    }
                else:
                    # Fortsett hendelse
                    current_event['end_time'] = str(row['referenceTime'])
                    current_event['duration_hours'] += 1
                    current_event['max_wind_speed'] = max(current_event['max_wind_speed'], wind_speed)
                    current_event['max_wind_gust'] = max(current_event['max_wind_gust'], wind_gust)
                    current_event['min_temperature'] = min(current_event['min_temperature'], temperature)
                    current_event['snow_depth_end'] = snow_depth
                    current_event['total_snow_change'] += snow_change
                    current_event['risk_score'] = max(current_event['risk_score'], total_risk)

            else:
                # Avslutt pågående hendelse
                if current_event is not None:
                    if current_event['duration_hours'] >= 1:
                        events.append(current_event)
                    current_event = None

        # Avslutt siste hendelse
        if current_event is not None and current_event['duration_hours'] >= 1:
            events.append(current_event)

        return events

    def present_fixed_results(self, events, start_date, end_date):
        """Present resultater fra forbedret deteksjon"""

        print("\n🎯 FORBEDREDE RESULTATER (FIKSET)")
        print("=" * 60)
        print(f"Periode: {start_date} til {end_date}")
        print(f"Totalt: {len(events)} snøfokk-hendelser")

        if not events:
            print("❌ Ingen snøfokk-hendelser oppdaget")
            return

        # Kategoriser etter drift-type
        drift_types = {}
        total_hours = 0
        invisible_count = 0

        for event in events:
            drift_type = event['drift_type']['type']
            if drift_type not in drift_types:
                drift_types[drift_type] = []
            drift_types[drift_type].append(event)
            total_hours += event['duration_hours']

            if event.get('invisible_drift', False):
                invisible_count += 1

        print(f"Total varighet: {total_hours} timer")
        print(f"Usynlig snøfokk: {invisible_count} hendelser (farlig for veier!)")
        print()

        for drift_type, type_events in drift_types.items():
            count = len(type_events)
            hours = sum(e['duration_hours'] for e in type_events)
            danger = type_events[0]['drift_type']['road_danger']

            print(f"🏷️ {drift_type.replace('_', ' ').upper()}:")
            print(f"   Hendelser: {count}")
            print(f"   Timer: {hours}")
            print(f"   Veifare: {danger}")
            print()

        # Vis mest kritiske
        print("🚨 MEST KRITISKE HENDELSER:")
        critical_events = sorted(events, key=lambda x: x['risk_score'], reverse=True)[:3]

        for i, event in enumerate(critical_events, 1):
            print(f"\n{i}. {event['start_time'][:16]} - {event['end_time'][11:16]}")
            print(f"   Varighet: {event['duration_hours']} timer")
            print(f"   Type: {event['drift_type']['type']}")
            print(f"   Veifare: {event['drift_type']['road_danger']}")
            print(f"   Risikoscore: {event['risk_score']:.2f}")
            print(f"   Vind: {event['max_wind_speed']:.1f} m/s (kast: {event['max_wind_gust']:.1f})")
            print(f"   Temp: {event['min_temperature']:.1f}°C")
            print(f"   Snøendring: {event['total_snow_change']:+.1f} cm")

            conditions = event['conditions']
            print(f"   Betingelser: Vind({'✅' if conditions['wind_ok'] else '❌'}) "
                  f"Temp({'✅' if conditions['temp_ok'] else '❌'}) "
                  f"Snø({'✅' if conditions['snow_ok'] else '❌'})")

    async def run_fixed_analysis(self, start_date, end_date):
        """Kjør fikset snøfokk-analyse"""

        print("🔧 FIKSET FORBEDRET SNØFOKK-ANALYSE")
        print("=" * 60)
        print("Bruker samme metode som fungerende WeatherService")
        print("Justerte terskler for å fange flere hendelser")
        print("Spesiell fokus på 'usynlig' snøfokk")
        print()

        # Hent data med pandas-metoden
        df = self.fetch_weather_data_pandas(start_date, end_date)

        if df is None:
            print("❌ Kunne ikke hente værdata")
            return []

        # Detekter hendelser
        events = self.detect_enhanced_snowdrift_events_pandas(df)

        # Present resultater
        self.present_fixed_results(events, start_date, end_date)

        # Lagre resultater
        output_file = Path(__file__).parent.parent.parent / 'data' / 'analyzed' / 'fixed_enhanced_snowdrift_analysis.json'

        result_data = {
            'analysis_type': 'fixed_enhanced_snowdrift_detection',
            'analysis_date': datetime.now().isoformat(),
            'period': {'start': str(start_date), 'end': str(end_date)},
            'station': {'id': self.station_id, 'name': 'Gullingen Skisenter'},
            'methodology': {
                'adjusted_thresholds': {
                    'wind_speed': 6.0,
                    'temperature': -1.0,
                    'snow_depth': 3.0,
                    'risk_threshold': 0.5
                },
                'special_features': ['invisible_drift_detection', 'road_danger_classification']
            },
            'statistics': {
                'total_events': len(events),
                'total_hours': sum(e['duration_hours'] for e in events),
                'invisible_drift_events': len([e for e in events if e.get('invisible_drift', False)])
            },
            'events': events
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Resultater lagret i {output_file}")

        return events

async def main():
    detector = FixedEnhancedSnowdriftDetector()

    # Test med vinterperiode som vi vet har data
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 31)

    await detector.run_fixed_analysis(start_date, end_date)

if __name__ == '__main__':
    asyncio.run(main())
