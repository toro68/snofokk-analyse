#!/usr/bin/env python3
"""
Snowdrift Performance Tester - Tester optimalisert konfigurasjon mot historisk data
"""
import sys
from pathlib import Path
import json
from datetime import datetime, date, timedelta
import asyncio

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from snofokk.config import settings
from snofokk.services.weather import WeatherService
from snofokk.services.analysis import AnalysisService

class SnowdriftPerformanceTester:
    """Tester ytelsen til optimaliserte parametere"""
    
    def __init__(self):
        self.weather_service = WeatherService()
        self.config_path = Path(__file__).parent.parent.parent / 'config' / 'optimized_snowdrift_config.json'
        self.load_optimized_config()
    
    def load_optimized_config(self):
        """Last inn optimalisert konfigurasjon"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.optimized_config = json.load(f)
            print("✅ Optimalisert konfigurasjon lastet")
        except FileNotFoundError:
            print("❌ Kjør først optimize_snowdrift_parameters.py")
            self.optimized_config = None
    
    def create_optimized_analyzer(self):
        """Lag AnalysisService med optimaliserte parametere"""
        if not self.optimized_config:
            return None
        
        # Bruk optimaliserte parametere
        config = self.optimized_config['snowdrift_detection']
        
        class OptimizedAnalysisService(AnalysisService):
            def __init__(self):
                super().__init__()
                # Override standard parametere med optimaliserte
                self.min_wind_speed = config['wind']['min_speed_ms']
                self.max_temperature = config['temperature']['max_temp_c']
                self.min_snow_depth = config['snow']['min_depth_cm']
                self.min_duration_hours = 1  # Fra optimalisert config
        
        return OptimizedAnalysisService()
    
    async def test_winter_period(self, start_date, end_date, period_name):
        """Test en vinter-periode med både original og optimaliserte parametere"""
        print(f"\n🧪 Tester {period_name}")
        print(f"   Periode: {start_date} til {end_date}")
        
        # Hent værdata
        weather_data = await self.weather_service.get_historical_data(
            station_id=settings.weather_station_id,
            start_date=start_date,
            end_date=end_date
        )
        
        if not weather_data:
            print("   ❌ Ingen værdata")
            return None
        
        print(f"   📊 {len(weather_data)} datapunkter hentet")
        
        # Test med original parametere
        original_analyzer = AnalysisService()
        original_events = original_analyzer.detect_snowdrift_periods(weather_data)
        
        # Test med optimaliserte parametere
        optimized_analyzer = self.create_optimized_analyzer()
        if not optimized_analyzer:
            return None
        
        optimized_events = optimized_analyzer.detect_snowdrift_periods(weather_data)
        
        return {
            'period': period_name,
            'data_points': len(weather_data),
            'original': {
                'events': len(original_events),
                'total_hours': sum(event['duration_hours'] for event in original_events)
            },
            'optimized': {
                'events': len(optimized_events),
                'total_hours': sum(event['duration_hours'] for event in optimized_events)
            },
            'comparison': {
                'events_change': len(optimized_events) - len(original_events),
                'events_change_pct': ((len(optimized_events) - len(original_events)) / max(len(original_events), 1)) * 100,
                'hours_change': sum(event['duration_hours'] for event in optimized_events) - sum(event['duration_hours'] for event in original_events)
            }
        }
    
    async def run_comprehensive_test(self):
        """Kjør fullstendig test av alle vinter-perioder"""
        print("🔬 YTELSESTEST - ORIGINAL VS OPTIMALISERT")
        print("=" * 60)
        
        if not self.optimized_config:
            print("❌ Ingen optimalisert konfigurasjon funnet")
            return
        
        # Test samme perioder som i historisk analyse
        test_periods = [
            (date(2024, 12, 1), date(2025, 3, 31), "Vinter 2024-2025"),
            (date(2023, 12, 1), date(2024, 3, 31), "Vinter 2023-2024"),
            (date(2022, 12, 1), date(2023, 3, 31), "Vinter 2022-2023")
        ]
        
        results = []
        
        for start_date, end_date, period_name in test_periods:
            result = await self.test_winter_period(start_date, end_date, period_name)
            if result:
                results.append(result)
        
        # Analyser resultatene
        self.analyze_results(results)
        
        # Lagre resultater
        output_file = Path(__file__).parent.parent.parent / 'data' / 'analyzed' / 'snowdrift_performance_test.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'test_date': datetime.now().isoformat(),
                'optimized_config_used': self.optimized_config,
                'results': results,
                'summary': self.calculate_summary(results)
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Detaljerte resultater lagret i {output_file}")
    
    def analyze_results(self, results):
        """Analyser og presenter testresultater"""
        print("\n📈 SAMMENLIGNING RESULTATER")
        print("=" * 60)
        
        total_original_events = 0
        total_optimized_events = 0
        total_original_hours = 0
        total_optimized_hours = 0
        
        for result in results:
            period = result['period']
            orig = result['original']
            opt = result['optimized']
            comp = result['comparison']
            
            print(f"\n{period}:")
            print(f"   Original:     {orig['events']} hendelser, {orig['total_hours']} timer")
            print(f"   Optimalisert: {opt['events']} hendelser, {opt['total_hours']} timer")
            print(f"   Endring:      {comp['events_change']:+d} hendelser ({comp['events_change_pct']:+.1f}%)")
            
            total_original_events += orig['events']
            total_optimized_events += opt['events']
            total_original_hours += orig['total_hours']
            total_optimized_hours += opt['total_hours']
        
        # Total sammenligning
        print(f"\n🎯 TOTALT OVER ALLE PERIODER:")
        print(f"   Original:     {total_original_events} hendelser, {total_original_hours} timer")
        print(f"   Optimalisert: {total_optimized_events} hendelser, {total_optimized_hours} timer")
        
        if total_original_events > 0:
            event_change_pct = ((total_optimized_events - total_original_events) / total_original_events) * 100
            print(f"   Endring:      {total_optimized_events - total_original_events:+d} hendelser ({event_change_pct:+.1f}%)")
        
        # Vurdering
        print(f"\n📊 VURDERING:")
        if total_optimized_events > total_original_events:
            print("   ✅ Optimalisert konfigurasjon fanger flere hendelser")
            print("   💡 Dette kan indikere bedre sensitivitet")
        elif total_optimized_events < total_original_events:
            print("   ⚠️  Optimalisert konfigurasjon fanger færre hendelser")
            print("   💡 Dette kan redusere false positives")
        else:
            print("   ↔️  Samme antall hendelser oppdaget")
        
        print(f"\n🔧 HOVEDFORSKJELLER I PARAMETERE:")
        config = self.optimized_config['snowdrift_detection']
        print(f"   Minimum vind: 6.0 → {config['wind']['min_speed_ms']} m/s")
        print(f"   Maksimal temp: -2.0 → {config['temperature']['max_temp_c']}°C")
        print(f"   Minimum snø: 3.0 → {config['snow']['min_depth_cm']} cm")
    
    def calculate_summary(self, results):
        """Beregn sammendrag av resultater"""
        total_original = sum(r['original']['events'] for r in results)
        total_optimized = sum(r['optimized']['events'] for r in results)
        
        return {
            'total_periods_tested': len(results),
            'total_original_events': total_original,
            'total_optimized_events': total_optimized,
            'improvement_events': total_optimized - total_original,
            'improvement_percentage': ((total_optimized - total_original) / max(total_original, 1)) * 100 if total_original > 0 else 0,
            'recommendation': 'DEPLOY' if total_optimized >= total_original * 0.8 else 'NEEDS_TUNING'
        }

async def main():
    tester = SnowdriftPerformanceTester()
    await tester.run_comprehensive_test()

if __name__ == '__main__':
    asyncio.run(main())
