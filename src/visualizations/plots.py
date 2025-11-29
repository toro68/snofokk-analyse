"""
Værdata-visualiseringer.

Modulære plotting-funksjoner for Streamlit-appen.
"""

import warnings
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

from src.config import settings


class WeatherPlots:
    """
    Håndterer alle visualiseringer.
    
    Alle metoder er klassemetoder for enkel bruk uten instansiering.
    """
    
    @classmethod
    def create_overview_plot(
        cls,
        df: pd.DataFrame,
        title: str = "Værdata - Gullingen"
    ) -> plt.Figure:
        """
        Lag oversiktsplot med temperatur, vind og snø.
        
        Args:
            df: DataFrame med værdata
            title: Tittel på plottet
            
        Returns:
            Matplotlib Figure
        """
        if df is None or df.empty:
            return cls._empty_figure("Ingen data tilgjengelig")
        
        fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
        fig.suptitle(title, fontsize=14, fontweight='bold')
        
        times = df['reference_time']
        viz = settings.viz
        
        # 1. Temperatur
        cls._plot_temperature(axes[0], times, df, viz)
        
        # 2. Vind
        cls._plot_wind(axes[1], times, df, viz)
        
        # 3. Snødybde + nedbør
        cls._plot_snow_precip(axes[2], times, df, viz)
        
        # Formatering
        cls._format_time_axis(axes[-1])
        cls._safe_layout(fig)
        
        return fig
    
    @classmethod
    def create_compact_plot(
        cls,
        df: pd.DataFrame,
        title: str = "Værforhold"
    ) -> plt.Figure:
        """
        Lag kompakt 2-panels plot for dashbord.
        
        Args:
            df: DataFrame med værdata
            title: Tittel på plottet
            
        Returns:
            Matplotlib Figure
        """
        if df is None or df.empty:
            return cls._empty_figure("Ingen data tilgjengelig")
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5), sharex=True)
        fig.suptitle(title, fontsize=12, fontweight='bold')
        
        times = df['reference_time']
        viz = settings.viz
        
        # Temperatur + vind
        cls._plot_temp_wind_combined(ax1, times, df, viz)
        
        # Snø + nedbør
        cls._plot_snow_precip(ax2, times, df, viz)
        
        cls._format_time_axis(ax2)
        cls._safe_layout(fig)
        
        return fig
    
    @classmethod
    def create_wind_chill_plot(
        cls,
        df: pd.DataFrame,
        title: str = "Vindkjøling"
    ) -> plt.Figure:
        """
        Lag plot som viser vindkjøling vs temperatur.
        
        Args:
            df: DataFrame med værdata
            title: Tittel
            
        Returns:
            Matplotlib Figure
        """
        if df is None or df.empty:
            return cls._empty_figure("Ingen data tilgjengelig")
        
        from src.analyzers.base import BaseAnalyzer
        
        fig, ax = plt.subplots(figsize=(10, 4))
        
        times = df['reference_time']
        temp = df['air_temperature']
        wind = df['wind_speed']
        
        # Beregn vindkjøling
        wind_chill = [
            BaseAnalyzer.calculate_wind_chill(t, w) 
            for t, w in zip(temp, wind)
        ]
        
        ax.plot(times, temp, color=settings.viz.color_temp, 
               linewidth=2, label='Lufttemperatur', alpha=0.7)
        ax.plot(times, wind_chill, color=settings.viz.color_critical,
               linewidth=2, label='Vindkjøling', linestyle='--')
        
        # Terskler
        ax.axhline(y=-12, color=settings.viz.color_warning, 
                  linestyle=':', alpha=0.7, label='Advarsel (-12°C)')
        ax.axhline(y=-15, color=settings.viz.color_critical,
                  linestyle=':', alpha=0.7, label='Kritisk (-15°C)')
        ax.axhline(y=0, color='navy', linestyle='-', alpha=0.3)
        
        ax.fill_between(times, temp, wind_chill, 
                       where=[wc < t for t, wc in zip(temp, wind_chill)],
                       alpha=0.2, color=settings.viz.color_critical,
                       label='Vindkjøling-effekt')
        
        ax.set_ylabel('Temperatur (°C)')
        ax.set_title(title)
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3)
        
        cls._format_time_axis(ax)
        cls._safe_layout(fig)
        
        return fig
    
    @classmethod
    def _plot_temperature(cls, ax, times, df, viz):
        """Plot temperatur."""
        if 'air_temperature' in df.columns:
            temp = df['air_temperature'].ffill()
            ax.plot(times, temp, color=viz.color_temp, 
                   linewidth=2, label='Temperatur')
            ax.axhline(y=0, color='navy', linestyle='--', 
                      alpha=0.5, label='Frysepunkt')
            ax.axhline(y=-5, color=viz.color_critical,
                      linestyle=':', alpha=0.4, label='Snøfokk-terskel')
        
        ax.set_ylabel('°C')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)
    
    @classmethod
    def _plot_wind(cls, ax, times, df, viz):
        """Plot vindstyrke."""
        if 'wind_speed' in df.columns:
            wind = df['wind_speed'].ffill()
            ax.plot(times, wind, color=viz.color_wind,
                   linewidth=2, label='Vind')
            
            # Vindkast hvis tilgjengelig
            if 'wind_gust' in df.columns:
                gust = df['wind_gust'].ffill()
                ax.plot(times, gust, color=viz.color_wind,
                       linewidth=1, alpha=0.5, linestyle='--', label='Vindkast')
            
            ax.axhline(y=8, color=viz.color_warning,
                      linestyle='--', alpha=0.5, label='Advarsel (8 m/s)')
            ax.axhline(y=10, color=viz.color_critical,
                      linestyle='--', alpha=0.5, label='Kritisk (10 m/s)')
        
        ax.set_ylabel('m/s')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)
    
    @classmethod
    def _plot_snow_precip(cls, ax, times, df, viz):
        """Plot snødybde og nedbør."""
        ax2 = ax.twinx()
        
        # Snødybde (venstre akse)
        if 'surface_snow_thickness' in df.columns:
            snow = df['surface_snow_thickness'].ffill()
            ax.fill_between(times, 0, snow, color=viz.color_snow,
                           alpha=0.3, label='Snødybde')
            ax.plot(times, snow, color=viz.color_snow, linewidth=2)
        
        ax.set_ylabel('Snødybde (cm)', color=viz.color_snow)
        ax.tick_params(axis='y', labelcolor=viz.color_snow)
        
        # Nedbør (høyre akse)
        if 'precipitation_1h' in df.columns:
            precip = df['precipitation_1h'].fillna(0)
            ax2.bar(times, precip, width=0.03, alpha=0.6,
                   color=viz.color_precip, label='Nedbør')
        
        ax2.set_ylabel('Nedbør (mm/h)', color=viz.color_precip)
        ax2.tick_params(axis='y', labelcolor=viz.color_precip)
        
        # Kombinert legend
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper right', fontsize=8)
        
        ax.grid(True, alpha=0.3)
    
    @classmethod
    def _plot_temp_wind_combined(cls, ax, times, df, viz):
        """Plot temperatur og vind på samme akse."""
        ax2 = ax.twinx()
        
        # Temperatur (venstre)
        if 'air_temperature' in df.columns:
            temp = df['air_temperature'].ffill()
            ax.plot(times, temp, color=viz.color_temp,
                   linewidth=2, label='Temp')
            ax.axhline(y=0, color='navy', linestyle='--', alpha=0.3)
        
        ax.set_ylabel('°C', color=viz.color_temp)
        ax.tick_params(axis='y', labelcolor=viz.color_temp)
        
        # Vind (høyre)
        if 'wind_speed' in df.columns:
            wind = df['wind_speed'].ffill()
            ax2.plot(times, wind, color=viz.color_wind,
                    linewidth=2, label='Vind')
        
        ax2.set_ylabel('m/s', color=viz.color_wind)
        ax2.tick_params(axis='y', labelcolor=viz.color_wind)
        
        # Legend
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper right', fontsize=8)
        
        ax.grid(True, alpha=0.3)
    
    @classmethod
    def _format_time_axis(cls, ax):
        """Formater tidsakse."""
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m %H:%M'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        ax.set_xlabel('Tid')
    
    @classmethod
    def _safe_layout(cls, fig):
        """Sikker layout-justering."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                plt.tight_layout()
            except Exception:
                plt.subplots_adjust(bottom=0.15, top=0.92, hspace=0.3)
    
    @classmethod
    def _empty_figure(cls, message: str) -> plt.Figure:
        """Lag tom figur med melding."""
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.text(0.5, 0.5, message, ha='center', va='center',
               fontsize=14, color='gray', transform=ax.transAxes)
        ax.axis('off')
        return fig
