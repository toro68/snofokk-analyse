#!/usr/bin/env python3
"""
DEBUG-versjon av Streamlit-appen for å diagnostisere nedbørtype-klassifisering.
"""

import os
import sys

import pandas as pd
import streamlit as st

# Legg til current directory til path
sys.path.append('.')

st.title("🔍 DEBUG: Nedbørtype-klassifisering")

st.markdown("### Import-status")

# Test import
try:
    from validert_glattfore_logikk import (
        detect_precipitation_type,
        detect_slippery_road_risk,
        is_slippery_road_risk,
    )
    st.success("✅ Alle funksjoner fra validert_glattfore_logikk importert OK")

    # Test en klassifisering
    test_result = detect_precipitation_type(1.0, 5.0, -2.0, 3.0)
    st.info(f"Test klassifisering: {test_result}")

except ImportError as e:
    st.error(f"❌ Import feilet: {e}")

# Test app-import
try:
    from src.live_conditions_app import VALIDATED_LOGIC_AVAILABLE, LiveConditionsChecker
    st.info(f"VALIDATED_LOGIC_AVAILABLE: {VALIDATED_LOGIC_AVAILABLE}")

    if VALIDATED_LOGIC_AVAILABLE:
        st.success("✅ App registrerer at validert logikk er tilgjengelig")
    else:
        st.error("❌ App registrerer at validert logikk IKKE er tilgjengelig")

except Exception as e:
    st.error(f"❌ App-import feilet: {e}")

st.markdown("### Test nedbørtype-klassifisering")

if st.button("Kjør test"):
    try:
        # Test data
        test_data = pd.DataFrame({
            'time': pd.date_range('2025-01-01', periods=3, freq='h'),
            'air_temperature': [2.0, -1.0, 0.5],
            'precipitation_mm': [10.0, 5.0, 8.0],
            'snow_depth': [50, 48, 45],
            'wind_speed': [3, 15, 5]
        })

        st.write("**Testdata:**")
        st.dataframe(test_data)

        # Test klassifisering
        checker = LiveConditionsChecker()
        df_classified = checker.classify_precipitation_types(test_data)

        st.write("**Klassifiserte data:**")
        st.dataframe(df_classified[['time', 'air_temperature', 'precipitation_mm', 'precipitation_type']])

        # Test plot
        fig = checker.create_precipitation_classification_plot(test_data)
        st.pyplot(fig)

        st.success("✅ ALLE TESTER OK!")

    except Exception as e:
        st.error(f"❌ Test feilet: {e}")
        st.text(f"Feiltype: {type(e).__name__}")
        import traceback
        st.text(traceback.format_exc())

st.markdown("### Filsystem-status")
cwd = os.getcwd()
st.info(f"Current working directory: {cwd}")

if os.path.exists('validert_glattfore_logikk.py'):
    st.success("✅ validert_glattfore_logikk.py finnes")
else:
    st.error("❌ validert_glattfore_logikk.py MANGLER")

if os.path.exists('src/live_conditions_app.py'):
    st.success("✅ src/live_conditions_app.py finnes")
else:
    st.error("❌ src/live_conditions_app.py MANGLER")
