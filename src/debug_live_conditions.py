#!/usr/bin/env python3
"""
DEBUG VERSJON - Live Føreforhold
===============================
"""

import streamlit as st
import pandas as pd
import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Last miljøvariabler
load_dotenv()

def test_api_connection():
    """Test API-tilkobling med debugging."""
    
    st.title("🔧 DEBUG: Live Føreforhold")
    
    # Sjekk API-nøkkel
    api_key = os.getenv('FROST_CLIENT_ID')
    if not api_key:
        st.error("❌ FROST_CLIENT_ID ikke funnet i .env fil!")
        st.info("Opprett .env fil med: FROST_CLIENT_ID=din_nokkel")
        return
    
    st.success(f"✅ API-nøkkel funnet: {api_key[:10]}...")
    
    # Test enkel API-kall
    with st.spinner("Tester API-tilkobling..."):
        try:
            # Enkel test - bare siste målinger
            from datetime import timezone
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=24)
            fmt = "%Y-%m-%dT%H:%M:%SZ"
            
            url = 'https://frost.met.no/observations/v0.jsonld'
            parameters = {
                'sources': os.getenv('WEATHER_STATION', 'SN46220'),  # Gullingen Skisenter
                'elements': 'air_temperature,wind_speed',  # Kun 2 parametere for test
                'referencetime': f"{start_time.strftime(fmt)}/{end_time.strftime(fmt)}",
                'timeoffsets': 'PT0H'
            }
            
            st.write("🔗 API URL:", url)
            st.write("📋 Parametere:", parameters)
            
            response = requests.get(url, parameters, auth=(api_key, ''), timeout=30)
            
            st.write(f"📡 HTTP Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                st.success(f"✅ API suksess! Fikk {len(data.get('data', []))} målinger")
                
                # Vis litt data
                if data.get('data'):
                    st.json(data['data'][0])  # Vis første måling
                    
                    # Parse til DataFrame
                    records = []
                    for obs in data['data'][:10]:  # Kun første 10
                        record = {'referenceTime': obs['referenceTime']}
                        for observation in obs['observations']:
                            element = observation['elementId']
                            value = observation['value']
                            record[element] = value
                        records.append(record)
                    
                    df = pd.DataFrame(records)
                    st.success(f"✅ DataFrame opprettet med {len(df)} rader")
                    st.dataframe(df.head())
                    
                    # Sjekk siste målinger
                    if 'air_temperature' in df.columns:
                        latest_temp = df['air_temperature'].iloc[-1]
                        st.metric("🌡️ Siste temperatur", f"{latest_temp:.1f}°C")
                    
                    if 'wind_speed' in df.columns:
                        latest_wind = df['wind_speed'].iloc[-1]
                        st.metric("💨 Siste vindstyrke", f"{latest_wind:.1f} m/s")
                
            elif response.status_code == 401:
                st.error("❌ 401 Unauthorized - Sjekk API-nøkkel!")
            elif response.status_code == 403:
                st.error("❌ 403 Forbidden - API-nøkkel har ikke tilgang!")
            elif response.status_code == 404:
                st.error("❌ 404 Not Found - Sjekk stasjon-ID eller parametere!")
            else:
                st.error(f"❌ API feil: {response.status_code}")
                st.text("Response text:")
                st.text(response.text)
                
        except requests.exceptions.Timeout:
            st.error("❌ Timeout - API bruker for lang tid!")
        except requests.exceptions.ConnectionError:
            st.error("❌ Connection Error - Sjekk internettforbindelse!")
        except Exception as e:
            st.error(f"❌ Ukjent feil: {e}")
            import traceback
            st.text(traceback.format_exc())

def show_environment_info():
    """Vis miljøinformasjon."""
    
    st.subheader("🔧 Miljøinformasjon")
    
    # Python miljø
    import sys
    st.write(f"🐍 Python versjon: {sys.version}")
    
    # Installed packages
    import pkg_resources
    packages = [d.project_name for d in pkg_resources.working_set]
    relevant_packages = [p for p in packages if any(x in p.lower() for x in ['requests', 'pandas', 'streamlit', 'dotenv'])]
    st.write("📦 Relevante pakker:", relevant_packages)
    
    # Miljøvariabler
    st.write("🌍 Miljøvariabler:")
    env_vars = {
        'FROST_CLIENT_ID': '✅ Satt' if os.getenv('FROST_CLIENT_ID') else '❌ Ikke satt',
        'PWD': os.getenv('PWD', 'Ikke satt'),
        'HOME': os.getenv('HOME', 'Ikke satt')[:50] + '...' if os.getenv('HOME') else 'Ikke satt'
    }
    
    for key, value in env_vars.items():
        st.write(f"  • {key}: {value}")

def main():
    """Hovedfunksjon for debugging."""
    
    st.set_page_config(
        page_title="DEBUG: Live Føreforhold",
        page_icon="🔧"
    )
    
    # Test API
    test_api_connection()
    
    st.markdown("---")
    
    # Vis miljøinfo
    show_environment_info()
    
    st.markdown("---")
    st.info("💡 Når dette fungerer, kan du gå tilbake til hovedappen!")

if __name__ == "__main__":
    main()
