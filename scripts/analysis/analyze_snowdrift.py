#!/usr/bin/env python3
"""
Script for å analysere værdata og identifisere forhold som fører til snøfokk.
Analyserer temperatur, vind, snødybde og luftfuktighet for å finne mønstre.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import logging
from pathlib import Path

# Logging oppsett
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/snowdrift_analysis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_and_clean_data(file_path):
    """
    Laster og forbereder data for analyse.
    
    Args:
        file_path (str): Sti til CSV-fil med værdata
        
    Returns:
        pd.DataFrame: Renset og forberedt datasett
    """
    logger.info("Laster værdata...")
    df = pd.read_csv(file_path)
    
    # Konverter timestamp til datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    # Fjern rader hvor alle verdier mangler
    df = df.dropna(how='all')
    
    # Beregn gjennomsnittlige verdier per time for å håndtere duplikater
    df = df.resample('H').mean()
    
    # Legg til beregnede kolonner
    df['hour'] = df.index.hour
    df['month'] = df.index.month
    df['wind_sustained'] = df['wind_speed'].rolling(window=3).mean()
    
    logger.info(f"Datasett lastet: {len(df)} rader")
    return df

def analyze_wind_conditions(df):
    """
    Analyserer vindforhold og deres sammenheng med andre parametere.
    
    Args:
        df (pd.DataFrame): DataFrame med værdata
        
    Returns:
        dict: Statistikk og terskelverdier for vind
    """
    logger.info("Analyserer vindforhold...")
    
    # Finn perioder med vedvarende vind over terskel
    wind_thresholds = range(6, 15, 1)
    wind_durations = []
    
    for threshold in wind_thresholds:
        high_wind = df['wind_sustained'] > threshold
        wind_periods = high_wind.astype(int).diff().fillna(0).abs()
        wind_durations.append(wind_periods.sum() / 2)
    
    optimal_wind_threshold = wind_thresholds[np.argmax(wind_durations)]
    
    # Analyser vindretning
    wind_dir_stats = df['wind_from_direction'].describe()
    
    return {
        'optimal_wind_threshold': optimal_wind_threshold,
        'wind_direction_stats': wind_dir_stats
    }

def analyze_temperature_conditions(df):
    """
    Analyserer temperaturforhold og deres påvirkning.
    
    Args:
        df (pd.DataFrame): DataFrame med værdata
        
    Returns:
        dict: Statistikk og terskelverdier for temperatur
    """
    logger.info("Analyserer temperaturforhold...")
    
    # Finn temperaturterskel hvor det er mest sannsynlig med snøfokk
    temp_range = np.arange(-20, 0, 0.5)
    temp_counts = []
    
    for temp in temp_range:
        cold_conditions = (df['air_temperature'] < temp) & (df['wind_speed'] > 6)
        temp_counts.append(cold_conditions.sum())
    
    optimal_temp_threshold = temp_range[np.argmax(temp_counts)]
    
    return {
        'optimal_temp_threshold': optimal_temp_threshold,
        'temp_stats': df['air_temperature'].describe()
    }

def analyze_humidity_impact(df):
    """
    Analyserer luftfuktighetens påvirkning på snøfokk.
    Lav luftfuktighet øker sannsynligheten for snøfokk da det indikerer tørr snø.
    
    Args:
        df (pd.DataFrame): DataFrame med værdata
        
    Returns:
        dict: Statistikk og terskelverdier for luftfuktighet
    """
    logger.info("Analyserer luftfuktighet...")
    
    # Undersøk sammenheng mellom luftfuktighet og andre faktorer
    humidity_wind_corr = df['relative_humidity'].corr(df['wind_speed'])
    humidity_temp_corr = df['relative_humidity'].corr(df['air_temperature'])
    
    # Finn optimal luftfuktighetsterskel (nå ser vi etter lav luftfuktighet)
    humidity_range = range(30, 75, 5)  # Endret område for å finne tørre forhold
    humidity_counts = []
    
    for hum in humidity_range:
        favorable_conditions = (
            (df['relative_humidity'] < hum) &  # Endret til å se etter forhold UNDER terskelen
            (df['wind_speed'] > 6) & 
            (df['air_temperature'] < -5)
        )
        humidity_counts.append(favorable_conditions.sum())
    
    optimal_humidity = humidity_range[np.argmax(humidity_counts)]
    
    return {
        'optimal_humidity': optimal_humidity,
        'humidity_wind_correlation': humidity_wind_corr,
        'humidity_temp_correlation': humidity_temp_corr
    }

def identify_snowdrift_conditions(df, wind_threshold=6.0, temp_threshold=-5.0, 
                                humidity_threshold=60.0, duration_hours=3,
                                min_snow_depth=10.0, wind_gust_threshold=16.96,
                                wind_dir_change_threshold=37.83,
                                snow_change_high=1.61, snow_change_moderate=0.84,
                                wind_weight=0.4, temp_weight=0.3, snow_weight=0.3):
    """
    Identifiserer perioder med høy sannsynlighet for snøfokk.
    Krever minst 10 cm snødybde for at snøfokk skal være mulig.
    
    Args:
        df (pd.DataFrame): DataFrame med værdata
        wind_threshold (float): Minimumsgrense for vind (m/s)
        temp_threshold (float): Maksimumsgrense for temperatur (°C)
        humidity_threshold (float): Maksimumsgrense for luftfuktighet (%)
        duration_hours (int): Minimum varighet for forhold (timer)
        min_snow_depth (float): Minimum snødybde i cm for at snøfokk skal være mulig
        wind_gust_threshold (float): Grense for vindkast (m/s)
        wind_dir_change_threshold (float): Grense for vindretningsendring (grader)
        snow_change_high (float): Grense for stor snøendring (cm)
        snow_change_moderate (float): Grense for moderat snøendring (cm)
        wind_weight (float): Vekting av vindfaktor
        temp_weight (float): Vekting av temperaturfaktor
        snow_weight (float): Vekting av snøfaktor
        
    Returns:
        pd.DataFrame: Perioder med sannsynlig snøfokk
    """
    logger.info("Identifiserer sannsynlige snøfokkperioder...")
    
    # Beregn endring i vindretning
    df['wind_dir_change'] = df['wind_from_direction'].diff().abs()
    df['wind_dir_change'] = df['wind_dir_change'].fillna(0)
    # Juster for overgang rundt 360 grader
    df.loc[df['wind_dir_change'] > 180, 'wind_dir_change'] = 360 - df['wind_dir_change']
    
    # Beregn snøendring
    df['snow_depth_change'] = df['surface_snow_thickness'].diff().abs()
    
    # Beregn risikoscore for hver faktor (0-1)
    wind_score = (
        (df['wind_speed'] >= wind_threshold).astype(float) * 0.6 +
        (df['max_wind_gust'] >= wind_gust_threshold).astype(float) * 0.2 +
        (df['wind_dir_change'] >= wind_dir_change_threshold).astype(float) * 0.2
    )
    
    temp_score = (df['air_temperature'] <= temp_threshold).astype(float)
    
    snow_score = (
        (df['surface_snow_thickness'] >= min_snow_depth).astype(float) * 0.4 +
        (df['snow_depth_change'] >= snow_change_high).astype(float) * 0.4 +
        (df['snow_depth_change'] >= snow_change_moderate).astype(float) * 0.2
    )
    
    humidity_score = (df['relative_humidity'] <= humidity_threshold).astype(float)
    
    # Beregn total risikoscore med vekting
    total_score = (
        wind_score * wind_weight +
        temp_score * temp_weight +
        snow_score * snow_weight
    ) * humidity_score  # Luftfuktighet fungerer som en modifiserende faktor
    
    # Definer høyrisiko-perioder (score > 0.7)
    high_risk = total_score > 0.7
    
    # Finn sammenhengende perioder
    labeled_periods = high_risk.astype(int).diff().fillna(0).abs().cumsum()
    period_lengths = high_risk.groupby(labeled_periods).transform('count')
    
    # Filtrer ut perioder som varer lenge nok
    significant_periods = high_risk & (period_lengths >= duration_hours)
    
    # Lag DataFrame med relevante perioder
    snowdrift_periods = df[significant_periods].copy()
    snowdrift_periods['risk_score'] = total_score[significant_periods]
    
    # Beregn statistikk for hver faktor
    if len(snowdrift_periods) > 0:
        logger.info("\nStatistikk for snøfokkperioder:")
        logger.info(f"Gjennomsnittlig vindstyrke: {snowdrift_periods['wind_speed'].mean():.1f} m/s")
        logger.info(f"Maksimal vindkast: {snowdrift_periods['max_wind_gust'].max():.1f} m/s")
        logger.info(f"Gjennomsnittlig temperatur: {snowdrift_periods['air_temperature'].mean():.1f}°C")
        logger.info(f"Gjennomsnittlig snødybde: {snowdrift_periods['surface_snow_thickness'].mean():.1f} cm")
        logger.info(f"Gjennomsnittlig snøendring: {snowdrift_periods['snow_depth_change'].mean():.2f} cm")
        logger.info(f"Gjennomsnittlig risikoscore: {snowdrift_periods['risk_score'].mean():.2f}")
        logger.info(f"Gjennomsnittlig vindretningsendring: {snowdrift_periods['wind_dir_change'].mean():.1f}°")
    
    logger.info(f"Fant {len(snowdrift_periods)} timer med sannsynlig snøfokk")
    return snowdrift_periods

def plot_conditions(df, snowdrift_periods, output_dir='data/analyzed'):
    """
    Lager visualiseringer av værforhold og snøfokkperioder.
    
    Args:
        df (pd.DataFrame): Komplett værdatasett
        snowdrift_periods (pd.DataFrame): Perioder med sannsynlig snøfokk
        output_dir (str): Mappe for lagring av plott
    """
    logger.info("Genererer visualiseringer...")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Plot 1: Vindhastighetsdistribusjon
    plt.figure(figsize=(10, 6))
    sns.histplot(data=df, x='wind_speed', bins=30)
    plt.title('Fordeling av vindhastighet')
    plt.savefig(f'{output_dir}/wind_distribution.png')
    plt.close()
    
    # Plot 2: Temperatur vs. vindhastighet
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=df, x='air_temperature', y='wind_speed', alpha=0.5)
    sns.scatterplot(data=snowdrift_periods, x='air_temperature', y='wind_speed', 
                    color='red', alpha=0.5, label='Snøfokk')
    plt.title('Temperatur vs. vindhastighet')
    plt.legend()
    plt.savefig(f'{output_dir}/temp_wind_relationship.png')
    plt.close()
    
    # Plot 3: Månedlig fordeling av snøfokkperioder
    monthly_counts = snowdrift_periods.groupby('month').size()
    plt.figure(figsize=(10, 6))
    monthly_counts.plot(kind='bar')
    plt.title('Månedlig fordeling av snøfokkperioder')
    plt.xlabel('Måned')
    plt.ylabel('Antall timer med snøfokk')
    plt.savefig(f'{output_dir}/monthly_distribution.png')
    plt.close()
    
    # Plot 4: Snødybde vs. vindhastighet
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=df, x='surface_snow_thickness', y='wind_speed', alpha=0.5)
    sns.scatterplot(data=snowdrift_periods, x='surface_snow_thickness', y='wind_speed',
                    color='red', alpha=0.5, label='Snøfokk')
    plt.title('Snødybde vs. vindhastighet')
    plt.xlabel('Snødybde (cm)')
    plt.ylabel('Vindhastighet (m/s)')
    plt.legend()
    plt.savefig(f'{output_dir}/snow_wind_relationship.png')
    plt.close()

def main():
    """Hovedfunksjon for snøfokkanalyse."""
    try:
        # Last data
        df = load_and_clean_data('data/raw/historical_data.csv')
        
        # Analyser forhold
        wind_analysis = analyze_wind_conditions(df)
        temp_analysis = analyze_temperature_conditions(df)
        humidity_analysis = analyze_humidity_impact(df)
        
        # Identifiser snøfokkperioder med optimaliserte parametere
        snowdrift_periods = identify_snowdrift_conditions(
            df,
            wind_threshold=wind_analysis['optimal_wind_threshold'],
            temp_threshold=temp_analysis['optimal_temp_threshold'],
            humidity_threshold=humidity_analysis['optimal_humidity']
        )
        
        # Generer visualiseringer
        plot_conditions(df, snowdrift_periods)
        
        # Skriv sammendrag
        logger.info("\nAnalyseresultater for snøfokk:")
        logger.info(f"Optimal vindterskel: {wind_analysis['optimal_wind_threshold']} m/s")
        logger.info(f"Optimal temperaturterskel: {temp_analysis['optimal_temp_threshold']}°C")
        logger.info(f"Optimal luftfuktighetsterskel: {humidity_analysis['optimal_humidity']}%")
        logger.info(f"Totalt antall timer med sannsynlig snøfokk: {len(snowdrift_periods)}")
        
        # Lagre resultater
        results_file = 'data/analyzed/snowdrift_summary.txt'
        with open(results_file, 'w') as f:
            f.write("=== Snøfokkanalyse ===\n\n")
            f.write(f"Optimal vindterskel: {wind_analysis['optimal_wind_threshold']} m/s\n")
            f.write(f"Optimal temperaturterskel: {temp_analysis['optimal_temp_threshold']}°C\n")
            f.write(f"Optimal luftfuktighetsterskel: {humidity_analysis['optimal_humidity']}%\n")
            f.write(f"Totalt antall timer med sannsynlig snøfokk: {len(snowdrift_periods)}\n\n")
            
            f.write("Vindretningsstatistikk:\n")
            f.write(str(wind_analysis['wind_direction_stats']))
            
            # Lagre perioder med snøfokk
            snowdrift_periods.to_csv('data/analyzed/snowdrift_periods.csv')
        
    except Exception as e:
        logger.error(f"En feil oppstod under analysen: {str(e)}")

if __name__ == "__main__":
    main() 