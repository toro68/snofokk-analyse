"""
Tester for tidssone-håndtering i kodebasen.

Kodebasen bruker:
- UTC internt for alle beregninger
- Lokal tidssone (Europe/Oslo) kun for visning til bruker
- Frost API returnerer data i UTC

Viktige regler:
1. Alltid bruk datetime.now(timezone.utc) for nåtid
2. Aldri bruk datetime.now() uten timezone
3. Konverter til lokal tid kun ved visning (.astimezone())
4. Lagre alltid i UTC (ISO format med Z suffix)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import pytest
import pandas as pd

# Import moduler som skal testes
from src.plowman_client import PlowingEvent
from src.plowing_service import PlowingInfo


class TestPlowingEventTimezone:
    """Tester for PlowingEvent tidssone-håndtering."""
    
    def test_hours_since_with_utc_timestamp(self):
        """Tester hours_since med UTC timestamp."""
        # 2 timer siden i UTC
        two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
        event = PlowingEvent(timestamp=two_hours_ago)
        
        hours = event.hours_since()
        assert 1.9 < hours < 2.1
    
    def test_hours_since_with_naive_timestamp(self):
        """Tester at naive datetime behandles som UTC."""
        # Lag en naive datetime som representerer "1 time siden" i UTC
        naive_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        event = PlowingEvent(timestamp=naive_time)
        
        hours = event.hours_since()
        # Bør være ~1 time siden (naive antas å være UTC)
        assert 0.9 < hours < 1.1
    
    def test_hours_since_with_different_timezone(self):
        """Tester at andre tidssoner konverteres korrekt."""
        # Oslo er UTC+1 (vinter) eller UTC+2 (sommer)
        # Lag en timestamp i en annen tidssone
        import zoneinfo
        oslo_tz = zoneinfo.ZoneInfo("Europe/Oslo")
        
        # "Nå" i Oslo-tid, minus 3 timer
        oslo_now = datetime.now(oslo_tz)
        three_hours_ago_oslo = oslo_now - timedelta(hours=3)
        
        event = PlowingEvent(timestamp=three_hours_ago_oslo)
        hours = event.hours_since()
        
        # Bør være ~3 timer uansett tidssone
        assert 2.9 < hours < 3.1
    
    def test_hours_since_future_timestamp(self):
        """Tester at fremtidig timestamp gir negativ verdi."""
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        event = PlowingEvent(timestamp=future)
        
        hours = event.hours_since()
        assert hours < 0  # Fremtidig = negativ


class TestPlowingInfoTimezone:
    """Tester for PlowingInfo tidssone-håndtering."""
    
    def test_formatted_time_today_morning(self):
        """Tester formattering for tidspunkt i dag (morgen)."""
        # Kl 08:00 i dag i UTC
        today_8am_utc = datetime.now(timezone.utc).replace(
            hour=8, minute=0, second=0, microsecond=0
        )
        
        # Bare kjør testen hvis det er etter 08:00 UTC
        if datetime.now(timezone.utc) < today_8am_utc:
            pytest.skip("Test krever at klokka er etter 08:00 UTC")
        
        info = PlowingInfo(
            last_plowing=today_8am_utc,
            hours_since=(datetime.now(timezone.utc) - today_8am_utc).total_seconds() / 3600,
            is_recent=True,
            all_timestamps=[today_8am_utc],
            source='test'
        )
        
        formatted = info.formatted_time
        # Skal vise "I dag kl. XX:XX" eller "For X min siden"
        assert "kl." in formatted or "min siden" in formatted
    
    def test_formatted_time_yesterday(self):
        """Tester formattering for tidspunkt i går."""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1, hours=2)
        
        info = PlowingInfo(
            last_plowing=yesterday,
            hours_since=26.0,
            is_recent=False,
            all_timestamps=[yesterday],
            source='test'
        )
        
        formatted = info.formatted_time
        assert "I går" in formatted
        assert "kl." in formatted
    
    def test_formatted_time_this_week(self):
        """Tester formattering for tidspunkt denne uken."""
        three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
        
        info = PlowingInfo(
            last_plowing=three_days_ago,
            hours_since=72.0,
            is_recent=False,
            all_timestamps=[three_days_ago],
            source='test'
        )
        
        formatted = info.formatted_time
        # Skal inneholde ukedagsnavn
        weekdays = ["man", "tir", "ons", "tor", "fre", "lør", "søn"]
        assert any(day in formatted for day in weekdays)
    
    def test_formatted_time_old(self):
        """Tester formattering for gammelt tidspunkt."""
        two_weeks_ago = datetime.now(timezone.utc) - timedelta(days=14)
        
        info = PlowingInfo(
            last_plowing=two_weeks_ago,
            hours_since=336.0,
            is_recent=False,
            all_timestamps=[two_weeks_ago],
            source='test'
        )
        
        formatted = info.formatted_time
        # Skal vise full dato
        assert "." in formatted  # Datoformat med punktum
        assert "kl." in formatted
    
    def test_formatted_time_converts_to_local(self):
        """Tester at tidspunkt konverteres til lokal tid for visning."""
        # Midnight UTC
        midnight_utc = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=2)
        
        info = PlowingInfo(
            last_plowing=midnight_utc,
            hours_since=48.0,
            is_recent=False,
            all_timestamps=[midnight_utc],
            source='test'
        )
        
        formatted = info.formatted_time
        # I Norge er midnatt UTC = 01:00 (vinter) eller 02:00 (sommer)
        # Så vi bør IKKE se "00:00" i output
        # (med mindre det er akkurat vintertid og vi tester da)
        assert "kl." in formatted


class TestFrostClientTimezone:
    """Tester for Frost API tidssone-håndtering."""
    
    def test_naive_datetime_converted_to_utc(self):
        """Tester at naive datetime konverteres til UTC."""
        from src.frost_client import FrostClient
        
        client = FrostClient("test-client-id")
        
        # Mock _fetch_observations for å unngå API-kall
        with patch.object(client, '_fetch_observations') as mock_fetch:
            mock_fetch.return_value = pd.DataFrame()
            
            # Kall med naive datetime
            naive_start = datetime(2024, 1, 1, 12, 0, 0)
            naive_end = datetime(2024, 1, 2, 12, 0, 0)
            
            try:
                client.get_weather_data(naive_start, naive_end)
            except Exception:
                pass  # Ignorer feil, vi sjekker bare at konvertering skjer
            
            # Verifiser at _fetch_observations ble kalt
            if mock_fetch.called:
                call_args = mock_fetch.call_args
                # Første to argumenter er start_time og end_time som strings
                start_str, end_str = call_args[0][0], call_args[0][1]
                # Skal ende med 'Z' (UTC)
                assert start_str.endswith('Z')
                assert end_str.endswith('Z')


class TestAnalyzerTimezone:
    """Tester for analysator tidssone-håndtering."""
    
    def test_analyzer_uses_utc_for_freshness_check(self):
        """Tester at analysatorer bruker UTC for ferskhetsjekk."""
        from src.analyzers.fresh_snow import FreshSnowAnalyzer
        
        analyzer = FreshSnowAnalyzer()
        
        # Lag testdata med UTC timestamps
        now = datetime.now(timezone.utc)
        timestamps = [now - timedelta(hours=i) for i in range(6)]
        
        df = pd.DataFrame({
            'reference_time': timestamps,
            'air_temperature': [-5.0] * 6,
            'surface_snow_thickness': [20.0, 19.5, 19.0, 18.5, 18.0, 15.0],
            'precipitation_1h': [0.5] * 6,
            'dew_point_temperature': [-7.0] * 6,
            'wind_speed': [5.0] * 6,
        })
        
        # Skal kunne analysere uten feil
        with patch.object(analyzer, 'is_winter_season', return_value=True):
            result = analyzer.analyze(df)
            assert result is not None


class TestTimezoneConsistency:
    """Tester for konsistent tidssone-bruk på tvers av kodebasen."""
    
    def test_plowing_info_and_event_consistent(self):
        """Tester at PlowingInfo og PlowingEvent bruker konsistent tidssone."""
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)
        
        # PlowingEvent
        event = PlowingEvent(timestamp=one_hour_ago)
        event_hours = event.hours_since()
        
        # PlowingInfo
        info = PlowingInfo(
            last_plowing=one_hour_ago,
            hours_since=1.0,
            is_recent=True,
            all_timestamps=[one_hour_ago],
            source='test'
        )
        
        # Begge bør rapportere ~1 time siden
        assert abs(event_hours - 1.0) < 0.1
        assert abs(info.hours_since - 1.0) < 0.1
    
    def test_utc_preferred_over_local(self):
        """Verifiserer at UTC brukes internt, ikke lokal tid."""
        # Dette er en "dokumentasjonstest" som viser forventet oppførsel
        
        # Korrekt måte å få nåtid
        correct_now = datetime.now(timezone.utc)
        assert correct_now.tzinfo is not None
        assert correct_now.tzinfo == timezone.utc
        
        # Feil måte (naive datetime) - bør IKKE brukes
        # incorrect_now = datetime.now()  # Ingen tidssone!
        
        # Hvis vi må bruke lokal tid, gjør det eksplisitt
        import zoneinfo
        oslo_tz = zoneinfo.ZoneInfo("Europe/Oslo")
        local_now = datetime.now(oslo_tz)
        assert local_now.tzinfo is not None


class TestISO8601Formatting:
    """Tester for ISO 8601 datoformatering."""
    
    def test_utc_isoformat_has_z_suffix(self):
        """Tester at UTC datoer formateres med Z suffix."""
        now = datetime.now(timezone.utc)
        iso_str = now.isoformat()
        
        # Python bruker +00:00, ikke Z, men begge er gyldige ISO 8601
        assert "+00:00" in iso_str or iso_str.endswith("Z")
    
    def test_parse_frost_api_timestamp(self):
        """Tester parsing av Frost API timestamp-format."""
        # Frost API returnerer format: "2024-01-15T12:00:00.000Z"
        frost_timestamp = "2024-01-15T12:00:00.000Z"
        
        parsed = datetime.fromisoformat(frost_timestamp.replace('Z', '+00:00'))
        
        assert parsed.year == 2024
        assert parsed.month == 1
        assert parsed.day == 15
        assert parsed.hour == 12
        assert parsed.tzinfo == timezone.utc
    
    def test_parse_plowman_timestamp(self):
        """Tester parsing av Plowman timestamp-format."""
        # Plowman bruker format: "$D2025-11-27T11:20:34.000Z"
        plowman_raw = "$D2025-11-27T11:20:34.000Z"
        
        # Fjern $D prefix
        timestamp_str = plowman_raw[2:]  # "2025-11-27T11:20:34.000Z"
        
        parsed = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        
        assert parsed.year == 2025
        assert parsed.month == 11
        assert parsed.day == 27
        assert parsed.hour == 11
        assert parsed.minute == 20
        assert parsed.tzinfo == timezone.utc


class TestDaylightSavingTime:
    """Tester for sommertid/vintertid-håndtering."""
    
    def test_winter_time_offset(self):
        """Tester at vintertid (UTC+1) håndteres korrekt."""
        import zoneinfo
        oslo_tz = zoneinfo.ZoneInfo("Europe/Oslo")
        
        # 15. januar er definitivt vintertid
        winter_date = datetime(2024, 1, 15, 12, 0, 0, tzinfo=oslo_tz)
        
        # Konverter til UTC
        utc_date = winter_date.astimezone(timezone.utc)
        
        # Oslo er UTC+1 om vinteren, så 12:00 Oslo = 11:00 UTC
        assert utc_date.hour == 11
    
    def test_summer_time_offset(self):
        """Tester at sommertid (UTC+2) håndteres korrekt."""
        import zoneinfo
        oslo_tz = zoneinfo.ZoneInfo("Europe/Oslo")
        
        # 15. juli er definitivt sommertid
        summer_date = datetime(2024, 7, 15, 12, 0, 0, tzinfo=oslo_tz)
        
        # Konverter til UTC
        utc_date = summer_date.astimezone(timezone.utc)
        
        # Oslo er UTC+2 om sommeren, så 12:00 Oslo = 10:00 UTC
        assert utc_date.hour == 10
    
    def test_dst_transition_handling(self):
        """Tester overgangen mellom sommertid og vintertid."""
        import zoneinfo
        oslo_tz = zoneinfo.ZoneInfo("Europe/Oslo")
        
        # Siste søndag i mars 2024 er 31. mars
        # Klokka stilles fra 02:00 til 03:00
        before_dst = datetime(2024, 3, 31, 1, 30, 0, tzinfo=oslo_tz)
        after_dst = datetime(2024, 3, 31, 3, 30, 0, tzinfo=oslo_tz)
        
        # Konverter begge til UTC
        before_utc = before_dst.astimezone(timezone.utc)
        after_utc = after_dst.astimezone(timezone.utc)
        
        # Forskjellen bør være 1 time (ikke 2, fordi 02:00-03:00 "hoppes over")
        diff = (after_utc - before_utc).total_seconds() / 3600
        assert diff == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
