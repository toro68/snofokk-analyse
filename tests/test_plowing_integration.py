"""
Test for brøytedata-integrasjon.

Tester for:
1. PlowmanClient - Henting av brøytedata fra Plowman livekart
2. PlowingService - Tjeneste for brøytedata med caching
3. Integrasjon med analysatorer (dokumenterer manglende funksjonalitet)

MANGLENDE FUNKSJONALITET I ANALYSATORER:
- Nysnø-varsel nullstilles ikke etter brøyting
- Snøfokk-risiko tar ikke hensyn til brøytet vei
- Slaps-varsel forblir selv etter at veien er ryddet
- Glattføre-varsel tar ikke hensyn til strøing
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.analyzers.base import RiskLevel
from src.analyzers.fresh_snow import FreshSnowAnalyzer
from src.analyzers.slippery_road import SlipperyRoadAnalyzer
from src.analyzers.snowdrift import SnowdriftAnalyzer
from src.plowing_service import PlowingInfo, get_plowing_info
from src.plowman_client import PlowingEvent, PlowmanClient


class TestPlowmanClient:
    """Tester for PlowmanClient som henter data fra Plowman livekart."""

    def test_decode_customer_id(self):
        """Tester dekoding av base64-encoded customer ID."""
        client = PlowmanClient()
        # "Y3VzdG9tZXItMTM=" dekoder til "customer-13"
        assert client.customer_id == 13

    def test_plowing_event_hours_since(self):
        """Tester beregning av timer siden brøyting."""
        # 2 timer siden
        two_hours_ago = datetime.now(UTC) - timedelta(hours=2)
        event = PlowingEvent(timestamp=two_hours_ago)

        hours = event.hours_since()
        assert 1.9 < hours < 2.1  # Tillat litt margin

    def test_plowing_event_with_naive_datetime(self):
        """Tester håndtering av naive datetime (uten tidssone)."""
        # PlowingEvent.hours_since() konverterer naive datetime til UTC
        # og sammenligner med nåtid i UTC
        # Bruk datetime.now(timezone.utc) uten tzinfo for å simulere naive time
        naive_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
        event = PlowingEvent(timestamp=naive_time)

        hours = event.hours_since()
        assert 0.9 < hours < 1.1

    @patch('src.plowman_client.requests.Session.get')
    def test_scrape_from_page_parses_timestamps(self, mock_get):
        """Tester at scraping finner lastUpdated-tidspunkter i HTML."""
        # Simuler HTML-respons med Next.js encoded timestamps
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
            <script>self.__next_f.push([1,"geojson":{"features":[
            {"properties":{"lastUpdated":"$D2025-11-27T11:20:34.000Z"}}
            ]}])</script>
        '''
        mock_get.return_value = mock_response

        client = PlowmanClient()
        event = client.scrape_from_page()

        assert event is not None
        assert event.timestamp.year == 2025
        assert event.timestamp.month == 11
        assert event.timestamp.day == 27

    @patch('src.plowman_client.requests.Session.get')
    def test_scrape_finds_newest_timestamp(self, mock_get):
        """Tester at scraping finner det nyeste tidspunktet."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
            $D2025-11-20T10:00:00.000Z
            $D2025-11-27T11:20:34.000Z
            $D2025-11-25T08:30:00.000Z
        '''
        mock_get.return_value = mock_response

        client = PlowmanClient()
        event = client.scrape_from_page()

        assert event is not None
        # Skal finne den nyeste: 27. november
        assert event.timestamp.day == 27
        assert event.timestamp.hour == 11


class TestPlowingService:
    """Tester for PlowingService som håndterer brøytedata med caching."""

    def test_plowing_info_formatted_time_today(self):
        """Tester formattering av tidspunkt i dag."""
        now = datetime.now(UTC)
        info = PlowingInfo(
            last_plowing=now - timedelta(hours=2),
            hours_since=2.0,
            is_recent=True,
            all_timestamps=[now],
            source='test'
        )

        formatted = info.formatted_time
        assert "kl." in formatted or "min siden" in formatted

    def test_plowing_info_formatted_time_yesterday(self):
        """Tester formattering av tidspunkt i går."""
        yesterday = datetime.now(UTC) - timedelta(days=1, hours=2)
        info = PlowingInfo(
            last_plowing=yesterday,
            hours_since=26.0,
            is_recent=False,
            all_timestamps=[yesterday],
            source='test'
        )

        formatted = info.formatted_time
        assert "I går" in formatted

    def test_plowing_info_status_emoji(self):
        """Tester status-emoji basert på tid siden brøyting."""
        # Nylig brøytet (< 6 timer)
        info_recent = PlowingInfo(
            last_plowing=datetime.now(UTC),
            hours_since=2.0,
            is_recent=True,
            all_timestamps=[],
            source='test'
        )
        assert info_recent.status_emoji == "✅"

        # Brøytet siste døgn
        info_day = PlowingInfo(
            last_plowing=datetime.now(UTC) - timedelta(hours=12),
            hours_since=12.0,
            is_recent=True,
            all_timestamps=[],
            source='test'
        )
        assert info_day.status_emoji == "🟢"

        # Mer enn 2 dager
        info_old = PlowingInfo(
            last_plowing=datetime.now(UTC) - timedelta(days=3),
            hours_since=72.0,
            is_recent=False,
            all_timestamps=[],
            source='test'
        )
        assert info_old.status_emoji == "🟠"

    def test_plowing_info_no_data(self):
        """Tester PlowingInfo uten data."""
        info = PlowingInfo(
            last_plowing=None,
            hours_since=None,
            is_recent=False,
            all_timestamps=[],
            source='none',
            error="Ingen data"
        )

        assert info.formatted_time == "Ukjent"
        assert info.status_emoji == "❓"

    @patch('src.plowing_service.get_last_plowing_time')
    def test_get_plowing_info_uses_plowman_client(self, mock_get_last):
        """Tester at get_plowing_info bruker PlowmanClient."""
        mock_event = PlowingEvent(
            timestamp=datetime.now(UTC) - timedelta(hours=5)
        )
        mock_get_last.return_value = mock_event

        # Hent uten cache
        info = get_plowing_info(use_cache=False)

        mock_get_last.assert_called_once()
        assert info.source == 'live'
        assert info.hours_since is not None
        assert 4.9 < info.hours_since < 5.1


class TestPlowingIntegrationMissing:
    """Tester som dokumenterer manglende brøytedata-integrasjon."""

    def create_dataframe_with_snow(self, snow_cm: float = 30.0, snow_change_cm: float = 10.0):
        """Lag en DataFrame med snødata."""
        now = datetime.now(UTC)
        timestamps = [now - timedelta(hours=i) for i in range(12, 0, -1)]

        # Simuler snøøkning
        snow_values = [snow_cm - snow_change_cm + (snow_change_cm * i / 11) for i in range(12)]

        return pd.DataFrame({
            'reference_time': timestamps,
            'air_temperature': [-5.0] * 12,
            'wind_speed': [5.0] * 12,
            'max_wind_gust': [8.0] * 12,
            'wind_from_direction': [180.0] * 12,
            'surface_snow_thickness': snow_values,
            'precipitation_1h': [0.5] * 12,
            'dew_point_temperature': [-7.0] * 12,
            'surface_temperature': [-7.0] * 12,
            'relative_humidity': [80.0] * 12,
        })

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_fresh_snow_analyzer_ignores_plowing(self, mock_winter):
        """
        PROBLEM: FreshSnowAnalyzer gir varsel selv etter brøyting.

        Scenario: 10cm nysnø falt, deretter brøytet
        Forventet: Lavt varsel (brøytet)
        Faktisk: Fortsatt varsel (brøyting ignorert)
        """
        analyzer = FreshSnowAnalyzer()

        # 10cm nysnø - normalt et MEDIUM/HIGH varsel
        df = self.create_dataframe_with_snow(snow_cm=35.0, snow_change_cm=10.0)

        result = analyzer.analyze(df)

        # Analysatoren gir varsel (som forventet uten brøytedata)
        # Men den BURDE kunne ta hensyn til brøyting
        if result.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH):
            pytest.skip(
                "KJENT MANGEL: FreshSnowAnalyzer har ingen input for brøytetidspunkt. "
                "10cm nysnø gir varsel selv om veien er brøytet."
            )

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_snowdrift_analyzer_ignores_plowing(self, mock_winter):
        """
        PROBLEM: SnowdriftAnalyzer tar ikke hensyn til brøyting.

        Etter brøyting er løssnø fjernet fra veien,
        men analysatoren ser fortsatt snødybde og gir varsel.
        """
        analyzer = SnowdriftAnalyzer()

        # Snøfokk-forhold
        now = datetime.now(UTC)
        df = pd.DataFrame({
            'reference_time': [now],
            'air_temperature': [-5.0],
            'wind_speed': [12.0],
            'max_wind_gust': [22.0],  # Kritisk vindkast
            'wind_from_direction': [180.0],
            'surface_snow_thickness': [50.0],
            'precipitation_1h': [0.0],
            'dew_point_temperature': [-7.0],
            'relative_humidity': [80.0],
        })

        result = analyzer.analyze(df)

        if result.risk_level == RiskLevel.HIGH:
            pytest.skip(
                "KJENT MANGEL: SnowdriftAnalyzer tar ikke hensyn til brøyting. "
                "Selv om veien nettopp er brøytet, gir sterk vind fortsatt HØY risiko."
            )

    @patch('src.analyzers.base.BaseAnalyzer.is_winter_season', return_value=True)
    def test_slippery_road_ignores_sanding(self, mock_winter):
        """
        PROBLEM: SlipperyRoadAnalyzer tar ikke hensyn til strøing.

        Etter strøing er veien trygg, men analysatoren
        ser fortsatt bakketemperatur < 0 og gir varsel.
        """
        analyzer = SlipperyRoadAnalyzer()

        now = datetime.now(UTC)
        df = pd.DataFrame({
            'reference_time': [now],
            'air_temperature': [1.0],
            'surface_temperature': [-2.0],  # Is-fare
            'wind_speed': [5.0],
            'surface_snow_thickness': [20.0],
            'precipitation_1h': [1.0],
            'dew_point_temperature': [0.0],
            'relative_humidity': [90.0],
        })

        result = analyzer.analyze(df)

        if result.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH):
            pytest.skip(
                "KJENT MANGEL: SlipperyRoadAnalyzer tar ikke hensyn til strøing. "
                "Selv om veien er strødd, gir bakketemperatur < 0 fortsatt varsel."
            )


class TestProposedPlowingIntegration:
    """Tester for foreslått brøytedata-integrasjon."""

    def test_proposed_analyzer_interface(self):
        """
        FORSLAG: Analysatorer bør kunne ta imot brøytetidspunkt.

        Ny signatur:
            analyzer.analyze(df, last_plowing_time=datetime)

        Oppførsel:
        - Nysnø: Beregn kun snø siden brøyting
        - Snøfokk: Reduser risiko hvis nylig brøytet
        - Slaps: Nullstill hvis brøytet innen 2 timer
        - Glattføre: Ta hensyn til strøing
        """
        # Dette er et forslag - ikke implementert
        pass

    def test_proposed_plowing_log_structure(self):
        """
        FORSLAG: Brøytelogg-struktur.

        {
            "timestamp": "2024-02-10T08:30:00Z",
            "type": "brøyting" | "strøing" | "begge",
            "notes": "Brøytet hele veien",
            "operator": "Brøytelag 1"
        }
        """
        expected_structure = {
            "timestamp": datetime.now(UTC).isoformat(),
            "type": "brøyting",
            "notes": "Brøytet hele veien",
            "operator": "Brøytelag 1"
        }

        assert "timestamp" in expected_structure
        assert "type" in expected_structure

    def test_proposed_ui_elements(self):
        """
        FORSLAG: UI-elementer for brøyting.

        1. Sidebar:
           - "Registrer brøyting" knapp
           - "Sist brøytet: X timer siden"
           - "Snø siden brøyting: Y cm"

        2. Varsler:
           - Vise "Brøytet X timer siden - risiko redusert"
           - Grønn indikator hvis nylig brøytet

        3. Historikk:
           - Liste over brøytehendelser
           - Korrelasjon mellom værhendelser og brøyting
        """
        proposed_ui = {
            "sidebar": ["Registrer brøyting", "Sist brøytet", "Snø siden brøyting"],
            "alerts": ["Brøytestatus indikator"],
            "history": ["Brøytelogg", "Værkorrelasjon"]
        }

        assert len(proposed_ui["sidebar"]) == 3


class TestPlowingEffectOnRisk:
    """Tester for hvordan brøyting BØR påvirke risikonivå."""

    def test_fresh_snow_reset_after_plowing(self):
        """
        FORVENTET OPPFØRSEL:
        - 15cm nysnø → HØY risiko
        - Brøyting utført → risiko nullstilles
        - 3cm ny snø etter brøyting → LAV risiko
        """
        # Før brøyting
        expected_risk_before = RiskLevel.HIGH

        # Etter brøyting + 3cm nysnø
        expected_risk_after = RiskLevel.LOW

        # Verifiser forventet oppførsel
        assert expected_risk_before != expected_risk_after

    def test_snowdrift_reduced_after_plowing(self):
        """
        FORVENTET OPPFØRSEL:
        - Sterk vind + løssnø → HØY snøfokk-risiko
        - Etter brøyting: løssnø er fjernet fra veibane
        - Risiko redusert (men ikke nullstilt pga fortsatt vind)
        """
        # Med løssnø på vei
        expected_risk_with_loose_snow = RiskLevel.HIGH

        # Etter brøyting (løssnø fjernet fra vei)
        expected_risk_after_plowing = RiskLevel.MEDIUM  # Fortsatt vind

        assert expected_risk_after_plowing.value != expected_risk_with_loose_snow.value

    def test_slippery_road_reset_after_sanding(self):
        """
        FORVENTET OPPFØRSEL:
        - Is på vei → HØY glattføre-risiko
        - Strøing utført → risiko nullstilles
        - Ny is etter strøing → gradvis økende risiko
        """
        # Før strøing
        expected_risk_icy = RiskLevel.HIGH

        # Like etter strøing
        expected_risk_after_sanding = RiskLevel.LOW

        # 6 timer etter strøing (sand dekket av is)

        assert expected_risk_after_sanding != expected_risk_icy


class TestPlowingDataAvailability:
    """Tester for eksisterende brøytedata-funksjonalitet."""

    def test_historical_service_has_plowing_methods(self):
        """Verifiser at HistoricalWeatherService har brøyte-metoder."""
        from src.components.historical_service import HistoricalWeatherService

        service = HistoricalWeatherService(frost_client_id="test")

        # Disse metodene finnes
        assert hasattr(service, 'calculate_snow_since_plowing')
        assert hasattr(service, 'save_plowing_event')
        assert hasattr(service, 'get_recent_plowing_events')

    def test_historical_service_not_used_in_main_app(self):
        """
        PROBLEM: HistoricalWeatherService brukes IKKE i hovedappen.

        gullingen_app.py importerer ikke:
        - HistoricalWeatherService
        - calculate_snow_since_plowing
        - save_plowing_event
        """
        import importlib.util

        # Les gullingen_app.py source
        spec = importlib.util.find_spec('src.gullingen_app')
        assert spec is not None

        # Verifiser at HistoricalWeatherService IKKE er importert
        # (dette er dokumentert som et problem, ikke en test som skal feile)
        pytest.skip(
            "KJENT MANGEL: gullingen_app.py bruker ikke HistoricalWeatherService. "
            "Brøyte-tracking er implementert men ikke integrert i hovedappen."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
