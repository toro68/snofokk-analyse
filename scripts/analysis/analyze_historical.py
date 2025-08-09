import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import logging

# Sett opp logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config():
    """Laster konfigurasjon fra config.json."""
    try:
        config_path = Path('config/alert_config.json')
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Kunne ikke laste konfigurasjon: {str(e)}")
        raise

def assess_snowdrift_risk(data_row, config):
    """Vurderer risiko for snøfokk basert på værdata."""
    try:
        # Vindkriterier
        wind_speed = data_row['wind_speed']
        wind_strong = wind_speed >= config.get('wind_strong', 10.61)
        wind_moderate = wind_speed >= config.get('wind_moderate', 7.77)
        
        # Håndter vindkast og vindretning
        max_gust = data_row.get('max_wind_speed_3h', wind_speed)
        wind_gust = max_gust >= config.get('wind_gust', 16.96)
        
        # Sjekk vindretningsendring hvis tilgjengelig
        if 'wind_from_direction' in data_row:
            wind_dir = data_row['wind_from_direction']
            wind_dir_significant = wind_dir >= config.get('wind_dir_change', 37.83)
        else:
            wind_dir_significant = False
        
        logger.info(f"Vind - Hastighet: {wind_speed}, Moderat: {wind_moderate}, Sterk: {wind_strong}")
        logger.info(f"Vind - Kast: {max_gust}, Retningsendring: {wind_dir_significant}")
        
        # Temperaturkriterier
        temp = data_row['air_temperature']
        temp_cold = temp <= config.get('temp_cold', -2.2)
        temp_cool = temp <= config.get('temp_cool', 0.0)
        
        logger.info(f"Temperatur - Verdi: {temp}, Cool: {temp_cool}, Cold: {temp_cold}")
        
        # Snøkriterier
        snow_depth = data_row['surface_snow_thickness']
        snow_change = abs(data_row.get('snow_change', 0))
        
        snow_high = snow_change >= config.get('snow_high', 1.61)
        snow_moderate = snow_change >= config.get('snow_moderate', 0.84)
        snow_low = snow_change >= config.get('snow_low', 0.31)
        
        logger.info(f"Snø - Dybde: {snow_depth}, Endring: {snow_change}")
        logger.info(f"Snø - Low: {snow_low}, Moderate: {snow_moderate}, High: {snow_high}")
        
        # Luftfuktighet
        humidity = data_row['relative_humidity']
        humidity_ok = humidity < config.get('humidity_max', 85.0)  # Under 85% = økt risiko
        
        logger.info(f"Luftfuktighet - Verdi: {humidity}, Tørr nok for snøfokk: {humidity_ok}")
        
        # Beregn risikoscore med vekting
        risk_score = 0
        if (wind_moderate or wind_strong) and temp_cool and snow_low and humidity_ok:
            logger.info("Alle grunnkriterier oppfylt, beregner risikoscore...")
            
            # Vindrisiko (40%) - inkluderer nå vindretning
            wind_factor = (
                1.0 if wind_strong or (wind_moderate and wind_dir_significant) else
                0.7 if wind_moderate else
                0.3 if wind_gust else
                0.0
            )
            wind_score = wind_factor * config.get('wind_weight', 0.4)
            logger.info(f"Vind score: {wind_score} (faktor: {wind_factor})")
            
            # Temperaturrisiko (30%)
            temp_factor = (
                1.0 if temp_cold else
                0.7 if temp_cool else
                0.0
            )
            temp_score = temp_factor * config.get('temp_weight', 0.3)
            logger.info(f"Temperatur score: {temp_score} (faktor: {temp_factor})")
            
            # Snørisiko (30%)
            snow_factor = (
                1.0 if snow_high else
                0.7 if snow_moderate else
                0.3 if snow_low else
                0.0
            )
            snow_score = snow_factor * config.get('snow_weight', 0.3)
            logger.info(f"Snø score: {snow_score} (faktor: {snow_factor})")
            
            # Total risikoscore
            risk_score = wind_score + temp_score + snow_score
            logger.info(f"Total risikoscore: {risk_score}")
            
        return {
            'risk_score': risk_score,
            'conditions': {
                'wind_speed': wind_speed,
                'wind_gust': max_gust,
                'wind_dir_change': wind_dir if 'wind_dir' in locals() else None,
                'temperature': temp,
                'snow_depth': snow_depth,
                'snow_change': snow_change,
                'humidity': humidity
            },
            'factors': {
                'wind': {
                    'strong': wind_strong,
                    'moderate': wind_moderate,
                    'gust': wind_gust,
                    'dir_change': wind_dir_significant if 'wind_dir_significant' in locals() else False,
                    'score': wind_score if 'wind_score' in locals() else 0
                },
                'temp': {
                    'cold': temp_cold,
                    'cool': temp_cool,
                    'score': temp_score if 'temp_score' in locals() else 0
                },
                'snow': {
                    'high': snow_high,
                    'moderate': snow_moderate,
                    'low': snow_low,
                    'score': snow_score if 'snow_score' in locals() else 0
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Feil ved risikovurdering: {str(e)}")
        return False

def main():
    """Hovedfunksjon for analyse av historiske data."""
    try:
        config = load_config()
        
        # Definer tidsperiode
        start_date = "2023-11-01"
        end_date = "2024-05-01"
        
        # Les historiske data
        df = pd.read_csv('data/raw/historical_data.csv')
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Filtrer data for ønsket periode
        mask = (df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)
        df = df[mask]
        
        # Beregn endring i snødybde per time
        df = df.sort_values('timestamp')
        df['time_diff'] = df['timestamp'].diff().dt.total_seconds() / 3600  # Timer
        df['snow_change'] = abs(df['surface_snow_thickness'].diff() / df['time_diff'])
        df['snow_change'] = df['snow_change'].fillna(0)
        
        # Analyser hver time i perioden
        alerts = []
        for timestamp, group in df.groupby('timestamp'):
            data = {
                'wind_speed': float(group['wind_speed'].mean()),
                'air_temperature': float(group['air_temperature'].mean()),
                'surface_snow_thickness': float(group['surface_snow_thickness'].max()),
                'relative_humidity': float(group['relative_humidity'].mean()),
                'snow_change': float(group['snow_change'].fillna(0).max()),
                'wind_from_direction': float(group['wind_from_direction'].mean())
            }
            
            risk_assessment = assess_snowdrift_risk(data, config)
            if risk_assessment and risk_assessment['risk_score'] >= config['risk_threshold']:
                alerts.append({
                    'timestamp': timestamp,
                    'risk_score': risk_assessment['risk_score'],
                    'conditions': risk_assessment['conditions'],
                    'factors': risk_assessment['factors']
                })
        
        # Logg resultater
        logger.info(f"\nFant {len(alerts)} potensielle varsler i perioden")
        logger.info("\nDetaljer for hvert varsel:")
        
        for alert in alerts:
            logger.info(f"\n=== Varsel {alert['timestamp']} ===")
            logger.info(f"Risikoscore: {alert['risk_score']:.2f}")
            logger.info("\nVærforhold:")
            logger.info(f"Vind: {alert['conditions']['wind_speed']:.1f} m/s")
            logger.info(f"Vindkast: {alert['conditions']['wind_gust']:.1f} m/s")
            logger.info(f"Vindretning: {alert['conditions']['wind_dir_change']}°")
            logger.info(f"Temperatur: {alert['conditions']['temperature']:.1f}°C")
            logger.info(f"Snødybde: {alert['conditions']['snow_depth']:.1f} cm")
            logger.info(f"Snøendring: {alert['conditions']['snow_change']:.2f} cm/t")
            logger.info(f"Luftfuktighet: {alert['conditions']['humidity']:.1f}%")
            logger.info("\nRisikofaktorer:")
            logger.info(f"Vind score: {alert['factors']['wind']['score']:.2f}")
            logger.info(f"Temperatur score: {alert['factors']['temp']['score']:.2f}")
            logger.info(f"Snø score: {alert['factors']['snow']['score']:.2f}")
            
    except Exception as e:
        logger.error(f"Feil i hovedfunksjon: {str(e)}")

if __name__ == '__main__':
    main() 