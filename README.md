# Snøfokk & Glatt Vei Analyse - Empirisk Validert System

Et norsk væranalysesystem for realistisk snøfokk- og glatt vei-risikovurdering basert på **empirisk validerte kriterier** og operasjonell relevans.

**SISTE OPPDATERING**: 12. august 2025 - Nedbørtype-klassifisering fullført og validert

## 🌐 **LIVE VÆRAPP - PRODUKSJONSKLART**

**Professional Live Conditions App**: `src/live_conditions_app.py`
- ✅ **Empirisk validert nedbørtype-klassifisering** (149 episoder)
- ✅ **Vindblåst snø-deteksjon** med korrekte terskler
- ✅ **Kombinert risikograf** (snøfokk + glattføre + slush)
- ✅ **Robust håndtering av manglende data**
- ✅ **Glattføre kun ved regn** (ikke vindblåst snø)
- Minimal datanedlasting (48 timer)
- Optimert for Gullingen Skisenter (SN46220)

### 🚀 **Rask Start:**

**Unix/macOS:**
```bash
# Automatisk venv-aktivering og oppdatering
./activate_env.sh

# Eller manuelt:
source venv/bin/activate
streamlit run src/live_conditions_app.py
```

**Windows (PowerShell):**
```powershell
# Automatisk venv-aktivering og oppdatering
.\activate_env.ps1

# Eller manuelt:
venv\Scripts\Activate.ps1
streamlit run src/live_conditions_app.py
```

## 🎯 **EMPIRISK VALIDERTE KRITERIER**

### 📊 **Nedbørtype-klassifisering (NYTT)**
Basert på analyse av 149 episoder med nedbør og vinddata:

#### 🌧️ **REGN**: 
- Temp > 0°C + snømengde MINKENDE + vind < 8 m/s
- Høy konfidens ved temp > 2°C

#### ❄️ **SNØ**: 
- Temp < -2°C + snømengde ØKENDE + vind < 8 m/s
- Høy konfidens ved temp < -3°C

#### 🌪️ **VINDBLÅST SNØ**: 
- **Høy konfidens**: Temp < 0°C + vind > 12 m/s + snø-reduksjon < -5 cm
- **Medium konfidens**: Temp < 0°C + vind > 10 m/s + snø-reduksjon < -3 cm
- **Median vindterskel**: 12.2 m/s
- **29 empiriske episoder** identifisert

#### 🌨️ **SNØ MED VINDPÅVIRKNING**: 
- Temp < 0°C + vind 6-10 m/s + liten snø-endring

#### 💧 **VÅT SNØ**: 
- Temp rundt 0°C + snømengde ØKENDE + moderat vind

## 🚨 **KRITISKE GLATTFØRE-KRITERIER**

### ⚠️ **VIKTIG: KUN REGN SKAPER GLATTFØRE**

**Empirisk validert regel**: VINDBLÅST SNØ ≠ GLATTFØRE
- ❌ **Vindblåst snø er IKKE regn** 
- ❌ **Vindblåst snø skaper IKKE glattføre**
- ✅ **Kun regn ved lav temperatur gir risiko**

### �️ **Glattføre-deteksjon:**
- **Høy risiko**: Regn + temp 0-2°C + tidligere frost
- **Medium risiko**: Regn + temp rundt 0°C
- **INGEN risiko**: Vindblåst snø (uavhengig av temperatur)

### 🎯 **Korrelasjon vind vs snømengde-endring:**
- **Kald** (< -2°C): -0.423 (sterk negativ korrelasjon)
- **Rundt frysing** (-2 til 0°C): -0.411 (sterk negativ korrelasjon)  
- **Lett pluss** (0 til 2°C): -0.165 (svak negativ korrelasjon)

## 🏔️ **SNØFOKK-ANALYSE FUNN**

### ❄️ **FYSISK REALISTISKE KRITERIER**

For snøfokk må **ALLE** følgende være oppfylt:

#### 🌨️ **Meteorologiske kriterier:**
- **Vindstyrke** ≥ 6 m/s
- **Temperatur** ≤ -1°C  
- **Snødybde** ≥ 3 cm

#### ❄️ **KRITISK: Løssnø-tilgjengelighet** 
- **Ingen mildvær** (>0°C) siste 24-48 timer
- **Sammenhengende frost** siste 12+ timer
- **Helst nysnø** (nedbør) siste 72 timer

### 📊 **SESONG 2023-2024 RESULTATER (Gullingen)**

- **27 snøfokk-perioder** totalt (fysisk realistisk)
- **310 timer** ekte snøfokk-forhold (13 døgn)
- **Kun 5.1%** av sesongen har snøfokk-risiko
- **Mildvær ødelegger løssnø** 69.3% av tiden

## 💻 **STREAMLIT-APP FUNKSJONER**

### 🎨 **Visualiseringer:**
1. **Kombinert risikograf** (snøfokk + glattføre + slush)
2. **Nedbørtype-klassifisering** (empirisk validert)
3. **Værtrender** med risikovurdering
4. **Robust fallback** for manglende data

### � **Tekniske features:**
- Empirisk validert `detect_precipitation_type()`
- Korrekt `is_slippery_road_risk()` (kun regn)
- Automatisk kolonne-deteksjon for nedbør
- Real-time data fra Frost API

## 📁 **RYDDIG PROSJEKTSTRUKTUR**

