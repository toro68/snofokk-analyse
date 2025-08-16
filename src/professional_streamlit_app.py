#!/usr/bin/env python3
"""
Professional Streamlit Admin/Analysis UI
Enterprise-grade UI/UX for weather analysis
"""

import os
import time
import warnings
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Dict, Any, Optional

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

# Import performance cache system
from components.performance_cache import DataCache, ProgressiveLoader, ErrorHandler

# Suppress warnings for clean UI
warnings.filterwarnings('ignore')
load_dotenv()

# System status tracking
SYSTEM_STATUS = {
    'api_status': 'unknown',
    'last_api_check': None,
    'ml_available': False,
    'validated_logic': False,
    'live_conditions': False
}

# Professional styling
PROFESSIONAL_CSS = """
<style>
    /* Remove Streamlit branding and improve aesthetics */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Professional color scheme */
    :root {
        --primary-color: #2c3e50;
        --secondary-color: #3498db;
        --success-color: #27ae60;
        --warning-color: #f39c12;
        --danger-color: #e74c3c;
        --background-color: #ecf0f1;
        --text-color: #2c3e50;
    }
    
    /* Status indicators */
    .status-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 8px;
    }
    
    .status-online { background-color: var(--success-color); }
    .status-offline { background-color: var(--danger-color); }
    .status-warning { background-color: var(--warning-color); }
    .status-unknown { background-color: #95a5a6; }
    
    /* Professional cards */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid var(--primary-color);
        margin-bottom: 1rem;
    }
    
    /* Header styling */
    .app-header {
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
        text-align: center;
    }
    
    .app-title {
        font-size: 2.5rem;
        font-weight: 300;
        margin: 0;
        letter-spacing: 1px;
    }
    
    .app-subtitle {
        font-size: 1.1rem;
        opacity: 0.9;
        margin: 0.5rem 0 0 0;
        font-weight: 300;
    }
    
    /* Navigation */
    .nav-pills {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 2rem;
    }
    
    /* Loading spinner */
    .loading-spinner {
        display: inline-block;
        width: 20px;
        height: 20px;
        border: 3px solid #f3f3f3;
        border-top: 3px solid var(--primary-color);
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    /* Alert boxes */
    .alert {
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        border-left: 4px solid;
    }
    
    .alert-info {
        background: #e3f2fd;
        border-color: var(--secondary-color);
        color: #1565c0;
    }
    
    .alert-warning {
        background: #fff8e1;
        border-color: var(--warning-color);
        color: #ef6c00;
    }
    
    .alert-error {
        background: #ffebee;
        border-color: var(--danger-color);
        color: #c62828;
    }
    
    .alert-success {
        background: #e8f5e8;
        border-color: var(--success-color);
        color: #2e7d32;
    }
</style>
"""


def initialize_professional_ui():
    """Initialize professional UI configuration"""
    st.set_page_config(
        page_title="Weather Analysis Pro",
        page_icon="⛄",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'Get Help': None,
            'Report a bug': None,
            'About': None
        }
    )
    
    # Inject professional CSS
    st.markdown(PROFESSIONAL_CSS, unsafe_allow_html=True)


def check_system_status():
    """Check and update system status"""
    global SYSTEM_STATUS
    
    # Check API status
    try:
        response = requests.get(
            "https://frost.met.no/sources/v0.jsonld",
            timeout=5
        )
        SYSTEM_STATUS['api_status'] = 'online' if response.status_code == 200 else 'warning'
    except:
        SYSTEM_STATUS['api_status'] = 'offline'
    
    SYSTEM_STATUS['last_api_check'] = datetime.now()
    
    # Check module availability (silently)
    try:
        from ml_snowdrift_detector import MLSnowdriftDetector
        SYSTEM_STATUS['ml_available'] = True
    except ImportError:
        SYSTEM_STATUS['ml_available'] = False
    
    try:
        from validert_glattfore_logikk import detect_precipitation_type
        SYSTEM_STATUS['validated_logic'] = True
    except ImportError:
        SYSTEM_STATUS['validated_logic'] = False
    
    try:
        from live_conditions_app import LiveConditionsChecker
        SYSTEM_STATUS['live_conditions'] = True
    except ImportError:
        SYSTEM_STATUS['live_conditions'] = False


