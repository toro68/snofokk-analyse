#!/usr/bin/env python3
"""
Avansert mobil weather app med historisk analyse og brøyting-tracking
STEG 2: Nysnø-mengde, historisk analyse, brøyting-tracking
"""

import os
import warnings
from datetime import datetime, timedelta
from typing import Optional, List

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Import komponenter
from components.mobile_layout import MobileLayout
from components.weather_utils import validate_weather_data
from components.historical_service import HistoricalWeatherService
from components.advanced_charts import AdvancedCharts

# Konfigurer advarsler
warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')

# Last miljøvariabler
load_dotenv()


class AdvancedMobileWeatherApp:
    """Avansert mobil værapp med historisk analyse"""
    
    def __init__(self):
        self.frost_client_id = os.getenv('FROST_CLIENT_ID')
        self.station_id = os.getenv("WEATHER_STATION", "SN46220")
        
        # Initialiser services
        if self.frost_client_id:
            self.historical_service = HistoricalWeatherService(
                self.frost_client_id, 
                self.station_id
            )
        else:
            self.historical_service = None

    def run_advanced_app(self):
        """Kjør avansert mobile app"""
        
        # Konfigurer mobil layout
        MobileLayout.configure_mobile_page()
        
        # Header med advanced features
        st.markdown("""
        <div style="text-align: center; margin-bottom: 1rem;">
            <h1 style="margin: 0; color: #2d3436;">❄️ Gullingen Væranalyse</h1>
            <p style="margin: 0; color: #636e72; font-size: 0.9rem;">
                Historisk analyse • Nysnø-tracking • Brøyting-optimalisering
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Sjekk API-tilgang
        if not self.frost_client_id:
            st.error("⚠️ FROST_CLIENT_ID mangler i .env-filen")
            st.info("Demo-modus: Bruker forhåndslagrede februar-data")
            
            # Vis februar-data som demo
            self._show_demo_mode()
            return
        
        # Hovedfunksjonalitet
        self._show_main_interface()

    def _show_demo_mode(self):
        """Vis demo med februar-data"""
        st.markdown("### 📊 Demo: Februar 2024 værdata")
        
        if self.historical_service:
            # Last februar-data
            df = self.historical_service.load_february_data()
            
            if not df.empty:
                # Beregn nysnø
                df = self.historical_service.calculate_new_snow(df)
                
                # Vis data-periode
                st.info(f"**Periode:** {df['time'].min().strftime('%d.%m.%Y')} - {df['time'].max().strftime('%d.%m.%Y')} ({len(df)} målinger)")
                
                # Demo brøyting (3. februar)
                demo_plowing = datetime(2024, 2, 3, 8, 0)
                snow_analysis = self.historical_service.calculate_snow_since_plowing(df, demo_plowing)
                
                # Vis charts
                self._show_analysis_results(df, snow_analysis, demo_plowing)
            else:
                st.error("Kunne ikke laste februar-data")

    def _show_main_interface(self):
        """Vis hovedgrensesnitt med alle funksjoner"""
        
        # Sidebar for innstillinger
        with st.sidebar:
            st.markdown("### ⚙️ Analyseinnstillinger")
            
            # Periode-valg
            period_type = st.radio(
                "Velg periode:",
                ["🕐 Siste timer", "📅 Egendefinert", "❄️ Siden sist brøytet"],
                index=0
            )
            
            if period_type == "🕐 Siste timer":
                hours_back = st.slider("Timer tilbake:", 6, 72, 24)
                start_date = datetime.now() - timedelta(hours=hours_back)
                end_date = datetime.now()
                last_plowed = None
                
            elif period_type == "📅 Egendefinert":
                col1, col2 = st.columns(2)
                with col1:
                    start_date = st.date_input(
                        "Fra dato:",
                        value=datetime.now().date() - timedelta(days=3),
                        max_value=datetime.now().date()
                    )
                    start_time = st.time_input("Fra kl:", value=datetime.now().time())
                
                with col2:
                    end_date = st.date_input(
                        "Til dato:",
                        value=datetime.now().date(),
                        max_value=datetime.now().date()
                    )
                    end_time = st.time_input("Til kl:", value=datetime.now().time())
                
                # Kombinér dato og tid
                start_date = datetime.combine(start_date, start_time)
                end_date = datetime.combine(end_date, end_time)
                last_plowed = None
                
            else:  # Siden sist brøytet
                st.markdown("**🚜 Sist brøytet:**")
                
                # Hent lagrede brøyting-hendelser
                recent_plowing = self.historical_service.get_recent_plowing_events(5)
                
                if recent_plowing:
                    plowing_options = ["Velg fra tidligere..."] + [
                        f"{event['timestamp'].strftime('%d.%m %H:%M')} - {event.get('notes', 'Ingen notat')[:20]}"
                        for event in recent_plowing
                    ]
                    
                    selected_plowing = st.selectbox(
                        "Tidligere brøytinger:",
                        plowing_options
                    )
                    
                    if selected_plowing != "Velg fra tidligere...":
                        idx = plowing_options.index(selected_plowing) - 1
                        last_plowed = recent_plowing[idx]['timestamp']
                    else:
                        last_plowed = None
                else:
                    last_plowed = None
                
                # Manuell dato/tid input
                if last_plowed is None:
                    plowing_date = st.date_input(
                        "Dato brøytet:",
                        value=datetime.now().date() - timedelta(days=1),
                        max_value=datetime.now().date()
                    )
                    plowing_time = st.time_input(
                        "Tidspunkt:",
                        value=datetime.now().time()
                    )
                    last_plowed = datetime.combine(plowing_date, plowing_time)
                
                # Registrer ny brøyting
                if st.button("📝 Registrer ny brøyting"):
                    notes = st.text_input("Notat (valgfritt):", key="plowing_notes")
                    self.historical_service.save_plowing_event(last_plowed, notes)
                    st.success("Brøyting registrert!")
                    st.rerun()
                
                # Sett periode fra sist brøytet til nå
                start_date = last_plowed
                end_date = datetime.now()
            
            # Valider periode
            is_valid, validation_msg = self.historical_service.validate_date_range(start_date, end_date)
            
            if not is_valid:
                st.error(f"❌ {validation_msg}")
                return
            else:
                st.success(f"✅ {validation_msg}")
            
            # Data-henting knapp
            if st.button("📡 Hent værdata", type="primary"):
                self._fetch_and_analyze_data(start_date, end_date, last_plowed)

    def _fetch_and_analyze_data(self, start_date: datetime, end_date: datetime, last_plowed: Optional[datetime]):
        """Hent og analyser data for valgt periode"""
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Steg 1: Hent data
            status_text.text("📡 Henter værdata...")
            progress_bar.progress(20)
            
            # Konverter til ISO-format for API
            start_iso = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_iso = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            df = self.historical_service.fetch_historical_data(start_iso, end_iso)
            progress_bar.progress(50)
            
            if df.empty:
                st.error("❌ Ingen data mottatt for valgt periode")
                return
            
            # Steg 2: Valider data
            status_text.text("🔍 Validerer datakvalitet...")
            validation = validate_weather_data(df)
            progress_bar.progress(70)
            
            if not validation['valid']:
                st.warning("⚠️ Dårlig datakvalitet")
                with st.expander("Se datakvalitet-detaljer"):
                    for issue in validation['issues']:
                        st.write(f"• {issue}")
            
            # Steg 3: Beregn nysnø
            status_text.text("❄️ Beregner nysnø...")
            df = self.historical_service.calculate_new_snow(df)
            progress_bar.progress(90)
            
            # Steg 4: Analyser brøyting
            if last_plowed:
                status_text.text("🚜 Analyserer brøytebehov...")
                snow_analysis = self.historical_service.calculate_snow_since_plowing(df, last_plowed)
            else:
                snow_analysis = {'total_new_snow': 0, 'plowing_needed': False, 'recommendation': 'Ingen brøyting-referanse'}
            
            progress_bar.progress(100)
            status_text.text("✅ Analyse fullført!")
            
            # Lagre data i session state for gjenbruk
            st.session_state['analysis_data'] = df
            st.session_state['snow_analysis'] = snow_analysis
            st.session_state['last_plowed'] = last_plowed
            
            # Vis resultater
            self._show_analysis_results(df, snow_analysis, last_plowed)
            
        except Exception as e:
            st.error(f"❌ Feil under analyse: {str(e)}")
        finally:
            progress_bar.empty()
            status_text.empty()

    def _show_analysis_results(self, df: pd.DataFrame, snow_analysis: dict, last_plowed: Optional[datetime]):
        """Vis analysens resultater"""
        
        # Hovedsammendrag
        st.markdown("---")
        st.markdown("## 📊 Analyseresultater")
        
        # Sammendragskort
        AdvancedCharts.create_weather_summary_cards(df, snow_analysis)
        
        # Brøyteanbefalinger
        st.markdown("### 🚜 Brøyteanbefalinger")
        
        if snow_analysis['plowing_needed']:
            st.error(f"🔴 **{snow_analysis['recommendation']}**")
        else:
            st.success(f"🟢 **{snow_analysis['recommendation']}**")
        
        # Detaljer
        if last_plowed:
            hours_since = snow_analysis.get('hours_since_plowing', 0)
            st.info(f"⏱️ {hours_since:.1f} timer siden sist brøytet ({last_plowed.strftime('%d.%m %H:%M')})")
        
        # Interaktive charts
        st.markdown("### 📈 Detaljerte analyser")
        
        # Chart-valg
        chart_tabs = st.tabs([
            "🌨️ Snøanalyse", 
            "📊 Multivær", 
            "🎯 Brøytevurdering",
            "⚠️ Risiko-tidslinje"
        ])
        
        with chart_tabs[0]:
            # Komplett snøanalyse
            snow_chart = AdvancedCharts.create_snow_analysis_chart(df, last_plowed)
            st.plotly_chart(snow_chart, use_container_width=True)
        
        with chart_tabs[1]:
            # Multi-værdata chart
            st.markdown("**Velg værdata å vise:**")
            available_metrics = [
                '🌡️ Temperatur', '💨 Vind', '❄️ Snø', 
                '🌧️ Nedbør', '💧 Fuktighet'
            ]
            
            selected_metrics = st.multiselect(
                "Værdata:",
                available_metrics,
                default=['🌡️ Temperatur', '❄️ Snø'],
                key="metrics_selector"
            )
            
            if selected_metrics:
                multi_chart = AdvancedCharts.create_multi_weather_chart(df, selected_metrics)
                st.plotly_chart(multi_chart, use_container_width=True)
        
        with chart_tabs[2]:
            # Brøytevurdering
            plowing_chart = AdvancedCharts.create_plowing_recommendation_chart(snow_analysis, df)
            st.plotly_chart(plowing_chart, use_container_width=True)
        
        with chart_tabs[3]:
            # Risiko-tidslinje
            risk_chart = AdvancedCharts.create_risk_timeline(df)
            st.plotly_chart(risk_chart, use_container_width=True)
        
        # Raw data ekspander
        with st.expander("🔍 Rådata (siste 20 målinger)", expanded=False):
            st.dataframe(df.tail(20), use_container_width=True)
        
        # Export muligheter
        self._show_export_options(df, snow_analysis)

    def _show_export_options(self, df: pd.DataFrame, snow_analysis: dict):
        """Vis eksport-muligheter"""
        
        st.markdown("### 💾 Eksport data")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # CSV export
            csv_data = df.to_csv(index=False)
            st.download_button(
                "📁 Last ned CSV",
                csv_data,
                f"weather_data_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                "text/csv"
            )
        
        with col2:
            # JSON export av analyse
            import json
            analysis_json = json.dumps({
                'snow_analysis': snow_analysis,
                'period': {
                    'start': df['time'].min().isoformat(),
                    'end': df['time'].max().isoformat(),
                    'data_points': len(df)
                },
                'generated': datetime.now().isoformat()
            }, indent=2, ensure_ascii=False)
            
            st.download_button(
                "📋 Analyse JSON",
                analysis_json,
                f"snow_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                "application/json"
            )
        
        with col3:
            # Rapport-generering
            if st.button("📄 Generer rapport"):
                self._generate_text_report(df, snow_analysis)

    def _generate_text_report(self, df: pd.DataFrame, snow_analysis: dict):
        """Generer tekstrapport"""
        
        report = f"""
# VÆRRAPPORT - GULLINGEN SKISENTER

**Generert:** {datetime.now().strftime('%d.%m.%Y kl. %H:%M')}
**Periode:** {df['time'].min().strftime('%d.%m.%Y %H:%M')} - {df['time'].max().strftime('%d.%m.%Y %H:%M')}
**Målinger:** {len(df)} datapunkter

## SAMMENDRAG
- **Nysnø totalt:** {snow_analysis.get('total_new_snow', 0)} cm
- **Dominerende snøtype:** {snow_analysis.get('dominant_type', 'ukjent').replace('_', ' ')}
- **Brøyteanbefalng:** {snow_analysis.get('recommendation', 'Ingen anbefaling')}

## VÆRFORHOLD
- **Temperatur:** {df['air_temperature'].min():.1f}°C - {df['air_temperature'].max():.1f}°C (snitt: {df['air_temperature'].mean():.1f}°C)
- **Vind:** Maks {df['wind_speed'].max():.1f} m/s (snitt: {df['wind_speed'].mean():.1f} m/s)
- **Snødybde:** {df.get('snow_depth_cm', df.get('surface_snow_thickness', pd.Series([0]))).min():.1f} - {df.get('snow_depth_cm', df.get('surface_snow_thickness', pd.Series([0]))).max():.1f} cm

## ANBEFALINGER
{'🔴 BRØYTING ANBEFALT - ' + snow_analysis.get('recommendation', '') if snow_analysis.get('plowing_needed', False) else '🟢 BRØYTING IKKE NØDVENDIG'}

---
Rapport generert av Gullingen Væranalyse-system
        """
        
        st.download_button(
            "📄 Last ned rapport",
            report,
            f"weather_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            "text/plain"
        )
        
        st.success("✅ Rapport generert!")


def main():
    """Hovedfunksjon"""
    app = AdvancedMobileWeatherApp()
    app.run_advanced_app()


if __name__ == "__main__":
    main()
