import pandas as pd
import numpy as np

# Last inn data
data = pd.read_csv('scripts/data/processed/frost_data_2025-01-30_to_2025-03-01.csv')
feb15 = data[data.iloc[:,0].str.contains('2025-02-15')]

# Standardparametre
params = {
    'wind_strong': 10.61,
    'wind_moderate': 7.77,
    'wind_gust': 16.96,
    'wind_dir_change': 37.83,
    'wind_weight': 0.4,
    'temp_cold': -2.2,
    'temp_cool': 0,
    'temp_weight': 0.3,
    'snow_high': 1.61,
    'snow_moderate': 0.84,
    'snow_low': 0.31,
    'snow_weight': 0.3,
    'min_duration': 2
}

# Beregn risiko
risk_df = pd.DataFrame(index=feb15.index)
    
# Beregn risikoscore basert på vind, temperatur og snødybde
wind_risk = np.zeros(len(feb15))
temp_risk = np.zeros(len(feb15))
snow_risk = np.zeros(len(feb15))

# Vindrisiko - sett til 0 når vindstyrken er under 6 m/s
mask_wind = feb15['wind_speed'] >= 6.0
wind_risk[mask_wind & (feb15['wind_speed'] >= params['wind_strong'])] = 1.0
wind_risk[mask_wind & (feb15['wind_speed'] >= params['wind_moderate']) & (feb15['wind_speed'] < params['wind_strong'])] = 0.5

# Temperaturrisiko
temp_risk[feb15['air_temperature'] <= params['temp_cold']] = 1.0
temp_risk[(feb15['air_temperature'] > params['temp_cold']) & (feb15['air_temperature'] <= params['temp_cool'])] = 0.5

# Snørisiko - sjekk om det er snø tilgjengelig
snow_available = feb15['surface_snow_thickness'] > 0
snow_diff = feb15['surface_snow_thickness'].diff().abs()
snow_risk[snow_available & (snow_diff >= params['snow_high'])] = 1.0
snow_risk[snow_available & (snow_diff >= params['snow_moderate']) & (snow_diff < params['snow_high'])] = 0.5

# Beregn total risikoscore - vektet sum av risikoene
risk_scores = (
    params['wind_weight'] * wind_risk +
    params['temp_weight'] * temp_risk +
    params['snow_weight'] * snow_risk
)

# Sett risiko til 0 når vindstyrken er under 6 m/s
risk_scores[feb15['wind_speed'] < 6.0] = 0.0

# Vis resultater
result = pd.DataFrame({
    'timestamp': feb15['timestamp'],
    'wind_speed': feb15['wind_speed'],
    'air_temperature': feb15['air_temperature'],
    'snow_thickness': feb15['surface_snow_thickness'],
    'snow_diff': snow_diff,
    'wind_risk': wind_risk,
    'temp_risk': temp_risk,
    'snow_risk': snow_risk,
    'risk_score': risk_scores
})

print("Analyse av værdata for 15. februar 2025:")
print("-" * 50)
print(result)

# Sjekk om det er noen perioder med høy risiko (over 0.6)
high_risk = result[result['risk_score'] > 0.6]
if len(high_risk) > 0:
    print('\nPerioder med høy risiko (score > 0.6):')
    print(high_risk)
else:
    print('\nIngen perioder med høy risiko funnet.')

# Analyser hvorfor alarmen ikke ble utløst
print("\nAnalyse av hvorfor alarmen ikke ble utløst:")
print("-" * 50)

# Sjekk vindkriterier
print(f"Vindkriterier (moderat: {params['wind_moderate']}, sterk: {params['wind_strong']}):")
wind_ok = feb15['wind_speed'] >= params['wind_moderate']
print(f"Timer med tilstrekkelig vind: {wind_ok.sum()} av {len(feb15)}")

# Sjekk temperaturkriterier
print(f"\nTemperaturkriterier (kald: {params['temp_cold']}, kjølig: {params['temp_cool']}):")
temp_ok = feb15['air_temperature'] <= params['temp_cold']
print(f"Timer med tilstrekkelig lav temperatur: {temp_ok.sum()} av {len(feb15)}")

# Sjekk snøkriterier
print(f"\nSnøkriterier (moderat endring: {params['snow_moderate']}, stor endring: {params['snow_high']}):")
snow_ok = snow_diff >= params['snow_moderate']
print(f"Timer med tilstrekkelig snøendring: {snow_ok.sum()} av {len(feb15)}")

# Sjekk kombinerte kriterier
combined_ok = (wind_ok & temp_ok & snow_ok)
print(f"\nTimer med alle kriterier oppfylt samtidig: {combined_ok.sum()} av {len(feb15)}")

# Sjekk om det er perioder med nesten høy nok risiko
medium_risk = result[(result['risk_score'] > 0.4) & (result['risk_score'] <= 0.6)]
if len(medium_risk) > 0:
    print('\nPerioder med middels risiko (score 0.4-0.6):')
    print(medium_risk)
else:
    print('\nIngen perioder med middels risiko funnet.')

# Sjekk maksimal risikoscore
max_risk = result['risk_score'].max()
max_risk_time = result.loc[result['risk_score'].idxmax(), 'timestamp']
print(f"\nMaksimal risikoscore: {max_risk} (tidspunkt: {max_risk_time})")

# Sjekk om det var noen perioder med høy risiko for individuelle faktorer
print("\nPerioder med høy risiko for individuelle faktorer:")
print(f"Vind: {(wind_risk == 1.0).sum()} timer")
print(f"Temperatur: {(temp_risk == 1.0).sum()} timer")
print(f"Snø: {(snow_risk == 1.0).sum()} timer") 