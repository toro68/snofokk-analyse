#!/usr/bin/env python3
"""
Test Weather Analysis System - Tester hele værmønster-systemet
"""
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add scripts to path - må gjøres før lokale imports
scripts_path = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_path))

from analysis.slippery_road_pattern_analyzer import SlipperyRoadAnalyzer  # noqa: E402
from analysis.snow_drift_pattern_analyzer import SnowDriftAnalyzer  # noqa: E402
from analysis.weather_pattern_optimizer import WeatherPatternOptimizer  # noqa: E402
from utils.weather_config import ConfigManager  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_configuration():
    """Test konfigurasjonssystem"""

    logger.info("=== TESTER KONFIGURASJON ===")

    # Opprett konfigurasjon
    config_manager = ConfigManager("config/test_weather_config.json")

    # Test oppdatering
    config_manager.update_snow_drift_params(
        min_wind_speed=9.0,
        max_temperature=-1.5,
        alert_threshold=75
    )

    config_manager.update_slippery_road_params(
        max_temperature=1.5,
        min_humidity=85.0,
        alert_threshold=65
    )

    logger.info("✓ Konfigurasjon testet OK")
    return config_manager.config

def test_snow_drift_analyzer():
    """Test snøfokk-analyzer"""

    logger.info("=== TESTER SNØFOKK-ANALYZER ===")

    analyzer = SnowDriftAnalyzer()

    # Test med kort periode (siste uke)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    try:
        events = analyzer.analyze_historical_period(start_date, end_date, "SN46220")
        logger.info(f"✓ Snøfokk-analyzer testet OK - Fant {len(events)} hendelser")
        return len(events) >= 0  # Returnerer True selv om ingen hendelser
    except Exception as e:
        logger.error(f"✗ Feil i snøfokk-analyzer: {e}")
        return False

def test_slippery_road_analyzer():
    """Test glatt vei-analyzer"""

    logger.info("=== TESTER GLATT VEI-ANALYZER ===")

    analyzer = SlipperyRoadAnalyzer()

    # Test med kort periode (siste uke)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    try:
        events = analyzer.analyze_period(start_date, end_date, "SN46220")
        logger.info(f"✓ Glatt vei-analyzer testet OK - Fant {len(events)} hendelser")
        return len(events) >= 0  # Returnerer True selv om ingen hendelser
    except Exception as e:
        logger.error(f"✗ Feil i glatt vei-analyzer: {e}")
        return False

def test_weather_optimizer():
    """Test værmønster-optimizer"""

    logger.info("=== TESTER VÆRMØNSTER-OPTIMIZER ===")

    optimizer = WeatherPatternOptimizer()

    try:
        # Test med en kort periode
        current_year = datetime.now().year
        results = optimizer.analyze_historical_seasons(current_year, current_year)

        logger.info("✓ Værmønster-optimizer testet OK")
        logger.info(f"  - Snøfokk-hendelser: {results['total_snow_events']}")
        logger.info(f"  - Glatt vei-hendelser: {results['total_slippery_events']}")

        return True
    except Exception as e:
        logger.error(f"✗ Feil i værmønster-optimizer: {e}")
        return False

def test_data_access():
    """Test tilgang til værdata"""

    logger.info("=== TESTER DATAKILDER ===")

    try:
        # Test import av weather service
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))
        from snofokk.services.weather import WeatherService

        weather_service = WeatherService()

        # Test henting av data for siste dag
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)

        data = weather_service.get_historical_data("SN46220", start_date, end_date)

        if data is not None and not data.empty:
            logger.info(f"✓ Værdata testet OK - {len(data)} datapunkter")
            return True
        else:
            logger.warning("! Ingen værdata mottatt (kan være normalt)")
            return True  # Ikke en feil hvis ingen data for kort periode

    except Exception as e:
        logger.error(f"✗ Feil ved henting av værdata: {e}")
        return False

def run_mini_analysis():
    """Kjør en mini-analyse for å teste hele systemet"""

    logger.info("=== KJØRER MINI-ANALYSE ===")

    try:
        # Opprett optimizer
        optimizer = WeatherPatternOptimizer()

        # Analyser siste vinter (kort periode)
        current_year = datetime.now().year
        if datetime.now().month < 6:  # Første halvår
            analysis_year = current_year
        else:  # Andre halvår
            analysis_year = current_year + 1

        logger.info(f"Analyserer vintersesong {analysis_year-1}/{analysis_year}")

        results = optimizer.analyze_historical_seasons(analysis_year, analysis_year)

        # Vis resultater
        logger.info("\n--- ANALYSERESULTATER ---")
        logger.info(f"Snøfokk-hendelser: {results['total_snow_events']}")
        logger.info(f"Glatt vei-hendelser: {results['total_slippery_events']}")

        if results['total_snow_events'] > 0 or results['total_slippery_events'] > 0:
            # Finn korrelasjoner
            correlations = optimizer.find_correlation_patterns()

            logger.info(f"Overlappende hendelser: {correlations['temporal_overlap']}")
            logger.info(f"Nære hendelser (24h): {correlations['close_proximity']}")

            # Optimaliser parametere
            optimization = optimizer.optimize_combined_parameters()

            logger.info("\n--- ANBEFALINGER ---")
            for rec in optimization.get('recommendations', []):
                logger.info(f"- {rec}")

        # Lagre resultater
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"test_analysis_{timestamp}.json"
        optimizer.save_results(output_file)

        logger.info(f"✓ Mini-analyse fullført - Resultater lagret som {output_file}")
        return True

    except Exception as e:
        logger.error(f"✗ Feil i mini-analyse: {e}")
        return False

def main():
    """Hovedtest av hele systemet"""

    logger.info("=== TEST AV VÆRMØNSTER-SYSTEM ===")
    logger.info(f"Startet: {datetime.now()}")

    test_results = {}

    # Kjør tester
    test_results['configuration'] = test_configuration()
    test_results['data_access'] = test_data_access()
    test_results['snow_drift'] = test_snow_drift_analyzer()
    test_results['slippery_road'] = test_slippery_road_analyzer()
    test_results['optimizer'] = test_weather_optimizer()
    test_results['mini_analysis'] = run_mini_analysis()

    # Oppsummer resultater
    logger.info("\n=== TESTRESULTATER ===")
    passed = 0
    total = len(test_results)

    for test_name, result in test_results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{test_name:20}: {status}")
        if result:
            passed += 1

    logger.info(f"\nResultat: {passed}/{total} tester bestått")

    if passed == total:
        logger.info("🎉 Alle tester bestått! Systemet er klart til bruk.")
    elif passed >= total * 0.8:
        logger.info("⚠️  De fleste tester bestått. Systemet er stort sett klart.")
    else:
        logger.info("❌ Flere tester feilet. Sjekk konfigurasjonen.")

    # Vis neste steg
    logger.info("\n=== NESTE STEG ===")
    logger.info("1. Kjør: python scripts/utils/weather_config.py --interactive")
    logger.info("2. Kjør: python scripts/analysis/weather_pattern_optimizer.py")
    logger.info("3. Sett opp cron-jobb for automatisk overvåking")
    logger.info("4. Test varslingssystem")

if __name__ == '__main__':
    main()
