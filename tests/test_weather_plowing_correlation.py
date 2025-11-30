#!/usr/bin/env python3
"""
Test av samsvar mellom faktiske brøytingsrapporter og værdata.
Validerer hvor godt våre prediktive algoritmer matcher real-world operasjoner.
"""
import sys
from pathlib import Path

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from analyze_weather_plowing_correlation import (
    SnowPlowingRecord,
    WeatherCorrelation,
    WeatherPlowingCorrelationAnalyzer,
)


class TestWeatherPlowingCorrelation:
    """Test samsvar mellom værdata og brøytingsaktivitet"""

    @pytest.fixture
    def analyzer(self):
        """Setup analyzer med testdata"""
        analyzer = WeatherPlowingCorrelationAnalyzer()
        return analyzer

    def test_load_plowing_data_successfully(self, analyzer):
        """Test at brøytingsdata lastes inn korrekt"""
        records = analyzer.load_plowing_data("Rapport 2022-2025.csv")

        assert len(records) > 0
        assert all(isinstance(r, SnowPlowingRecord) for r in records)

        # Verify data integrity
        for record in records[:5]:  # Check first 5 records
            assert record.date is not None
            assert record.start_time is not None
            assert record.end_time is not None
            assert record.duration_hours >= 0
            assert record.distance_km >= 0
            assert record.route == "Hyttegrenda"
            assert record.unit in ["8810", "8894", "9389", "8810.0", "8894.0", "9389.0"]

    def test_weather_correlation_analysis(self, analyzer):
        """Test at værkorrelasjon fungerer"""
        # Load data
        plowing_records = analyzer.load_plowing_data("Rapport 2022-2025.csv")
        assert len(plowing_records) > 100  # Should have substantial data

        # Analyze correlations
        correlations = analyzer.analyze_correlations()

        # Should have correlations for most records
        assert len(correlations) >= len(plowing_records) * 0.8  # At least 80% coverage

        # Verify correlation structure
        for correlation in correlations[:5]:
            assert isinstance(correlation, WeatherCorrelation)
            assert correlation.plowing_record is not None
            assert correlation.weather_conditions is not None
            assert 0 <= correlation.correlation_score <= 2.0  # Reasonable score range
            assert correlation.actual_needed is True  # All records are actual plowing

    def test_prediction_accuracy_threshold(self, analyzer):
        """Test at prediksjonsaccuracy er over akseptabel terskel"""
        analyzer.load_plowing_data("Rapport 2022-2025.csv")
        correlations = analyzer.analyze_correlations()
        report = analyzer.generate_correlation_report(correlations)

        # Minimum 85% accuracy for our weather-based predictions
        accuracy = report['summary']['prediction_accuracy']
        assert accuracy >= 85.0, f"Prediksjonsaccuracy {accuracy:.1f}% er under akseptabel terskel (85%)"

        # Should have reasonable correlation scores
        avg_score = report['summary']['avg_correlation_score']
        assert avg_score > 0.5, f"Gjennomsnittlig korrelasjonsscore {avg_score:.3f} er for lav"

    def test_seasonal_patterns_validation(self, analyzer):
        """Test at sesongmønstre stemmer med forventninger"""
        analyzer.load_plowing_data("Rapport 2022-2025.csv")
        correlations = analyzer.analyze_correlations()
        report = analyzer.generate_correlation_report(correlations)

        patterns = report['operational_patterns']
        monthly_dist = patterns['monthly_distribution']

        # Winter months should dominate (Dec=12, Jan=1, Feb=2, Mar=3)
        winter_months = [12, 1, 2, 3]
        winter_operations = sum(monthly_dist.get(month, 0) for month in winter_months)
        total_operations = sum(monthly_dist.values())

        winter_percentage = (winter_operations / total_operations) * 100
        assert winter_percentage >= 80, f"Kun {winter_percentage:.1f}% av brøytinger er i vintermåneder"

        # January should be busiest month (Norwegian winter peak)
        busiest_month = patterns['busiest_month']
        assert busiest_month in [1, 2, 12], f"Travleste måned {busiest_month} er ikke typisk vinter"

    def test_operational_timing_patterns(self, analyzer):
        """Test at operasjonelle tidsmønstre er realistiske"""
        analyzer.load_plowing_data("Rapport 2022-2025.csv")
        correlations = analyzer.analyze_correlations()
        report = analyzer.generate_correlation_report(correlations)

        patterns = report['operational_patterns']
        hourly_dist = patterns['hourly_distribution']

        # Most plowing should happen during daytime/work hours (6-18)
        daytime_operations = sum(hourly_dist.get(hour, 0) for hour in range(6, 19))
        total_operations = sum(hourly_dist.values())

        daytime_percentage = (daytime_operations / total_operations) * 100
        assert daytime_percentage >= 60, f"Kun {daytime_percentage:.1f}% av brøytinger skjer på dagtid"

        # Peak hours should be reasonable (typically morning/late afternoon)
        busiest_hour = patterns['busiest_hour']
        assert 6 <= busiest_hour <= 18, f"Travleste time {busiest_hour} er utenfor normal arbeidstid"

    def test_weather_conditions_realism(self, analyzer):
        """Test at værforhold under brøyting er realistiske"""
        analyzer.load_plowing_data("Rapport 2022-2025.csv")
        correlations = analyzer.analyze_correlations()
        report = analyzer.generate_correlation_report(correlations)

        weather_stats = report['weather_statistics']

        # Average conditions during plowing should indicate winter weather
        avg_temp = weather_stats['avg_temperature']
        assert avg_temp <= 5.0, f"Gjennomsnittstemp {avg_temp:.1f}°C er for høy for brøyting"

        avg_snow_depth = weather_stats['avg_snow_depth']
        assert avg_snow_depth >= 5.0, f"Gjennomsnittlig snødybde {avg_snow_depth:.1f}cm er for lav"

        # Should have some precipitation activity
        avg_precipitation = weather_stats['avg_precipitation']
        assert avg_precipitation > 0, "Ingen nedbør registrert under brøytingsperioder"

    def test_unit_distribution_balance(self, analyzer):
        """Test at arbeidsfordelingen mellom enheter er rimelig"""
        analyzer.load_plowing_data("Rapport 2022-2025.csv")
        correlations = analyzer.analyze_correlations()
        report = analyzer.generate_correlation_report(correlations)

        patterns = report['operational_patterns']
        unit_dist = patterns['unit_distribution']

        # Should have operations for multiple units
        assert len(unit_dist) >= 2, "Kun en enhet brukes for brøyting"

        # No single unit should dominate completely (>90%)
        total_ops = sum(unit_dist.values())
        for unit, ops in unit_dist.items():
            unit_percentage = (ops / total_ops) * 100
            assert unit_percentage <= 90, f"Enhet {unit} har {unit_percentage:.1f}% av alle operasjoner"

    def test_missed_predictions_analysis(self, analyzer):
        """Test analyse av tapte prediksjoner"""
        analyzer.load_plowing_data("Rapport 2022-2025.csv")
        correlations = analyzer.analyze_correlations()
        report = analyzer.generate_correlation_report(correlations)

        missed_predictions = report['missed_predictions']
        total_operations = report['summary']['total_plowing_operations']

        # Should not miss more than 20% of predictions
        missed_count = len(missed_predictions)
        missed_percentage = (missed_count / total_operations) * 100
        assert missed_percentage <= 20, f"Tapte {missed_percentage:.1f}% av prediksjoner (for høyt)"

        # Missed predictions should have reasonable scores
        if missed_predictions:
            for missed in missed_predictions[:3]:  # Check first 3
                assert 0 <= missed['score'] <= 1.0, "Unrealistisk score for tapt prediksjon"
                assert 'weather' in missed, "Mangler værdata for tapt prediksjon"

    def test_correlation_consistency_over_time(self, analyzer):
        """Test at korrelasjon er konsistent over tid"""
        analyzer.load_plowing_data("Rapport 2022-2025.csv")
        correlations = analyzer.analyze_correlations()

        # Group by year
        yearly_accuracy = {}
        for correlation in correlations:
            year = correlation.plowing_record.date.year
            if year not in yearly_accuracy:
                yearly_accuracy[year] = {'correct': 0, 'total': 0}

            yearly_accuracy[year]['total'] += 1
            if correlation.match:
                yearly_accuracy[year]['correct'] += 1

        # Each year with data should have reasonable accuracy
        for year, stats in yearly_accuracy.items():
            if stats['total'] >= 5:  # Only check years with sufficient data
                accuracy = (stats['correct'] / stats['total']) * 100
                assert accuracy >= 75, f"År {year} har kun {accuracy:.1f}% accuracy"

    def test_generate_comprehensive_report(self, analyzer):
        """Test at komplett rapport genereres korrekt"""
        plowing_records = analyzer.load_plowing_data("Rapport 2022-2025.csv")
        correlations = analyzer.analyze_correlations()
        report = analyzer.generate_correlation_report(correlations)

        # Verify report structure
        required_sections = ['summary', 'weather_statistics', 'operational_patterns', 'missed_predictions']
        for section in required_sections:
            assert section in report, f"Mangler {section} i rapport"

        # Verify summary completeness
        summary = report['summary']
        required_summary_fields = ['total_plowing_operations', 'correct_predictions', 'prediction_accuracy']
        for field in required_summary_fields:
            assert field in summary, f"Mangler {field} i sammendrag"

        # Numbers should be consistent
        assert summary['total_plowing_operations'] == len(plowing_records)
        assert summary['correct_predictions'] <= summary['total_plowing_operations']

        print(f"\n✓ Rapport generert: {summary['total_plowing_operations']} operasjoner analysert")
        print(f"✓ Prediksjonsaccuracy: {summary['prediction_accuracy']:.1f}%")


