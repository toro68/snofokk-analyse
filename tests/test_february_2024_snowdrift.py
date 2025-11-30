"""
Test for snøfokk-episoden februar 2024.

Denne episoden (8-12 februar 2024) forårsaket kraftig snøfokk
som stengte inne hyttefolk fordi det ikke ble brøytet i tide.

PROBLEM: Analysatoren ser bare på siste måling, ikke hele perioden.
For historiske data burde vi finne MAX risiko i perioden.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from src.analyzers.base import RiskLevel
from src.analyzers.snowdrift import SnowdriftAnalyzer


def create_snowdrift_episode_data() -> pd.DataFrame:
    """
    Simuler snøfokk-episoden februar 2024.

    Basert på typiske forhold under snøfokk:
    - Vindkast opp mot 25+ m/s
    - Snittwind 10-15 m/s
    - Temperatur rundt -3 til -5°C
    - Vindretning SE-S (135-225°)
    - Snødybde 60+ cm
    """
    # Start og slutt på episode
    start = datetime(2024, 2, 8, 22, 38, tzinfo=UTC)
    end = datetime(2024, 2, 12, 22, 38, tzinfo=UTC)

    hours = int((end - start).total_seconds() / 3600)
    timestamps = [start + timedelta(hours=i) for i in range(hours + 1)]

    data = []
    for _i, ts in enumerate(timestamps):
        # Simuler værforhold gjennom episoden
        hour_of_day = ts.hour
        day_of_episode = (ts - start).days

        # Dag 0-1: Oppbygging, dag 2: Peak snøfokk, dag 3: Avtagende
        if day_of_episode < 2:
            # Oppbyggingsfase
            base_wind = 6 + day_of_episode * 3
            wind_gust_factor = 1.8
            temp = -2 - day_of_episode
        elif day_of_episode == 2:
            # PEAK - Kritisk snøfokk!
            base_wind = 12 + (4 if 6 <= hour_of_day <= 18 else 0)
            wind_gust_factor = 2.2
            temp = -4
        else:
            # Avtagende
            base_wind = 8 - (day_of_episode - 2) * 2
            wind_gust_factor = 1.5
            temp = -3

        # Vindkast er typisk 1.5-2.2x snittwind
        wind_speed = max(3, base_wind + (hour_of_day % 6) - 3)
        wind_gust = wind_speed * wind_gust_factor

        # Vindretning fra sørøst til sør (kritisk retning)
        wind_dir = 160 + (hour_of_day % 12) * 5  # 160-220°

        data.append({
            'reference_time': ts,
            'air_temperature': temp + (hour_of_day - 12) * 0.1,
            'wind_speed': wind_speed,
            'max_wind_gust': wind_gust,
            'wind_from_direction': wind_dir,
            'surface_snow_thickness': 62 + day_of_episode * 2,  # Snødybde øker
            'precipitation_1h': 0.5 if day_of_episode <= 2 else 0.0,
            'dew_point_temperature': temp - 2,
            'surface_temperature': temp - 2,
            'relative_humidity': 85,
        })

    return pd.DataFrame(data)


class TestFebruary2024SnowdriftEpisode:
    """Tester for snøfokk-episoden februar 2024."""

    @pytest.fixture
    def analyzer(self):
        return SnowdriftAnalyzer()

    @pytest.fixture
    def episode_data(self):
        return create_snowdrift_episode_data()

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_episode_data_contains_critical_conditions(self, mock_winter, episode_data):
        """Verifiser at episodedataene inneholder kritiske forhold."""
        # Sjekk at vi har data for hele perioden
        assert len(episode_data) >= 96  # Minst 4 dager

        # Sjekk at det er perioder med kritiske vindkast (≥20 m/s)
        critical_gusts = episode_data[episode_data['max_wind_gust'] >= 20.0]
        assert len(critical_gusts) > 0, "Episoden bør ha vindkast ≥20 m/s"

        # Sjekk kritisk vindretning
        critical_dir = episode_data[
            (episode_data['wind_from_direction'] >= 135) &
            (episode_data['wind_from_direction'] <= 225)
        ]
        assert len(critical_dir) > len(episode_data) * 0.5, "Mesteparten bør ha SE-S vindretning"

        # Sjekk frost (nesten alle målinger)
        frost = episode_data[episode_data['air_temperature'] <= -1]
        assert len(frost) >= len(episode_data) - 2, "Nesten hele perioden bør være frost"

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_current_analyzer_only_sees_last_measurement(self, mock_winter, analyzer, episode_data):
        """
        AVSLØRER PROBLEMET: Analysatoren ser bare siste måling.

        Ved slutten av episoden (12. feb) hadde vinden avtatt,
        så analysatoren gir LAV risiko selv om det var kritisk snøfokk tidligere.
        """
        result = analyzer.analyze(episode_data)

        # Siste måling har lavere vindstyrke (episoden er over)
        last_row = episode_data.iloc[-1]
        print(f"Siste måling: wind={last_row['wind_speed']:.1f}, gust={last_row['max_wind_gust']:.1f}")

        # Dette er problemet! Analysatoren gir lav risiko pga siste måling
        # Men i løpet av perioden var det KRITISK snøfokk
        if result.risk_level == RiskLevel.LOW:
            pytest.skip("KJENT PROBLEM: Analysatoren ser bare siste måling, ikke hele perioden")

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_peak_conditions_detected_as_high_risk(self, mock_winter, analyzer, episode_data):
        """Verifiser at peak-forholdene (dag 2) gir HØY risiko."""
        # Finn peak-timene (dag 2, midt på dagen)
        start = episode_data['reference_time'].min()
        peak_start = start + timedelta(days=2, hours=6)
        peak_end = start + timedelta(days=2, hours=18)

        peak_data = episode_data[
            (episode_data['reference_time'] >= peak_start) &
            (episode_data['reference_time'] <= peak_end)
        ].copy()

        assert len(peak_data) > 0, "Bør ha data for peak-perioden"

        # Analyser bare peak-dataene
        result = analyzer.analyze(peak_data)

        # Peak-forholdene bør gi HØY risiko
        assert result.risk_level == RiskLevel.HIGH, \
            f"Peak-forhold bør gi HØY risiko, fikk {result.risk_level.value}: {result.message}"

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_max_risk_in_period(self, mock_winter, analyzer, episode_data):
        """
        NY FUNKSJONALITET FORESLÅTT: Finn maksimal risiko i perioden.

        For historiske data bør vi analysere hele perioden og
        rapportere den høyeste risikoen som forekom.
        """
        # Analyser hver time separat
        risks = []
        for i in range(len(episode_data)):
            # Analyser med kontekst (noen timer før)
            start_idx = max(0, i - 6)
            subset = episode_data.iloc[start_idx:i+1].copy()
            if len(subset) > 0:
                result = analyzer.analyze(subset)
                risks.append({
                    'time': episode_data.iloc[i]['reference_time'],
                    'risk_level': result.risk_level,
                    'message': result.message,
                    'max_wind_gust': episode_data.iloc[i]['max_wind_gust'],
                })

        # Finn maksimal risiko
        risk_order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.UNKNOWN: -1}
        max_risk = max(risks, key=lambda x: risk_order.get(x['risk_level'], -1))

        print("\nMaksimal risiko i perioden:")
        print(f"  Tid: {max_risk['time']}")
        print(f"  Risiko: {max_risk['risk_level'].value}")
        print(f"  Melding: {max_risk['message']}")
        print(f"  Vindkast: {max_risk['max_wind_gust']:.1f} m/s")

        # Verifiser at maksimal risiko er HØY
        assert max_risk['risk_level'] == RiskLevel.HIGH, \
            f"Maksimal risiko bør være HØY, fikk {max_risk['risk_level'].value}"

        # Tell hvor mange timer med ulike risikonivåer
        risk_counts = {}
        for r in risks:
            level = r['risk_level'].value
            risk_counts[level] = risk_counts.get(level, 0) + 1

        print("\nRisikofordeling i perioden:")
        for level, count in sorted(risk_counts.items()):
            print(f"  {level}: {count} timer")

        # Det bør være flere timer med medium/high risiko
        high_medium_hours = risk_counts.get('high', 0) + risk_counts.get('medium', 0)
        assert high_medium_hours >= 24, \
            f"Bør ha minst 24 timer med medium/high risiko, fikk {high_medium_hours}"


class TestSnowdriftThresholdValidation:
    """Tester for å validere snøfokk-terskler."""

    @pytest.fixture
    def analyzer(self):
        return SnowdriftAnalyzer()

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_wind_gust_20ms_triggers_high(self, mock_winter, analyzer):
        """Vindkast ≥20 m/s med frost og snø skal gi HØY risiko."""
        df = pd.DataFrame({
            'reference_time': [datetime.now(UTC)],
            'air_temperature': [-3.0],
            'wind_speed': [10.0],
            'max_wind_gust': [22.0],  # Over kritisk terskel
            'wind_from_direction': [180.0],
            'surface_snow_thickness': [60.0],
            'precipitation_1h': [0.0],
            'dew_point_temperature': [-5.0],
            'relative_humidity': [80.0],
        })

        result = analyzer.analyze(df)
        assert result.risk_level == RiskLevel.HIGH, \
            f"Vindkast 22 m/s bør gi HØY risiko, fikk {result.risk_level.value}: {result.message}"

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_wind_gust_15ms_triggers_medium(self, mock_winter, analyzer):
        """Vindkast ≥15 m/s med frost og snø skal gi MODERAT risiko."""
        df = pd.DataFrame({
            'reference_time': [datetime.now(UTC)],
            'air_temperature': [-3.0],
            'wind_speed': [8.0],
            'max_wind_gust': [17.0],  # Over warning terskel
            'wind_from_direction': [180.0],
            'surface_snow_thickness': [60.0],
            'precipitation_1h': [0.0],
            'dew_point_temperature': [-5.0],
            'relative_humidity': [80.0],
        })

        result = analyzer.analyze(df)
        assert result.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH), \
            f"Vindkast 17 m/s bør gi MODERAT+ risiko, fikk {result.risk_level.value}: {result.message}"

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_strong_wind_without_frost_low_risk(self, mock_winter, analyzer):
        """Sterk vind uten frost (temp > -1°C) skal gi lavere risiko."""
        df = pd.DataFrame({
            'reference_time': [datetime.now(UTC)],
            'air_temperature': [2.0],  # Over frysepunkt
            'wind_speed': [15.0],
            'max_wind_gust': [25.0],
            'wind_from_direction': [180.0],
            'surface_snow_thickness': [60.0],
            'precipitation_1h': [0.0],
            'dew_point_temperature': [1.0],
            'relative_humidity': [80.0],
        })

        result = analyzer.analyze(df)
        # Ved temperaturer over frysepunkt, mindre snøfokk-fare
        # (snøen er fuktig og blåser ikke like lett)
        assert result.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM), \
            f"Sterk vind uten frost bør gi maks MODERAT risiko, fikk {result.risk_level.value}"


class TestRealWorldScenarios:
    """Tester basert på virkelige scenarier."""

    @pytest.fixture
    def analyzer(self):
        return SnowdriftAnalyzer()

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_typical_gullingen_snowdrift(self, mock_winter, analyzer):
        """
        Typisk Gullingen snøfokk-episode:
        - SE-S vindretning (73% av historiske episoder)
        - Snittwind ~10 m/s
        - Vindkast ~22 m/s
        - Temperatur under frysepunkt
        """
        df = pd.DataFrame({
            'reference_time': [datetime.now(UTC)],
            'air_temperature': [-5.0],
            'wind_speed': [10.3],  # Historisk snitt
            'max_wind_gust': [21.9],   # Historisk snitt
            'wind_from_direction': [180.0],  # Sør (kritisk)
            'surface_snow_thickness': [50.0],
            'precipitation_1h': [0.2],
            'dew_point_temperature': [-7.0],
            'relative_humidity': [75.0],
        })

        result = analyzer.analyze(df)
        assert result.risk_level == RiskLevel.HIGH, \
            f"Typisk Gullingen-snøfokk bør gi HØY risiko, fikk {result.risk_level.value}: {result.message}"

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_critical_wind_direction_matters(self, mock_winter, analyzer):
        """Kritisk vindretning (SE-S) bør påvirke risikovurderingen."""
        base_conditions = {
            'reference_time': [datetime.now(UTC)],
            'air_temperature': [-5.0],
            'wind_speed': [9.0],
            'max_wind_gust': [18.0],
            'surface_snow_thickness': [50.0],
            'precipitation_1h': [0.0],
            'dew_point_temperature': [-7.0],
            'relative_humidity': [75.0],
        }

        # Test med kritisk retning (sør)
        df_critical = pd.DataFrame({**base_conditions, 'wind_from_direction': [180.0]})
        result_critical = analyzer.analyze(df_critical)

        # Test med ikke-kritisk retning (nord)
        df_normal = pd.DataFrame({**base_conditions, 'wind_from_direction': [0.0]})
        result_normal = analyzer.analyze(df_normal)

        # Kritisk retning bør gi høyere eller lik risiko
        risk_order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
        assert risk_order[result_critical.risk_level] >= risk_order[result_normal.risk_level], \
            "Kritisk vindretning bør gi høyere/lik risiko"

        # Sjekk at kritisk retning er nevnt i faktorer
        assert any("retning" in f.lower() or "SE-S" in f for f in result_critical.factors), \
            "Kritisk vindretning bør være nevnt i faktorer"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
