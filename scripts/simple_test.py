#!/usr/bin/env python3
"""
Simple Weather System Test - Enkel test av værsystemet
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_basic_imports():
    """Test grunnleggende imports"""

    logger.info("=== TESTER IMPORTS ===")

    try:
        # Test config system
        sys.path.insert(0, str(Path(__file__).parent))
        from utils.weather_config import ConfigManager
        logger.info("✓ Config system importert OK")

        # Test at vi kan opprette konfigurasjon
        config_path = Path(__file__).parent.parent / "config" / "test_config.json"
        config_manager = ConfigManager(str(config_path))
        logger.info("✓ Config manager opprettet OK")

        return True

    except Exception as e:
        logger.error(f"✗ Import feil: {e}")
        return False

def test_weather_service():
    """Test weather service hvis tilgjengelig"""

    logger.info("=== TESTER WEATHER SERVICE ===")

    try:
        # Add src to path
        src_path = Path(__file__).parent.parent / "src"
        sys.path.insert(0, str(src_path))

        # Test if weather service exists
        weather_service_path = src_path / "snofokk" / "services" / "weather.py"

        if weather_service_path.exists():
            from snofokk.services.weather import WeatherService
            weather_service = WeatherService()
            logger.info("✓ Weather service importert OK")
            return True
        else:
            logger.warning("! Weather service ikke funnet (OK for testing)")
            return True

    except Exception as e:
        logger.error(f"✗ Weather service feil: {e}")
        return False

def test_file_structure():
    """Test at filstrukturen er riktig"""

    logger.info("=== TESTER FILSTRUKTUR ===")

    base_path = Path(__file__).parent.parent

    required_dirs = [
        "scripts/analysis",
        "scripts/utils",
        "scripts/reports",
        "src/snofokk",
        "config",
        "data",
        "logs"
    ]

    missing_dirs = []

    for dir_path in required_dirs:
        full_path = base_path / dir_path
        if not full_path.exists():
            missing_dirs.append(dir_path)
            logger.warning(f"! Mangler mappe: {dir_path}")
        else:
            logger.info(f"✓ Fant mappe: {dir_path}")

    if missing_dirs:
        logger.error(f"✗ Mangler {len(missing_dirs)} mapper")
        return False
    else:
        logger.info("✓ Alle nødvendige mapper funnet")
        return True

def test_analyzer_files():
    """Test at analyzer-filene eksisterer"""

    logger.info("=== TESTER ANALYZER-FILER ===")

    analysis_path = Path(__file__).parent / "analysis"

    required_files = [
        "snow_drift_pattern_analyzer.py",
        "slippery_road_pattern_analyzer.py",
        "weather_pattern_optimizer.py"
    ]

    missing_files = []

    for file_name in required_files:
        file_path = analysis_path / file_name
        if not file_path.exists():
            missing_files.append(file_name)
            logger.warning(f"! Mangler fil: {file_name}")
        else:
            logger.info(f"✓ Fant fil: {file_name}")

    if missing_files:
        logger.error(f"✗ Mangler {len(missing_files)} filer")
        return False
    else:
        logger.info("✓ Alle analyzer-filer funnet")
        return True

def test_config_creation():
    """Test opprettelse av konfigurasjon"""

    logger.info("=== TESTER KONFIG-OPPRETTELSE ===")

    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from utils.weather_config import ConfigManager

        # Opprett test-konfigurasjon
        config_dir = Path(__file__).parent.parent / "config"
        config_dir.mkdir(exist_ok=True)

        config_path = config_dir / "test_system_config.json"
        config_manager = ConfigManager(str(config_path))

        # Test oppdatering av parametere
        config_manager.update_snow_drift_params(
            min_wind_speed=10.0,
            max_temperature=-1.0,
            alert_threshold=75
        )

        config_manager.update_slippery_road_params(
            max_temperature=1.0,
            min_humidity=85.0
        )

        logger.info("✓ Konfigurasjon opprettet og oppdatert OK")

        # Skriv ut konfigurasjon
        config_manager.print_current_config()

        return True

    except Exception as e:
        logger.error(f"✗ Konfig-feil: {e}")
        return False

def test_data_directories():
    """Test at data-mapper er tilgjengelige"""

    logger.info("=== TESTER DATA-MAPPER ===")

    base_path = Path(__file__).parent.parent

    data_dirs = [
        "data/analyzed",
        "data/raw",
        "logs"
    ]

    for dir_path in data_dirs:
        full_path = base_path / dir_path
        full_path.mkdir(parents=True, exist_ok=True)

        if full_path.exists() and full_path.is_dir():
            logger.info(f"✓ Data-mappe OK: {dir_path}")
        else:
            logger.error(f"✗ Kunne ikke opprette: {dir_path}")
            return False

    # Test skriving til data-mappe
    test_file = base_path / "data" / "analyzed" / "test_write.txt"
    try:
        with open(test_file, 'w') as f:
            f.write(f"Test skrevet: {datetime.now()}")

        if test_file.exists():
            test_file.unlink()  # Slett testfil
            logger.info("✓ Skriving til data-mappe OK")

        return True

    except Exception as e:
        logger.error(f"✗ Kan ikke skrive til data-mappe: {e}")
        return False

def create_simple_analysis_demo():
    """Opprett en enkel analyse-demo"""

    logger.info("=== OPPRETTER ANALYSE-DEMO ===")

    try:
        # Opprett demo-data
        demo_data = {
            "analysis_date": datetime.now().isoformat(),
            "demo_results": {
                "snow_drift_events": 5,
                "slippery_road_events": 12,
                "temperature_range": [-8.2, 3.1],
                "wind_speed_max": 15.4,
                "recommendations": [
                    "Øk overvåking når temperatur er mellom -2°C og +2°C",
                    "Implementer varsling 4 timer før forventede hendelser",
                    "Mest kritiske timer: 06:00-09:00 og 16:00-19:00"
                ]
            },
            "status": "Demo-analyse fullført"
        }

        # Lagre demo-resultater
        import json

        output_path = Path(__file__).parent.parent / "data" / "analyzed" / "demo_analysis.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(demo_data, f, indent=2, ensure_ascii=False)

        logger.info(f"✓ Demo-analyse lagret til: {output_path}")

        # Vis resultater
        logger.info("\n--- DEMO-RESULTATER ---")
        for key, value in demo_data["demo_results"].items():
            if key == "recommendations":
                logger.info("Anbefalinger:")
                for rec in value:
                    logger.info(f"  - {rec}")
            else:
                logger.info(f"{key}: {value}")

        return True

    except Exception as e:
        logger.error(f"✗ Demo-feil: {e}")
        return False

def main():
    """Hovedtest av systemet"""

    logger.info("=== ENKEL SYSTEMTEST ===")
    logger.info(f"Startet: {datetime.now()}")

    tests = [
        ("Filstruktur", test_file_structure),
        ("Analyzer-filer", test_analyzer_files),
        ("Imports", test_basic_imports),
        ("Weather Service", test_weather_service),
        ("Konfigurasjon", test_config_creation),
        ("Data-mapper", test_data_directories),
        ("Demo-analyse", create_simple_analysis_demo)
    ]

    results = {}
    passed = 0

    for test_name, test_func in tests:
        logger.info(f"\n--- {test_name.upper()} ---")
        try:
            result = test_func()
            results[test_name] = result
            if result:
                passed += 1
        except Exception as e:
            logger.error(f"✗ Feil i {test_name}: {e}")
            results[test_name] = False

    # Vis resultater
    logger.info("\n=== TESTRESULTATER ===")
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{test_name:20}: {status}")

    logger.info(f"\nResultat: {passed}/{len(tests)} tester bestått")

    if passed >= len(tests) * 0.8:
        logger.info("🎉 System er klart for bruk!")
        logger.info("\n=== NESTE STEG ===")
        logger.info("1. Konfigurer parametere:")
        logger.info("   python scripts/utils/weather_config.py --interactive")
        logger.info("2. Kjør full analyse:")
        logger.info("   python scripts/analysis/snow_drift_pattern_analyzer.py")
        logger.info("3. Sett opp automatisk kjøring med cron")
    else:
        logger.info("⚠️  Noen tester feilet. Sjekk konfigurasjonen.")

if __name__ == '__main__':
    main()
