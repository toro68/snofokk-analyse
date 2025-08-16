import logging

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# Sett opp logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def plot_snowdrift_timeline():
    """Lager visualiseringer av snøfokkperioder over tid."""
    try:
        # Les data
        df = pd.read_csv('data/analyzed/snowdrift_dates.csv')
        df['dato'] = pd.to_datetime(df['dato'])

        # Plot 1: Tidslinje med vindstyrke
        plt.figure(figsize=(15, 8))
        plt.scatter(df['dato'], df['vindstyrke'],
                   c=df['risikoscore'], cmap='YlOrRd',
                   s=50, alpha=0.6)
        plt.colorbar(label='Risikoscore')
        plt.title('Snøfokkperioder over tid')
        plt.xlabel('Dato')
        plt.ylabel('Vindstyrke (m/s)')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('data/analyzed/snowdrift_timeline.png')
        plt.close()

        # Plot 2: Månedlig fordeling
        plt.figure(figsize=(12, 6))
        monthly_counts = df.groupby(df['dato'].dt.strftime('%Y-%m')).size()
        monthly_counts.plot(kind='bar')
        plt.title('Antall timer med snøfokk per måned')
        plt.xlabel('Måned')
        plt.ylabel('Antall timer')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('data/analyzed/snowdrift_monthly.png')
        plt.close()

        # Plot 3: Heatmap over timer på døgnet
        plt.figure(figsize=(12, 6))
        df['time'] = pd.to_datetime(df['klokkeslett']).dt.hour
        df['måned'] = df['dato'].dt.strftime('%m')
        heatmap_data = pd.crosstab(df['time'], df['måned'])
        sns.heatmap(heatmap_data, cmap='YlOrRd',
                   cbar_kws={'label': 'Antall tilfeller'})
        plt.title('Fordeling av snøfokk over døgnet og måneder')
        plt.xlabel('Måned')
        plt.ylabel('Time på døgnet')
        plt.tight_layout()
        plt.savefig('data/analyzed/snowdrift_heatmap.png')
        plt.close()

        logger.info("Genererte visualiseringer av snøfokkperioder")

    except Exception as e:
        logger.error(f"En feil oppstod under plotting: {str(e)}")

if __name__ == '__main__':
    plot_snowdrift_timeline()
