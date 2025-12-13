"""
Avanserte chart-komponenter for værdata-utforskning
"""
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.config import settings


class AdvancedCharts:
    """Avanserte chart-komponenter for værutforskning"""

    @staticmethod
    def create_multi_weather_chart(df: pd.DataFrame, selected_metrics: list[str]) -> go.Figure:
        """Lag multi-panel værdata chart"""

        if df.empty:
            fig = go.Figure()
            fig.add_annotation(text="Ingen data tilgjengelig",
                             xref="paper", yref="paper", x=0.5, y=0.5)
            return fig

        # Definer tilgjengelige metrics
        available_metrics = {
            'Temperatur': ['air_temperature', 'surface_temperature'],
            'Vind': ['wind_speed', 'max(wind_speed_of_gust PT1H)'],
            'Snø': ['snow_depth_cm', 'new_snow_cm'],
            'Nedbør': ['sum(precipitation_amount PT1H)', 'accumulated(precipitation_amount)'],
            'Fuktighet': ['relative_humidity', 'dew_point_temperature'],
            'Snøtype': ['snow_type']
        }

        # Filtrer valgte metrics som faktisk eksisterer
        valid_metrics = []
        for metric in selected_metrics:
            if metric in available_metrics:
                metric_cols = available_metrics[metric]
                if any(col in df.columns for col in metric_cols):
                    valid_metrics.append(metric)

        if not valid_metrics:
            fig = go.Figure()
            fig.add_annotation(text="Ingen gyldige metrics valgt",
                             xref="paper", yref="paper", x=0.5, y=0.5)
            return fig

        # Lag subplot
        num_plots = len(valid_metrics)
        fig = make_subplots(
            rows=num_plots,
            cols=1,
            subplot_titles=valid_metrics,
            shared_xaxes=True,
            vertical_spacing=0.08
        )

        colors = px.colors.qualitative.Set1

        for i, metric in enumerate(valid_metrics, 1):
            metric_cols = available_metrics[metric]

            for j, col in enumerate(metric_cols):
                if col in df.columns and not df[col].isna().all():

                    if col == 'snow_type':
                        # Spesiell håndtering for kategorisk data
                        AdvancedCharts._add_categorical_trace(fig, df, col, i, colors[j % len(colors)])
                    elif 'new_snow' in col:
                        # Bar chart for nysnø
                        fig.add_trace(
                            go.Bar(
                                x=df['time'],
                                y=df[col],
                                name=col.replace('_', ' ').title(),
                                marker_color=colors[j % len(colors)],
                                opacity=0.7
                            ),
                            row=i, col=1
                        )
                    else:
                        # Line chart for kontinuerlige data
                        fig.add_trace(
                            go.Scatter(
                                x=df['time'],
                                y=df[col],
                                mode='lines',
                                name=col.replace('_', ' ').title(),
                                line={"color": colors[j % len(colors)], "width": 2}
                            ),
                            row=i, col=1
                        )

        # Oppdater layout for mobile
        fig.update_layout(
            height=200 * num_plots + 100,
            showlegend=True,
            title="Detaljert Væranalyse",
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1
            },
            margin={"l": 10, "r": 10, "t": 80, "b": 40}
        )

        # Oppdater x-akse
        fig.update_xaxes(
            title_text="Tid",
            row=num_plots, col=1
        )

        return fig

    @staticmethod
    def _add_categorical_trace(fig: go.Figure, df: pd.DataFrame, col: str, row: int, color: str):
        """Legg til kategorisk trace (snøtype)"""

        # Konverter kategorier til numeriske verdier
        category_map = {
            'ingen': 0,
            'tørr_pudder': 1,
            'tørr': 2,
            'våt': 3,
            'slaps': 4
        }

        df_cat = df[df[col] != 'ingen'].copy()
        if df_cat.empty:
            return

        df_cat['cat_numeric'] = df_cat[col].map(category_map)

        fig.add_trace(
            go.Scatter(
                x=df_cat['time'],
                y=df_cat['cat_numeric'],
                mode='markers',
                name='Snøtype',
                marker={
                    "color": color,
                    "size": 8,
                    "symbol": 'circle'
                },
                text=df_cat[col],
                hovertemplate='<b>%{text}</b><br>Tid: %{x}<extra></extra>'
            ),
            row=row, col=1
        )

    @staticmethod
    def create_snow_analysis_chart(df: pd.DataFrame, last_plowed: datetime | None = None) -> go.Figure:
        """Lag spesialisert snøanalyse-chart"""

        if df.empty:
            fig = go.Figure()
            fig.add_annotation(text="Ingen snødata tilgjengelig",
                             xref="paper", yref="paper", x=0.5, y=0.5)
            return fig

        fig = make_subplots(
            rows=3, cols=1,
            subplot_titles=['Snødybde & Nysnø', 'Temperatur & Snøtype', 'Vindforhold'],
            shared_xaxes=True,
            vertical_spacing=0.1,
            specs=[[{"secondary_y": True}], [{"secondary_y": True}], [{"secondary_y": False}]]
        )

        # Panel 1: Snødybde og nysnø
        if 'snow_depth_cm' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['time'],
                    y=df['snow_depth_cm'],
                    mode='lines',
                    name='Total snødybde',
                    line={"color": 'blue', "width": 2}
                ),
                row=1, col=1
            )

        if 'new_snow_cm' in df.columns:
            fig.add_trace(
                go.Bar(
                    x=df['time'],
                    y=df['new_snow_cm'],
                    name='Nysnø (cm/t)',
                    marker_color='lightblue',
                    opacity=0.6
                ),
                row=1, col=1
            )

        # Panel 2: Temperatur og snøtype
        if 'air_temperature' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['time'],
                    y=df['air_temperature'],
                    mode='lines',
                    name='Lufttemperatur',
                    line={"color": 'red', "width": 2}
                ),
                row=2, col=1
            )

        if 'surface_temperature' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['time'],
                    y=df['surface_temperature'],
                    mode='lines',
                    name='Overflatetemperatur',
                    line={"color": 'orange', "width": 1, "dash": 'dash'}
                ),
                row=2, col=1
            )

        # Frysepunkt referanselinje
        fig.add_hline(
            y=0, line_dash="dash", line_color="gray",
            annotation_text="Frysepunkt",
            row=2, col=1
        )

        # Panel 3: Vind
        if 'wind_speed' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['time'],
                    y=df['wind_speed'],
                    mode='lines',
                    name='Vindstyrke',
                    line={"color": 'green', "width": 2}
                ),
                row=3, col=1
            )

        if 'max(wind_speed_of_gust PT1H)' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['time'],
                    y=df['max(wind_speed_of_gust PT1H)'],
                    mode='lines',
                    name='Vindkast',
                    line={"color": 'darkgreen', "width": 1, "dash": 'dot'}
                ),
                row=3, col=1
            )

        # Snøfokk-terskel
        fig.add_hline(
            y=8, line_dash="dash", line_color="red",
            annotation_text="Snøfokk-terskel",
            row=3, col=1
        )

        # Markér sist brøytet
        if last_plowed:
            for i in range(1, 4):
                fig.add_vline(
                    x=last_plowed,
                    line_dash="solid",
                    line_color="purple",
                    line_width=2,
                    annotation_text="Sist brøytet" if i == 1 else "",
                    row=i, col=1
                )

        # Layout
        fig.update_layout(
            height=800,
            title="Komplett Snøanalyse",
            showlegend=True,
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1}
        )

        return fig

    @staticmethod
    def create_plowing_recommendation_chart(snow_analysis: dict, df: pd.DataFrame) -> go.Figure:
        """Lag chart med brøyteanbefalinger"""

        fig = go.Figure()

        if df.empty:
            fig.add_annotation(text="Ingen data for anbefalinger",
                             xref="paper", yref="paper", x=0.5, y=0.5)
            return fig

        # Terskler for brøyting
        wet_snow_threshold = settings.historical.plowing_threshold_wet_cm
        dry_snow_threshold = settings.historical.plowing_threshold_dry_cm

        # Finn akkumulert nysnø over tid
        if 'new_snow_cm' in df.columns:
            df_copy = df.copy()
            df_copy['cumulative_snow'] = df_copy['new_snow_cm'].cumsum()

            # Hovedlinje - akkumulert snø
            fig.add_trace(
                go.Scatter(
                    x=df_copy['time'],
                    y=df_copy['cumulative_snow'],
                    mode='lines+markers',
                    name='Akkumulert nysnø',
                    line={"color": 'blue', "width": 3},
                    marker={"size": 4}
                )
            )

            # Terskler
            fig.add_hline(
                y=wet_snow_threshold,
                line_dash="dash",
                line_color="orange",
                annotation_text=f"Våt snø terskel ({wet_snow_threshold}cm)"
            )

            fig.add_hline(
                y=dry_snow_threshold,
                line_dash="dash",
                line_color="red",
                annotation_text=f"Tørr snø terskel ({dry_snow_threshold}cm)"
            )

            # Kritisk zone
            max_snow = df_copy['cumulative_snow'].max()
            if max_snow > wet_snow_threshold:
                fig.add_hrect(
                    y0=wet_snow_threshold, y1=max(max_snow, dry_snow_threshold),
                    fillcolor="orange", opacity=0.2,
                    annotation_text="Vurder brøyting", annotation_position="top left"
                )

            if max_snow > dry_snow_threshold:
                fig.add_hrect(
                    y0=dry_snow_threshold, y1=max_snow,
                    fillcolor="red", opacity=0.2,
                    annotation_text="Brøyting anbefalt", annotation_position="top left"
                )

        # Layout
        fig.update_layout(
            title=f"Brøyteanbefalinger - {snow_analysis.get('recommendation', 'Ingen anbefaling')}",
            xaxis_title="Tid",
            yaxis_title="Akkumulert nysnø (cm)",
            height=400,
            showlegend=True
        )

        return fig

    @staticmethod
    def create_weather_summary_cards(df: pd.DataFrame, snow_analysis: dict) -> None:
        """Lag sammendrag-kort for værperioden"""

        th = settings.chart_risk_timeline

        if df.empty:
            st.warning("Ingen data for sammendrag")
            return

        # Beregn statistikk
        period_start = df['time'].min()
        period_end = df['time'].max()
        duration_hours = (period_end - period_start).total_seconds() / 3600

        # Temperatur-statistikk
        temp_col = 'air_temperature'
        temp_stats = {}
        if temp_col in df.columns:
            temp_stats = {
                'avg': df[temp_col].mean(),
                'min': df[temp_col].min(),
                'max': df[temp_col].max()
            }

        # Vind-statistikk
        wind_col = 'wind_speed'
        wind_stats = {}
        if wind_col in df.columns:
            wind_stats = {
                'avg': df[wind_col].mean(),
                'max': df[wind_col].max(),
                'strong_hours': (df[wind_col] > th.snowdrift_wind_low_ms).sum()
            }

        # Nedbør-statistikk
        precip_col = 'sum(precipitation_amount PT1H)'
        _ = precip_col  # bevarer kolonnenavn for evt. videre utvidelser

        # Vis kort i kolonner
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown("""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        border-radius: 10px; padding: 1rem; color: white; text-align: center;">
                <h4 style="margin: 0;">Periode</h4>
                <p style="margin: 0.5rem 0; font-size: 0.9rem;">
                    {:.1f} timer<br>
                    {} - {}
                </p>
            </div>
            """.format(
                duration_hours,
                period_start.strftime("%d.%m %H:%M"),
                period_end.strftime("%d.%m %H:%M")
            ), unsafe_allow_html=True)

        with col2:
            if temp_stats:
                st.markdown("""
                <div style="background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
                            border-radius: 10px; padding: 1rem; color: white; text-align: center;">
                    <h4 style="margin: 0;">Temperatur</h4>
                    <p style="margin: 0.5rem 0; font-size: 0.9rem;">
                        Snitt: {:.1f}°C<br>
                        Min/Max: {:.1f}°/{:.1f}°C
                    </p>
                </div>
                """.format(
                    temp_stats['avg'],
                    temp_stats['min'],
                    temp_stats['max']
                ), unsafe_allow_html=True)

        with col3:
            if wind_stats:
                st.markdown("""
                <div style="background: linear-gradient(135deg, #48cae4 0%, #023e8a 100%);
                            border-radius: 10px; padding: 1rem; color: white; text-align: center;">
                    <h4 style="margin: 0;">Vind</h4>
                    <p style="margin: 0.5rem 0; font-size: 0.9rem;">
                        Snitt: {:.1f} m/s<br>
                        Max: {:.1f} m/s ({} t sterk)
                    </p>
                </div>
                """.format(
                    wind_stats['avg'],
                    wind_stats['max'],
                    wind_stats['strong_hours']
                ), unsafe_allow_html=True)

        with col4:
            # Snø-sammendrag
            total_snow = snow_analysis.get('total_new_snow', 0)
            snow_type = snow_analysis.get('dominant_type', 'ukjent')
            plowing_needed = snow_analysis.get('plowing_needed', False)

            bg_color = "linear-gradient(135deg, #ff4757 0%, #c44569 100%)" if plowing_needed else "linear-gradient(135deg, #26de81 0%, #20bf6b 100%)"

            st.markdown("""
            <div style="background: {};
                        border-radius: 10px; padding: 1rem; color: white; text-align: center;">
                <h4 style="margin: 0;">Nysnø</h4>
                <p style="margin: 0.5rem 0; font-size: 0.9rem;">
                    {:.1f} cm {}<br>
                    {}
                </p>
            </div>
            """.format(
                bg_color,
                total_snow,
                snow_type.replace('_', ' '),
                "Brøyt nå!" if plowing_needed else "OK"
            ), unsafe_allow_html=True)

    @staticmethod
    def create_risk_timeline(df: pd.DataFrame) -> go.Figure:
        """Lag tidslinje med risiko-markører"""

        th = settings.chart_risk_timeline

        fig = go.Figure()

        if df.empty:
            fig.add_annotation(text="Ingen data for risiko-tidslinje",
                             xref="paper", yref="paper", x=0.5, y=0.5)
            return fig

        # Beregn risiko-score basert på værforhold
        df_risk = df.copy()

        # Snøfokk-risiko (0-3)
        snowdrift_risk = 0
        if 'wind_speed' in df.columns and 'air_temperature' in df.columns:
            wind_risk = (
                (df_risk['wind_speed'] > th.snowdrift_wind_low_ms).astype(int)
                + (df_risk['wind_speed'] > th.snowdrift_wind_high_ms).astype(int)
            )
            temp_risk = (
                (df_risk['air_temperature'] < th.snowdrift_temp_cold_c).astype(int)
                + (df_risk['air_temperature'] < th.snowdrift_temp_very_cold_c).astype(int)
            )
            snowdrift_risk = wind_risk + temp_risk

        # Glattføre-risiko (0-2)
        slippery_risk = 0
        if 'air_temperature' in df.columns:
            slippery_risk = (
                (df_risk['air_temperature'] >= th.slippery_temp_min_c) &
                (df_risk['air_temperature'] <= th.slippery_temp_max_c)
            ).astype(int)

            if 'relative_humidity' in df.columns:
                slippery_risk += (df_risk['relative_humidity'] > th.slippery_humidity_high_pct).astype(int)

        # Kombinert risiko
        total_risk = snowdrift_risk + slippery_risk

        # Fargekoding
        colors = []
        for risk in total_risk:
            if risk >= th.risk_red_min:
                colors.append('red')
            elif risk >= th.risk_orange_min:
                colors.append('orange')
            elif risk >= th.risk_yellow_min:
                colors.append('yellow')
            else:
                colors.append('green')

        # Scatter plot med risiko-farger
        fig.add_trace(
            go.Scatter(
                x=df_risk['time'],
                y=total_risk,
                mode='markers',
                marker={
                    "color": colors,
                    "size": 8,
                    "line": {"width": 1, "color": 'black'}
                },
                name='Risiko-nivå',
                hovertemplate='<b>Risiko: %{y}</b><br>Tid: %{x}<extra></extra>'
            )
        )

        # Risiko-soner
        fig.add_hrect(y0=0, y1=th.band_green_max, fillcolor="green", opacity=0.1, annotation_text="Lav risiko")
        fig.add_hrect(y0=th.band_green_max, y1=th.band_yellow_max, fillcolor="yellow", opacity=0.1, annotation_text="Moderat risiko")
        fig.add_hrect(y0=th.band_yellow_max, y1=th.band_orange_max, fillcolor="orange", opacity=0.1, annotation_text="Høy risiko")
        fig.add_hrect(y0=th.band_orange_max, y1=th.band_red_max, fillcolor="red", opacity=0.1, annotation_text="Kritisk risiko")

        fig.update_layout(
            title="Risiko-tidslinje (Snøfokk + Glattføre)",
            xaxis_title="Tid",
            yaxis_title="Risiko-score",
            height=th.chart_height_px,
            yaxis={"range": [0, th.yaxis_max]}
        )

        return fig