**Arkivering fullført 12. august 2025** - Systemet er nå produksjonsklart med kun relevante filer.

### 🎯 **Aktive filer (hovedmappen):**
- **`validert_glattfore_logikk.py`** - Empirisk validert hovedlogikk
- **6 dokumentasjonsfiler** - Kun aktuelle MD-filer
- **Konfigurasjon** - `.aigenrc`, `requirements.txt`, aktivering-script

### 📂 **Organiserte mapper:**
```
src/                    # Hovedapplikasjon (Streamlit)
scripts/                # Organiserte script etter kategori  
data/                   # Kun aktuelle data (gullingen-stasjon)
logs/                   # Relevante logger (app, alerts)
config/                 # Systemkonfigurasjoner
docs/                   # Teknisk dokumentasjon
models/                 # ML-modeller
tests/                  # Organiserte tester
archive/                # Arkiverte filer (33 script + data)
```

### 🗄️ **Arkiv-struktur:**
- **`archive/outdated_scripts/`** - 33 arkiverte Python-filer
- **`archive/outdated_md_files/`** - 9 utdaterte MD-filer  
- **`archive/outdated_data/`** - Gamle data og logger

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Frost API access (Norwegian Meteorological Institute)

### Installation
```bash
# Clone and enter directory
cd alarm-system

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### Configuration
1. Copy `config/test_config.json` and update with your settings
2. Set environment variables in `.env` file
3. Configure Frost API credentials

### Running

```bash
# Test the refactored weekly report
python scripts/reports/weekly_weather_report_v2_refactored.py --test

# Run the FINAL realistic snowdrift analysis (with loose snow criteria)
python scripts/analysis/revised_snowdrift_with_loose_snow.py

# Investigate available snow quality data
python scripts/analysis/investigate_snow_quality_data.py

# Run Streamlit app (if available)
streamlit run src/snofokk/app.py
```

### Key Analysis Scripts

- **`revised_snowdrift_with_loose_snow.py`**: Final realistic analysis with physical loose snow criteria
- **`investigate_snow_quality_data.py`**: Investigates available parameters for loose snow assessment
- **`realistic_snowdrift_analyzer.py`**: Basic realistic grouping without loose snow criteria
- **`diagnose_snowdrift_data.py`**: Diagnostic tool for understanding data quality and distributions

## 🔧 Development

### Modern Architecture (NEW - v2.1)
- **Modular design**: Services separated by responsibility
- **Modern configuration**: Pydantic settings with environment variables
- **Type safety**: Full type hints and data models
- **Error handling**: Robust error handling and logging
- **Caching**: LRU cache for API calls
- **Plotting**: Improved matplotlib with better data handling

### Key Services
- `WeatherService`: Frost API integration with caching
- `AnalysisService`: Snow drift risk calculation
- `PlottingService`: Visualization generation

### Legacy Support
The old `weekly_weather_report_v2.py` is kept for compatibility, but the new refactored version is recommended.

## 📊 Features

- **Weather Data**: Real-time data from Norwegian Met Office
- **Risk Analysis**: Snow drift risk assessment
- **Alerting**: Automated email notifications
- **Visualization**: Interactive plots and graphs
- **ML Optimization**: Parameter optimization for risk models
- **Scheduling**: Cron/launchd integration for automated reports

## 📅 Scheduling (macOS)

### Cron (Simple)
```bash
# Edit crontab
crontab -e

# Add line for Friday 8 AM
0 8 * * 5 cd /path/to/alarm-system && /path/to/venv/bin/python scripts/reports/weekly_weather_report_v2_refactored.py
```

### LaunchD (Recommended)
See documentation for creating `.plist` files for more robust scheduling.

## 🌐 Web Deployment Options

1. **Streamlit Cloud** (Fastest)
2. **FastAPI + Docker** (Full control)
3. **Local server** (Internal use)

## 🎯 REVOLUSJONERENDE ERKJENNELSER

### 💡 **Glatt Vei-Analyse:**
1. ✅ **Regn-på-snø** er hovedproblemet - ikke rimfrost
2. ✅ **Stabilt kaldt vær** = beste kjøreforhold på snø
3. ✅ **Temperaturoverganger** skaper farlige forhold
4. ✅ **Snøfall fungerer som naturlig strøing**
5. ✅ **Mars er verst** pga vårløsning og ustabile temperaturer
6. ✅ **99 realistiske perioder** vs 420 urealistiske (rimfrost-fokus)

### ❄️ **Snøfokk-Analyse:**
1. ✅ **Snøfokk er MYE sjeldnere** enn tidligere antatt
2. ✅ **Mildvær er den kritiske begrensende faktoren**
3. ✅ **240 mildvær-perioder** ødelegger løssnø regelmessig
4. ✅ **Høyere andel ekstreme episoder** når løssnø er tilstede
5. ✅ **"Usynlig snøfokk"** er den vanligste typen

### 🔬 **Metodiske gjennombrudd:**
- **Fysisk realisme** over teoretiske modeller
- **Operasjonell relevans** over akademisk presisjon  
- **Periode-definisjon** basert på faktisk varighets-krav
- **Ekskludering** av beskyttende faktorer (snøfall for glatt vei)
- **Inkludering** av begrensende faktorer (mildvær for snøfokk)

> **"Dette er de mest realistiske analysene av norske vinterforhold!"**

## 📝 License

Internal use - Norwegian Weather Analysis System
