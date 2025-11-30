"""
Værdata-visualiseringer.

Modulære plotting-funksjoner for Streamlit-appen.
"""

import warnings

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
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
    def create_snow_precip_plot(
        cls,
        df: pd.DataFrame,
        title: str = "Snødybde og nedbør"
    ) -> plt.Figure:
        """Lag enkeltplot med snødybde og nedbør."""
        if df is None or df.empty:
            return cls._empty_figure("Ingen data tilgjengelig")

        fig, ax = plt.subplots(figsize=(12, 4))
        fig.suptitle(title, fontsize=13, fontweight='bold')

        times = df['reference_time']
        viz = settings.viz

        cls._plot_snow_precip(ax, times, df, viz)
        cls._format_time_axis(ax)
        cls._safe_layout(fig)

        return fig

    @classmethod
    def create_snow_depth_plot(
        cls,
        df: pd.DataFrame,
        title: str = "Snødybde"
    ) -> plt.Figure:
        """Lag enkel visualisering av snødybde."""
        if df is None or df.empty:
            return cls._empty_figure("Ingen data tilgjengelig")

        fig, ax = plt.subplots(figsize=(6, 4))
        fig.suptitle(title, fontsize=12, fontweight='bold')

        times = df['reference_time']
        viz = settings.viz
        cls._plot_snow_only(ax, times, df, viz)
        cls._format_time_axis(ax)
        cls._safe_layout(fig)
        return fig

    @classmethod
    def create_precip_plot(
        cls,
        df: pd.DataFrame,
        title: str = "Nedbør"
    ) -> plt.Figure:
        """Lag enkel visualisering av nedbør."""
        if df is None or df.empty:
            return cls._empty_figure("Ingen data tilgjengelig")

        fig, ax = plt.subplots(figsize=(6, 4))
        fig.suptitle(title, fontsize=12, fontweight='bold')

        times = df['reference_time']
        viz = settings.viz
        cls._plot_precip_only(ax, times, df, viz)
        cls._format_time_axis(ax)
        cls._safe_layout(fig)
        return fig

    @classmethod
    def create_temperature_plot(
        cls,
        df: pd.DataFrame,
        title: str = "Temperatur"
    ) -> plt.Figure:
        if df is None or df.empty:
            return cls._empty_figure("Ingen data tilgjengelig")

        fig, ax = plt.subplots(figsize=(6, 4))
        fig.suptitle(title, fontsize=12, fontweight='bold')
        times = df['reference_time']
        viz = settings.viz
        cls._plot_temperature(ax, times, df, viz)
        cls._format_time_axis(ax)
        cls._safe_layout(fig)
        return fig

    @classmethod
    def create_wind_plot(
        cls,
        df: pd.DataFrame,
        title: str = "Vind"
    ) -> plt.Figure:
        if df is None or df.empty:
            return cls._empty_figure("Ingen data tilgjengelig")

        fig, ax = plt.subplots(figsize=(6, 4))
        fig.suptitle(title, fontsize=12, fontweight='bold')
        times = df['reference_time']
        viz = settings.viz
        cls._plot_wind(ax, times, df, viz)
        cls._format_time_axis(ax)
        cls._safe_layout(fig)
        return fig

    @classmethod
    def create_wind_direction_plot(
        cls,
        df: pd.DataFrame,
        title: str = "Vindretning"
    ) -> plt.Figure:
        """Lag plot for vindretning med kritisk sektor markert."""
        if df is None or df.empty:
            return cls._empty_figure("Ingen data tilgjengelig")

        fig, ax = plt.subplots(figsize=(6, 4))
        fig.suptitle(title, fontsize=12, fontweight='bold')
        times = df['reference_time']
        viz = settings.viz
        cls._plot_wind_direction(ax, times, df, viz)
        cls._format_time_axis(ax)
        cls._safe_layout(fig)
        return fig

    @classmethod
    def create_accumulated_precip_plot(
        cls,
        df: pd.DataFrame,
        title: str = "Akkumulert nedbør"
    ) -> plt.Figure:
        """Lag plot for akkumulert nedbør."""
        if df is None or df.empty:
            return cls._empty_figure("Ingen data tilgjengelig")

        fig, ax = plt.subplots(figsize=(6, 4))
        fig.suptitle(title, fontsize=12, fontweight='bold')
        times = df['reference_time']
        viz = settings.viz
        cls._plot_accumulated_precip(ax, times, df, viz)
        cls._format_time_axis(ax)
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
            for t, w in zip(temp, wind, strict=False)
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
                        where=[wc < t for t, wc in zip(temp, wind_chill, strict=False)],
                        alpha=0.2, color=settings.viz.color_critical,
                        label='Vindkjøling-effekt')

        invalid_mask = [t >= 10 or w < 1.34 for t, w in zip(temp, wind, strict=False)]
        if any(invalid_mask):
            y_min, y_max = ax.get_ylim()
            ax.fill_between(
                times,
                [y_min] * len(times),
                [y_max] * len(times),
                where=invalid_mask,
                color='#B0BEC5',
                alpha=0.15,
                label='Ikke gyldig (mildvær/lite vind)'
            )
            ax.set_ylim(y_min, y_max)

        ax.set_ylabel('Temperatur (°C)')
        ax.set_title(title)
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3)

        cls._format_time_axis(ax)
        cls._safe_layout(fig)

        return fig

    @classmethod
    def _plot_temperature(cls, ax, times, df, viz):
        """Plot temperatur med bakketemperatur og duggpunkt."""
        if 'air_temperature' in df.columns:
            temp = df['air_temperature'].ffill()
            ax.plot(times, temp, color=viz.color_temp,
                   linewidth=2, label='Lufttemperatur')

        # Bakketemperatur - kritisk for isdannelse
        if 'surface_temperature' in df.columns:
            surface_temp = df['surface_temperature'].ffill()
            ax.plot(times, surface_temp, color='#1E88E5',
                    linewidth=2, linestyle='-', label='Bakketemperatur')
            # Marker frysefare: luft > 0, bakke < 0
            if 'air_temperature' in df.columns:
                temp = df['air_temperature'].ffill()
                freeze_risk = (temp > 0) & (surface_temp < 0)
                if freeze_risk.any():
                    ax.fill_between(times, temp, surface_temp,
                                   where=freeze_risk, alpha=0.3,
                                   color='#E53935', label='Skjult frysefare')

        # Duggpunkt - kritisk for snø vs regn
        if 'dew_point_temperature' in df.columns:
            dew_point = df['dew_point_temperature'].ffill()
            ax.plot(times, dew_point, color='#7E57C2',
                    linewidth=1.5, linestyle='--', label='Duggpunkt')

        # Frysepunkt-linje
        ax.axhline(y=0, color='navy', linestyle='-', alpha=0.4, linewidth=1)

        ax.set_ylabel('°C')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)

    @classmethod
    def _plot_wind(cls, ax, times, df, viz):
        """Plot vindstyrke."""
        thresholds = settings.snowdrift

        if 'wind_speed' in df.columns:
            wind = df['wind_speed'].ffill()
            ax.plot(times, wind, color=viz.color_wind,
                    linewidth=2, label='Vind')

            # Marker terskler for snittvind
            ax.axhline(thresholds.wind_speed_warning, color=viz.color_warning,
                       linestyle=':', linewidth=1, alpha=0.7, label='Vind 8 m/s (advarsel)')
            ax.axhline(thresholds.wind_speed_critical, color=viz.color_critical,
                       linestyle='--', linewidth=1, alpha=0.7, label='Vind 10 m/s (kritisk)')

            # Vindkast hvis tilgjengelig
            gust_col = 'max_wind_gust' if 'max_wind_gust' in df.columns else 'wind_gust'
            if gust_col in df.columns:
                gust = df[gust_col].ffill()
                ax.plot(times, gust, color=viz.color_wind,
                        linewidth=1, alpha=0.6, linestyle='--', label='Vindkast')

                ax.axhline(thresholds.wind_gust_warning, color='#EF6C00', linestyle=':',
                           linewidth=1, alpha=0.6, label='Vindkast 15 m/s (advarsel)')
                ax.axhline(thresholds.wind_gust_critical, color='#B71C1C', linestyle='--',
                           linewidth=1, alpha=0.6, label='Vindkast 22 m/s (kritisk)')

        ax.set_ylabel('m/s')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)

    @classmethod
    def _plot_snow_precip(cls, ax, times, df, viz):
        """Plot snødybde og nedbør."""
        ax2 = ax.twinx()

        # Snødybde (venstre akse)
        thresholds = settings.fresh_snow

        if 'surface_snow_thickness' in df.columns:
            snow = df['surface_snow_thickness'].ffill()
            ax.fill_between(times, 0, snow, color=viz.color_snow,
                           alpha=0.3, label='Snødybde')
            ax.plot(times, snow, color=viz.color_snow, linewidth=2)

            # Vis seks-timers snøøkning direkte i figuren
            snow_change_6h = snow.diff(periods=6)
            significant = snow_change_6h >= thresholds.snow_increase_warning
            critical = snow_change_6h >= thresholds.snow_increase_critical
            if significant.any():
                ax.scatter(times[significant], snow[significant],
                           color='#E65100', marker='^', s=40, label='≥5 cm (6t)')
            if critical.any():
                ax.scatter(times[critical], snow[critical],
                           color='#B71C1C', marker='^', s=80,
                           linewidth=1.5, label='≥10 cm (6t)')


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
    def _plot_snow_only(cls, ax, times, df, viz):
        if 'surface_snow_thickness' not in df.columns:
            ax.text(0.5, 0.5, 'Ingen snødata', ha='center', va='center', transform=ax.transAxes)
            return

        snow = df['surface_snow_thickness'].ffill()
        ax.fill_between(times, 0, snow, color=viz.color_snow,
                        alpha=0.3)
        ax.plot(times, snow, color=viz.color_snow, linewidth=2, label='Snødybde')

        # Beregn snøendring siste 6 timer (nysnø-indikator)
        ax2 = ax.twinx()
        snow_change_6h = snow.diff(periods=6).fillna(0)  # 6 timers endring

        # Vis bare positive endringer (nysnø)
        new_snow = snow_change_6h.clip(lower=0)
        ax2.bar(times, new_snow, width=0.02, alpha=0.6,
                color='#43A047', label='Nysnø (6t)')

        # Marker signifikant nysnø (≥5 cm)
        significant = new_snow >= 5
        if significant.any():
            ax2.scatter(times[significant], new_snow[significant],
                       color='#E53935', s=50, zorder=5, marker='v',
                       label='≥5 cm (brøyting)')

        ax2.set_ylabel('Nysnø siste 6t (cm)', color='#43A047')
        ax2.tick_params(axis='y', labelcolor='#43A047')
        ax2.set_ylim(bottom=0)

        # Kombinert legend
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper right', fontsize=8)

        ax.set_ylabel('Snødybde (cm)')
        ax.grid(True, alpha=0.3)

    @classmethod
    def _plot_precip_only(cls, ax, times, df, viz):
        if 'precipitation_1h' not in df.columns:
            ax.text(0.5, 0.5, 'Ingen nedbørsdata', ha='center', va='center', transform=ax.transAxes)
            return

        precip = df['precipitation_1h'].fillna(0)
        ax.bar(times, precip, width=0.03, alpha=0.6,
               color=viz.color_precip, label='Nedbør (mm/h)')


        ax.set_ylabel('Nedbør (mm/h)')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)

    @classmethod
    def _plot_wind_direction(cls, ax, times, df, viz):
        """Plot vindretning med kritisk sektor markert (SE-S 135-225°)."""
        if 'wind_from_direction' not in df.columns:
            ax.text(0.5, 0.5, 'Ingen vindretningsdata', ha='center', va='center', transform=ax.transAxes)
            return

        wind_dir = df['wind_from_direction'].ffill()

        # Plott vindretning
        ax.scatter(times, wind_dir, c=viz.color_wind, s=15, alpha=0.7, label='Vindretning')

        # Marker kritisk sektor (SE-S: 135-225°) - spesielt utsatt for snøfokk
        ax.axhspan(135, 225, alpha=0.2, color='#E53935', label='Kritisk sektor (SE-S)')

        # Horisontal linje for hovedretninger
        ax.axhline(y=0, color='gray', linestyle=':', alpha=0.5)
        ax.axhline(y=90, color='gray', linestyle=':', alpha=0.5)
        ax.axhline(y=180, color='gray', linestyle=':', alpha=0.5)
        ax.axhline(y=270, color='gray', linestyle=':', alpha=0.5)
        ax.axhline(y=360, color='gray', linestyle=':', alpha=0.5)

        # Y-akse labels
        ax.set_ylim(0, 360)
        ax.set_yticks([0, 45, 90, 135, 180, 225, 270, 315, 360])
        ax.set_yticklabels(['N', 'NE', 'Ø', 'SE', 'S', 'SW', 'V', 'NW', 'N'])

        ax.set_ylabel('Retning')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)

    @classmethod
    def _plot_accumulated_precip(cls, ax, times, df, viz):
        """Plot akkumulert nedbør over perioden."""
        if 'precipitation_1h' not in df.columns:
            ax.text(0.5, 0.5, 'Ingen nedbørsdata', ha='center', va='center', transform=ax.transAxes)
            return

        precip = df['precipitation_1h'].fillna(0)
        accumulated = precip.cumsum()

        # Akkumulert linje
        ax.fill_between(times, 0, accumulated, alpha=0.3, color=viz.color_precip)
        ax.plot(times, accumulated, color=viz.color_precip, linewidth=2, label='Akkumulert nedbør')

        # Vis total
        total = accumulated.iloc[-1] if len(accumulated) > 0 else 0
        ax.axhline(y=total, color=viz.color_precip, linestyle='--', alpha=0.5)
        ax.text(times.iloc[-1], total, f'  {total:.1f} mm', va='center', fontsize=9, color=viz.color_precip)

        ax.set_ylabel('Akkumulert (mm)')
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, alpha=0.3)

    @classmethod
    def _plot_temp_wind_combined(cls, ax, times, df, viz):
        """Plot temperatur og vind på samme akse."""
        ax2 = ax.twinx()

        # Temperatur (venstre)
        if 'air_temperature' in df.columns:
            temp = df['air_temperature'].ffill()
            ax.plot(times, temp, color=viz.color_temp,
                   linewidth=2, label='Lufttemperatur')

        if 'dew_point_temperature' in df.columns:
            dew_point = df['dew_point_temperature'].ffill()
            ax.plot(times, dew_point, color='#7E57C2', linestyle='--',
                    linewidth=1.6, label='Duggpunkt')

        ax.set_ylabel('°C', color=viz.color_temp)
        ax.tick_params(axis='y', labelcolor=viz.color_temp)

        # Vind (høyre)
        if 'wind_speed' in df.columns:
            wind = df['wind_speed'].ffill()
            ax2.plot(times, wind, color=viz.color_wind,
                     linewidth=2, label='Vind')

        gust_col = 'max_wind_gust' if 'max_wind_gust' in df.columns else 'wind_gust'
        if gust_col in df.columns:
            gust = df[gust_col].ffill()
            ax2.plot(times, gust, color=viz.color_wind,
                     linewidth=1.2, linestyle='--', alpha=0.7, label='Vindkast')


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
