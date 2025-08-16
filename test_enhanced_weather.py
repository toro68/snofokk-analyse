#!/usr/bin/env python3
"""
Test av forbedret værtjeneste som utnytter alle tilgjengelige data fra Gullingen.
"""

import sys
from pathlib import Path

# Legg til src til path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from snofokk.services.enhanced_weather import EnhancedWeatherService

def main():
    """Test den forbedrede værtjenesten."""
    print("🌤️  TESTING AV FORBEDRET VÆRTJENESTE")
    print("=" * 60)
    
    try:
        service = EnhancedWeatherService()
        
        # Test tilgjengelige elementer
        print("📡 TILGJENGELIGE VÆRELEMENTER:")
        elements = service.get_available_elements()
        print(f"  • Totalt: {len(elements)} elementer")
        
        critical_elements = [
            'air_temperature', 
            'wind_speed', 
            'precipitation_amount',
            'surface_snow_thickness',
            'wind_from_direction'
        ]
        
        available_critical = [e for e in critical_elements if e in elements]
        print(f"  • Kritiske elementer tilgjengelig: {len(available_critical)}/{len(critical_elements)}")
        
        # Test værdata henting (siste 24 timer)
        print("\n🔍 TESTING VÆRDATA HENTING:")
        from datetime import datetime, timedelta
        
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)
        
        weather_data = service.get_enhanced_weather_data(
            start_time=start_time,
            end_time=end_time
        )
        
        if weather_data:
            print(f"  ✅ Hentet {len(weather_data)} observasjoner")
            print(f"  📊 Kolonner: {list(weather_data.columns)}")
            
            # Test risikoanalyse
            print("\n⚠️  TESTING RISIKOANALYSE:")
            risk_analysis = service.analyze_snowdrift_risk(weather_data)
            
            print(f"  🌨️  Snøfokk-risiko: {risk_analysis['snowdrift_risk']:.2f}")
            print(f"  🧊 Glattføre-risiko: {risk_analysis['icing_risk']:.2f}")
            print(f"  ❄️  Nedbør-risiko: {risk_analysis['precipitation_risk']:.2f}")
            
            # Test værrapport
            print("\n📋 VÆRRAPPORT:")
            conditions = service.get_current_conditions()
            for key, value in conditions.items():
                print(f"  • {key}: {value}")
                
        else:
            print("  ⚠️  Ingen værdata hentet")
            
    except Exception as e:
        print(f"❌ Feil under testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
