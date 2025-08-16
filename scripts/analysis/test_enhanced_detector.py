#!/usr/bin/env python3
"""
Test Enhanced Detector - Test den forbedrede detektoren mot kjente snøfokk-perioder
"""
import asyncio
import sys
from datetime import date
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from enhanced_snowdrift_detector import EnhancedSnowdriftDetector


async def test_multiple_periods():
    """Test den forbedrede detektoren mot flere kjente perioder"""

    detector = EnhancedSnowdriftDetector()

    # Test flere perioder
    test_periods = [
        (date(2024, 1, 1), date(2024, 1, 31), "Januar 2024"),
        (date(2024, 2, 1), date(2024, 2, 29), "Februar 2024"),
        (date(2024, 3, 1), date(2024, 3, 31), "Mars 2024"),
        (date(2023, 12, 1), date(2023, 12, 31), "Desember 2023"),
        (date(2023, 1, 1), date(2023, 1, 31), "Januar 2023")
    ]

    print("🧪 TESTING FORBEDRET SNØFOKK-DETEKTOR")
    print("=" * 60)
    print("Tester mot flere kjente vinterperioder...")
    print()

    all_results = []

    for start_date, end_date, period_name in test_periods:
        print(f"📅 TESTER: {period_name}")
        print("-" * 40)

        try:
            events = await detector.run_enhanced_analysis(start_date, end_date)

            result = {
                'period': period_name,
                'start_date': str(start_date),
                'end_date': str(end_date),
                'events_found': len(events) if events else 0,
                'total_hours': sum(e['duration_hours'] for e in events) if events else 0
            }

            all_results.append(result)

            if events:
                # Analyser typer
                drift_types = {}
                for event in events:
                    drift_type = event['drift_type']['type']
                    if drift_type not in drift_types:
                        drift_types[drift_type] = 0
                    drift_types[drift_type] += 1

                print(f"✅ Fant {len(events)} hendelser ({sum(e['duration_hours'] for e in events)} timer)")
                for dtype, count in drift_types.items():
                    print(f"   • {dtype}: {count} hendelser")
            else:
                print("❌ Ingen hendelser funnet")

            print()

        except Exception as e:
            print(f"❌ Feil for {period_name}: {e}")
            print()

    # Sammendrag
    print("📊 SAMMENDRAG AV ALLE TESTER")
    print("=" * 60)

    total_events = sum(r['events_found'] for r in all_results)
    total_hours = sum(r['total_hours'] for r in all_results)

    print(f"Totalt testet: {len(test_periods)} perioder")
    print(f"Totalt funnet: {total_events} snøfokk-hendelser")
    print(f"Total varighet: {total_hours} timer")
    print()

    for result in all_results:
        status = "✅" if result['events_found'] > 0 else "❌"
        print(f"{status} {result['period']}: {result['events_found']} hendelser ({result['total_hours']} timer)")

    # Vurdering
    periods_with_events = len([r for r in all_results if r['events_found'] > 0])
    success_rate = (periods_with_events / len(all_results)) * 100

    print(f"\n🎯 DETEKSJONSRATE: {success_rate:.1f}%")

    if success_rate >= 60:
        print("✅ GOD deteksjon - systemet finner snøfokk i de fleste perioder")
    elif success_rate >= 40:
        print("⚠️ MODERAT deteksjon - kan trenge justering")
    else:
        print("❌ LAV deteksjon - trenger betydelig justering")

    print("\n💡 ANBEFALING:")
    if total_events == 0:
        print("• Ingen hendelser funnet - sjekk API-tilkobling og parametre")
        print("• Mulig at optimaliserte terskler er for strenge")
        print("• Test med lavere grenseverdier")
    elif total_events < 10:
        print("• Få hendelser funnet - vurder å senke terskler")
        print("• Spesielt viktig å fange 'usynlig' snøfokk")
    else:
        print("• God deteksjon - fortsett med fintuning")
        print("• Fokuser på å klassifisere drift-typer korrekt")

async def main():
    await test_multiple_periods()

if __name__ == '__main__':
    asyncio.run(main())
