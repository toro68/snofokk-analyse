#!/usr/bin/env python3
"""
Enhanced Research-grade Snowdrift Analyzer with Snow Dynamics

Key improvements:
- Dynamic wind thresholds based on snow conditions
- Snow change detection (fresh snow, transport, stable)
- Enhanced loose snow logic with fresh snow override
- Improved risk scoring system

Author: Analysis based on conversation findings
Date: 2025-08-09
"""

import argparse
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

def fetch_frost_data(station_id: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    """Hent data fra Frost API for gitt periode."""

    frost_client_id = os.getenv('FROST_CLIENT_ID')
    if not frost_client_id:
        raise ValueError("FROST_CLIENT_ID ikke funnet i .env fil")

    elements = [
        'air_temperature',
        'wind_speed',
        'wind_from_direction',
        'surface_snow_thickness',
        'sum(precipitation_amount PT1H)',
        'relative_humidity',
        'surface_temperature',
        'dew_point_temperature'
    ]

    url = 'https://frost.met.no/observations/v0.jsonld'
    parameters = {
        'sources': station_id,
        'elements': ','.join(elements),
        'referencetime': f"{start_date}/{end_date}"
    }

    try:
        response = requests.get(url, parameters, auth=(frost_client_id, ''), timeout=60)
        response.raise_for_status()

        data = response.json()
        if not data.get('data'):
            print(f"Ingen data mottatt for periode {start_date} til {end_date}")
            return None

        records = []
        for obs in data['data']:
            record = {'referenceTime': pd.to_datetime(obs['referenceTime'])}

            for observation in obs['observations']:
                element = observation['elementId']
                value = observation['value']
                record[element] = value

            records.append(record)

        df = pd.DataFrame(records)
        df = df.sort_values('referenceTime').drop_duplicates('referenceTime').reset_index(drop=True)

        return df

    except Exception as e:
        print(f"Feil ved henting av data: {e}")
        return None

def add_snow_dynamics_features(df: pd.DataFrame) -> pd.DataFrame:
    """Legg til snødynamikk-features for forbedret snøfokk-analyse."""

    df = df.copy()

    # Grunnleggende snødybde-endringer
    df['snow_change_1h'] = df['surface_snow_thickness'].diff()
    df['snow_change_3h'] = df['surface_snow_thickness'].diff(3)
    df['snow_change_6h'] = df['surface_snow_thickness'].diff(6)

    # Snødynamikk-klassifikasjoner
    df['fresh_snow_1h'] = (df['snow_change_1h'] >= 0.3).astype(int)
    df['snow_transport_1h'] = (df['snow_change_1h'] <= -0.2).astype(int)
    df['fresh_snow_6h'] = (df['snow_change_6h'] >= 1.0).astype(int)
    df['snow_loss_6h'] = (df['snow_change_6h'] <= -1.0).astype(int)

    # Snødynamikk-faktor for risikovurdering
    df['snow_dynamics_factor'] = 1.0
    df.loc[df['fresh_snow_1h'] == 1, 'snow_dynamics_factor'] = 1.2  # Nysnø forsterker
    df.loc[df['snow_transport_1h'] == 1, 'snow_dynamics_factor'] = 1.3  # Transport bekrefter

    # Vindpersistens (forbedret)
    df['consec_wind_ge5'] = (df['wind_speed'] >= 5).astype(int).groupby((df['wind_speed'] < 5).cumsum()).cumsum()
    df['consec_wind_ge6'] = (df['wind_speed'] >= 6).astype(int).groupby((df['wind_speed'] < 6).cumsum()).cumsum()
    df['consec_wind_ge7'] = (df['wind_speed'] >= 7).astype(int).groupby((df['wind_speed'] < 7).cumsum()).cumsum()
    df['wind_persistent_3h'] = (df['consec_wind_ge6'] >= 3).astype(int)

    # Vindretning-analyse
    df['high_risk_sector'] = ((df['wind_from_direction'] >= 300) | (df['wind_from_direction'] <= 60)).astype(int)

    def categorize_wind_direction(direction):
        if pd.isna(direction):
            return 'unknown'
        elif 315 <= direction or direction < 45:
            return 'N'
        elif 45 <= direction < 135:
            return 'E'
        elif 135 <= direction < 225:
            return 'S'
        elif 225 <= direction < 315:
            return 'W'
        else:
            return 'unknown'

    df['wind_sector'] = df['wind_from_direction'].apply(categorize_wind_direction)

    # FORBEDRET LØSSNØ-LOGIKK med snødynamikk
    df['temp_above_zero_last_24h'] = df['air_temperature'].rolling(24, min_periods=12).apply(lambda x: (x > 0).any()).fillna(0)
    df['continuous_frost_12h'] = (df['air_temperature'].rolling(12, min_periods=6).apply(lambda x: (x <= -1).all())).fillna(0)

    # Dynamisk løssnø: Nysnø erstatter mildvær-sjekk
    df['loose_snow_gate'] = 0
    # Hovedregel: Ingen mildvær ELLER kontinuerlig frost
    df.loc[(df['temp_above_zero_last_24h'] == 0) | (df['continuous_frost_12h'] == 1), 'loose_snow_gate'] = 1
    # OVERRIDE: Nysnø gir alltid løssnø
    df.loc[df['fresh_snow_1h'] == 1, 'loose_snow_gate'] = 1
    # BONUS: Nysnø-periode gir utvidet løssnø
    df.loc[df['fresh_snow_6h'] == 1, 'loose_snow_gate'] = 1

    # Nedbør-features
    df['precip_mm_h'] = df['sum(precipitation_amount PT1H)'].fillna(0)
    df['last_6h_precip'] = df['precip_mm_h'].rolling(6, min_periods=1).sum()

    return df

def enhanced_risk_classification(row: pd.Series) -> tuple[str, list[str]]:
    """Forbedret risikoklassifisering med snødynamikk."""

    factors = []

    # Grunndata
    wind = row.get('wind_speed', np.nan)
    temp = row.get('air_temperature', np.nan)
    snow_depth = row.get('surface_snow_thickness', np.nan)
    loose_snow = row.get('loose_snow_gate', 0)

    # Snødynamikk
    fresh_snow = row.get('fresh_snow_1h', 0)
    snow_transport = row.get('snow_transport_1h', 0)
    dynamics_factor = row.get('snow_dynamics_factor', 1.0)

    # Persistens
    consec_6 = row.get('consec_wind_ge6', 0)
    consec_7 = row.get('consec_wind_ge7', 0)

    # Vindretning
    high_risk_sector = row.get('high_risk_sector', 0)

    if not np.isfinite(wind) or not np.isfinite(temp):
        return 'unknown', ["Mangler vind/temperatur data"]

    # DYNAMISKE VINDTERSKLER basert på snøforhold
    if fresh_snow:
        high_wind_threshold = 7.0  # Senket ved nysnø
        medium_wind_threshold = 5.0
        factors.append(f"Nysnø-forsterkning (endring: +{row.get('snow_change_1h', 0):.1f} cm/h)")
    elif snow_transport:
        high_wind_threshold = 8.0
        medium_wind_threshold = 6.0
        factors.append(f"Vindtransport-indikator (tap: {row.get('snow_change_1h', 0):.1f} cm/h)")
    else:
        high_wind_threshold = 9.0  # Standard
        medium_wind_threshold = 7.0

    # Grunnkriterier
    basic_criteria = (
        wind >= medium_wind_threshold and
        temp <= -1.0 and
        snow_depth >= 3.0 and
        loose_snow == 1
    )

    if not basic_criteria:
        return 'low', factors + [f"Grunnkriterier ikke oppfylt (vind: {wind:.1f}, temp: {temp:.1f}, snø: {snow_depth:.0f})"]

    # Legg til grunnfaktorer
    factors.append(f"Vind {wind:.1f} m/s (terskel: {medium_wind_threshold:.1f})")
    factors.append(f"Temperatur {temp:.1f}°C")
    factors.append(f"Snødybde {snow_depth:.0f} cm")

    # HIGH RISK-kriterier
    high_risk_conditions = (
        wind >= high_wind_threshold and
        (consec_7 >= 2 or fresh_snow or snow_transport)  # Persistens ELLER dynamikk
    )

    if high_risk_conditions:
        factors.append(f"Høy vindstyrke (≥{high_wind_threshold:.1f} m/s)")
        if consec_7 >= 2:
            factors.append(f"Persistant vind ({consec_7}h ≥7 m/s)")
        if high_risk_sector:
            factors.append("Høyrisiko vindsektor (NV-N-NØ)")

        return 'high', factors

    # MEDIUM RISK med forbedringer
    medium_multiplier = dynamics_factor  # 1.2 for nysnø, 1.3 for transport
    effective_wind = wind * medium_multiplier

    if effective_wind >= 7.0:  # Effektiv vind over terskel
        if dynamics_factor > 1.0:
            factors.append(f"Dynamikk-bonus (effektiv vind: {effective_wind:.1f} m/s)")
        if consec_6 >= 3:
            factors.append(f"Moderat persistens ({consec_6}h ≥6 m/s)")
        if high_risk_sector:
            factors.append("Gunstig vindretning")

        return 'medium', factors

    return 'low', factors

def analyze_enhanced_snowdrift(df: pd.DataFrame) -> pd.DataFrame:
    """Analyser snøfokk med forbedrede kriterier."""

    print("🔬 Legger til snødynamikk-features...")
    df = add_snow_dynamics_features(df)

    print("⚖️ Klassifiserer risiko med forbedrede kriterier...")
    risk_data = df.apply(enhanced_risk_classification, axis=1, result_type='expand')
    df[['risk_level', 'factors']] = risk_data

    return df

def analyze_slippery_road_enhanced(df: pd.DataFrame) -> pd.DataFrame:
    """Analyser glatt føre med forbedrede kriterier."""

    def classify_slippery_risk(row):
        factors = []

        temp = row.get('air_temperature', np.nan)
        snow_depth = row.get('surface_snow_thickness', np.nan)
        precip = row.get('precip_mm_h', 0)
        snow_change_6h = row.get('snow_change_6h', 0)

        if not np.isfinite(temp):
            return 'unknown', ["Mangler temperatur"]

        # Nysnø-beskyttelse (forbedret)
        if snow_change_6h >= 1.0:
            return 'low', factors + [f"Nysnø-beskyttelse (+{snow_change_6h:.1f} cm/6h)"]

        # Regn-på-snø (hovedscenario)
        rain_on_snow = (
            0 <= temp <= 4 and
            snow_depth >= 5 and
            precip >= 0.2  # Senket terskel
        )

        if rain_on_snow:
            factors.extend([
                f"Mildvær ({temp:.1f}°C)",
                f"Snødekke ({snow_depth:.0f} cm)",
                f"Regn ({precip:.1f} mm/h)"
            ])

            if precip >= 1.0:  # Kraftig regn
                return 'high', factors + ["Kraftig regn på snø"]
            else:
                return 'medium', factors + ["Regn på snø"]

        # Temperaturovergang
        temp_transition = -1 <= temp <= 1 and snow_depth >= 3
        if temp_transition:
            factors.append(f"Temperaturovergang ({temp:.1f}°C)")
            return 'medium', factors

        # Stabilt kaldt
        if temp <= -5 and snow_depth >= 3:
            return 'low', factors + [f"Stabilt kaldt ({temp:.1f}°C)"]

        return 'low', factors + ["Ingen risikofaktorer"]

    risk_data = df.apply(classify_slippery_risk, axis=1, result_type='expand')
    df[['risk_slippery', 'factors_slippery']] = risk_data

    return df

def main():
    parser = argparse.ArgumentParser(description='Enhanced Snowdrift Analyzer med snødynamikk')
    parser.add_argument('--station', default='SN46220', help='Stasjons-ID')
    parser.add_argument('--days', type=int, help='Dager tilbake fra nå')
    parser.add_argument('--from', dest='start_date', help='Start dato (YYYY-MM-DD)')
    parser.add_argument('--to', dest='end_date', help='Slutt dato (YYYY-MM-DD)')
    parser.add_argument('--out', default='data/analyzed', help='Output mappe')

    args = parser.parse_args()

    # Beregn datoer
    if args.days:
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(days=args.days)
        start_date = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_date = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        timestamp = f"{args.days}days_{end_time.strftime('%Y%m%d_%H%M')}"
    elif args.start_date and args.end_date:
        start_date = f"{args.start_date}T00:00:00Z"
        end_date = f"{args.end_date}T23:59:59Z"
        timestamp = f"{args.start_date}_to_{args.end_date}"
    else:
        # Default: siste 7 dager
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(days=7)
        start_date = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_date = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        timestamp = f"7days_{end_time.strftime('%Y%m%d_%H%M')}"

    print("=== ENHANCED SNOWDRIFT ANALYZER ===")
    print(f"Stasjon: {args.station}")
    print(f"Periode: {start_date} til {end_date}")
    print(f"Output: {args.out}")

    # Hent data
    print("\n📡 Henter data fra Frost API...")
    df = fetch_frost_data(args.station, start_date, end_date)

    if df is None or len(df) == 0:
        print("❌ Ingen data mottatt!")
        return

    print(f"✅ Hentet {len(df)} målinger")

    # Analyser
    print("\n❄️ Analyserer snøfokk med snødynamikk...")
    df = analyze_enhanced_snowdrift(df)

    print("\n🧊 Analyserer glatt føre...")
    df = analyze_slippery_road_enhanced(df)

    # Lagre resultater
    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Features CSV
    features_file = output_dir / f"enhanced_features_{args.station}_{timestamp}.csv"
    df.to_csv(features_file, index=False)

    # Statistikk
    total_hours = len(df)
    snowdrift_high = (df['risk_level'] == 'high').sum()
    snowdrift_medium = (df['risk_level'] == 'medium').sum()
    slippery_high = (df['risk_slippery'] == 'high').sum()
    slippery_medium = (df['risk_slippery'] == 'medium').sum()

    fresh_snow_hours = df['fresh_snow_1h'].sum()
    transport_hours = df['snow_transport_1h'].sum()

    print("\n📊 ENHANCED ANALYSE-RESULTATER:")
    print(f"• Total timer: {total_hours:,}")
    print(f"• Snøfokk HIGH: {snowdrift_high} timer ({snowdrift_high/total_hours*100:.1f}%)")
    print(f"• Snøfokk MEDIUM: {snowdrift_medium} timer ({snowdrift_medium/total_hours*100:.1f}%)")
    print(f"• Glatt føre HIGH: {slippery_high} timer ({slippery_high/total_hours*100:.1f}%)")
    print(f"• Glatt føre MEDIUM: {slippery_medium} timer ({slippery_medium/total_hours*100:.1f}%)")
    print("\n🆕 SNØDYNAMIKK:")
    print(f"• Nysnø-timer (≥0.3 cm/h): {fresh_snow_hours} ({fresh_snow_hours/total_hours*100:.1f}%)")
    print(f"• Vindtransport-timer (≤-0.2 cm/h): {transport_hours} ({transport_hours/total_hours*100:.1f}%)")

    # Sammenlign med standard kriterier
    standard_snowdrift = (
        (df['wind_speed'] >= 7) &
        (df['air_temperature'] <= -1) &
        (df['surface_snow_thickness'] >= 3) &
        (df['loose_snow_gate'] == 1)
    ).sum()

    enhanced_snowdrift = snowdrift_high + snowdrift_medium

    print("\n⚖️ SAMMENLIGNING:")
    print(f"• Standard kriterier: {standard_snowdrift} timer")
    print(f"• Enhanced kriterier: {enhanced_snowdrift} timer")
    print(f"• Forbedring: {enhanced_snowdrift - standard_snowdrift:+d} timer ({(enhanced_snowdrift - standard_snowdrift)/standard_snowdrift*100:+.1f}%)")

    print(f"\n💾 Lagret: {features_file}")
    print("✅ Enhanced analyse fullført!")

if __name__ == "__main__":
    main()
