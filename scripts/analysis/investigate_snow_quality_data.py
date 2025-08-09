#!/usr/bin/env python3
"""
Undersøk tilgjengelige data for løssnø/nysnø kvalitet
"""

import pandas as pd
import numpy as np
import pickle
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

def investigate_snow_quality_parameters():
    """Undersøk hvilke parametere vi har for å vurdere snøkvalitet."""
    
    # Last cached data
    cache_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/cache/weather_data_2023-11-01_2024-04-30.pkl'
    
    with open(cache_file, 'rb') as f:
        df = pickle.load(f)
    
    print("🔍 UNDERSØKER TILGJENGELIGE SNØ-PARAMETERE")
    print("=" * 50)
    
    # Vis alle kolonner
    print(f"📊 Totalt {len(df.columns)} parametere tilgjengelig:")
    for i, col in enumerate(df.columns, 1):
        non_null_count = df[col].notna().sum()
        null_percentage = (df[col].isna().sum() / len(df)) * 100
        print(f"{i:2d}. {col:<30} | {non_null_count:>6} verdier ({null_percentage:5.1f}% NaN)")
    
    print("\n🎯 SNØ-RELATERTE PARAMETERE:")
    print("=" * 50)
    
    snow_params = [col for col in df.columns if 'snow' in col.lower() or 'precipitation' in col.lower()]
    
    for param in snow_params:
        non_null = df[param].notna().sum()
        if non_null > 0:
            print(f"\n📈 {param}:")
            print(f"   Gyldige verdier: {non_null}/{len(df)}")
            print(f"   Min: {df[param].min():.2f}")
            print(f"   Max: {df[param].max():.2f}")
            print(f"   Gjennomsnitt: {df[param].mean():.2f}")
            
            # Vis noen eksempelverdier
            sample_data = df[df[param].notna()][['referenceTime', param]].head(10)
            print(f"   Eksempler:")
            for _, row in sample_data.iterrows():
                print(f"     {row['referenceTime']}: {row[param]:.2f}")
    
    # Sjekk spesifikke parametere for løssnø
    print("\n🔍 SØKER ETTER NYSNØ/LØSSNØ PARAMETERE:")
    print("=" * 50)
    
    potential_params = [
        'surface_snow_thickness',
        'sum(precipitation_amount PT1H)',
        'air_temperature',
        'surface_air_pressure', 
        'relative_humidity'
    ]
    
    for param in potential_params:
        if param in df.columns:
            non_null = df[param].notna().sum()
            print(f"✅ {param}: {non_null} verdier")
            
            if param == 'sum(precipitation_amount PT1H)':
                # Analyser nedbør-data
                precip_data = df[df[param].notna()]
                if len(precip_data) > 0:
                    print(f"   Nedbør > 0: {(precip_data[param] > 0).sum()} timer")
                    print(f"   Maks nedbør: {precip_data[param].max():.2f} mm/t")
        else:
            print(f"❌ {param}: Ikke tilgjengelig")
    
    # Analysér temperatur-pattern for å identifisere mildvær
    print("\n🌡️ TEMPERATUR-ANALYSE FOR LØSSNØ VURDERING:")
    print("=" * 50)
    
    if 'air_temperature' in df.columns:
        temp_data = df[df['air_temperature'].notna()].copy()
        
        # Identifiser mildvær-perioder (temp > 0°C)
        temp_data['mild_weather'] = temp_data['air_temperature'] > 0
        
        # Beregn sammenhengende mildvær-perioder
        temp_data['mild_group'] = (temp_data['mild_weather'] != temp_data['mild_weather'].shift()).cumsum()
        
        mild_periods = []
        for group_id in temp_data[temp_data['mild_weather']]['mild_group'].unique():
            group_data = temp_data[temp_data['mild_group'] == group_id]
            if len(group_data) > 0:
                mild_periods.append({
                    'start': group_data['referenceTime'].min(),
                    'end': group_data['referenceTime'].max(),
                    'duration_hours': len(group_data),
                    'max_temp': group_data['air_temperature'].max()
                })
        
        print(f"🔥 Antall mildvær-perioder (>0°C): {len(mild_periods)}")
        
        if mild_periods:
            long_mild_periods = [p for p in mild_periods if p['duration_hours'] >= 6]
            print(f"🔥 Lange mildvær-perioder (≥6t): {len(long_mild_periods)}")
            
            print("\n📅 Eksempler på lange mildvær-perioder:")
            for i, period in enumerate(long_mild_periods[:10], 1):
                print(f"{i:2d}. {period['start'].strftime('%d.%m.%Y %H:%M')} - {period['end'].strftime('%d.%m.%Y %H:%M')}")
                print(f"    Varighet: {period['duration_hours']}t, Maks temp: {period['max_temp']:.1f}°C")
    
    # Foreslå nye kriterier for løssnø
    print("\n💡 FORSLAG TIL LØSSNØ-KRITERIER:")
    print("=" * 50)
    print("""
    For at snøfokk skal kunne oppstå må følgende være oppfylt:
    
    1. 🌨️ GRUNNLEGGENDE SNØFOKK-KRITERIER:
       • Vindstyrke ≥ 6 m/s
       • Temperatur ≤ -1°C  
       • Snødybde ≥ 3 cm
    
    2. ❄️ LØSSNØ-KRITERIER (NYE):
       • Ingen mildvær (>0°C) siste 24-48 timer
       • Helst nysnø (nedbør) siste 72 timer
       • Kontinuerlig frost siste 12+ timer
    
    3. 🎯 KVALITETSKRITERIER:
       • Gyldig vinddata tilgjengelig
       • Temperaturdata for siste 24-48t
       
    Dette vil gi en MYE mer realistisk snøfokk-analyse!
    """)

