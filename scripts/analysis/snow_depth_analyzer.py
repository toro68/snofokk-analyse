#!/usr/bin/env python3
"""
Analyse av snødybde-endringer som indikator på snøfokk.
Identifiserer store endringer i snødybde som ikke forklares av nedbør.
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Legg til prosjektets rotmappe i Python-stien
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Logging oppsett
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SnowDepthAnalyzer:
    """Analyserer snødybde-endringer som indikator på snøfokk."""

    def __init__(self):
        self.snow_drift_indicators = {}
        self.anomaly_thresholds = {}

    def load_weather_data(self) -> pd.DataFrame:
        """Laster værdata med snødybde-målinger."""
        try:
            cache_file = "data/cache/weather_data_2023-11-01_2024-04-30.pkl"
            if os.path.exists(cache_file):
                logger.info(f"Laster værdata fra {cache_file}")
                df = pd.read_pickle(cache_file)

                # Konverter datetime
                if 'referenceTime' in df.columns:
                    df['time'] = pd.to_datetime(df['referenceTime'])
                    df = df.drop(columns=['referenceTime'])

                # Sorter etter tid
                df = df.sort_values('time').reset_index(drop=True)

                logger.info(f"Lastet {len(df)} værobservasjoner")
                return df

        except Exception as e:
            logger.error(f"Feil ved lasting av værdata: {e}")
            return pd.DataFrame()

    def calculate_snow_depth_changes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Beregner endringer i snødybde over tid."""
        df_analysis = df.copy()

        # Sikre at vi har nødvendige kolonner
        required_cols = ['surface_snow_thickness', 'sum(precipitation_amount PT1H)', 'time']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            logger.error(f"Manglende kolonner: {missing_cols}")
            return pd.DataFrame()

        # Beregn snødybde-endringer
        df_analysis['snow_depth_change_10min'] = df_analysis['surface_snow_thickness'].diff()
        df_analysis['snow_depth_change_1h'] = df_analysis['surface_snow_thickness'].diff(periods=6)  # 6 x 10min = 1h
        df_analysis['snow_depth_change_3h'] = df_analysis['surface_snow_thickness'].diff(periods=18)  # 3h

        # Beregn rullende nedbør for sammenligning
        df_analysis['precipitation_1h'] = df_analysis['sum(precipitation_amount PT1H)']
        df_analysis['precipitation_3h'] = df_analysis['precipitation_1h'].rolling(window=18, min_periods=1).sum()

        # Identifiser betydelige endringer
        df_analysis['significant_snow_increase'] = (df_analysis['snow_depth_change_1h'] > 0.005).astype(int)  # >5mm økning
        df_analysis['significant_snow_decrease'] = (df_analysis['snow_depth_change_1h'] < -0.005).astype(int)  # >5mm reduksjon

        # Snøendring uten korresponderende nedbør (snøfokk-indikator)
        df_analysis['unexplained_snow_increase'] = (
            (df_analysis['snow_depth_change_1h'] > 0.010) &  # >10mm økning
            (df_analysis['precipitation_1h'] < 0.002)  # <2mm nedbør
        ).astype(int)

        df_analysis['unexplained_snow_decrease'] = (
            (df_analysis['snow_depth_change_1h'] < -0.010) &  # >10mm reduksjon
            (df_analysis['precipitation_1h'] < 0.002)  # <2mm nedbør
        ).astype(int)

        # Beregn snødybde-volatilitet (standard deviation over rullende vindu)
        df_analysis['snow_depth_volatility_1h'] = df_analysis['surface_snow_thickness'].rolling(window=6).std()
        df_analysis['snow_depth_volatility_3h'] = df_analysis['surface_snow_thickness'].rolling(window=18).std()

        logger.info("Beregnet snødybde-endringer og volatilitet")
        return df_analysis

    def identify_snow_drift_events(self, df: pd.DataFrame) -> pd.DataFrame:
        """Identifiserer sannsynlige snøfokk-hendelser basert på snødybde-endringer."""

        # Kriterier for snøfokk-deteksjon
        conditions = {
            'rapid_snow_redistribution': (
                (abs(df['snow_depth_change_1h']) > 0.015) &  # >15mm endring på 1h
                (df['precipitation_1h'] < 0.003) &  # <3mm nedbør
                (df.get('wind_speed', 0) > 3.0)  # Vindstyrke >3 m/s
            ),

            'high_snow_volatility': (
                (df['snow_depth_volatility_1h'] > 0.020) &  # Høy volatilitet
                (df.get('wind_speed', 0) > 2.0)  # Moderat vind
            ),

            'unexplained_accumulation': (
                df['unexplained_snow_increase'] == 1
            ),

            'unexplained_erosion': (
                df['unexplained_snow_decrease'] == 1
            ),

            'rapid_bidirectional_change': (
                (df['snow_depth_change_10min'].abs() > 0.005) &  # >5mm på 10min
                (df['snow_depth_change_10min'].shift(1).abs() > 0.005) &  # Forrige også stor
                (df['snow_depth_change_10min'] * df['snow_depth_change_10min'].shift(1) < 0)  # Motsatt retning
            )
        }

        # Kombiner alle indikatorer
        df['snow_drift_indicator_score'] = 0
        for condition_name, condition in conditions.items():
            df[f'snow_drift_{condition_name}'] = condition.astype(int)
            df['snow_drift_indicator_score'] += condition.astype(int)

        # Kategoriser risiko basert på score
        df['snow_drift_risk_level'] = 'LOW'
        df.loc[df['snow_drift_indicator_score'] >= 1, 'snow_drift_risk_level'] = 'MEDIUM'
        df.loc[df['snow_drift_indicator_score'] >= 2, 'snow_drift_risk_level'] = 'HIGH'
        df.loc[df['snow_drift_indicator_score'] >= 3, 'snow_drift_risk_level'] = 'EXTREME'

        return df

    def analyze_correlation_with_weather(self, df: pd.DataFrame) -> dict:
        """Analyserer korrelasjon mellom snødybde-endringer og værforhold."""

        # Velg relevante værvariable
        weather_vars = ['wind_speed', 'air_temperature', 'wind_from_direction']
        snow_change_vars = [
            'snow_depth_change_1h',
            'snow_depth_volatility_1h',
            'snow_drift_indicator_score'
        ]

        correlations = {}

        for weather_var in weather_vars:
            if weather_var in df.columns:
                correlations[weather_var] = {}
                for snow_var in snow_change_vars:
                    if snow_var in df.columns:
                        corr = df[weather_var].corr(df[snow_var])
                        correlations[weather_var][snow_var] = corr

        # Analyser vindretning vs snødybde-endringer
        if 'wind_from_direction' in df.columns:
            wind_direction_analysis = self._analyze_wind_direction_effects(df)
            correlations['wind_direction_analysis'] = wind_direction_analysis

        return correlations

    def _analyze_wind_direction_effects(self, df: pd.DataFrame) -> dict:
        """Analyserer hvordan vindretning påvirker snødybde-endringer."""

        # Grupper vindretninger i sektorer
        df['wind_sector'] = pd.cut(df['wind_from_direction'],
                                  bins=[0, 45, 135, 225, 315, 360],
                                  labels=['N', 'E', 'S', 'W', 'N2'],
                                  include_lowest=True)

        # Kombiner N og N2
        df['wind_sector'] = df['wind_sector'].replace('N2', 'N')

        wind_effects = {}
        for sector in ['N', 'E', 'S', 'W']:
            sector_data = df[df['wind_sector'] == sector]
            if len(sector_data) > 100:  # Nok data for analyse
                wind_effects[sector] = {
                    'avg_snow_change': sector_data['snow_depth_change_1h'].mean(),
                    'snow_volatility': sector_data['snow_depth_volatility_1h'].mean(),
                    'drift_score': sector_data['snow_drift_indicator_score'].mean(),
                    'sample_size': len(sector_data)
                }

        return wind_effects

    def generate_snow_drift_thresholds(self, df: pd.DataFrame) -> dict:
        """Genererer optimale terskelverdier for snøfokk-deteksjon basert på snødybde."""

        # Analyser distribusjoner
        stats = {
            'snow_depth_change_1h': {
                'p95': df['snow_depth_change_1h'].quantile(0.95),
                'p05': df['snow_depth_change_1h'].quantile(0.05),
                'p99': df['snow_depth_change_1h'].quantile(0.99),
                'p01': df['snow_depth_change_1h'].quantile(0.01),
                'std': df['snow_depth_change_1h'].std()
            },
            'snow_depth_volatility_1h': {
                'p90': df['snow_depth_volatility_1h'].quantile(0.90),
                'p95': df['snow_depth_volatility_1h'].quantile(0.95),
                'p99': df['snow_depth_volatility_1h'].quantile(0.99),
                'mean': df['snow_depth_volatility_1h'].mean()
            }
        }

        # Anbefalte terskelverdier
        thresholds = {
            'rapid_change_warning': float(abs(stats['snow_depth_change_1h']['p95'])),  # 95th percentile
            'rapid_change_critical': float(abs(stats['snow_depth_change_1h']['p99'])),  # 99th percentile
            'high_volatility_warning': float(stats['snow_depth_volatility_1h']['p90']),
            'high_volatility_critical': float(stats['snow_depth_volatility_1h']['p95']),
            'extreme_volatility': float(stats['snow_depth_volatility_1h']['p99'])
        }

        return {
            'statistics': stats,
            'recommended_thresholds': thresholds
        }

    def run_comprehensive_analysis(self) -> dict:
        """Kjører komplett analyse av snødybde-endringer."""
        logger.info("Starter analyse av snødybde-endringer...")

        try:
            # 1. Last data
            df = self.load_weather_data()
            if df.empty:
                raise ValueError("Ingen værdata tilgjengelig")

            # 2. Beregn snødybde-endringer
            df_analysis = self.calculate_snow_depth_changes(df)

            # 3. Identifiser snøfokk-hendelser
            df_with_indicators = self.identify_snow_drift_events(df_analysis)

            # 4. Analyser korrelasjoner
            correlations = self.analyze_correlation_with_weather(df_with_indicators)

            # 5. Generer terskelverdier
            thresholds = self.generate_snow_drift_thresholds(df_with_indicators)

            # 6. Sammendrag av funn
            summary = self._generate_analysis_summary(df_with_indicators, correlations, thresholds)

            results = {
                'timestamp': datetime.now().isoformat(),
                'data_summary': {
                    'total_observations': len(df_with_indicators),
                    'snow_drift_events': {
                        'HIGH': len(df_with_indicators[df_with_indicators['snow_drift_risk_level'] == 'HIGH']),
                        'MEDIUM': len(df_with_indicators[df_with_indicators['snow_drift_risk_level'] == 'MEDIUM']),
                        'EXTREME': len(df_with_indicators[df_with_indicators['snow_drift_risk_level'] == 'EXTREME'])
                    }
                },
                'correlations': correlations,
                'thresholds': thresholds,
                'summary': summary,
                'status': 'completed'
            }

            # Lagre resultater
            output_file = "data/analyzed/snow_depth_drift_analysis.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"Analyse fullført og lagret i {output_file}")
            return results

        except Exception as e:
            logger.error(f"Feil i snødybde-analyse: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def _generate_analysis_summary(self, df: pd.DataFrame, correlations: dict, thresholds: dict) -> dict:
        """Genererer sammendrag av analyseresultater."""

        # Finn de mest ekstreme hendelsene
        extreme_events = df[df['snow_drift_risk_level'] == 'EXTREME']
        high_events = df[df['snow_drift_risk_level'] == 'HIGH']

        # Beregn statistikk
        total_events = len(extreme_events) + len(high_events)

        # Identifiser sterkeste korrelasjoner
        strong_correlations = {}
        for weather_var, corr_dict in correlations.items():
            if isinstance(corr_dict, dict):
                for snow_var, corr_val in corr_dict.items():
                    if pd.notna(corr_val) and abs(corr_val) > 0.3:  # Moderate til sterke korrelasjoner
                        strong_correlations[f"{weather_var}_vs_{snow_var}"] = corr_val

        # Sikre at threshold-verdier eksisterer
        recommended_thresholds = thresholds.get('recommended_thresholds', {})

        return {
            'total_significant_events': total_events,
            'event_frequency': total_events / len(df) * 100 if len(df) > 0 else 0,  # Prosent av tid
            'strongest_correlations': strong_correlations,
            'recommended_monitoring': {
                'rapid_change_threshold': recommended_thresholds.get('rapid_change_critical', 0.0),
                'volatility_threshold': recommended_thresholds.get('high_volatility_critical', 0.0)
            },
            'key_findings': [
                f"Identifiserte {total_events} betydelige snøfokk-hendelser",
                f"Snøfokk forekommer {total_events / len(df) * 100:.1f}% av tiden" if len(df) > 0 else "Ingen data å analysere",
                "Snødybde-volatilitet er sterk indikator på aktiv snøfokk"
            ]
        }


def main():
    """Hovedfunksjon for snødybde-analyse."""

    print("❄️ ANALYSE AV SNØDYBDE-ENDRINGER SOM SNØFOKK-INDIKATOR")
    print("=" * 60)

    analyzer = SnowDepthAnalyzer()

    # Kjør analyse
    results = analyzer.run_comprehensive_analysis()

    if results['status'] == 'completed':
        print("\n✅ SNØDYBDE-ANALYSE FULLFØRT")

        # Vis sammendrag
        data_summary = results.get('data_summary', {})
        summary = results.get('summary', {})

        print(f"📊 Analyserte observasjoner: {data_summary.get('total_observations', 0):,}")
        print(f"🌨️ Totale snøfokk-hendelser: {summary.get('total_significant_events', 0)}")
        print(f"📈 Hendelsesfrekvens: {summary.get('event_frequency', 0):.1f}% av tiden")

        # Vis anbefalte terskelverdier
        thresholds = results.get('thresholds', {}).get('recommended_thresholds', {})
        print("\n🎯 ANBEFALTE TERSKELVERDIER:")
        print(f"• Rask endring (kritisk): {thresholds.get('rapid_change_critical', 0)*1000:.1f}mm/time")
        print(f"• Høy volatilitet (kritisk): {thresholds.get('high_volatility_critical', 0)*1000:.1f}mm std")

        # Vis nøkkelfunn
        key_findings = summary.get('key_findings', [])
        print("\n🔍 NØKKELFUNN:")
        for finding in key_findings:
            print(f"  • {finding}")

        print("\n💾 Resultater lagret i: data/analyzed/snow_depth_drift_analysis.json")

    else:
        print(f"\n❌ ANALYSE FEILET: {results.get('error', 'Ukjent feil')}")


if __name__ == "__main__":
    main()
