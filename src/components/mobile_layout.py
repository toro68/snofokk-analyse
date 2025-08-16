"""
Mobil-optimaliserte UI komponenter for værdata visning
"""
import streamlit as st
import pandas as pd
from typing import Dict, Any


class MobileLayout:
    """Mobil-first layout komponenter for weather app"""
    
    @staticmethod
    def prepare_weather_data(df: pd.DataFrame) -> pd.DataFrame:
        """
        Preparer værdata for konsistent visning.
        Konverterer enheter og saniterer data.
        """
        if df.empty:
            return df
        
        df_prepared = df.copy()
        
        # Konverter snødybde til cm hvis nødvendig
        if 'surface_snow_thickness' in df_prepared.columns:
            snow_data = df_prepared['surface_snow_thickness'].copy()
            # Sanitize: negative verdier er ofte sentinel values for missing data
            snow_data = snow_data.where(snow_data >= 0, None)
            # Konverter fra meter til cm hvis verdiene ser ut til å være i meter
            df_prepared['surface_snow_thickness_cm'] = snow_data.apply(
                lambda x: x * 100 if pd.notna(x) and x < 10 else x
            )
        
        return df_prepared
    
    @staticmethod
    def configure_mobile_page():
        """Konfigurer siden for mobil-first design"""
        st.set_page_config(
            page_title="❄️ Snøfokk Varsling",
            page_icon="❄️",
            layout="wide",  # Paradoksalt, men gir mer kontroll over responsive design
            initial_sidebar_state="auto",  # Auto for bedre PWA-opplevelse
            menu_items={
                'Get Help': 'https://github.com/toro68/snofokk-analyse',
                'Report a bug': 'https://github.com/toro68/snofokk-analyse/issues',
                'About': """
                # ❄️ Snøfokk & Glattføre Varsling
                
                Mobil-optimalisert væranalyse for Gullingen Skisenter.
                
                **Utviklet for operative beslutninger:**
                - 📱 Mobil-first design  
                - ⚡ Rask lasting
                - 🔄 Offline støtte via PWA
                - 📊 Sanntidsdata fra Meteorologisk institutt
                - 💾 Installerbar som app
                """
            }
        )
        
        # Custom CSS for mobile optimization
        st.markdown("""
        <style>
        /* MOBIL-FIRST CSS */
        
        /* PWA Mode - skjul Streamlit UI når installert som app */
        @media (display-mode: standalone) {
            header[data-testid="stHeader"] {
                display: none;
            }
            
            .main .block-container {
                padding-top: 0.5rem;
            }
            
            /* Skjul footer og andre Streamlit-elementer */
            footer {
                display: none;
            }
            
            .stActionButton {
                display: none;
            }
        }
        
        /* Print styles for accessibility */
        @media print {
            /* Skjul interaktive elementer */
            .stButton, .stSelectbox, .stCheckbox {
                display: none !important;
            }
            
            /* Optimaliser for print */
            .main .block-container {
                padding: 0;
                max-width: 100%;
            }
            
            .risk-card {
                border: 2px solid #333 !important;
                background: white !important;
                color: black !important;
                page-break-inside: avoid;
            }
            
            /* Vis URL-er i lenker */
            a[href]:after {
                content: " (" attr(href) ")";
                font-size: 0.8em;
            }
        }
        
        /* Base responsive styles */
        .main .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
            padding-left: 1rem;
            padding-right: 1rem;
            max-width: 100%;
        }
        
        /* Mobile-optimized cards with improved accessibility */
        .risk-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 12px;
            padding: 1rem;
            margin: 0.5rem 0;
            color: white;
            text-align: center;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            /* Accessibility improvements */
            role: region;
            border: 2px solid transparent;
            transition: border-color 0.3s ease;
        }
        
        .risk-card:focus-within {
            border-color: #ffffff;
            outline: 2px solid #0066cc;
            outline-offset: 2px;
        }
        
        .risk-card-high {
            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
            /* Høy kontrast for tilgjengelighet */
            border: 2px solid #d63031;
        }
        
        .risk-card-medium {
            background: linear-gradient(135deg, #feca57 0%, #ff9ff3 100%);
            color: #2d3436; /* Bedre kontrast */
            border: 2px solid #fdcb6e;
        }
        
        .risk-card-low {
            background: linear-gradient(135deg, #48cae4 0%, #023e8a 100%);
            border: 2px solid #0984e3;
        }
        
        /* Quick status indicators with accessibility */
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            /* Add text alternative for screen readers */
        }
        
        .status-high { 
            background-color: #ff4757;
            border: 1px solid #c44569;
        }
        .status-medium { 
            background-color: #ffa502;
            border: 1px solid #ff6348;
        }
        .status-low { 
            background-color: #26de81;
            border: 1px solid #20bf6b;
        }
        .status-unknown { 
            background-color: #747d8c;
            border: 1px solid #57606f;
        }
        
        /* Compact metric display with semantic structure */
        .metric-compact {
            text-align: center;
            background: #f8f9fa;
            border-radius: 8px;
            padding: 0.5rem;
            margin: 0.25rem;
            border: 1px solid #dee2e6;
            /* Accessibility */
            role: group;
        }
        
        .metric-value {
            font-size: 1.5rem;
            font-weight: bold;
            color: #2d3436;
            display: block;
        }
        
        .metric-label {
            font-size: 0.8rem;
            color: #636e72;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: block;
        }
        
        /* Mobile-friendly buttons */
        .stButton > button {
            width: 100%;
            border-radius: 8px;
            border: none;
            padding: 0.75rem;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        
        /* Responsive text sizes */
        @media (max-width: 768px) {
            .main .block-container {
                padding-left: 0.5rem;
                padding-right: 0.5rem;
            }
            
            h1 { font-size: 1.5rem !important; }
            h2 { font-size: 1.25rem !important; }
            h3 { font-size: 1.1rem !important; }
            
            .metric-value { font-size: 1.25rem; }
        }
        
        /* Hide unnecessary elements on mobile */
        @media (max-width: 480px) {
            .row-widget.stRadio > div { flex-direction: column; }
            .stMultiSelect { font-size: 0.9rem; }
        }
        
        /* Custom scrollbars for mobile */
        ::-webkit-scrollbar {
            width: 4px;
            height: 4px;
        }
        
        ::-webkit-scrollbar-track {
            background: #f1f1f1;
        }
        
        ::-webkit-scrollbar-thumb {
            background: #888;
            border-radius: 2px;
        }
        
        /* Focus states for accessibility */
        .stButton > button:focus,
        .stSelectbox > div > div:focus {
            outline: 2px solid #0066cc;
            outline-offset: 2px;
        }
        
        /* Screen reader only content */
        .sr-only {
            position: absolute;
            width: 1px;
            height: 1px;
            padding: 0;
            margin: -1px;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            white-space: nowrap;
            border: 0;
        }
        
        /* Skip to main content link for accessibility */
        .skip-to-main {
            position: absolute;
            top: -40px;
            left: 6px;
            background: #0066cc;
            color: white;
            padding: 8px;
            text-decoration: none;
            border-radius: 4px;
            z-index: 1000;
        }
        
        .skip-to-main:focus {
            top: 6px;
        }
        </style>
        """, unsafe_allow_html=True)

    @staticmethod 
    def show_mobile_header():
        """Kompakt mobil-header med kritisk info"""
        st.markdown("""
        <div style="text-align: center; margin-bottom: 1rem;">
            <h1 style="margin: 0; color: #2d3436;">❄️ Gullingen Skisenter</h1>
            <p style="margin: 0; color: #636e72; font-size: 0.9rem;">Snøfokk & Glattføre Varsling</p>
        </div>
        """, unsafe_allow_html=True)

    @staticmethod
    def _create_risk_card(title: str, icon: str, risk_data: Dict[str, Any], card_id: str) -> str:
        """
        Hjelpefunksjon for å lage risikokort.
        Reduserer kode-duplikasjon.
        """
        risk_level = risk_data.get('risk_level', 'unknown')
        message = risk_data.get('message', 'Ukjent status')
        
        # Map risk level to CSS class
        css_class_map = {
            'high': 'risk-card-high',
            'medium': 'risk-card-medium', 
            'low': 'risk-card-low'
        }
        css_class = css_class_map.get(risk_level, 'risk-card')
        
        # Create accessible HTML with proper ARIA attributes
        return f"""
        <div class="risk-card {css_class}" role="region" aria-labelledby="{card_id}-title" tabindex="0">
            <h3 id="{card_id}-title" style="margin: 0;">{icon} {title}</h3>
            <p style="margin: 0.5rem 0; font-size: 1.1rem; font-weight: bold;" aria-label="Risikostatus: {message}">
                {message}
            </p>
            <span class="sr-only">Risikonivå: {risk_level}</span>
        </div>
        """

    @staticmethod
    def show_risk_cards(snowdrift_risk: Dict[str, Any], slippery_risk: Dict[str, Any]):
        """Mobil-optimaliserte risikokort med forbedret tilgjengelighet"""
        
        # Quick status row - most important info first
        col1, col2 = st.columns(2)
        
        with col1:
            snowdrift_card = MobileLayout._create_risk_card(
                title="Snøfokk",
                icon="🌪️", 
                risk_data=snowdrift_risk,
                card_id="snowdrift"
            )
            st.markdown(snowdrift_card, unsafe_allow_html=True)
        
        with col2:
            slippery_card = MobileLayout._create_risk_card(
                title="Glattføre",
                icon="🧊",
                risk_data=slippery_risk, 
                card_id="slippery"
            )
            st.markdown(slippery_card, unsafe_allow_html=True)

    @staticmethod
    def show_current_conditions(df: pd.DataFrame):
        """Kompakt visning av nåværende forhold med forbedret datahåndtering"""
        if df.empty:
            st.warning("Ingen værdata tilgjengelig")
            return
        
        # Bruk forbedret dataprepareringsfunksjon
        df_prepared = MobileLayout.prepare_weather_data(df)
        latest = df_prepared.iloc[-1]
        
        # Show skeleton loader initially, then real data
        if 'conditions_loaded' not in st.session_state:
            MobileLayout.show_skeleton_loader("metrics")
            st.session_state.conditions_loaded = True
            st.rerun()
        
        st.markdown("### 🌡️ Aktuelle forhold")
        
        # 4 viktigste målinger i kompakt grid med forbedret accessibility
        col1, col2, col3, _ = st.columns(4)
        
        with col1:
            temp = latest.get('air_temperature', None)
            if pd.notna(temp):
                st.markdown(f"""
                <div class="metric-compact" role="group" aria-labelledby="temp-label">
                    <div class="metric-value" id="temp-value">{temp:.1f}°</div>
                    <div class="metric-label" id="temp-label">Temp</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-compact" role="group" aria-label="Temperatur ikke tilgjengelig">
                    <div class="metric-value">-</div>
                    <div class="metric-label">Temp</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            wind = latest.get('wind_speed', None)
            if pd.notna(wind):
                st.markdown(f"""
                <div class="metric-compact" role="group" aria-labelledby="wind-label">
                    <div class="metric-value" id="wind-value">{wind:.1f}</div>
                    <div class="metric-label" id="wind-label">Vind m/s</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-compact" role="group" aria-label="Vindhastighet ikke tilgjengelig">
                    <div class="metric-value">-</div>
                    <div class="metric-label">Vind m/s</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col3:
            # Bruk den forberedte snødata
            snow = latest.get('surface_snow_thickness_cm', None)
            if pd.notna(snow) and snow is not None and snow >= 0:
                st.markdown(f"""
                <div class="metric-compact" role="group" aria-labelledby="snow-label">
                    <div class="metric-value" id="snow-value">{snow:.0f}</div>
                    <div class="metric-label" id="snow-label">Snø cm</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-compact" role="group" aria-label="Snødybde ikke tilgjengelig">
                    <div class="metric-value">-</div>
                    <div class="metric-label">Snø cm</div>
                </div>
                """, unsafe_allow_html=True)
        
    @staticmethod
    def show_skeleton_loader(content_type: str = "card"):
        """Vis skeleton loader mens data lastes"""
        
        if content_type == "card":
            st.markdown("""
            <div class="skeleton-container">
                <div class="skeleton skeleton-card"></div>
                <div class="skeleton skeleton-text"></div>
                <div class="skeleton skeleton-text" style="width: 60%"></div>
            </div>
            
            <style>
            @keyframes shimmer {
                0% { background-position: -200% 0; }
                100% { background-position: 200% 0; }
            }
            
            .skeleton {
                background: linear-gradient(90deg, 
                    #f0f0f0 25%, 
                    #e0e0e0 50%, 
                    #f0f0f0 75%);
                background-size: 200% 100%;
                animation: shimmer 1.5s infinite;
                border-radius: 8px;
            }
            
            .skeleton-card {
                height: 120px;
                margin: 10px 0;
                border-radius: 12px;
            }
            
            .skeleton-text {
                height: 20px;
                margin: 10px 0;
                width: 80%;
            }
            
            .skeleton-container {
                margin-bottom: 1rem;
            }
            </style>
            """, unsafe_allow_html=True)
        
        elif content_type == "metrics":
            st.markdown("""
            <div class="metrics-skeleton">
                <div class="skeleton skeleton-metric"></div>
                <div class="skeleton skeleton-metric"></div>
                <div class="skeleton skeleton-metric"></div>
                <div class="skeleton skeleton-metric"></div>
            </div>
            
            <style>
            .metrics-skeleton {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 0.5rem;
                margin: 1rem 0;
            }
            
            .skeleton-metric {
                height: 80px;
                border-radius: 8px;
                background: linear-gradient(90deg, 
                    #f0f0f0 25%, 
                    #e0e0e0 50%, 
                    #f0f0f0 75%);
                background-size: 200% 100%;
                animation: shimmer 1.5s infinite;
            }
            
            @media (max-width: 768px) {
                .metrics-skeleton {
                    grid-template-columns: repeat(2, 1fr);
                }
            }
            </style>
            """, unsafe_allow_html=True)

    @staticmethod
    def show_mobile_chart(df: pd.DataFrame, initial_chart_type: str = "temperature"):
        """Mobil-optimalisert chart visning med forbedret datahåndtering"""
        if df.empty:
            st.info("Ingen data å vise")
            return
        
        # Preparer data konsistent
        df_prepared = MobileLayout.prepare_weather_data(df)
        
        # Smaller chart for mobile
        st.markdown("### 📊 Værtrend (siste 24t)")
        
        # Chart selection for mobile
        chart_options = {
            "🌡️ Temperatur": "temperature",
            "💨 Vind": "wind", 
            "❄️ Snø": "snow",
            "🌧️ Nedbør": "precipitation"
        }
        
        # Find initial selection key
        initial_key = "🌡️ Temperatur"
        for key, value in chart_options.items():
            if value == initial_chart_type:
                initial_key = key
                break
        
        selected = st.selectbox(
            "Velg værdata:",
            options=list(chart_options.keys()),
            index=list(chart_options.keys()).index(initial_key)
        )
        
        selected_chart_type = chart_options[selected]
        
        if selected_chart_type == "temperature" and 'air_temperature' in df_prepared.columns:
            st.line_chart(df_prepared.set_index('time')['air_temperature'], height=300)
        elif selected_chart_type == "wind" and 'wind_speed' in df_prepared.columns:
            st.line_chart(df_prepared.set_index('time')['wind_speed'], height=300)
        elif selected_chart_type == "snow" and 'surface_snow_thickness_cm' in df_prepared.columns:
            # Bruk konsistent snødata
            st.line_chart(df_prepared.set_index('time')['surface_snow_thickness_cm'], height=300)
        elif selected_chart_type == "precipitation":
            # Handle multiple possible precipitation column names
            precip_cols = [col for col in df_prepared.columns if 'precipitation_amount' in col and col.startswith('sum(')]
            if precip_cols:
                # Create a renamed series to avoid Altair field name issues
                precip_data = df_prepared[precip_cols[0]].copy()
                precip_df = pd.DataFrame({
                    'time': df_prepared['time'],
                    'precipitation': precip_data
                })
                st.bar_chart(precip_df.set_index('time')['precipitation'], height=300)
            else:
                st.info("Ingen nedbør data tilgjengelig")
        else:
            st.info(f"Ingen {selected.lower()} data tilgjengelig")

    @staticmethod
    def show_mobile_controls():
        """Kompakte kontroller for mobil"""
        st.markdown("### ⚙️ Innstillinger")
        
        # Compact control layout
        col1, col2 = st.columns(2)
        
        with col1:
            auto_refresh = st.checkbox("🔄 Auto-oppdater", value=True)
            if auto_refresh:
                st.caption("Oppdaterer hvert 5. minutt")
        
        with col2:
            if st.button("🔄 Oppdater nå", key="mobile_refresh"):
                st.rerun()

    @staticmethod
    def show_mobile_footer():
        """Kompakt footer med essential info"""
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; color: #636e72; font-size: 0.8rem;">
            📡 Data: Meteorologisk institutt • 🏔️ Gullingen Skisenter (639 moh)<br>
            💻 <a href="https://github.com/toro68/snofokk-analyse">GitHub</a> • 
            📱 Mobil-optimalisert versjon
        </div>
        """, unsafe_allow_html=True)

    @staticmethod
    def detect_mobile() -> bool:
        """
        Forsøk å detektere mobil enhet.
        
        Merk: Streamlit har begrensede muligheter for user-agent deteksjon.
        Denne funksjonen returnerer True for mobil-first design approach.
        For mer avansert deteksjon, vurder å bruke streamlit-js-eval eller
        lignende JavaScript-baserte løsninger.
        
        Returns:
            bool: True for mobil-first approach (anbefalt for denne appen)
        """
        # I en mer avansert implementasjon kunne vi:
        # 1. Bruke streamlit-js-eval for å få window.innerWidth
        # 2. Sjekke user-agent string via JavaScript
        # 3. Implementere server-side user-agent parsing
        
        # For nå: mobil-first design er default
        return True

    @staticmethod
    def get_optimal_layout_config() -> Dict[str, Any]:
        """
        Returner optimal layout-konfigurasjon basert på detektert enhet.
        
        Returns:
            Dict med layout-innstillinger
        """
        is_mobile = MobileLayout.detect_mobile()
        
        return {
            'is_mobile': is_mobile,
            'columns_per_row': 2 if is_mobile else 4,
            'chart_height': 300 if is_mobile else 400,
            'compact_metrics': is_mobile,
            'sidebar_collapsed': is_mobile
        }

    @staticmethod
    def show_data_quality_indicator(df: pd.DataFrame):
        """Kompakt datakvalitetsindikator"""
        if df.empty:
            st.error("🔴 Ingen data")
            return
        
        # Beregn datakvalitet
        total_points = len(df)
        missing_temp = df['air_temperature'].isna().sum() if 'air_temperature' in df.columns else total_points
        missing_wind = df['wind_speed'].isna().sum() if 'wind_speed' in df.columns else total_points
        
        quality_score = ((total_points - missing_temp - missing_wind) / (total_points * 2)) * 100
        
        if quality_score >= 80:
            st.success(f"✅ Datakvalitet: {quality_score:.0f}%")
        elif quality_score >= 50:
            st.warning(f"⚠️ Datakvalitet: {quality_score:.0f}%")
        else:
            st.error(f"❌ Datakvalitet: {quality_score:.0f}%")