def analyze_loose_snow_availability():
    """Analyser tilgjengelighet av løssnø basert på temperatur-historikk."""
    
    cache_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/cache/weather_data_2023-11-01_2024-04-30.pkl'
    
    with open(cache_file, 'rb') as f:
        df = pickle.load(f)
    
    print("\n🔍 DETALJERT LØSSNØ-ANALYSE:")
    print("=" * 50)
    
    # Sorter etter tid
    df_sorted = df.sort_values('referenceTime').reset_index(drop=True)
    
    # Beregn løssnø-tilgjengelighet for hver time
    df_sorted['loose_snow_available'] = False
    df_sorted['hours_since_mild'] = None
    df_sorted['frost_duration'] = 0
    
    # For hver rad, sjekk temperatur-historikk
    for idx in range(len(df_sorted)):
        current_time = df_sorted.loc[idx, 'referenceTime']
        current_temp = df_sorted.loc[idx, 'air_temperature']
        
        if pd.isna(current_temp):
            continue
            
        # Sjekk temperatur siste 48 timer
        lookback_hours = 48
        start_time = current_time - timedelta(hours=lookback_hours)
        
        # Filtrer til relevant tidsperiode
        recent_data = df_sorted[
            (df_sorted['referenceTime'] >= start_time) & 
            (df_sorted['referenceTime'] <= current_time) &
            (df_sorted['air_temperature'].notna())
        ]
        
        if len(recent_data) == 0:
            continue
            
        # Sjekk om det har vært mildvær
        has_mild_weather = (recent_data['air_temperature'] > 0).any()
        
        # Beregn timer siden siste mildvær
        if has_mild_weather:
            mild_times = recent_data[recent_data['air_temperature'] > 0]['referenceTime']
            last_mild_time = mild_times.max()
            hours_since_mild = (current_time - last_mild_time).total_seconds() / 3600
            df_sorted.loc[idx, 'hours_since_mild'] = hours_since_mild
        else:
            df_sorted.loc[idx, 'hours_since_mild'] = lookback_hours + 1  # Lenger enn lookback
        
        # Beregn sammenhengende frost-periode
        frost_hours = 0
        for prev_idx in range(idx, -1, -1):
            prev_temp = df_sorted.loc[prev_idx, 'air_temperature']
            if pd.isna(prev_temp) or prev_temp > 0:
                break
            frost_hours += 1
        
        df_sorted.loc[idx, 'frost_duration'] = frost_hours
        
        # Vurder løssnø-tilgjengelighet
        # Kriterier: Minst 24t siden mildvær OG minst 12t sammenhengende frost
        if (df_sorted.loc[idx, 'hours_since_mild'] >= 24 and 
            df_sorted.loc[idx, 'frost_duration'] >= 12):
            df_sorted.loc[idx, 'loose_snow_available'] = True
    
    # Statistikk
    total_hours = len(df_sorted[df_sorted['air_temperature'].notna()])
    loose_snow_hours = df_sorted['loose_snow_available'].sum()
    
    print(f"📊 Timer med gyldig temperaturdata: {total_hours}")
    print(f"❄️ Timer med løssnø tilgjengelig: {loose_snow_hours}")
    print(f"📈 Prosentandel med løssnø: {(loose_snow_hours/total_hours)*100:.1f}%")
    
    # Lagre for senere bruk
    output_file = '/Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system/data/cache/loose_snow_analysis.pkl'
    with open(output_file, 'wb') as f:
        pickle.dump(df_sorted, f)
    
    print(f"💾 Lagret løssnø-analyse til {output_file}")
    
    return df_sorted

def main():
    """Hovedfunksjon."""
    try:
        investigate_snow_quality_parameters()
        analyze_loose_snow_availability()
        
    except Exception as e:
        print(f"❌ Feil: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
