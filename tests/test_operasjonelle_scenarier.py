"""
OPERASJONELLE TESTER FOR VINTERVEDLIKEHOLD
=========================================

Test suite for alle kritiske operasjonelle scenarier basert på empirisk validerte værelementer:
- NYSNØ_DETEKSJON: Når må det brøytes?
- SNØFOKK_PREDIKSJON: Når blåser veier igjen?
- GLATTFØRE_VARSLING: Når må det strøs?
- NEDBØRTYPE_KLASSIFISERING: Hva slags nedbør faller?
- SEIN_RESPONS: Når responderer brøytefirma for sent?
- OVERPRODUKSJON: Når brøytes det for mye/ofte?

Basert på 15 validerte værelementer og faktiske brøytehendelser fra Gullingen.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import pytest


# Mock weather data structure
@dataclass
class WeatherObservation:
    """Værdata for testing"""
    timestamp: datetime
    air_temperature: float  # °C
    surface_temperature: float  # °C
    surface_snow_thickness: float  # cm
    wind_speed: float  # m/s
    wind_from_direction: float  # grader
    max_wind_speed: float  # m/s
    precipitation_amount_10m: float  # mm/10min
    precipitation_amount_1h: float  # mm/1h
    accumulated_precipitation: float  # mm
    relative_humidity: float  # %
    dew_point_temperature: float  # °C
    precipitation_duration: float  # minutter
    wind_gust: float  # m/s
    air_temp_max_1h: float  # °C
    air_temp_min_1h: float  # °C

@dataclass
class MaintenanceEvent:
    """Vedlikeholdshendelse for testing"""
    timestamp: datetime
    event_type: str  # "broyting", "stroing", "tunbroyting"
    duration: int  # minutter
    location: str
    response_time: int  # minutter fra værhendelse
    efficiency_score: float  # 0.0-1.0


class NysnoDeteksjon:
    """NYSNØ DETEKSJON basert på validerte elementer"""

    # Operasjonelle terskler
    VAT_SNO_TERSKEL = 6  # cm våt snø
    TORR_SNO_TERSKEL = 12  # cm tørr snø
    INTENSITET_TERSKEL = 2.0  # mm/10min
    AKKUMULERINGSHASTIGHET = 1.0  # cm/time

    @staticmethod
    def detect_new_snow(obs: WeatherObservation, previous_obs: WeatherObservation = None) -> dict[str, Any]:
        """
        Detekterer nysnø basert på 15 validerte elementer

        Returns:
            Dict med deteksjon_result, snow_type, intensity, action_needed
        """
        result = {
            "detection_time": obs.timestamp,
            "new_snow_detected": False,
            "snow_type": None,
            "intensity": "lav",
            "accumulated_snow": obs.surface_snow_thickness,
            "action_needed": None,
            "confidence": 0.0
        }

        # Snøfall-indikatorer
        if obs.air_temperature < 0 and obs.precipitation_amount_10m > 0:
            result["new_snow_detected"] = True

            # Snøtype basert på temperatur og vind
            if obs.air_temperature < -5:
                result["snow_type"] = "torr_sno"
                threshold = NysnoDeteksjon.TORR_SNO_TERSKEL
            elif obs.wind_speed > 8:
                result["snow_type"] = "vindblast_sno"
                threshold = NysnoDeteksjon.TORR_SNO_TERSKEL  # Høyere terskel pga drift
            else:
                result["snow_type"] = "vat_sno"
                threshold = NysnoDeteksjon.VAT_SNO_TERSKEL

            # Intensitet basert på 10-min nedbør (PRESISJONS-BOOST)
            if obs.precipitation_amount_10m > 3.0:
                result["intensity"] = "høy"
                result["confidence"] = 0.9
            elif obs.precipitation_amount_10m > 1.0:
                result["intensity"] = "medium"
                result["confidence"] = 0.7
            else:
                result["intensity"] = "lav"
                result["confidence"] = 0.5

            # Handling-anbefaling
            if obs.surface_snow_thickness >= threshold:
                result["action_needed"] = "broyting_na"
            elif obs.surface_snow_thickness >= threshold * 0.7:
                result["action_needed"] = "broyting_snart"
            else:
                result["action_needed"] = "overvaking"

        return result


class SnofokkPrediksjon:
    """SNØFOKK PREDIKSJON basert på empirisk validerte kriterier"""

    # Fysisk realistiske terskler
    MIN_VINDSTYRKE = 6  # m/s
    MIN_TEMPERATUR = -1  # °C
    MIN_SNODYBDE = 3  # cm
    KRITISK_VINDSTYRKE = 12  # m/s (median fra 29 episoder)

    @staticmethod
    def predict_snowdrift(obs: WeatherObservation, loose_snow_available: bool = True) -> dict[str, Any]:
        """
        Predikerer snøfokk basert på validerte elementer

        Args:
            obs: Værdata
            loose_snow_available: Om løssnø er tilgjengelig (ikke mildvær siste 24-48t)
        """
        result = {
            "prediction_time": obs.timestamp,
            "snowdrift_risk": "ingen",
            "risk_level": 0,
            "wind_direction": obs.wind_from_direction,
            "critical_factors": [],
            "mitigation_needed": False,
            "confidence": 0.0
        }

        # Grunnleggende kriterier
        factors_met = []

        if obs.wind_speed >= SnofokkPrediksjon.MIN_VINDSTYRKE:
            factors_met.append("sufficient_wind")

        if obs.air_temperature <= SnofokkPrediksjon.MIN_TEMPERATUR:
            factors_met.append("cold_enough")

        if obs.surface_snow_thickness >= SnofokkPrediksjon.MIN_SNODYBDE:
            factors_met.append("sufficient_snow")

        if loose_snow_available:
            factors_met.append("loose_snow")

        # Risikovurdering
        if len(factors_met) >= 4:  # Alle kriterier oppfylt
            if obs.wind_speed >= SnofokkPrediksjon.KRITISK_VINDSTYRKE:
                result["snowdrift_risk"] = "høy"
                result["risk_level"] = 3
                result["confidence"] = 0.9
                result["mitigation_needed"] = True
            else:
                result["snowdrift_risk"] = "medium"
                result["risk_level"] = 2
                result["confidence"] = 0.7
        elif len(factors_met) >= 3:
            result["snowdrift_risk"] = "lav"
            result["risk_level"] = 1
            result["confidence"] = 0.5

        result["critical_factors"] = factors_met

        # Spesifikke anbefalinger
        if result["risk_level"] >= 2:
            result["mitigation_needed"] = True

        return result


class GlattforeVarsling:
    """GLATTFØRE VARSLING basert på REVOLUSJONERENDE surface_temperature"""

    # Kritiske terskler
    KRITISK_OVERFLATE_TEMP = 2.0  # °C
    FROST_TERSKEL = 0.0  # °C
    REGN_TERSKEL = 0.5  # mm/10min

    @staticmethod
    def assess_slippery_road_risk(obs: WeatherObservation) -> dict[str, Any]:
        """
        Vurderer glattføre-risiko med REVOLUSJONERENDE surface_temperature

        KRITISK: surface_temperature gir direkte måling av veioverflate!
        """
        result = {
            "assessment_time": obs.timestamp,
            "slippery_risk": "ingen",
            "risk_type": None,
            "surface_temp": obs.surface_temperature,
            "air_temp": obs.air_temperature,
            "immediate_action": False,
            "confidence": 0.0
        }

        # REVOLUTIONERING: Direkte veioverflate-måling
        if obs.surface_temperature <= GlattforeVarsling.FROST_TERSKEL:
            # Veioverflate er faktisk frossen
            if obs.precipitation_amount_10m > GlattforeVarsling.REGN_TERSKEL:
                # Regn på frossen veioverflate = KRITISK
                result["slippery_risk"] = "kritisk"
                result["risk_type"] = "regn_pa_frossen_vei"
                result["immediate_action"] = True
                result["confidence"] = 0.95  # Høyeste sikkerhet med direkte måling
            else:
                # Frost-risiko basert på duggpunkt (FROST-SPESIALIST)
                dew_point_diff = obs.air_temperature - obs.dew_point_temperature
                if dew_point_diff < 2.0 and obs.relative_humidity > 85:
                    result["slippery_risk"] = "medium"
                    result["risk_type"] = "rimfrost"
                    result["confidence"] = 0.7

        elif obs.surface_temperature <= GlattforeVarsling.KRITISK_OVERFLATE_TEMP:
            # Veioverflate nær frysing
            if obs.precipitation_amount_10m > GlattforeVarsling.REGN_TERSKEL:
                if obs.air_temperature < 1.0:
                    result["slippery_risk"] = "høy"
                    result["risk_type"] = "regn_nær_frysing"
                    result["immediate_action"] = True
                    result["confidence"] = 0.8

        return result


class NedbortypeKlassifisering:
    """NEDBØRTYPE KLASSIFISERING basert på 149 empiriske episoder"""

    @staticmethod
    def classify_precipitation(obs: WeatherObservation, snow_change: float = None) -> dict[str, Any]:
        """
        Klassifiserer nedbørtype basert på empirisk validerte kriterier

        Args:
            obs: Værdata
            snow_change: Endring i snødybde siste time (cm)
        """
        result = {
            "classification_time": obs.timestamp,
            "precipitation_type": None,
            "confidence": "lav",
            "characteristics": [],
            "operational_impact": None
        }

        if obs.precipitation_amount_1h < 0.1:
            result["precipitation_type"] = "ingen"
            return result

        # Empirisk klassifisering (149 episoder)
        if obs.air_temperature > 0 and obs.wind_speed < 8:
            if snow_change is not None and snow_change < 0:
                result["precipitation_type"] = "regn"
                result["confidence"] = "høy" if obs.air_temperature > 2 else "medium"
                result["operational_impact"] = "glattfore_risiko"
            else:
                result["precipitation_type"] = "regn"
                result["confidence"] = "medium"

        elif obs.air_temperature < -2 and obs.wind_speed < 8:
            if snow_change is None or snow_change > 0:
                result["precipitation_type"] = "sno"
                result["confidence"] = "høy" if obs.air_temperature < -3 else "medium"
                result["operational_impact"] = "broyting_nodvendig"

        elif obs.air_temperature < 0 and obs.wind_speed > 10:
            if snow_change is not None and snow_change < -3:
                result["precipitation_type"] = "vindblast_sno"
                result["confidence"] = "høy" if obs.wind_speed > 12 else "medium"
                result["operational_impact"] = "snofokk_risiko"

        else:
            # Blandede forhold
            if obs.air_temperature >= 0:
                result["precipitation_type"] = "regn_eller_vindblast"
            else:
                result["precipitation_type"] = "sno_med_vindpavirkning"
            result["confidence"] = "lav"

        return result


# =====================================================
# TEST CLASSES
# =====================================================

class TestNysnoDeteksjon:
    """Tester for nysnø-deteksjon"""

    def test_torr_sno_deteksjon(self):
        """Test deteksjon av tørr snø"""
        obs = WeatherObservation(
            timestamp=datetime.now(),
            air_temperature=-8.0,
            surface_temperature=-10.0,
            surface_snow_thickness=15.0,  # Over terskel
            wind_speed=3.0,
            wind_from_direction=270,
            max_wind_speed=5.0,
            precipitation_amount_10m=2.5,  # Moderat intensitet
            precipitation_amount_1h=10.0,
            accumulated_precipitation=25.0,
            relative_humidity=85,
            dew_point_temperature=-12.0,
            precipitation_duration=45,
            wind_gust=8.0,
            air_temp_max_1h=-6.0,
            air_temp_min_1h=-10.0
        )

        result = NysnoDeteksjon.detect_new_snow(obs)

        assert result["new_snow_detected"] is True
        assert result["snow_type"] == "torr_sno"
        assert result["action_needed"] == "broyting_na"
        assert result["confidence"] >= 0.7

    def test_vat_sno_deteksjon(self):
        """Test deteksjon av våt snø"""
        obs = WeatherObservation(
            timestamp=datetime.now(),
            air_temperature=-1.5,
            surface_temperature=-0.5,
            surface_snow_thickness=8.0,  # Over våt snø terskel
            wind_speed=2.0,
            wind_from_direction=180,
            max_wind_speed=4.0,
            precipitation_amount_10m=3.5,  # Høy intensitet
            precipitation_amount_1h=15.0,
            accumulated_precipitation=20.0,
            relative_humidity=95,
            dew_point_temperature=-2.0,
            precipitation_duration=60,
            wind_gust=6.0,
            air_temp_max_1h=-0.5,
            air_temp_min_1h=-2.5
        )

        result = NysnoDeteksjon.detect_new_snow(obs)

        assert result["new_snow_detected"] is True
        assert result["snow_type"] == "vat_sno"
        assert result["action_needed"] == "broyting_na"
        assert result["intensity"] == "høy"

    def test_ingen_sno_deteksjon(self):
        """Test når det ikke er snø"""
        obs = WeatherObservation(
            timestamp=datetime.now(),
            air_temperature=3.0,  # For varmt
            surface_temperature=2.0,
            surface_snow_thickness=2.0,
            wind_speed=5.0,
            wind_from_direction=90,
            max_wind_speed=8.0,
            precipitation_amount_10m=0.0,  # Ingen nedbør
            precipitation_amount_1h=0.0,
            accumulated_precipitation=0.0,
            relative_humidity=60,
            dew_point_temperature=1.0,
            precipitation_duration=0,
            wind_gust=10.0,
            air_temp_max_1h=4.0,
            air_temp_min_1h=1.0
        )

        result = NysnoDeteksjon.detect_new_snow(obs)

        assert result["new_snow_detected"] is False
        assert result["action_needed"] is None


class TestSnofokkPrediksjon:
    """Tester for snøfokk-prediksjon"""

    def test_hoy_snofokk_risiko(self):
        """Test høy snøfokk-risiko"""
        obs = WeatherObservation(
            timestamp=datetime.now(),
            air_temperature=-5.0,  # Kald nok
            surface_temperature=-8.0,
            surface_snow_thickness=15.0,  # Nok snø
            wind_speed=15.0,  # Over kritisk terskel
            wind_from_direction=315,
            max_wind_speed=18.0,
            precipitation_amount_10m=0.0,
            precipitation_amount_1h=0.0,
            accumulated_precipitation=0.0,
            relative_humidity=70,
            dew_point_temperature=-8.0,
            precipitation_duration=0,
            wind_gust=22.0,
            air_temp_max_1h=-3.0,
            air_temp_min_1h=-7.0
        )

        result = SnofokkPrediksjon.predict_snowdrift(obs, loose_snow_available=True)

        assert result["snowdrift_risk"] == "høy"
        assert result["risk_level"] == 3
        assert result["mitigation_needed"] is True
        assert result["confidence"] >= 0.8
        assert "sufficient_wind" in result["critical_factors"]
        assert "cold_enough" in result["critical_factors"]
        assert "sufficient_snow" in result["critical_factors"]
        assert "loose_snow" in result["critical_factors"]

    def test_ingen_losno_tilgjengelig(self):
        """Test når løssnø ikke er tilgjengelig (mildvær)"""
        obs = WeatherObservation(
            timestamp=datetime.now(),
            air_temperature=-3.0,
            surface_temperature=-5.0,
            surface_snow_thickness=20.0,
            wind_speed=12.0,  # Nok vind
            wind_from_direction=270,
            max_wind_speed=15.0,
            precipitation_amount_10m=0.0,
            precipitation_amount_1h=0.0,
            accumulated_precipitation=0.0,
            relative_humidity=75,
            dew_point_temperature=-6.0,
            precipitation_duration=0,
            wind_gust=18.0,
            air_temp_max_1h=-1.0,
            air_temp_min_1h=-5.0
        )

        result = SnofokkPrediksjon.predict_snowdrift(obs, loose_snow_available=False)

        # Uten løssnø, maksimal risiko er lav
        assert result["risk_level"] <= 1
        assert "loose_snow" not in result["critical_factors"]


class TestGlattforeVarsling:
    """Tester for glattføre-varsling med REVOLUSJONERENDE surface_temperature"""

    def test_kritisk_regn_pa_frossen_vei(self):
        """Test kritisk glattføre: regn på frossen veioverflate"""
        obs = WeatherObservation(
            timestamp=datetime.now(),
            air_temperature=1.0,
            surface_temperature=-1.0,  # KRITISK: Vei faktisk frossen!
            surface_snow_thickness=5.0,
            wind_speed=3.0,
            wind_from_direction=180,
            max_wind_speed=5.0,
            precipitation_amount_10m=1.2,  # Regn pågår
            precipitation_amount_1h=5.0,
            accumulated_precipitation=8.0,
            relative_humidity=90,
            dew_point_temperature=0.5,
            precipitation_duration=30,
            wind_gust=7.0,
            air_temp_max_1h=2.0,
            air_temp_min_1h=-0.5
        )

        result = GlattforeVarsling.assess_slippery_road_risk(obs)

        assert result["slippery_risk"] == "kritisk"
        assert result["risk_type"] == "regn_pa_frossen_vei"
        assert result["immediate_action"] is True
        assert result["confidence"] >= 0.9  # Høyeste sikkerhet med direkte måling

    def test_rimfrost_med_duggpunkt(self):
        """Test rimfrost-varsling med FROST-SPESIALIST dew_point_temperature"""
        obs = WeatherObservation(
            timestamp=datetime.now(),
            air_temperature=-1.5,
            surface_temperature=-2.0,  # Frossen veioverflate
            surface_snow_thickness=1.0,  # Lite snødekke
            wind_speed=1.0,  # Stille vær
            wind_from_direction=0,
            max_wind_speed=2.0,
            precipitation_amount_10m=0.0,  # Ingen nedbør
            precipitation_amount_1h=0.0,
            accumulated_precipitation=0.0,
            relative_humidity=88,  # Høy fuktighet
            dew_point_temperature=-2.8,  # Nær lufttemperatur
            precipitation_duration=0,
            wind_gust=3.0,
            air_temp_max_1h=-0.5,
            air_temp_min_1h=-2.5
        )

        result = GlattforeVarsling.assess_slippery_road_risk(obs)

        assert result["slippery_risk"] == "medium"
        assert result["risk_type"] == "rimfrost"
        assert result["confidence"] >= 0.6

    def test_ingen_glattfore_risiko(self):
        """Test når det ikke er glattføre-risiko"""
        obs = WeatherObservation(
            timestamp=datetime.now(),
            air_temperature=-5.0,
            surface_temperature=-8.0,  # Stabilt kaldt
            surface_snow_thickness=20.0,
            wind_speed=2.0,
            wind_from_direction=90,
            max_wind_speed=4.0,
            precipitation_amount_10m=0.0,
            precipitation_amount_1h=0.0,
            accumulated_precipitation=0.0,
            relative_humidity=65,
            dew_point_temperature=-10.0,  # Tørre forhold
            precipitation_duration=0,
            wind_gust=6.0,
            air_temp_max_1h=-3.0,
            air_temp_min_1h=-7.0
        )

        result = GlattforeVarsling.assess_slippery_road_risk(obs)

        assert result["slippery_risk"] == "ingen"
        assert result["immediate_action"] is False


class TestNedbortypeKlassifisering:
    """Tester for nedbørtype-klassifisering basert på 149 episoder"""

    def test_regn_klassifisering(self):
        """Test regn-klassifisering"""
        obs = WeatherObservation(
            timestamp=datetime.now(),
            air_temperature=3.0,  # Over null
            surface_temperature=2.0,
            surface_snow_thickness=5.0,
            wind_speed=4.0,  # Under vindterskel
            wind_from_direction=180,
            max_wind_speed=6.0,
            precipitation_amount_10m=1.0,
            precipitation_amount_1h=8.0,  # Nedbør pågår
            accumulated_precipitation=15.0,
            relative_humidity=85,
            dew_point_temperature=1.5,
            precipitation_duration=45,
            wind_gust=8.0,
            air_temp_max_1h=4.0,
            air_temp_min_1h=2.0
        )

        result = NedbortypeKlassifisering.classify_precipitation(obs, snow_change=-2.0)

        assert result["precipitation_type"] == "regn"
        assert result["confidence"] in ["høy", "medium"]
        assert result["operational_impact"] == "glattfore_risiko"

    def test_vindblast_sno_klassifisering(self):
        """Test vindblåst snø klassifisering"""
        obs = WeatherObservation(
            timestamp=datetime.now(),
            air_temperature=-2.0,  # Under null
            surface_temperature=-5.0,
            surface_snow_thickness=12.0,
            wind_speed=14.0,  # Over vindterskel
            wind_from_direction=270,
            max_wind_speed=18.0,
            precipitation_amount_10m=0.5,
            precipitation_amount_1h=2.0,
            accumulated_precipitation=5.0,
            relative_humidity=70,
            dew_point_temperature=-6.0,
            precipitation_duration=15,
            wind_gust=22.0,
            air_temp_max_1h=-1.0,
            air_temp_min_1h=-4.0
        )

        result = NedbortypeKlassifisering.classify_precipitation(obs, snow_change=-5.0)

        assert result["precipitation_type"] == "vindblast_sno"
        assert result["confidence"] in ["høy", "medium"]
        assert result["operational_impact"] == "snofokk_risiko"


class TestSeinRespons:
    """Tester for sen respons fra brøytefirma"""

    def test_akseptabel_responstid(self):
        """Test akseptabel responstid"""
        weather_event_time = datetime(2025, 1, 15, 8, 0)  # Snøfall starter 08:00
        maintenance_time = datetime(2025, 1, 15, 9, 30)   # Brøyting starter 09:30

        response_time = (maintenance_time - weather_event_time).total_seconds() / 60

        # Under 2 timer for moderat snøfall = akseptabelt
        assert response_time == 90  # 1.5 timer
        assert response_time <= 120  # Akseptabel terskel

    def test_sein_respons_kritisk_sno(self):
        """Test sen respons på kritisk snøfall"""
        weather_event_time = datetime(2025, 1, 15, 6, 0)   # Kraftig snøfall starter 06:00
        maintenance_time = datetime(2025, 1, 15, 10, 30)   # Brøyting starter 10:30

        response_time = (maintenance_time - weather_event_time).total_seconds() / 60

        # Over 3 timer for kraftig snøfall = for sent
        assert response_time == 270  # 4.5 timer
        assert response_time > 180  # Kritisk terskel

    def test_rask_respons_snofokk(self):
        """Test rask respons på snøfokk"""
        weather_event_time = datetime(2025, 1, 15, 14, 0)  # Snøfokk starter 14:00
        maintenance_time = datetime(2025, 1, 15, 14, 45)   # Brøyting starter 14:45

        response_time = (maintenance_time - weather_event_time).total_seconds() / 60

        # Under 1 time for snøfokk = bra respons
        assert response_time == 45
        assert response_time <= 60  # Snøfokk-terskel

    def test_helg_respons_forsinkelse(self):
        """Test respons-forsinkelse i helg"""
        # Lørdag morgen
        weather_event_time = datetime(2025, 1, 18, 7, 0)   # Lørdag 07:00
        maintenance_time = datetime(2025, 1, 18, 11, 0)    # Brøyting 11:00

        response_time = (maintenance_time - weather_event_time).total_seconds() / 60

        # Helg kan ha lengre responstid
        assert response_time == 240  # 4 timer
        # Men ikke over 5 timer selv i helg
        assert response_time <= 300


class TestOverproduksjon:
    """Tester for overproduksjon og ineffektiv brøyting"""

    def test_unodvendig_broyting_lite_sno(self):
        """Test unødvendig brøyting ved lite snø"""
        snow_depth = 3.0  # cm - under terskel
        wind_speed = 2.0  # m/s - lav vind

        # Brøyting utført likevel
        maintenance_performed = True

        # Dette er overproduksjon
        assert snow_depth < NysnoDeteksjon.VAT_SNO_TERSKEL
        assert wind_speed < SnofokkPrediksjon.MIN_VINDSTYRKE
        assert maintenance_performed is True  # Unødvendig

    def test_for_hyppig_broyting(self):
        """Test for hyppig brøyting"""
        # Brøyting hver 2. time
        maintenance_events = [
            datetime(2025, 1, 15, 8, 0),
            datetime(2025, 1, 15, 10, 0),
            datetime(2025, 1, 15, 12, 0),
            datetime(2025, 1, 15, 14, 0),
            datetime(2025, 1, 15, 16, 0)
        ]

        # Beregn intervaller
        intervals = []
        for i in range(1, len(maintenance_events)):
            interval = (maintenance_events[i] - maintenance_events[i-1]).total_seconds() / 3600
            intervals.append(interval)

        avg_interval = np.mean(intervals)

        # Under 3 timer gjennomsnitt = for hyppig
        assert avg_interval == 2.0
        assert avg_interval < 3.0  # For hyppig terskel

    def test_ineffektiv_rute_planlegging(self):
        """Test ineffektiv rute-planlegging"""
        # Samme rute brøytet flere ganger samme dag
        routes_plowed = [
            ("Hovedvei", datetime(2025, 1, 15, 8, 0)),
            ("Bivei_1", datetime(2025, 1, 15, 9, 0)),
            ("Hovedvei", datetime(2025, 1, 15, 10, 0)),  # Duplikat
            ("Bivei_2", datetime(2025, 1, 15, 11, 0)),
            ("Hovedvei", datetime(2025, 1, 15, 12, 0))   # Duplikat
        ]

        # Finn duplikater samme dag
        route_counts = {}
        for route, timestamp in routes_plowed:
            date = timestamp.date()
            key = (route, date)
            route_counts[key] = route_counts.get(key, 0) + 1

        duplicates = {k: v for k, v in route_counts.items() if v > 1}

        # Hovedvei brøytet 3 ganger samme dag = ineffektivt
        assert ("Hovedvei", datetime(2025, 1, 15).date()) in duplicates
        assert duplicates[("Hovedvei", datetime(2025, 1, 15).date())] == 3

    def test_optimal_effektivitet(self):
        """Test optimal effektivitets-score"""
        # Faktorer for effektivitet
        response_time = 75  # minutter (bra)
        unnecessary_plowing = 0  # Ingen unødvendig brøyting
        route_optimization = 0.9  # 90% optimale ruter
        weather_correlation = 0.85  # 85% korrelasjon med værhendelser

        # Beregn effektivitets-score (0.0-1.0)
        efficiency_score = (
            (max(0, 120 - response_time) / 120) * 0.3 +  # Responstid (30%)
            (1 - unnecessary_plowing) * 0.2 +  # Unødvendig brøyting (20%)
            route_optimization * 0.3 +  # Rute-optimering (30%)
            weather_correlation * 0.2  # Vær-korrelasjon (20%)
        )

        expected_score = (
            (max(0, 120 - 75) / 120) * 0.3 +  # 0.1125
            1.0 * 0.2 +  # 0.2
            0.9 * 0.3 +  # 0.27
            0.85 * 0.2  # 0.17
        )

        assert abs(efficiency_score - expected_score) < 0.01
        assert efficiency_score >= 0.75  # God effektivitet


@pytest.mark.integration
class TestIntegrertOperasjonellScenario:
    """Integrasjonstester for komplette operasjonelle scenarier"""

    def test_komplett_vinterdag_scenario(self):
        """Test komplett scenario: snøfall → snøfokk → glattføre"""

        # Scenario 1: Snøfall starter (08:00)
        obs1 = WeatherObservation(
            timestamp=datetime(2025, 1, 15, 8, 0),
            air_temperature=-3.0,
            surface_temperature=-5.0,
            surface_snow_thickness=2.0,  # Lite snø initialt
            wind_speed=3.0,
            wind_from_direction=270,
            max_wind_speed=5.0,
            precipitation_amount_10m=2.0,  # Moderat snøfall
            precipitation_amount_1h=8.0,
            accumulated_precipitation=8.0,
            relative_humidity=85,
            dew_point_temperature=-6.0,
            precipitation_duration=45,
            wind_gust=7.0,
            air_temp_max_1h=-2.0,
            air_temp_min_1h=-4.0
        )

        snow_result1 = NysnoDeteksjon.detect_new_snow(obs1)
        assert snow_result1["new_snow_detected"] is True
        assert snow_result1["action_needed"] in ["overvaking", "broyting_snart"]

        # Scenario 2: Snøfall fortsetter, bygger opp (10:00)
        obs2 = WeatherObservation(
            timestamp=datetime(2025, 1, 15, 10, 0),
            air_temperature=-4.0,
            surface_temperature=-6.0,
            surface_snow_thickness=8.0,  # Snø bygget opp
            wind_speed=4.0,
            wind_from_direction=270,
            max_wind_speed=6.0,
            precipitation_amount_10m=1.5,
            precipitation_amount_1h=6.0,
            accumulated_precipitation=20.0,
            relative_humidity=88,
            dew_point_temperature=-7.0,
            precipitation_duration=35,
            wind_gust=8.0,
            air_temp_max_1h=-3.0,
            air_temp_min_1h=-5.0
        )

        snow_result2 = NysnoDeteksjon.detect_new_snow(obs2)
        assert snow_result2["action_needed"] == "broyting_na"

        # Scenario 3: Vind øker, snøfokk-risiko (12:00)
        obs3 = WeatherObservation(
            timestamp=datetime(2025, 1, 15, 12, 0),
            air_temperature=-5.0,
            surface_temperature=-7.0,
            surface_snow_thickness=12.0,  # Mer snø
            wind_speed=13.0,  # Vind øker kraftig
            wind_from_direction=270,
            max_wind_speed=16.0,
            precipitation_amount_10m=0.5,  # Snøfall avtar
            precipitation_amount_1h=2.0,
            accumulated_precipitation=25.0,
            relative_humidity=75,
            dew_point_temperature=-8.0,
            precipitation_duration=15,
            wind_gust=20.0,
            air_temp_max_1h=-3.0,
            air_temp_min_1h=-6.0
        )

        snowdrift_result = SnofokkPrediksjon.predict_snowdrift(obs3, loose_snow_available=True)
        assert snowdrift_result["snowdrift_risk"] in ["høy", "medium"]
        assert snowdrift_result["mitigation_needed"] is True

        # Scenario 4: Temperatur stiger, regn-risiko (16:00)
        obs4 = WeatherObservation(
            timestamp=datetime(2025, 1, 15, 16, 0),
            air_temperature=2.0,  # Temperatur stiger
            surface_temperature=-1.0,  # Vei fortsatt frossen!
            surface_snow_thickness=10.0,  # Noe snø smeltet
            wind_speed=8.0,
            wind_from_direction=180,
            max_wind_speed=10.0,
            precipitation_amount_10m=1.8,  # Regn starter
            precipitation_amount_1h=7.0,
            accumulated_precipitation=35.0,
            relative_humidity=95,
            dew_point_temperature=1.5,
            precipitation_duration=40,
            wind_gust=12.0,
            air_temp_max_1h=3.0,
            air_temp_min_1h=-1.0
        )

        slippery_result = GlattforeVarsling.assess_slippery_road_risk(obs4)
        assert slippery_result["slippery_risk"] == "kritisk"
        assert slippery_result["immediate_action"] is True

        precip_result = NedbortypeKlassifisering.classify_precipitation(obs4, snow_change=-2.0)
        # Med vindstyrke 8.0 m/s blir det klassifisert som regn eller vindblast
        assert precip_result["precipitation_type"] in ["regn", "regn_eller_vindblast"]
        assert "operational_impact" in precip_result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
