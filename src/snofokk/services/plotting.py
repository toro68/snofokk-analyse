"""
Plotting service for creating weather visualizations
"""
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import AutoMinorLocator
from pathlib import Path
from typing import List, Optional, Tuple
import logging

from ..models import WeatherData, SnowAnalysis
from ..config import settings

logger = logging.getLogger(__name__)

class PlottingService:
    """Service for creating weather plots and visualizations"""
    
    def __init__(self):
        # Set matplotlib style
        plt.style.use('default')
        plt.rcParams['figure.figsize'] = (12, 10)
        plt.rcParams['font.size'] = 10
    
    def create_weather_plot(
        self,
        df: WeatherData,
        snow_analyses: List[SnowAnalysis],
        target_file: Optional[Path] = None
    ) -> Tuple[bool, Optional[str]]:
        """Create comprehensive weather plot"""
        
        try:
            fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
            
            # Temperature plot
            self._plot_temperature(axes[0], df)
            
            # Wind plot  
            self._plot_wind(axes[1], df)
            
            # Snow depth and risk plot
            self._plot_snow_and_risk(axes[2], df)
            
            # Format time axis
            self._format_time_axis(axes)
            
            # Add title
            if 'referenceTime' in df.columns and not df.empty:
                start_time = df['referenceTime'].min()
                end_time = df['referenceTime'].max()
                fig.suptitle(
                    f'Værrapport: {start_time.strftime("%d.%m.%Y")} - {end_time.strftime("%d.%m.%Y")}',
                    fontsize=14,
                    fontweight='bold'
                )
            
            plt.tight_layout()
            
            # Save to file if specified
            if target_file:
                target_file.parent.mkdir(parents=True, exist_ok=True)
                plt.savefig(target_file, dpi=150, bbox_inches='tight')
                logger.info(f"Plot saved to {target_file}")
            
            # Convert to base64 string for web use (optional)
            import io
            import base64
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
            
            plt.close(fig)
            return True, img_base64
            
        except Exception as e:
            logger.error(f"Error creating weather plot: {e}")
            plt.close('all')
            return False, None
    
    def _plot_temperature(self, ax, df: WeatherData):
        """Plot temperature data"""
        if 'air_temperature' not in df.columns or df.empty:
            ax.text(0.5, 0.5, 'Ingen temperaturdata', ha='center', va='center', transform=ax.transAxes)
            ax.set_ylabel('Temperatur (°C)')
            return
        
        # Use referenceTime if available, otherwise use index
        if 'referenceTime' in df.columns:
            time_data = df['referenceTime']
        else:
            time_data = df.index
        
        # Filter out NaN values
        temp_data = df['air_temperature'].dropna()
        if temp_data.empty:
            ax.text(0.5, 0.5, 'Ingen gyldig temperaturdata', ha='center', va='center', transform=ax.transAxes)
            ax.set_ylabel('Temperatur (°C)')
            return
        
        # Align time data with temperature data
        time_aligned = time_data.loc[temp_data.index] if 'referenceTime' in df.columns else temp_data.index
        
        ax.plot(time_aligned, temp_data, 'r-', linewidth=1.5, label='Temperatur')
        
        # Add min/max if available
        if 'min(air_temperature PT1H)' in df.columns:
            min_temp_data = df['min(air_temperature PT1H)'].dropna()
            if not min_temp_data.empty:
                time_min_aligned = time_data.loc[min_temp_data.index] if 'referenceTime' in df.columns else min_temp_data.index
                ax.plot(time_min_aligned, min_temp_data, 'b--', alpha=0.7, label='Min temp')
                
        if 'max(air_temperature PT1H)' in df.columns:
            max_temp_data = df['max(air_temperature PT1H)'].dropna()
            if not max_temp_data.empty:
                time_max_aligned = time_data.loc[max_temp_data.index] if 'referenceTime' in df.columns else max_temp_data.index
                ax.plot(time_max_aligned, max_temp_data, 'orange', alpha=0.7, label='Max temp')
        
        # Add freezing line
        ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5, label='Frysepunkt')
        
        ax.set_ylabel('Temperatur (°C)')
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    def _plot_wind(self, ax, df: WeatherData):
        """Plot wind data"""
        if 'wind_speed' not in df.columns or df.empty:
            ax.text(0.5, 0.5, 'Ingen vinddata', ha='center', va='center', transform=ax.transAxes)
            ax.set_ylabel('Vindstyrke (m/s)')
            return
        
        # Use referenceTime if available, otherwise use index
        if 'referenceTime' in df.columns:
            time_data = df['referenceTime']
        else:
            time_data = df.index
        
        # Filter out NaN values
        wind_data = df['wind_speed'].dropna()
        if wind_data.empty:
            ax.text(0.5, 0.5, 'Ingen gyldig vinddata', ha='center', va='center', transform=ax.transAxes)
            ax.set_ylabel('Vindstyrke (m/s)')
            return
        
        # Align time data with wind data
        time_aligned = time_data.loc[wind_data.index] if 'referenceTime' in df.columns else wind_data.index
        
        ax.plot(time_aligned, wind_data, 'b-', linewidth=1.5, label='Vindstyrke')
        
        # Add max wind if available
        if 'max(wind_speed PT1H)' in df.columns:
            max_wind_data = df['max(wind_speed PT1H)'].dropna()
            if not max_wind_data.empty:
                time_max_aligned = time_data.loc[max_wind_data.index] if 'referenceTime' in df.columns else max_wind_data.index
                ax.plot(time_max_aligned, max_wind_data, 'navy', alpha=0.7, label='Max vind')
        
        # Add risk threshold line
        ax.axhline(y=settings.wind_impact_threshold, color='orange', linestyle='--', alpha=0.7, label='Risikogrense')
        
        ax.set_ylabel('Vindstyrke (m/s)')
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    def _plot_snow_and_risk(self, ax, df: WeatherData):
        """Plot snow depth and risk score"""
        # Use referenceTime if available, otherwise use index  
        if 'referenceTime' in df.columns:
            time_data = df['referenceTime']
        else:
            time_data = df.index
        
        # Snow depth
        if 'surface_snow_thickness' in df.columns:
            snow_data = df['surface_snow_thickness'].dropna()
            if not snow_data.empty:
                time_aligned = time_data.loc[snow_data.index] if 'referenceTime' in df.columns else snow_data.index
                ax.plot(time_aligned, snow_data, 'g-', linewidth=1.5, label='Snødybde')
                ax.set_ylabel('Snødybde (cm)')
            else:
                ax.text(0.5, 0.5, 'Ingen gyldig snødata', ha='center', va='center', transform=ax.transAxes)
                ax.set_ylabel('Snødybde (cm)')
        else:
            ax.text(0.5, 0.5, 'Ingen snødata', ha='center', va='center', transform=ax.transAxes)
            ax.set_ylabel('Snødybde (cm)')
        
        # Risk score on secondary y-axis
        if 'risk_score' in df.columns:
            risk_data = df['risk_score'].dropna()
            if not risk_data.empty:
                ax2 = ax.twinx()
                time_risk_aligned = time_data.loc[risk_data.index] if 'referenceTime' in df.columns else risk_data.index
                ax2.fill_between(time_risk_aligned, risk_data, alpha=0.3, color='red', label='Risikoscore')
                ax2.set_ylabel('Risikoscore')
                ax2.set_ylim(0, 1)
                ax2.legend(loc='upper right')
        
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)
    
    def _format_time_axis(self, axes):
        """Format time axis for all subplots"""
        for ax in axes:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m %H:%M'))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=6))
            ax.xaxis.set_minor_locator(mdates.HourLocator(interval=2))
        
        plt.xticks(rotation=45)

# Global plotting service instance
plotting_service = PlottingService()
