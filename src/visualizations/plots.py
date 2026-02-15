"""
Værdata-visualiseringer.

Modulære plotting-funksjoner for Streamlit-appen.
"""

import warnings
from datetime import datetime

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

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
        df_prepared, times = cls._prepare_time_series(df)
        if df_prepared is None or df_prepared.empty:
            return cls._empty_figure("Ingen data tilgjengelig")

        fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
        fig.suptitle(title, fontsize=14, fontweight='bold')

        viz = settings.viz

        # 1. Temperatur
        cls._plot_temperature(axes[0], times, df_prepared, viz)

        # 2. Vind
        cls._plot_wind(axes[1], times, df_prepared, viz)

        # 3. Snødybde + nedbør
        cls._plot_snow_precip(axes[2], times, df_prepared, viz)

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
        df_prepared, times = cls._prepare_time_series(df)
        if df_prepared is None or df_prepared.empty:
            return cls._empty_figure("Ingen data tilgjengelig")

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5), sharex=True)
        fig.suptitle(title, fontsize=12, fontweight='bold')

        viz = settings.viz

        # Temperatur + vind
        cls._plot_temp_wind_combined(ax1, times, df_prepared, viz)

        # Snø + nedbør
        cls._plot_snow_precip(ax2, times, df_prepared, viz)

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
        df_prepared, times = cls._prepare_time_series(df)
        if df_prepared is None or df_prepared.empty:
            return cls._empty_figure("Ingen data tilgjengelig")

        fig, ax = plt.subplots(figsize=(12, 4))
        fig.suptitle(title, fontsize=13, fontweight='bold')

        viz = settings.viz

        cls._plot_snow_precip(ax, times, df_prepared, viz)
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
        df_prepared, times = cls._prepare_time_series(df)
        if df_prepared is None or df_prepared.empty:
            return cls._empty_figure("Ingen data tilgjengelig")

        fig, ax = plt.subplots(figsize=(6, 4))
        fig.suptitle(title, fontsize=12, fontweight='bold')

        viz = settings.viz
        cls._plot_snow_only(ax, times, df_prepared, viz)
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
        df_prepared, times = cls._prepare_time_series(df)
        if df_prepared is None or df_prepared.empty:
            return cls._empty_figure("Ingen data tilgjengelig")

        fig, ax = plt.subplots(figsize=(6, 4))
        fig.suptitle(title, fontsize=12, fontweight='bold')

        viz = settings.viz
        cls._plot_precip_only(ax, times, df_prepared, viz)
        cls._format_time_axis(ax)
        cls._safe_layout(fig)
        return fig

    @classmethod
    def create_temperature_plot(
        cls,
        df: pd.DataFrame,
        title: str = "Temperatur"
    ) -> plt.Figure:
        df_prepared, times = cls._prepare_time_series(df)
        if df_prepared is None or df_prepared.empty:
            return cls._empty_figure("Ingen data tilgjengelig")

        fig, ax = plt.subplots(figsize=(6, 4))
        fig.suptitle(title, fontsize=12, fontweight='bold')
        viz = settings.viz
        cls._plot_temperature(ax, times, df_prepared, viz)
        cls._format_time_axis(ax)
        cls._safe_layout(fig)
        return fig

    @classmethod
    def create_wind_plot(
        cls,
        df: pd.DataFrame,
        title: str = "Vind"
    ) -> plt.Figure:
        df_prepared, times = cls._prepare_time_series(df)
        if df_prepared is None or df_prepared.empty:
            return cls._empty_figure("Ingen data tilgjengelig")

        fig, ax = plt.subplots(figsize=(6, 4))
        fig.suptitle(title, fontsize=12, fontweight='bold')
        viz = settings.viz
        cls._plot_wind(ax, times, df_prepared, viz)
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
        df_prepared, times = cls._prepare_time_series(df)
        if df_prepared is None or df_prepared.empty:
            return cls._empty_figure("Ingen data tilgjengelig")

        fig, ax = plt.subplots(figsize=(6, 4))
        fig.suptitle(title, fontsize=12, fontweight='bold')
        viz = settings.viz
        cls._plot_wind_direction(ax, times, df_prepared, viz)
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
        df_prepared, times = cls._prepare_time_series(df)
        if df_prepared is None or df_prepared.empty:
            return cls._empty_figure("Ingen data tilgjengelig")

        fig, ax = plt.subplots(figsize=(6, 4))
        fig.suptitle(title, fontsize=12, fontweight='bold')
        viz = settings.viz
        cls._plot_accumulated_precip(ax, times, df_prepared, viz)
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
        df_prepared, times = cls._prepare_time_series(df)
        if df_prepared is None or df_prepared.empty:
            return cls._empty_figure("Ingen data tilgjengelig")

        from src.analyzers.base import BaseAnalyzer

        fig, ax = plt.subplots(figsize=(10, 4))

        if 'air_temperature' not in df_prepared.columns or 'wind_speed' not in df_prepared.columns:
            return cls._empty_figure("Mangler temperatur- eller vinddata")

        temp = pd.to_numeric(df_prepared['air_temperature'], errors='coerce')
        wind = pd.to_numeric(df_prepared['wind_speed'], errors='coerce')

        # Beregn vindkjøling
        wind_chill: list[float] = []
        for t, w in zip(temp.tolist(), wind.tolist(), strict=False):
            if t is None or w is None or (isinstance(t, float) and np.isnan(t)) or (isinstance(w, float) and np.isnan(w)):
                wind_chill.append(np.nan)
            else:
                wind_chill.append(float(BaseAnalyzer.calculate_wind_chill(t, w)))

        ax.plot(times, temp, color=settings.viz.color_temp,
                linewidth=2, label='Lufttemperatur', alpha=0.7)
        ax.plot(times, wind_chill, color=settings.viz.color_critical,
                linewidth=2, label='Vindkjøling', linestyle='--')

        # Terskler (fra config)
        ax.axhline(
            y=settings.snowdrift.wind_chill_warning,
            color=settings.viz.color_warning,
            linestyle=':',
            linewidth=1.2,
            alpha=0.8,
            label=f"Advarsel ({settings.snowdrift.wind_chill_warning:.0f}°C)",
        )
        ax.axhline(
            y=settings.snowdrift.wind_chill_critical,
            color=settings.viz.color_critical,
            linestyle='--',
            linewidth=1.6,
            alpha=0.85,
            label=f"Kritisk ({settings.snowdrift.wind_chill_critical:.0f}°C)",
        )
        ax.axhline(y=0, color='navy', linestyle='-', alpha=0.3)

        temp_arr = np.asarray(temp, dtype=float)
        wc_arr = np.asarray(wind_chill, dtype=float)
        finite_mask = np.isfinite(temp_arr) & np.isfinite(wc_arr)
        where_mask = finite_mask & (wc_arr < temp_arr)

        if np.any(where_mask):
            ax.fill_between(
                times,
                temp_arr,
                wc_arr,
                where=where_mask,
                alpha=0.2,
                color=settings.viz.color_critical,
                label='Vindkjøling-effekt'
            )

        invalid_mask = []
        for t, w in zip(temp_arr.tolist(), np.asarray(wind, dtype=float).tolist(), strict=False):
            if not np.isfinite(t) or not np.isfinite(w):
                invalid_mask.append(False)
            else:
                invalid_mask.append(
                    bool(
                        t >= settings.viz.wind_chill_valid_temp_max_c
                        or w < settings.viz.wind_chill_valid_wind_min_ms
                    )
                )
        if any(invalid_mask):
            y_min, y_max = ax.get_ylim()
            ax.fill_between(
                times,
                [y_min] * len(times),
                [y_max] * len(times),
                where=invalid_mask,
                color=settings.viz.color_invalid,
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
    def _prepare_time_series(cls, df: pd.DataFrame | None) -> tuple[pd.DataFrame | None, pd.Series | None]:
        """Returner (df, times) klargjort for plotting.

        - Sikrer at reference_time finnes og er datetime
        - Sorterer og filtrerer bort NaT
        - Konverterer tidsakse til lokal tid og stripper timezone (matplotlib-robust)
        """
        if df is None or df.empty:
            return None, None

        if 'reference_time' not in df.columns:
            return None, None

        df_prepared = df.copy()
        times = pd.to_datetime(df_prepared['reference_time'], errors='coerce', utc=True)
        mask = times.notna()
        df_prepared = df_prepared.loc[mask].copy()
        times = times.loc[mask]

        if df_prepared.empty:
            return None, None

        # Lokal tid for visning (og for å unngå tz-aware problemer i matplotlib)
        try:
            local_tz = datetime.now().astimezone().tzinfo
            if local_tz is not None:
                times = times.dt.tz_convert(local_tz)
        except (TypeError, ValueError, AttributeError):
            # Behold UTC hvis lokal konvertering feiler
            pass

        # Strip timezone (matplotlib er mest stabil på naive datetimes)
        try:
            times = times.dt.tz_localize(None)
        except (TypeError, ValueError, AttributeError):
            pass

        df_prepared['reference_time'] = times
        df_prepared = df_prepared.sort_values('reference_time').reset_index(drop=True)

        return df_prepared, df_prepared['reference_time']

    @classmethod
    def _plot_temperature(cls, ax, times, df, viz):
        """Plot temperatur med bakketemperatur og duggpunkt."""
        if 'air_temperature' in df.columns:
            temp = cls._numeric(df, 'air_temperature').ffill()
            ax.plot(times, temp, color=viz.color_temp,
                   linewidth=2, label='Lufttemperatur')

        # Bakketemperatur - kritisk for isdannelse
        if 'surface_temperature' in df.columns:
            surface_temp = cls._numeric(df, 'surface_temperature').ffill()
            ax.plot(times, surface_temp, color='#1E88E5',
                    linewidth=2, linestyle='-', label='Bakketemperatur')
            # Marker frysefare: luft > 0, bakke < 0
            if 'air_temperature' in df.columns:
                temp = cls._numeric(df, 'air_temperature').ffill()
                freeze_point = settings.slippery.surface_temp_freeze
                freeze_risk = (temp > freeze_point) & (surface_temp < freeze_point)
                if freeze_risk.any():
                    ax.fill_between(times, temp, surface_temp,
                                   where=freeze_risk, alpha=0.3,
                                   color='#E53935', label='Skjult frysefare')

        # Duggpunkt - kritisk for snø vs regn
        if 'dew_point_temperature' in df.columns:
            dew_point = cls._numeric(df, 'dew_point_temperature').ffill()
            ax.plot(times, dew_point, color='#7E57C2',
                    linewidth=1.5, linestyle='--', label='Duggpunkt')

        # Frysepunkt-linje
        ax.axhline(y=settings.slippery.surface_temp_freeze, color='navy', linestyle='-', alpha=0.4, linewidth=1)

        ax.set_ylabel('°C')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)

    @classmethod
    def _plot_wind(cls, ax, times, df, viz):
        """Plot vindstyrke."""
        thresholds = settings.snowdrift

        if 'wind_speed' in df.columns:
            wind = cls._numeric(df, 'wind_speed').ffill()
            ax.plot(times, wind, color=viz.color_wind,
                    linewidth=2, label='Vind')

            # Marker terskler for snittvind
            ax.axhline(
                thresholds.wind_speed_warning,
                color=viz.color_warning,
                linestyle=':',
                linewidth=1,
                alpha=0.7,
                label=f"Vind {thresholds.wind_speed_warning:.0f} m/s (advarsel)",
            )
            ax.axhline(
                thresholds.wind_speed_critical,
                color=viz.color_critical,
                linestyle='--',
                linewidth=1,
                alpha=0.7,
                label=f"Vind {thresholds.wind_speed_critical:.0f} m/s (kritisk)",
            )

            # Vindkast hvis tilgjengelig
            gust_col = 'max_wind_gust' if 'max_wind_gust' in df.columns else 'wind_gust'
            if gust_col in df.columns:
                gust = cls._numeric(df, gust_col).ffill()
                ax.plot(times, gust, color=viz.color_wind,
                        linewidth=1, alpha=0.6, linestyle='--', label='Vindkast')

                high_gust = gust >= thresholds.wind_gust_warning
                if high_gust.any():
                    ax.fill_between(
                        times,
                        0,
                        gust,
                        where=high_gust,
                        color=viz.color_warning,
                        alpha=0.12,
                        label=f"Vindkast over {thresholds.wind_gust_warning:.0f} m/s",
                    )

                ax.axhline(
                    thresholds.wind_gust_warning,
                    color=viz.color_warning,
                    linestyle=':',
                    linewidth=1,
                    alpha=0.6,
                    label=f"Vindkast {thresholds.wind_gust_warning:.0f} m/s (advarsel)",
                )
                ax.axhline(
                    thresholds.wind_gust_critical,
                    color=viz.color_critical,
                    linestyle='--',
                    linewidth=1,
                    alpha=0.6,
                    label=f"Vindkast {thresholds.wind_gust_critical:.0f} m/s (kritisk)",
                )

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
            snow = cls._numeric(df, 'surface_snow_thickness').ffill()
            ax.fill_between(times, 0, snow, color=viz.color_snow,
                           alpha=0.3, label='Snødybde')
            ax.plot(times, snow, color=viz.color_snow, linewidth=2)

            lookback = max(1, int(settings.fresh_snow.lookback_hours))
            snow_change_lookback = snow.diff(periods=lookback).fillna(0)
            significant = snow_change_lookback >= thresholds.snow_increase_warning
            critical = snow_change_lookback >= thresholds.snow_increase_critical
            if significant.any():
                ax.scatter(
                    times[significant],
                    snow[significant],
                    color=viz.color_warning,
                    marker='^',
                    s=40,
                    label=f"≥{thresholds.snow_increase_warning:.0f} cm ({lookback}t)",
                )
            if critical.any():
                ax.scatter(
                    times[critical],
                    snow[critical],
                    color=viz.color_critical,
                    marker='^',
                    s=80,
                    linewidth=1.5,
                    label=f"≥{thresholds.snow_increase_critical:.0f} cm ({lookback}t)",
                )


        ax.set_ylabel('Snødybde (cm)', color=viz.color_snow)
        ax.tick_params(axis='y', labelcolor=viz.color_snow)

        # Nedbør (høyre akse)
        if 'precipitation_1h' in df.columns:
            precip = cls._numeric(df, 'precipitation_1h').fillna(0)
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

        snow = cls._numeric(df, 'surface_snow_thickness').ffill()
        ax.fill_between(times, 0, snow, color=viz.color_snow,
                        alpha=0.3)
        ax.plot(times, snow, color=viz.color_snow, linewidth=2, label='Snødybde')

        # Beregn snøendring siste N timer (nysnø-indikator)
        ax2 = ax.twinx()
        lookback = max(1, int(settings.fresh_snow.lookback_hours))
        snow_change_lookback = snow.diff(periods=lookback).fillna(0)

        # Vis bare positive endringer (nysnø)
        new_snow = snow_change_lookback.clip(lower=0)
        ax2.bar(times, new_snow, width=0.02, alpha=0.6,
            color='#43A047', label=f'Nysnø ({lookback}t)')

        # Marker signifikant nysnø (terskel fra config)
        thresholds = settings.fresh_snow
        significant = new_snow >= thresholds.snow_increase_warning
        if significant.any():
            ax2.scatter(times[significant], new_snow[significant],
                       color=viz.color_warning, s=50, zorder=5, marker='v',
                       label=f"≥{thresholds.snow_increase_warning:.0f} cm ({lookback}t)")

        ax2.set_ylabel(f'Nysnø siste {lookback}t (cm)', color='#43A047')
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

        precip = cls._numeric(df, 'precipitation_1h').fillna(0)
        ax.bar(times, precip, width=0.03, alpha=0.6,
               color=viz.color_precip, label='Nedbør (mm/h)')

        # Vis akkumulert nedbør siste 12 timer for slaps-vurdering
        accum_window = max(1, int(settings.slaps.precipitation_accum_hours))
        precip_accum = precip.rolling(window=accum_window, min_periods=1).sum()
        ax2 = ax.twinx()
        ax2.plot(
            times,
            precip_accum,
            color=viz.color_warning,
            linewidth=1.8,
            label=f'Nedbør siste {accum_window}t',
        )
        ax2.axhline(
            settings.slaps.precipitation_12h_min,
            color=viz.color_warning,
            linestyle=':',
            linewidth=1,
            alpha=0.8,
            label=f"Slaps terskel ({settings.slaps.precipitation_12h_min:.0f} mm)",
        )
        ax2.axhline(
            settings.slaps.precipitation_12h_heavy,
            color=viz.color_critical,
            linestyle='--',
            linewidth=1,
            alpha=0.8,
            label=f"Kraftig nedbør ({settings.slaps.precipitation_12h_heavy:.0f} mm)",
        )
        ax2.set_ylabel(f'Nedbør {accum_window}t (mm)', color=viz.color_warning)
        ax2.tick_params(axis='y', labelcolor=viz.color_warning)

        ax.set_ylabel('Nedbør (mm/h)')
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)

    @classmethod
    def _plot_wind_direction(cls, ax, times, df, viz):
        """Plot vindretning med kritisk sektor markert (fra settings)."""
        if 'wind_from_direction' not in df.columns:
            ax.text(0.5, 0.5, 'Ingen vindretningsdata', ha='center', va='center', transform=ax.transAxes)
            return

        wind_dir = cls._numeric(df, 'wind_from_direction').ffill()

        # Plott vindretning
        ax.scatter(times, wind_dir, c=viz.color_wind, s=15, alpha=0.7, label='Vindretning')

        # Marker kritisk sektor (vindretning) - spesielt utsatt for snøfokk
        sd = settings.snowdrift
        ax.axhspan(
            sd.critical_wind_dir_min,
            sd.critical_wind_dir_max,
            alpha=0.2,
            color=viz.color_critical,
            label=f"Kritisk sektor ({sd.critical_wind_dir_min:.0f}–{sd.critical_wind_dir_max:.0f}°)",
        )

        # Horisontal linje for hovedretninger
        ax.axhline(y=0, color='gray', linestyle=':', alpha=0.5)
        ax.axhline(y=90, color='gray', linestyle=':', alpha=0.5)
        ax.axhline(y=180, color='gray', linestyle=':', alpha=0.5)
        ax.axhline(y=270, color='gray', linestyle=':', alpha=0.5)
        ax.axhline(y=360, color='gray', linestyle=':', alpha=0.5)

        # Y-akse labels
        ax.set_ylim(0, 360)
        ax.set_yticks([0, 45, 90, 135, 180, 225, 270, 315, 360])
        ax.set_yticklabels(['N', 'NØ', 'Ø', 'SØ', 'S', 'SV', 'V', 'NV', 'N'])

        ax.set_ylabel('Retning')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)

    @classmethod
    def _plot_accumulated_precip(cls, ax, times, df, viz):
        """Plot akkumulert nedbør over perioden."""
        if 'precipitation_1h' not in df.columns:
            ax.text(0.5, 0.5, 'Ingen nedbørsdata', ha='center', va='center', transform=ax.transAxes)
            return

        precip = cls._numeric(df, 'precipitation_1h').fillna(0)
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
            temp = cls._numeric(df, 'air_temperature').ffill()
            ax.plot(times, temp, color=viz.color_temp,
                   linewidth=2, label='Lufttemperatur')

        if 'dew_point_temperature' in df.columns:
            dew_point = cls._numeric(df, 'dew_point_temperature').ffill()
            ax.plot(times, dew_point, color='#7E57C2', linestyle='--',
                    linewidth=1.6, label='Duggpunkt')

        ax.set_ylabel('°C', color=viz.color_temp)
        ax.tick_params(axis='y', labelcolor=viz.color_temp)

        # Vind (høyre)
        if 'wind_speed' in df.columns:
            wind = cls._numeric(df, 'wind_speed').ffill()
            ax2.plot(times, wind, color=viz.color_wind,
                     linewidth=2, label='Vind')

        gust_col = 'max_wind_gust' if 'max_wind_gust' in df.columns else 'wind_gust'
        if gust_col in df.columns:
            gust = cls._numeric(df, gust_col).ffill()
            ax2.plot(times, gust, color=viz.color_wind,
                     linewidth=1.2, linestyle='--', alpha=0.7, label='Vindkast')

        ax2.set_ylabel('m/s', color=viz.color_wind)
        ax2.tick_params(axis='y', labelcolor=viz.color_wind)

        # Legend
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper right', fontsize=8)

        ax.grid(True, alpha=0.3)

    @staticmethod
    def _numeric(df: pd.DataFrame, col: str) -> pd.Series:
        """Returner kolonne som numerisk serie (float) uten å kaste."""
        return pd.to_numeric(df[col], errors='coerce')

    @classmethod
    def _format_time_axis(cls, ax):
        """Formater tidsakse."""
        locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
        ax.xaxis.set_major_locator(locator)

        x_min, x_max = ax.get_xlim()
        span_days = max(0.0, x_max - x_min)
        span_hours = span_days * 24

        if span_hours >= 72:
            formatter = mdates.DateFormatter('%d.%m')
        elif span_hours >= 24:
            formatter = mdates.DateFormatter('%d.%m %H')
        else:
            formatter = mdates.DateFormatter('%H:%M')

        ax.xaxis.set_major_formatter(formatter)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        ax.set_xlabel('Tid')

    @classmethod
    def _safe_layout(cls, fig):
        """Sikker layout-justering."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                fig.tight_layout()
            except (RuntimeError, ValueError):
                fig.subplots_adjust(bottom=0.15, top=0.92, hspace=0.3)

    @classmethod
    def _empty_figure(cls, message: str) -> plt.Figure:
        """Lag tom figur med melding."""
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.text(0.5, 0.5, message, ha='center', va='center',
               fontsize=14, color='gray', transform=ax.transAxes)
        ax.axis('off')
        return fig
