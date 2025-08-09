# LIVE FØREFORHOLD WEB APP - DEPLOYMENT GUIDE
# ==========================================

## 🚀 HVORDAN KJØRE NETTSIDEN

### 1. LOKAL UTVIKLING
```bash
# Gå til prosjekt-mappen
cd /Users/tor.inge.jossang@aftenbladet.no/dev/alarm-system

# Installer Streamlit (hvis ikke gjort)
pip install streamlit matplotlib

# Start web app
streamlit run src/live_conditions_app.py
```

Nettsiden åpnes på: http://localhost:8501

### 2. CLOUD DEPLOYMENT (Gratis alternativer)

#### A) STREAMLIT CLOUD (Enklest)
1. Push koden til GitHub
2. Gå til share.streamlit.io
3. Koble til GitHub repo
4. Deploy!

#### B) HEROKU (Mer kontroll)
```bash
# Opprett Procfile
echo "web: streamlit run src/live_conditions_app.py --server.port=$PORT --server.address=0.0.0.0" > Procfile

# Deploy til Heroku
heroku create foereforhold-gullingen
git push heroku main
```

#### C) RAILWAY (Moderne alternativ)
1. Koble Railway til GitHub
2. Automatisk deployment ved push

### 3. LOKAL NETTVERK (Hjemme/kontor)
```bash
# Start med ekstern tilgang
streamlit run src/live_conditions_app.py --server.address=0.0.0.0

# Åpne i nettlesere på lokalt nettverk:
# http://[din-ip]:8501
```

## ⚡ YTELSESOPTIMALISERING

### 🔧 DATAEFFEKTIVITET

#### 1. MINIMAL API-BRUK
```python
# ✅ Kun 5 kritiske parametere (vs 20+ tidligere)
elements = [
    'air_temperature',      # Snøfokk + glatt vei
    'wind_speed',          # Snøfokk  
    'surface_snow_thickness', # Begge
    'sum(precipitation_amount PT1H)', # Glatt vei
    'relative_humidity'     # Glatt vei (kun når tilgjengelig)
]

# ✅ Kun siste 48 timer (vs hele sesonger)
hours_back = 48  # Ca 100 målinger vs 26,000+
```

#### 2. SMART CACHING
```python
# ✅ LRU cache på datahentig (1 time)
@lru_cache(maxsize=10)
def get_current_weather_data(hours_back: int = 48):
    # Unngår API-kall ved hver refresh
    
# ✅ Streamlit's innebygde caching
@st.cache_data(ttl=3600)  # 1 time cache
```

#### 3. RASK API-RESPONS
```python
# ✅ Performance Category C (raskere)
'performanceCategory': 'C'

# ✅ Kun nødvendige timeoffsets
'timeoffsets': 'PT0H'  # Kun hovedmålinger
```

### 📊 BRUKEROPPLEVELSE

#### Auto-refresh strategier:
```python
# Alternativ 1: Auto-refresh hver 5 min
time.sleep(300)
st.rerun()

# Alternativ 2: WebSocket updates (avansert)
# Alternativ 3: Manual refresh-knapp (implementert)
```

#### Progressive loading:
```python
# Vis cached data først, hent nye i bakgrunnen
with st.spinner("Oppdaterer data..."):
    # Last cached først
    show_cached_results()
    # Hent nye data asynkront
    update_in_background()
```

## 🎨 BRUKERGRENSESNITT

### Fargekoding:
- 🟢 **GRØNN**: Stabile/trygge forhold
- 🟡 **GUL**: Moderat risiko/vær oppmerksom  
- 🔴 **RØD**: Høy risiko/unngå kjøring

### Informasjonshierarki:
1. **Hovedstatus** (store, tydelige meldinger)
2. **Nøkkeldata** (temperatur, vind, snø)
3. **Detaljer** (faktorer, scenario)
4. **Trend** (graf siste 24t)

## 🔒 SIKKERHET & BEGRENSNINGER

### API-nøkkel håndtering:
```bash
# .env fil (IKKE i git!)
FROST_CLIENT_ID=din_frost_api_nokkel

# Eller miljøvariabler i deployment
export FROST_CLIENT_ID=din_nokkel
```

### Rate limiting:
- **Frost API**: 20,000 requests/måned gratis
- **Med caching**: ~500 requests/måned reell bruk
- **Sikkerhetsmargin**: 1 time cache = 720 requests/måned

### Feilhåndtering:
```python
# Graceful degradation
if api_fails():
    show_cached_data()
    display_warning("Bruker cached data")
```

## 📱 MOBILE-OPTIMALISERING

### Streamlit mobile support:
```python
# Responsive layout
st.set_page_config(layout="wide")

# Mobile-friendly metrics
col1, col2 = st.columns(2)  # Ikke 4+ på mobil
```

### PWA (Progressive Web App):
- Kan kjøres som "app" på mobil
- Offline-cached data
- Push-notifications (avansert)

## 🚦 DEPLOYMENT ANBEFALINGER

### Produksjon:
1. **Streamlit Cloud** (gratis, enkelt)
2. **DigitalOcean App Platform** (billig, skalerbar)
3. **AWS/Azure** (enterprise)

### Staging:
1. **Lokal testing** (alltid først)
2. **GitHub Codespaces** (cloud-utvikling)
3. **Railway preview** (PR-basert testing)

### Monitorering:
```python
# Logging av bruk
import logging
logging.info(f"User accessed at {datetime.now()}")

# Health checks
def health_check():
    return {"status": "ok", "last_update": last_data_fetch}
```

## 💡 FREMTIDIGE FORBEDRINGER

### Kort sikt:
- [ ] Flere værstasjonr (dropdown)
- [ ] Email/SMS-varsler ved høy risiko
- [ ] Historikk-visning (siste uke)

### Lang sikt:
- [ ] Kart-visning med flere stasjoner
- [ ] ML-baserte prediksjoner
- [ ] API for andre applikasjoner
- [ ] Mobile app (React Native/Flutter)

## 🛠️ TEKNISK STACK

```
Frontend:  Streamlit (Python)
Backend:   Samme process (enkel arkitektur)
API:       Frost.met.no (Norwegian Met Office)
Caching:   Python LRU Cache + Streamlit cache
Plotting:  Matplotlib
Deployment: Streamlit Cloud / Heroku / Railway
```

**TOTAL SETUP TID: 10-30 minutter!** 🚀
