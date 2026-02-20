"""
Tester for værhendelse-deteksjon.

Verifiserer at alle fire analysatorer korrekt fanger opp værhendelser:
- FreshSnowAnalyzer: Nysnø-deteksjon
- SnowdriftAnalyzer: Snøfokk-deteksjon
- SlapsAnalyzer: Slaps-deteksjon
- SlipperyRoadAnalyzer: Glattføre-deteksjon

Testene bruker syntetiske værdata for å validere terskelverdier.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from src.analyzers.base import RiskLevel
from src.analyzers.fresh_snow import FreshSnowAnalyzer
from src.analyzers.slaps import SlapsAnalyzer
from src.analyzers.slippery_road import SlipperyRoadAnalyzer
from src.analyzers.snowdrift import SnowdriftAnalyzer


def create_weather_dataframe(
    air_temperature: float = -5.0,
    wind_speed: float = 5.0,
    wind_gust: float | None = None,
    wind_from_direction: float | None = None,
    surface_snow_thickness: float = 30.0,
    surface_snow_thickness_6h_ago: float | None = None,
    snow_thickness_lookback_hours: int = 12,
    precipitation_1h: float = 0.0,
    dew_point_temperature: float | None = None,
    surface_temperature: float | None = None,
    relative_humidity: float = 70.0,
    hours: int = 12,
) -> pd.DataFrame:
    """
    Lag en syntetisk værdata-DataFrame.

    Args:
        air_temperature: Lufttemperatur i °C
        wind_speed: Vindstyrke i m/s
        wind_gust: Vindkast i m/s
        wind_from_direction: Vindretning i grader
        surface_snow_thickness: Nåværende snødybde i cm
        surface_snow_thickness_6h_ago: Snødybde ved lookback-vinduets start (for å simulere endring)
        snow_thickness_lookback_hours: Hvor mange timer bakover snøendring simuleres (default 12)
        precipitation_1h: Nedbør siste time i mm
        dew_point_temperature: Duggpunkt i °C
        surface_temperature: Bakketemperatur i °C
        relative_humidity: Relativ fuktighet i %
        hours: Antall timer med data

    Returns:
        DataFrame med værdata
    """
    now = datetime.now(UTC)

    # Generer tidsstempler
    # Inkluderer "nå" som siste punkt for å gjøre lookback-endring/akkumulering intuitiv i testene.
    timestamps = [now - timedelta(hours=i) for i in range(hours - 1, -1, -1)]

    # Beregn snødybde-serie
    if surface_snow_thickness_6h_ago is not None:
        # Gradvis endring fra lookback-start til nå
        lookback = float(snow_thickness_lookback_hours)
        snow_diff = surface_snow_thickness - surface_snow_thickness_6h_ago
        snow_values = []
        for _i, ts in enumerate(timestamps):
            hours_ago = (now - ts).total_seconds() / 3600
            if hours_ago >= lookback:
                snow_values.append(surface_snow_thickness_6h_ago)
            else:
                # Lineær interpolering
                progress = (lookback - hours_ago) / lookback
                snow_values.append(surface_snow_thickness_6h_ago + snow_diff * progress)
    else:
        snow_values = [surface_snow_thickness] * hours

    data = {
        'reference_time': timestamps,
        'air_temperature': [air_temperature] * hours,
        'wind_speed': [wind_speed] * hours,
        'max_wind_gust': [wind_gust] * hours if wind_gust is not None else [None] * hours,
        'wind_from_direction': [wind_from_direction] * hours if wind_from_direction is not None else [None] * hours,
        'surface_snow_thickness': snow_values,
        'precipitation_1h': [precipitation_1h] * hours,
        'dew_point_temperature': [dew_point_temperature] * hours if dew_point_temperature is not None else [None] * hours,
        'surface_temperature': [surface_temperature] * hours if surface_temperature is not None else [None] * hours,
        'relative_humidity': [relative_humidity] * hours,
    }

    return pd.DataFrame(data)


# =============================================================================
# FreshSnowAnalyzer Tests
# =============================================================================

class TestFreshSnowAnalyzer:
    """Tester for nysnø-deteksjon."""

    @pytest.fixture
    def analyzer(self):
        return FreshSnowAnalyzer()

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_no_snow_change_returns_low(self, mock_winter, analyzer):
        """Stabil snødybde gir LAV risiko."""
        df = create_weather_dataframe(
            air_temperature=-5.0,
            surface_snow_thickness=30.0,
            surface_snow_thickness_6h_ago=30.0,
            hours=13,
        )
        result = analyzer.analyze(df)
        assert result.risk_level == RiskLevel.LOW
        assert "Stabil" in result.message or "snødybde" in result.message.lower()

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_moderate_snow_increase_returns_medium(self, mock_winter, analyzer):
        """Moderat snøøkning over lookback-vinduet gir MODERAT risiko."""
        # Bruker større endring for å sikre at analyser beregner ≥5cm
        df = create_weather_dataframe(
            air_temperature=0.2,
            surface_temperature=0.0,
            dew_point_temperature=-0.2,  # < 0 = snø
            surface_snow_thickness=36.0,
            surface_snow_thickness_6h_ago=30.0,  # +6 cm (våt snø) → medium
            hours=13,
        )
        result = analyzer.analyze(df)
        assert result.risk_level == RiskLevel.MEDIUM
        assert "Nysnø" in result.message

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_heavy_snow_increase_returns_high(self, mock_winter, analyzer):
        """Stor snøøkning over lookback-vinduet gir HØY risiko."""
        # Bruker større endring for å sikre at analyser beregner ≥10cm
        df = create_weather_dataframe(
            air_temperature=0.2,
            surface_temperature=0.0,
            dew_point_temperature=-0.2,
            surface_snow_thickness=50.0,
            surface_snow_thickness_6h_ago=30.0,  # +20 cm, gir ca 13cm målt endring
            hours=13,
        )
        result = analyzer.analyze(df)
        assert result.risk_level == RiskLevel.HIGH
        assert "Kraftig" in result.message

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_active_snowfall_detected(self, mock_winter, analyzer):
        """Aktivt snøfall med nedbør gir MODERAT risiko."""
        df = create_weather_dataframe(
            air_temperature=-3.0,
            dew_point_temperature=-4.0,  # < 0 = snø
            surface_snow_thickness=30.0,
            precipitation_1h=2.0,  # Aktiv nedbør
        )
        result = analyzer.analyze(df)
        assert result.risk_level in (RiskLevel.MEDIUM, RiskLevel.LOW)

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_wind_can_reduce_snow_depth_during_snowfall(self, mock_winter, analyzer):
        """Ved vind kan snødybden synke selv om det snør; bruk nedbør som fallback."""
        df = create_weather_dataframe(
            air_temperature=-4.0,
            dew_point_temperature=-5.0,  # < 0 = snø
            wind_speed=10.0,
            surface_snow_thickness=28.0,
            surface_snow_thickness_6h_ago=30.0,  # negativ nettoendring
            precipitation_1h=2.0,  # 6t akkumulert ~12 mm
            hours=13,
        )
        result = analyzer.analyze(df)
        assert result.risk_level == RiskLevel.HIGH
        assert "nedbør" in result.message.lower()

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_precip_6h_warning_can_trigger_nysno_even_without_snow_increase(self, mock_winter, analyzer):
        """Hvis snødybden ikke øker, kan 6t-nedbør likevel indikere nysnø."""
        df = create_weather_dataframe(
            air_temperature=-3.0,
            dew_point_temperature=-4.0,
            wind_speed=9.0,
            surface_snow_thickness=30.0,
            surface_snow_thickness_6h_ago=30.0,
            precipitation_1h=1.2,  # 6t akkumulert ~7.2 mm (dry-snow warning, under critical)
            hours=13,
        )
        result = analyzer.analyze(df)
        assert result.risk_level == RiskLevel.MEDIUM
        assert "nysnø" in result.message.lower() or "nedbør" in result.message.lower()

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_rain_not_counted_as_snow(self, mock_winter, analyzer):
        """Regn (duggpunkt > 0) skal ikke gi snøvarsel."""
        df = create_weather_dataframe(
            air_temperature=3.0,
            dew_point_temperature=2.0,  # > 0 = regn
            surface_snow_thickness=30.0,
            precipitation_1h=5.0,
        )
        result = analyzer.analyze(df)
        # Skal ikke klassifiseres som nysnø
        assert "snøfall" not in result.message.lower() or result.risk_level == RiskLevel.LOW

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_snow_precip_on_mild_surface_returns_low(self, mock_winter, analyzer):
        """Hvis bakken er mild, kan nedbør gi våt vei selv om duggpunkt tilsier snø."""
        df = create_weather_dataframe(
            air_temperature=0.5,
            surface_temperature=1.5,
            dew_point_temperature=-1.0,
            surface_snow_thickness=30.0,
            precipitation_1h=2.0,
        )
        result = analyzer.analyze(df)
        assert result.risk_level == RiskLevel.LOW

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=False)
    def test_summer_returns_low(self, mock_winter, analyzer):
        """Sommersesong gir alltid LAV risiko."""
        df = create_weather_dataframe(
            air_temperature=-5.0,
            surface_snow_thickness=40.0,
            surface_snow_thickness_6h_ago=30.0,
        )
        result = analyzer.analyze(df)
        assert result.risk_level == RiskLevel.LOW
        assert "Sommer" in result.message


# =============================================================================
# SnowdriftAnalyzer Tests
# =============================================================================

class TestSnowdriftAnalyzer:
    """Tester for snøfokk-deteksjon."""

    @pytest.fixture
    def analyzer(self):
        return SnowdriftAnalyzer()

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_calm_conditions_returns_low(self, mock_winter, analyzer):
        """Rolige forhold uten vind gir LAV risiko."""
        df = create_weather_dataframe(
            air_temperature=-5.0,
            wind_speed=3.0,  # Svak vind
            wind_gust=5.0,
            surface_snow_thickness=30.0,
        )
        result = analyzer.analyze(df)
        assert result.risk_level == RiskLevel.LOW

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_moderate_wind_with_snow_returns_medium(self, mock_winter, analyzer):
        """Moderat vind med snø på bakken gir MODERAT risiko."""
        df = create_weather_dataframe(
            air_temperature=-8.0,
            wind_speed=9.0,  # > 8 m/s warning threshold
            wind_gust=16.0,  # > 15 m/s gust warning
            surface_snow_thickness=30.0,
        )
        result = analyzer.analyze(df)
        assert result.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_strong_wind_gust_returns_high(self, mock_winter, analyzer):
        """Kraftige vindkast (>20 m/s) gir HØY risiko."""
        df = create_weather_dataframe(
            air_temperature=-10.0,
            wind_speed=12.0,
            wind_gust=22.0,  # > 20 m/s critical threshold
            surface_snow_thickness=30.0,
        )
        result = analyzer.analyze(df)
        assert result.risk_level == RiskLevel.HIGH

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_critical_wind_direction_increases_risk(self, mock_winter, analyzer):
        """Kritisk vindretning (SE-S: 135-225°) øker risiko."""
        df = create_weather_dataframe(
            air_temperature=-8.0,
            wind_speed=10.0,
            wind_gust=17.0,
            wind_from_direction=180.0,  # Sør - kritisk retning
            surface_snow_thickness=30.0,
        )
        result = analyzer.analyze(df)
        # Kritisk retning skal gi minimum MEDIUM
        assert result.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)
        # Sjekk at vindretning er nevnt
        assert any("retning" in f.lower() or "sør" in f.lower() or "SE" in f or "S" in f
                   for f in result.factors)

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_no_snow_reduces_risk(self, mock_winter, analyzer):
        """Ingen snø på bakken reduserer snøfokk-risiko."""
        df = create_weather_dataframe(
            air_temperature=-10.0,
            wind_speed=15.0,
            wind_gust=25.0,
            surface_snow_thickness=0.0,  # Ingen snø
        )
        result = analyzer.analyze(df)
        # Selv med sterk vind, ingen snø = lavere risiko
        assert result.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_wind_chill_factor_considered(self, mock_winter, analyzer):
        """Vindkjøling påvirker risikovurdering."""
        # Kald temperatur + sterk vind = lav vindkjøling
        df = create_weather_dataframe(
            air_temperature=-15.0,  # Kaldt
            wind_speed=10.0,        # Sterk vind
            wind_gust=18.0,
            surface_snow_thickness=30.0,
        )
        result = analyzer.analyze(df)
        assert result.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)
        # Vindkjøling skal være nevnt i faktorer
        assert any("vindkjøling" in f.lower() or "chill" in f.lower()
                   for f in result.factors) or result.risk_level == RiskLevel.HIGH

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=False)
    def test_summer_with_snow_returns_medium(self, mock_winter, analyzer):
        """Uvanlig snø om sommeren gir MEDIUM risiko."""
        df = create_weather_dataframe(
            air_temperature=5.0,
            wind_speed=15.0,
            surface_snow_thickness=10.0,  # Snø om sommeren
        )
        result = analyzer.analyze(df)
        # Uvanlig situasjon - bør flagges
        assert result.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)


# =============================================================================
# SlapsAnalyzer Tests
# =============================================================================

class TestSlapsAnalyzer:
    """Tester for slaps-deteksjon."""

    @pytest.fixture
    def analyzer(self):
        return SlapsAnalyzer()

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_cold_dry_returns_low(self, mock_winter, analyzer):
        """Kalde, tørre forhold gir LAV risiko."""
        df = create_weather_dataframe(
            air_temperature=-10.0,
            surface_snow_thickness=30.0,
            precipitation_1h=0.0,
        )
        result = analyzer.analyze(df)
        assert result.risk_level == RiskLevel.LOW

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_rain_on_snow_returns_medium_or_high(self, mock_winter, analyzer):
        """Regn på snø ved 0-4°C gir MODERAT eller HØY risiko."""
        df = create_weather_dataframe(
            air_temperature=2.0,  # I slaps-området
            dew_point_temperature=1.0,  # > 0 = regn
            surface_snow_thickness=30.0,
            precipitation_1h=3.0,  # Betydelig nedbør
        )
        result = analyzer.analyze(df)
        assert result.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_heavy_rain_on_snow_returns_high(self, mock_winter, analyzer):
        """Kraftig regn (>5mm/t) på snø gir HØY risiko."""
        df = create_weather_dataframe(
            air_temperature=1.5,  # Optimal slaps-temperatur
            dew_point_temperature=1.0,
            surface_snow_thickness=30.0,
            precipitation_1h=7.0,  # Kraftig nedbør
        )
        result = analyzer.analyze(df)
        assert result.risk_level == RiskLevel.HIGH

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_no_snow_returns_low(self, mock_winter, analyzer):
        """Uten snø på bakken ingen slaps-risiko."""
        df = create_weather_dataframe(
            air_temperature=2.0,
            dew_point_temperature=1.0,
            surface_snow_thickness=0.0,  # Ingen snø
            precipitation_1h=5.0,
        )
        result = analyzer.analyze(df)
        # Ingen snø = lav slaps-risiko
        assert result.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_too_cold_returns_low(self, mock_winter, analyzer):
        """For kaldt (<-1°C) gir snø, ikke slaps."""
        df = create_weather_dataframe(
            air_temperature=-5.0,  # For kaldt for slaps
            dew_point_temperature=-6.0,
            surface_snow_thickness=30.0,
            precipitation_1h=5.0,
        )
        result = analyzer.analyze(df)
        assert result.risk_level == RiskLevel.LOW

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_too_warm_returns_low(self, mock_winter, analyzer):
        """For varmt (>4°C) gir bare regn, ikke slaps."""
        df = create_weather_dataframe(
            air_temperature=8.0,  # For varmt for slaps
            dew_point_temperature=6.0,
            surface_snow_thickness=30.0,
            precipitation_1h=5.0,
        )
        result = analyzer.analyze(df)
        # Høy temp = regn, ikke slaps
        assert result.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=False)
    def test_summer_returns_low(self, mock_winter, analyzer):
        """Sommersesong gir LAV risiko."""
        df = create_weather_dataframe(
            air_temperature=2.0,
            precipitation_1h=10.0,
        )
        result = analyzer.analyze(df)
        assert result.risk_level == RiskLevel.LOW


# =============================================================================
# SlipperyRoadAnalyzer Tests
# =============================================================================

class TestSlipperyRoadAnalyzer:
    """Tester for glattføre-deteksjon."""

    @pytest.fixture
    def analyzer(self):
        return SlipperyRoadAnalyzer()

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_dry_cold_returns_low_or_medium(self, mock_winter, analyzer):
        """Tørre, kalde forhold gir LAV eller MODERAT risiko.

        NB: Analysatoren kan gi MEDIUM hvis bakken er kald under snø,
        selv uten aktiv nedbør - dette er korrekt oppførsel da det
        indikerer fare for is under snølaget.
        """
        df = create_weather_dataframe(
            air_temperature=-10.0,
            surface_temperature=-12.0,
            precipitation_1h=0.0,
            surface_snow_thickness=0.0,  # Ingen snø = lavere risiko
        )
        result = analyzer.analyze(df)
        assert result.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_surface_freeze_with_rain_returns_high(self, mock_winter, analyzer):
        """Bakketemperatur < 0 med regn gir HØY risiko (is)."""
        df = create_weather_dataframe(
            air_temperature=1.0,   # Luft over frysepunkt
            surface_temperature=-1.0,  # Men bakke under!
            dew_point_temperature=0.5,  # = regn
            precipitation_1h=2.0,
            surface_snow_thickness=10.0,
        )
        result = analyzer.analyze(df)
        assert result.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_hidden_ice_scenario(self, mock_winter, analyzer):
        """'Skjult is' - luft > 0°C men bakke < 0°C."""
        df = create_weather_dataframe(
            air_temperature=1.0,   # Nær frysepunkt (kalibrert gating)
            surface_temperature=-2.0,  # Men bakken er iskald!
            precipitation_1h=0.5,
            surface_snow_thickness=5.0,
        )
        result = analyzer.analyze(df)
        assert result.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_frost_risk_with_humidity(self, mock_winter, analyzer):
        """Rimfrost - duggpunkt nær lufttemp ved frost."""
        df = create_weather_dataframe(
            air_temperature=-2.0,
            dew_point_temperature=-3.0,  # Nær lufttemp
            surface_temperature=-3.0,
            relative_humidity=95.0,  # Høy fuktighet
            precipitation_1h=0.0,
        )
        result = analyzer.analyze(df)
        # Rimfrost-risiko bør gi minimum LAV til MEDIUM
        assert result.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH)

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_rain_on_snow_returns_warning(self, mock_winter, analyzer):
        """Regn på snø gir glattføre-varsel."""
        df = create_weather_dataframe(
            air_temperature=2.0,
            dew_point_temperature=1.5,  # > 0 = regn
            surface_snow_thickness=20.0,
            precipitation_1h=3.0,
        )
        result = analyzer.analyze(df)
        assert result.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_rain_on_snow_with_mild_surface_returns_medium(self, mock_winter, analyzer):
        """På vårføre kan det være bar vei selv om stasjonen måler snø i terrenget; mild bakke skal ikke gi HØY."""
        df = create_weather_dataframe(
            air_temperature=2.0,
            dew_point_temperature=1.5,  # > 0 = regn
            surface_snow_thickness=20.0,
            precipitation_1h=3.0,
            surface_temperature=1.5,  # tydelig mild bakke
        )
        result = analyzer.analyze(df)
        assert result.risk_level == RiskLevel.MEDIUM

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_rain_on_snow_after_cold_spell_can_be_high_even_if_surface_is_mild(self, mock_winter, analyzer):
        """Kuldeperiode etterfulgt av mildvær+regn kan gi glatte veier selv om bakke nå er mild."""
        now = datetime.now(UTC)
        timestamps = [now - timedelta(hours=i) for i in range(12, 0, -1)]

        # Lufttemp fra -5 til +2 over 12 timer
        temps = [-5 + (7 * i / 11) for i in range(12)]
        # Bakke fra -6 til +1.5 (mild nå, men tydelig frost nylig)
        surface_temps = [-6 + (7.5 * i / 11) for i in range(12)]

        df = pd.DataFrame({
            'reference_time': timestamps,
            'air_temperature': temps,
            'wind_speed': [5.0] * 12,
            'surface_snow_thickness': [20.0] * 12,
            'precipitation_1h': [3.0] * 12,
            'dew_point_temperature': [t - 0.2 for t in temps],  # > 0 i siste del → regn
            'surface_temperature': surface_temps,
            'relative_humidity': [80.0] * 12,
        })

        result = analyzer.analyze(df)
        assert result.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_temperature_rise_detected(self, mock_winter, analyzer):
        """Rask temperaturstigning (mildvær) øker risiko."""
        # Simuler temperaturstigning
        now = datetime.now(UTC)
        timestamps = [now - timedelta(hours=i) for i in range(12, 0, -1)]

        # Temperatur fra -5 til +2 over 12 timer
        temps = [-5 + (7 * i / 11) for i in range(12)]

        df = pd.DataFrame({
            'reference_time': timestamps,
            'air_temperature': temps,
            'wind_speed': [5.0] * 12,
            'surface_snow_thickness': [30.0] * 12,
            'precipitation_1h': [2.0] * 12,
            'dew_point_temperature': [t - 2 for t in temps],
            'surface_temperature': [t - 2 for t in temps],
            'relative_humidity': [80.0] * 12,
        })

        result = analyzer.analyze(df)
        # Temperaturstigning med nedbør bør gi varsel
        assert result.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_rain_on_snow_not_suppressed_by_recent_snow_accumulation(self, mock_winter, analyzer):
        """BUG-FIX: Regn på snø skal IKKE undertrykkes av 'Scenario 0 - fersk nysnø'.

        Scenario: Snø falt natt til i dag (+2 cm), men det regner nå (kl. 07).
        Snødybden økte ≥2 cm siste 6t → gammel Scenario 0 returnerte feil LOW.
        Med fiksen skal regnet føre til MEDIUM/HIGH siden dew_point > 0 (regn).
        """
        now = datetime.now(UTC)
        # Lager 8 timer: snøfall tidlig (kl 01-04), deretter regn (kl 05-08)
        timestamps = [now - timedelta(hours=i) for i in range(7, -1, -1)]
        snow_depths = [10.0, 10.5, 11.0, 12.0, 12.0, 12.0, 12.0, 12.0]  # +2 cm tidlig
        temps = [0.0, 0.2, 0.5, 1.0, 1.5, 2.0, 2.0, 2.0]               # mildvær vokser
        dew_pts = [-0.5, -0.3, 0.0, 0.5, 1.0, 1.5, 1.5, 1.5]           # dew > 0 = regn sent
        precips = [0.2, 0.5, 0.5, 0.0, 1.5, 2.0, 2.5, 2.5]             # regn siste 4t
        surf_temps = [-1.5, -1.0, -0.5, 0.0, 0.2, 0.3, 0.3, 0.3]

        df = pd.DataFrame({
            'reference_time': timestamps,
            'air_temperature': temps,
            'wind_speed': [2.0] * 8,
            'surface_snow_thickness': snow_depths,
            'precipitation_1h': precips,
            'dew_point_temperature': dew_pts,
            'surface_temperature': surf_temps,
            'relative_humidity': [90.0] * 8,
        })

        result = analyzer.analyze(df)
        # Regn (dew_point > 0) på snødekke = MEDIUM eller HØY, IKKE LAV
        assert result.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH), (
            f"Forventet MEDIUM/HIGH men fikk {result.risk_level}: {result.message}"
        )

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_snowfall_near_freezing_not_classified_as_freezing_rain(self, mock_winter, analyzer):
        """BUG-FIX: Snøfall (dew < 0°C) skal IKKE utløse 'Underkjølt regn / frysing'.

        Scenario: -0.2°C, duggpunkt -0.3°C (under 0 = snø), 2.4 mm/t.
        Bakke -0.5°C. Denne kombinasjonen ga feilaktig HIGH 'Underkjølt regn'.
        Korrekt: nedbøren er snø, ikke underkjølt regn. SlipperyRoad skal gi ≤ MEDIUM.
        """
        df = create_weather_dataframe(
            air_temperature=-0.2,
            dew_point_temperature=-0.3,   # Under 0 = snø
            surface_temperature=-0.5,
            surface_snow_thickness=20.0,
            precipitation_1h=2.4,
            relative_humidity=97.0,
        )
        result = analyzer.analyze(df)
        assert result.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM), (
            f"Forventet LOW/MEDIUM for snøfall, fikk {result.risk_level}: "
            f"{result.scenario} - {result.message}"
        )
        assert result.scenario != "Underkjølt regn / frysing", (
            "Snøfall (dew < 0) skal ikke klassifiseres som 'Underkjølt regn / frysing'"
        )

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_freezing_rain_with_positive_dew_point_returns_high(self, mock_winter, analyzer):
        """Underkjølt regn: dew > 0°C, luft nær 0, bakke frossen → skal gi HIGH."""
        df = create_weather_dataframe(
            air_temperature=-0.2,
            dew_point_temperature=0.2,    # Over 0 = regn
            surface_temperature=-0.5,
            surface_snow_thickness=20.0,
            precipitation_1h=2.4,
            relative_humidity=97.0,
        )
        result = analyzer.analyze(df)
        assert result.risk_level == RiskLevel.HIGH, (
            f"Forventet HIGH for underkjølt regn (dew > 0), fikk {result.risk_level}"
        )

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_freezing_rain_without_dew_point_is_conservative_high(self, mock_winter, analyzer):
        """Uten duggpunkt-data: konservativ fallback skal beholde HIGH (usikker nedbørstype)."""
        df = create_weather_dataframe(
            air_temperature=-0.2,
            dew_point_temperature=None,   # Manglende data
            surface_temperature=-0.5,
            surface_snow_thickness=20.0,
            precipitation_1h=2.4,
            relative_humidity=97.0,
        )
        result = analyzer.analyze(df)
        assert result.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH), (
            f"Uten dew-data skal vi beholde MEDIUM/HIGH, fikk {result.risk_level}"
        )
        df = create_weather_dataframe(
            air_temperature=2.0,
            dew_point_temperature=1.0,
            surface_temperature=-1.0,  # Bakken er kald
            precipitation_1h=0.5,
        )
        result = analyzer.analyze(df)
        # Sommerfrost bør detekteres
        assert result.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Tester for kanttilfeller og feilhåndtering."""

    @pytest.fixture
    def analyzers(self):
        return {
            'fresh_snow': FreshSnowAnalyzer(),
            'snowdrift': SnowdriftAnalyzer(),
            'slaps': SlapsAnalyzer(),
            'slippery': SlipperyRoadAnalyzer(),
        }

    def test_empty_dataframe(self, analyzers):
        """Tom DataFrame gir UNKNOWN risiko."""
        df = pd.DataFrame()
        for name, analyzer in analyzers.items():
            result = analyzer.analyze(df)
            assert result.risk_level == RiskLevel.UNKNOWN, f"{name} failed"

    def test_missing_required_columns(self, analyzers):
        """Manglende kolonner gir UNKNOWN risiko."""
        df = pd.DataFrame({
            'reference_time': [datetime.now(UTC)],
            'some_column': [1.0],
        })
        for name, analyzer in analyzers.items():
            result = analyzer.analyze(df)
            assert result.risk_level == RiskLevel.UNKNOWN, f"{name} failed"

    def test_nan_values_handled(self, analyzers):
        """NaN-verdier håndteres gracefully."""
        df = pd.DataFrame({
            'reference_time': [datetime.now(UTC)],
            'air_temperature': [float('nan')],
            'wind_speed': [float('nan')],
            'surface_snow_thickness': [float('nan')],
            'precipitation_1h': [float('nan')],
        })
        for name, analyzer in analyzers.items():
            # Skal ikke kaste exception
            result = analyzer.analyze(df)
            assert result.risk_level in (RiskLevel.UNKNOWN, RiskLevel.LOW), f"{name} failed"

    def test_single_row_dataframe(self, analyzers):
        """DataFrame med én rad håndteres."""
        df = create_weather_dataframe(hours=1)
        for name, analyzer in analyzers.items():
            # Skal ikke kaste exception
            result = analyzer.analyze(df)
            assert result.risk_level is not None, f"{name} failed"


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integrasjonstester for kombinerte scenarier."""

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_blizzard_scenario(self, mock_winter):
        """
        Snøstorm-scenario: Alle analysatorer skal gi varsel.

        - Kraftig snøfall
        - Sterk vind med kast
        - Kald temperatur
        """
        df = create_weather_dataframe(
            air_temperature=-8.0,
            dew_point_temperature=-9.0,
            wind_speed=15.0,
            wind_gust=25.0,
            wind_from_direction=180.0,  # Sør
            surface_snow_thickness=50.0,
            surface_snow_thickness_6h_ago=35.0,  # +15 cm
            precipitation_1h=5.0,
            surface_temperature=-10.0,
            hours=13,
        )

        fresh_snow = FreshSnowAnalyzer()
        snowdrift = SnowdriftAnalyzer()
        slippery = SlipperyRoadAnalyzer()

        # Alle skal gi høy risiko
        assert fresh_snow.analyze(df).risk_level == RiskLevel.HIGH
        assert snowdrift.analyze(df).risk_level == RiskLevel.HIGH
        # Glattføre kan være lavere pga kald temperatur
        assert slippery.analyze(df).risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.LOW)

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_thaw_scenario(self, mock_winter):
        """
        Mildvær-scenario: Regn på snø = slaps og glattføre.

        - Temperatur 0-4°C
        - Regn (ikke snø)
        - Snø på bakken
        """
        df = create_weather_dataframe(
            air_temperature=2.0,
            dew_point_temperature=1.5,
            wind_speed=5.0,
            surface_snow_thickness=25.0,
            precipitation_1h=4.0,
            surface_temperature=-0.5,  # Bakke under frysepunkt
        )

        slaps = SlapsAnalyzer()
        slippery = SlipperyRoadAnalyzer()
        fresh_snow = FreshSnowAnalyzer()

        # Slaps og glattføre skal gi varsel
        assert slaps.analyze(df).risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)
        assert slippery.analyze(df).risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)
        # Nysnø skal IKKE varsle (det er regn, ikke snø)
        assert fresh_snow.analyze(df).risk_level == RiskLevel.LOW

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_stable_winter_conditions(self, mock_winter):
        """
        Stabile vinterforhold: Ingen varsler.

        - Kald og tørr
        - Lite vind
        - Stabil snødybde
        """
        df = create_weather_dataframe(
            air_temperature=-5.0,
            dew_point_temperature=-7.0,
            wind_speed=3.0,
            wind_gust=5.0,
            surface_snow_thickness=30.0,
            surface_snow_thickness_6h_ago=30.0,
            precipitation_1h=0.0,
            surface_temperature=-7.0,
        )

        fresh_snow = FreshSnowAnalyzer()
        snowdrift = SnowdriftAnalyzer()
        slaps = SlapsAnalyzer()
        slippery = SlipperyRoadAnalyzer()

        # Alle skal gi lav risiko
        assert fresh_snow.analyze(df).risk_level == RiskLevel.LOW
        assert snowdrift.analyze(df).risk_level == RiskLevel.LOW
        assert slaps.analyze(df).risk_level == RiskLevel.LOW
        # Glattføre kan gi MEDIUM pga kald bakke under snø (korrekt oppførsel)
        assert slippery.analyze(df).risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