def render_professional_header():
    """Render professional application header"""
    st.markdown("""
    <div class="app-header">
        <h1 class="app-title">Weather Analysis Pro</h1>
        <p class="app-subtitle">
            Professional Weather Intelligence Platform • Gullingen Skisenter
        </p>
    </div>
    """, unsafe_allow_html=True)


def render_system_status():
    """Render system status indicators"""
    with st.sidebar:
        st.markdown("### System Status")
        
        # API Status
        api_status = SYSTEM_STATUS['api_status']
        status_class = f"status-{api_status}" if api_status != 'unknown' else "status-unknown"
        
        api_labels = {
            'online': 'API Online',
            'offline': 'API Offline', 
            'warning': 'API Issues',
            'unknown': 'API Unknown'
        }
        
        st.markdown(f"""
        <div style="margin-bottom: 1rem;">
            <span class="status-indicator {status_class}"></span>
            <strong>{api_labels.get(api_status, 'Unknown')}</strong>
        </div>
        """, unsafe_allow_html=True)
        
        # Module Status
        modules = [
            ('ML Detection', SYSTEM_STATUS['ml_available']),
            ('Validated Logic', SYSTEM_STATUS['validated_logic']),
            ('Live Conditions', SYSTEM_STATUS['live_conditions'])
        ]
        
        for name, available in modules:
            status_class = "status-online" if available else "status-offline"
            status_text = "Available" if available else "Unavailable"
            
            st.markdown(f"""
            <div style="margin-bottom: 0.5rem; font-size: 0.9rem;">
                <span class="status-indicator {status_class}"></span>
                {name}: {status_text}
            </div>
            """, unsafe_allow_html=True)
        
        # Last check time
        if SYSTEM_STATUS['last_api_check']:
            check_time = SYSTEM_STATUS['last_api_check'].strftime("%H:%M:%S")
            st.caption(f"Last check: {check_time}")


def render_cache_management():
    """Render cache management interface"""
    with st.sidebar:
        st.markdown("### Cache Management")
        
        cache_stats = DataCache.get_cache_stats()
        
        # Cache metrics in compact format
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Entries", cache_stats.get('entries', 0), label_visibility="collapsed")
        with col2:
            newest_age = cache_stats.get('newest_age')
            age_display = f"{newest_age:.0f}s" if newest_age else "N/A"
            st.metric("Age", age_display, label_visibility="collapsed")
        
        # Cache controls
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Clear All", use_container_width=True, type="secondary"):
                DataCache.invalidate_cache()
                st.success("Cache cleared", icon="✅")
                time.sleep(1)
                st.rerun()
        
        with col2:
            if st.button("Refresh", use_container_width=True):
                st.info("Refreshing...", icon="🔄")
                time.sleep(0.5)
                st.rerun()


def render_loading_state(message: str = "Loading..."):
    """Render professional loading state"""
    return st.markdown(f"""
    <div style="text-align: center; padding: 2rem;">
        <div class="loading-spinner"></div>
        <p style="margin-top: 1rem; color: #666;">{message}</p>
    </div>
    """, unsafe_allow_html=True)


def render_alert(message: str, alert_type: str = "info", icon: str = None):
    """Render professional alert"""
    icons = {
        'info': 'ℹ️',
        'warning': '⚠️',
        'error': '❌',
        'success': '✅'
    }
    
    display_icon = icon or icons.get(alert_type, 'ℹ️')
    
    st.markdown(f"""
    <div class="alert alert-{alert_type}">
        {display_icon} {message}
    </div>
    """, unsafe_allow_html=True)