class TestRealWorldValidation:
    """Validering mot reelle operasjonelle forhold"""

    def test_winter_season_concentration(self):
        """Test at brøytingsaktivitet er konsentrert i vintersesongen"""
        analyzer = WeatherPlowingCorrelationAnalyzer()
        plowing_records = analyzer.load_plowing_data("Rapport 2022-2025.csv")

        # Count operations by month
        monthly_counts = {}
        for record in plowing_records:
            month = record.date.month
            monthly_counts[month] = monthly_counts.get(month, 0) + 1

        # Winter season should have most activity
        winter_core = [12, 1, 2]  # Dec, Jan, Feb
        winter_extended = [11, 12, 1, 2, 3]  # Nov-Mar

        winter_core_ops = sum(monthly_counts.get(month, 0) for month in winter_core)
        winter_extended_ops = sum(monthly_counts.get(month, 0) for month in winter_extended)
        total_ops = sum(monthly_counts.values())

        # At least 60% should be in core winter months
        core_percentage = (winter_core_ops / total_ops) * 100
        assert core_percentage >= 60, f"Kun {core_percentage:.1f}% av brøytinger i kjernevinter"

        # At least 90% should be in extended winter season
        extended_percentage = (winter_extended_ops / total_ops) * 100
        assert extended_percentage >= 90, f"Kun {extended_percentage:.1f}% av brøytinger i vintersesongen"

    def test_operational_efficiency_metrics(self):
        """Test operasjonelle effektivitetsmåltall"""
        analyzer = WeatherPlowingCorrelationAnalyzer()
        plowing_records = analyzer.load_plowing_data("Rapport 2022-2025.csv")

        # Calculate efficiency metrics
        total_hours = sum(record.duration_hours for record in plowing_records)
        total_distance = sum(record.distance_km for record in plowing_records)
        total_operations = len(plowing_records)

        # Average efficiency should be reasonable
        avg_speed = total_distance / total_hours if total_hours > 0 else 0
        avg_duration = total_hours / total_operations if total_operations > 0 else 0
        avg_distance = total_distance / total_operations if total_operations > 0 else 0

        # Plowing speed should be realistic (5-30 km/h)
        assert 5 <= avg_speed <= 30, f"Gjennomsnittshastighet {avg_speed:.1f} km/h er urealistisk"

        # Average operation should be reasonable duration (0.5-8 hours)
        assert 0.5 <= avg_duration <= 8, f"Gjennomsnittlig varighet {avg_duration:.1f}t er urealistisk"

        # Average distance per operation (5-50 km reasonable for route)
        assert 5 <= avg_distance <= 50, f"Gjennomsnittlig distanse {avg_distance:.1f}km er urealistisk"

        print("\n✓ Effektivitetsanalyse:")
        print(f"  Gjennomsnittshastighet: {avg_speed:.1f} km/h")
        print(f"  Gjennomsnittlig varighet: {avg_duration:.1f} timer")
        print(f"  Gjennomsnittlig distanse: {avg_distance:.1f} km")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
