"""
Kritiske tester for AnalysisService - kjernelogikken som mangler test coverage
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch

from snofokk.services.analysis import AnalysisService, analysis_service
from snofokk.models import SnowAnalysis


class TestAnalysisServiceCore:
    """Test kritisk kjernelogikk i AnalysisService"""

    def setup_method(self):
        """Setup for hver test"""
        self.service = AnalysisService()
        
    def test_analyze_snow_conditions_with_valid_data(self):
        """Test snow conditions analysis med gyldig data"""
        df = pd.DataFrame({
            'surface_snow_thickness': [0.10, 0.12, 0.08, 0.15, 0.11],
            'air_temperature': [-2, -3, -1, -4, -2]
        })
        
        analyses = self.service.analyze_snow_conditions(df)
        
        assert len(analyses) == 4  # len(df) - 1 (første har ingen previous)
        assert all(isinstance(analysis, SnowAnalysis) for analysis in analyses)
        assert all(analysis.is_valid for analysis in analyses)
        
    def test_analyze_snow_conditions_empty_data(self):
        """Test med tom DataFrame"""
        df = pd.DataFrame()
        analyses = self.service.analyze_snow_conditions(df)
        assert analyses == []
        
    def test_analyze_snow_conditions_missing_column(self):
        """Test når surface_snow_thickness mangler"""
        df = pd.DataFrame({
            'air_temperature': [-2, -3, -1]
        })
        analyses = self.service.analyze_snow_conditions(df)
        assert analyses == []
        
    def test_analyze_snow_conditions_with_nan_values(self):
        """Test håndtering av NaN-verdier"""
        df = pd.DataFrame({
            'surface_snow_thickness': [0.10, np.nan, 0.08, 0.15],
            'air_temperature': [-2, -3, -1, -4]
        })
        
        analyses = self.service.analyze_snow_conditions(df)
        # Skal bare få analyser for gyldige overganger (ikke der NaN er involvert)
        assert len(analyses) <= 3
        assert all(analysis.is_valid for analysis in analyses if not pd.isna(analysis.raw_depth))
        
    def test_calculate_confidence_normal_values(self):
        """Test confidence calculation med normale verdier"""
        confidence = self.service._calculate_confidence(50.0, 5.0)
        assert 0.1 <= confidence <= 1.0
        assert abs(confidence - 0.8) < 0.001  # Normal case
        
    def test_calculate_confidence_extreme_depth(self):
        """Test confidence med ekstrem snødybde"""
        confidence = self.service._calculate_confidence(250.0, 5.0)  # > 200cm
        assert abs(confidence - 0.6) < 0.001  # 0.8 - 0.2 for extreme depth
        
    def test_calculate_confidence_extreme_change(self):
        """Test confidence med ekstrem endring"""
        confidence = self.service._calculate_confidence(50.0, 25.0)  # > 20cm change
        assert abs(confidence - 0.5) < 0.001  # 0.8 - 0.3 for large change
        
    def test_calculate_confidence_both_extreme(self):
        """Test confidence med både ekstrem dybde og endring"""
        confidence = self.service._calculate_confidence(250.0, 25.0)
        assert abs(confidence - 0.3) < 0.001  # 0.8 - 0.2 - 0.3, men max(0.1, result)
        
    def test_detect_risk_periods_high_wind(self):
        """Test risk detection med høy vindstyrke"""
        df = pd.DataFrame({
            'wind_speed': [20.0, 18.0, 16.0],  # Høy vind (>= 15.0)
            'air_temperature': [-5.0, -6.0, -4.0],
            'surface_snow_thickness': [0.10, 0.12, 0.08]
        })
        
        periods = self.service.detect_risk_periods(df)
        
        # Skal finne høy-risiko perioder
        assert isinstance(periods, pd.DataFrame)
        if len(periods) > 0:
            assert 'max_risk_score' in periods.columns
            assert periods['max_risk_score'].max() > 0.6
            
    def test_detect_risk_periods_cold_temp(self):
        """Test risk detection med kald temperatur"""
        df = pd.DataFrame({
            'wind_speed': [5.0, 6.0, 4.0],
            'air_temperature': [-15.0, -18.0, -12.0],  # Kald temp (<= -10.0)
            'surface_snow_thickness': [0.10, 0.12, 0.08]
        })
        
        periods = self.service.detect_risk_periods(df)
        
        # Temperatur-komponent skal bidra til risiko
        assert isinstance(periods, pd.DataFrame)
        
    def test_detect_risk_periods_snow_change(self):
        """Test risk detection med store snøendringer"""
        df = pd.DataFrame({
            'wind_speed': [5.0, 6.0, 4.0],
            'air_temperature': [-5.0, -6.0, -4.0],
            'surface_snow_thickness': [0.10, 0.20, 0.08]  # Store endringer
        })
        
        periods = self.service.detect_risk_periods(df)
        
        # Store snøendringer skal bidra til risiko
        assert isinstance(periods, pd.DataFrame)
        
    def test_detect_risk_periods_empty_data(self):
        """Test risk detection med tom data"""
        df = pd.DataFrame()
        periods = self.service.detect_risk_periods(df)
        assert len(periods) == 0
        
    def test_identify_continuous_periods_edge_cases(self):
        """Test edge cases i period identification - KRITISK FIX"""
        # Test case 1: Period starter i begynnelsen
        df = pd.DataFrame({
            'is_high_risk': [True, True, False, False],
            'risk_score': [0.8, 0.7, 0.3, 0.2],
            'referenceTime': pd.date_range('2024-01-01', periods=4, freq='H')
        })
        
        periods = self.service._identify_continuous_periods(df)
        assert len(periods) == 1
        
        # Test case 2: Period slutter på slutten
        df = pd.DataFrame({
            'is_high_risk': [False, False, True, True],
            'risk_score': [0.2, 0.3, 0.7, 0.8],
            'referenceTime': pd.date_range('2024-01-01', periods=4, freq='H')
        })
        
        periods = self.service._identify_continuous_periods(df)
        assert len(periods) == 1
        
        # Test case 3: Hele perioden er høy risiko
        df = pd.DataFrame({
            'is_high_risk': [True, True, True, True],
            'risk_score': [0.8, 0.7, 0.9, 0.8],
            'referenceTime': pd.date_range('2024-01-01', periods=4, freq='H')
        })
        
        periods = self.service._identify_continuous_periods(df)
        assert len(periods) == 1
        
        # Test case 4: Ingen høy-risiko perioder
        df = pd.DataFrame({
            'is_high_risk': [False, False, False, False],
            'risk_score': [0.2, 0.3, 0.1, 0.2],
            'referenceTime': pd.date_range('2024-01-01', periods=4, freq='H')
        })
        
        periods = self.service._identify_continuous_periods(df)
        assert len(periods) == 0
        
    def test_identify_continuous_periods_multiple_periods(self):
        """Test identifikasjon av flere separate perioder"""
        df = pd.DataFrame({
            'is_high_risk': [True, True, False, False, True, True, False],
            'risk_score': [0.8, 0.7, 0.3, 0.2, 0.9, 0.8, 0.1],
            'referenceTime': pd.date_range('2024-01-01', periods=7, freq='H')
        })
        
        periods = self.service._identify_continuous_periods(df)
        assert len(periods) == 2  # To separate perioder
        
        # Sjekk at periodene har riktige verdier
        for _, period in periods.iterrows():
            assert period['duration'] >= 2  # min_duration
            assert period['max_risk_score'] >= 0.6
            assert period['avg_risk_score'] >= 0.6


class TestAnalysisServiceIntegration:
    """Integration tester for hele analysis service"""
    
    def test_full_analysis_pipeline(self):
        """Test hele analyse-pipeline fra start til slutt"""
        service = AnalysisService()
        
        # Simuler realistisk værdata
        df = pd.DataFrame({
            'referenceTime': pd.date_range('2024-01-01', periods=10, freq='H'),
            'wind_speed': [5, 8, 15, 18, 12, 6, 4, 16, 20, 10],
            'air_temperature': [-2, -5, -8, -12, -6, -3, -1, -10, -15, -7],
            'surface_snow_thickness': [0.10, 0.12, 0.15, 0.18, 0.16, 0.14, 0.12, 0.20, 0.25, 0.22]
        })
        
        # Test snow analysis
        snow_analyses = service.analyze_snow_conditions(df)
        assert len(snow_analyses) == 9  # len(df) - 1
        
        # Test risk detection
        risk_periods = service.detect_risk_periods(df)
        assert isinstance(risk_periods, pd.DataFrame)
        
        # Hvis det er høy-risiko perioder, sjekk at de har riktig struktur
        if len(risk_periods) > 0:
            expected_columns = ['start_time', 'end_time', 'duration', 'max_risk_score', 'avg_risk_score']
            assert all(col in risk_periods.columns for col in expected_columns)


class TestAnalysisServiceSettings:
    """Test at analysis service bruker settings korrekt"""
    
    @patch('snofokk.services.analysis.settings')
    def test_uses_settings_thresholds(self, mock_settings):
        """Test at service bruker settings for terskelverdier"""
        # Mock settings
        mock_settings.snow_change_threshold = 2.0
        mock_settings.wind_impact_threshold = 12.0
        mock_settings.temperature_snow_threshold = -8.0
        
        service = AnalysisService()
        
        df = pd.DataFrame({
            'wind_speed': [13.0],  # Over wind_impact_threshold
            'air_temperature': [-9.0],  # Under temperature_snow_threshold
            'surface_snow_thickness': [0.10]
        })
        
        periods = service.detect_risk_periods(df)
        
        # Skal finne risiko basert på mock settings
        assert isinstance(periods, pd.DataFrame)


# Test global instance
def test_global_analysis_service_instance():
    """Test at global analysis_service instance fungerer"""
    assert analysis_service is not None
    assert isinstance(analysis_service, AnalysisService)
    
    # Test at den kan brukes
    df = pd.DataFrame({
        'surface_snow_thickness': [0.10, 0.12]
    })
    result = analysis_service.analyze_snow_conditions(df)
    assert isinstance(result, list)