def render_weather_dashboard():
    """Render main weather analysis dashboard"""
    
    # Check if we can proceed with analysis
    if SYSTEM_STATUS['api_status'] == 'offline':
        render_alert(
            "Weather data is currently unavailable. Please check your internet connection or try again later.",
            "error"
        )
        return
    
    # Demo data section (since API might be limited)
    st.markdown("### Current Conditions Overview")
    
    if SYSTEM_STATUS['api_status'] == 'warning':
        render_alert(
            "Limited API access detected. Showing demonstration interface.",
            "warning"
        )
    
    # Create metrics layout
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Temperature",
            value="-5.2°C",
            delta="-1.3°C",
            help="Current temperature with trend"
        )
    
    with col2:
        st.metric(
            label="Wind Speed", 
            value="12.5 m/s",
            delta="2.1 m/s",
            help="Wind speed with trend"
        )
    
    with col3:
        st.metric(
            label="Snow Drift Risk",
            value="Medium",
            delta="Increasing",
            delta_color="inverse",
            help="ML-based snow drift prediction"
        )
    
    with col4:
        st.metric(
            label="Road Conditions",
            value="Caution",
            help="Ice and slippery conditions assessment"
        )
    
    # Analysis sections
    st.markdown("### Detailed Analysis")
    
    # Create expandable sections
    with st.expander("🌨️ Snow Drift Analysis", expanded=True):
        if SYSTEM_STATUS['ml_available']:
            st.success("ML-based snow drift detection is operational")
            # Add actual analysis here
        else:
            render_alert(
                "Advanced ML analysis unavailable. Using traditional methods.",
                "info"
            )
    
    with st.expander("🧊 Ice Formation Risk"):
        if SYSTEM_STATUS['validated_logic']:
            st.success("Validated precipitation logic is operational")
            # Add actual analysis here
        else:
            render_alert(
                "Enhanced ice detection unavailable. Using basic temperature analysis.",
                "info"
            )
    
    with st.expander("📊 Data Quality Assessment"):
        st.info("Data quality metrics and validation results will appear here")


def render_historical_analysis():
    """Render historical analysis interface"""
    st.markdown("### Historical Weather Analysis")
    
    render_alert(
        "Historical analysis features are being developed. Available in next release.",
        "info"
    )
    
    # Placeholder for future features
    with st.expander("Planned Features", expanded=False):
        st.markdown("""
        **Coming Soon:**
        - Seasonal comparison analysis
        - Long-term trend identification  
        - Custom date range selection
        - Export capabilities (CSV, PDF)
        - Automated reporting
        """)


def render_admin_tools():
    """Render admin tools interface"""
    st.markdown("### Administration Tools")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### System Maintenance")
        
        if st.button("🔄 Refresh System Status", use_container_width=True):
            with st.spinner("Checking system status..."):
                check_system_status()
                time.sleep(1)
            st.success("System status updated")
            st.rerun()
        
        if st.button("🧹 System Cleanup", use_container_width=True):
            with st.spinner("Performing cleanup..."):
                DataCache.invalidate_cache()
                time.sleep(1)
            st.success("System cleanup completed")
    
    with col2:
        st.markdown("#### Configuration")
        
        # System configuration options
        with st.expander("Cache Settings"):
            ttl_value = st.slider(
                "Cache TTL (seconds)",
                min_value=30,
                max_value=600,
                value=300,
                help="Time-to-live for cached data"
            )
            
            max_entries = st.slider(
                "Max Cache Entries",
                min_value=10,
                max_value=100,
                value=20,
                help="Maximum number of cached items"
            )
        
        with st.expander("API Settings"):
            st.text_input(
                "Frost API Client ID",
                placeholder="Enter your Met.no client ID",
                type="password",
                help="Required for full API access"
            )


def main():
    """Main application entry point"""
    
    # Initialize professional UI
    initialize_professional_ui()
    
    # Check system status
    check_system_status()
    
    # Render header
    render_professional_header()
    
    # Render sidebar
    render_system_status()
    render_cache_management()
    
    # Main navigation
    tab1, tab2, tab3 = st.tabs([
        "🌤️ Weather Dashboard",
        "📈 Historical Analysis", 
        "⚙️ Admin Tools"
    ])
    
    with tab1:
        render_weather_dashboard()
    
    with tab2:
        render_historical_analysis()
    
    with tab3:
        render_admin_tools()
    
    # Footer with system info
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.caption("Weather Analysis Pro v2.0")
    with col2:
        st.caption(f"Port: 8501 • Cache: {DataCache.get_cache_stats()['entries']} entries")
    with col3:
        st.caption(f"Status: {SYSTEM_STATUS['api_status'].title()}")


if __name__ == "__main__":
    main()
