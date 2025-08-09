# Snøfokk & Glatt Vei Analyse - Fysisk Realistisk Vurdering

Et norsk væranalysesystem for realistisk snøfokk- og glatt vei-risikovurdering basert på **fysisk korrekte kriterier** og operasjonell relevans.

**SISTE OPPDATERING**: Kritisk gjennomgang med korrekt Gullingen stasjon (SN46220) - alle analyser er rerun og validert.

## 🌐 **LIVE VÆRAPP TILGJENGELIG**

**Professional Live Conditions App**: `src/live_conditions_app.py`
- Minimal datanedlasting (48 timer)
- Profesjonelt grensesnitt uten emoji-støy
- Real-time snøfokk og glatt vei-risiko
- Sesongbevisst analyse (sommer/vinter)
- Optimert for Gullingen Skisenter (SN46220)

### 🚀 **Rask Start (alltid aktiver venv):**

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

## 🚨 KRITISKE FUNN: Glatt Vei-Analyse

### 🌧️❄️ **REGN-PÅ-SNØ: Det egentlige problemet!**

Omfattende analyse av sesongen 2023-2024 (Gullingen SN46220) avslører at **REGN PÅ SNØDEKTE VEIER** - ikke rimfrost - er hovedårsaken til farlige kjøreforhold:

#### 📊 **Nøkkelresultater:**
- **99 farlige perioder** per vintersesong (realistisk!)
- **460 timer** (19.2 døgn) med regn-på-snø forhold = **1.8% av vinteren**
- **Gjennomsnittlig varighet**: 4.6 timer per episode

#### 🎭 **To hovedscenarier:**
1. **🌧️ Regn på snø (mildvær)**: 49 perioder
   - Mildvær 0-4°C + regn på eksisterende snødekke  
   - Snøen smelter og blir til is/slush

2. **🧊 Frysing etter mildvær**: 50 perioder
   - Temperatur faller under 0°C etter mildværsperiode
   - Våt snø/slush fryser til farlige is-lag

#### 📅 **Sesongrealisme** (månedlig fordeling):
- **November**: 4 perioder (vinterstart)
- **Desember**: 10 perioder 
- **Januar**: 20 perioder 
- **Februar**: 25 perioder 
- **Mars**: 29 perioder (**VERST** - vårløsning!)
- **April**: 11 perioder (vinterslutt)

#### 🏆 **Værste episoder registrert:**
1. **23-24 januar 2024**: 22 timer, 41mm regn på 60cm snø
2. **02 februar 2024**: 11 timer, 20mm regn på 83cm snø  
3. **15-16 februar 2024**: 11 timer, 26mm regn på 58cm snø

### ✅ **KRITISK ERKJENNELSE:**
> **"Stabilt kaldt vær er ensbetydende med gode kjøreforhold på snødekte veier"**

Det er **TEMPERATUROVERGANGENE** - ikke konstant kaldt vær - som skaper farlige forhold!

#### ❌ **FEIL fokus (tidligere):**
- Rimfrost-kriterier: 45 perioder
- Fokus på lave temperaturer + fuktighet
- Ignorerte snøfall som beskyttende faktor

#### ✅ **RIKTIG fokus (oppdatert):**
- **Regn-på-snø kriterier**: 99 perioder
- Mildvær (0-4°C) + regn på snødekt vei
- **Snøfall >0.3mm/h BESKYTTER mot glatte forhold**

## 🏔️ Snøfokk-Analyse Funn

### ❄️ **FYSISK REALISTISKE SNØFOKK-KRITERIER**

For at snøfokk skal kunne oppstå må **ALLE** følgende være oppfylt:

#### 🌨️ **1. Grunnleggende meteorologiske kriterier:**
- **Vindstyrke** ≥ 6 m/s
- **Temperatur** ≤ -1°C  
- **Snødybde** ≥ 3 cm

#### ❄️ **2. KRITISK: Løssnø-tilgjengelighet** 
- **Ingen mildvær** (>0°C) siste 24-48 timer
- **Sammenhengende frost** siste 12+ timer
- **Helst nysnø** (nedbør) siste 72 timer

#### 🎯 **3. Data-kvalitetskrav:**
- Gyldig vinddata tilgjengelig
- Temperaturdata for siste 24-48t

### 📊 **SESONG 2023-2024 RESULTATER (Gullingen)**

Med fysisk realistiske kriterier:
- **27 snøfokk-perioder** totalt (ikke 64!)
- **310 timer** ekte snøfokk-forhold (13 døgn)
- **Kun 5.1%** av sesongen har snøfokk-risiko
- **Mildvær ødelegger løssnø** 69.3% av tiden

#### **Intensitetsfordeling:**
- **EKSTREM**: 5 perioder (18.5%) - høyere andel enn tidligere!
- **ALVORLIG**: 4 perioder (14.8%)
- **MODERAT**: 6 perioder (22.2%) 
- **LETT**: 12 perioder (44.4%)

### 🚨 **FEBRUAR 8-11, 2024 KRISE - BEKREFTET!**

Selv med strenge løssnø-kriterier:
- **6 snøfokk-perioder** med tilstrekkelig løssnø
- **82 timer** med ekte snøfokk-forhold
- **4 EKSTREME perioder** (maks 15.9 m/s)
- **GOOD snøkvalitet** i alle perioder

#### **Mest ekstreme episoder:**
1. **1-4. januar 2024**: 74 timer (16.2 m/s)
2. **10-11. februar 2024**: 33 timer krise (15.9 m/s)
3. **11-12. februar 2024**: 32 timer fortsatt krise (14.5 m/s)
4. **27-31. desember 2023**: 27 timer (18.6 m/s!)

### 💡 **Revolusjonerende erkjennelser:**

1. ✅ **Snøfokk er MYE sjeldnere** enn tidligere antatt
2. ✅ **Mildvær er den kritiske begrensende faktoren**
3. ✅ **240 mildvær-perioder** ødelegger løssnø regelmessig
4. ✅ **Høyere andel ekstreme episoder** når løssnø er tilstede
5. ✅ **"Usynlig snøfokk"** er den vanligste typen

Dette er den **FYSISK MEST REALISTISKE** snøfokk-analysen for norske forhold!

## 📁 Project Structure

```
alarm-system/
├── src/snofokk/                    # Core application package
│   ├── __init__.py
│   ├── config.py                   # Modern configuration management
│   ├── models.py                   # Data models and type definitions
│   └── services/                   # Service layer
│       ├── __init__.py
│       ├── weather.py              # Weather data fetching (Frost API)
│       ├── analysis.py             # Snow drift risk analysis
│       └── plotting.py             # Visualization services
│
├── scripts/                        # Organized executable scripts
│   ├── reports/                    # Report generation scripts
│   │   ├── weekly_weather_report_v2_refactored.py  # Main weekly report (NEW)
│   │   ├── weekly_weather_report_v2.py             # Legacy weekly report
│   │   ├── weekly_weather_report.py                # Original version
│   │   └── daily_report.py                         # Daily reporting
│   ├── analysis/                   # Analysis scripts
│   │   ├── analyze_historical_data.py
│   │   ├── analyze_snowdrift.py
│   │   ├── analyze_slippery_roads.py
│   │   ├── analyze_historical.py
│   │   ├── analyze_seasons.py
│   │   ├── season_periods_analyzer.py              # Snowdrift period grouping
│   │   ├── cached_major_periods_analyzer.py        # Cached analysis with caching
│   │   ├── diagnose_snowdrift_data.py              # Data diagnostic script
│   │   ├── realistic_snowdrift_analyzer.py         # Basic realistic analysis
│   │   ├── investigate_snow_quality_data.py        # Loose snow investigation
│   │   └── revised_snowdrift_with_loose_snow.py    # FINAL: Physical realistic analysis
│   ├── alerts/                     # Alert/notification scripts
│   │   ├── snowdrift_alert.py
│   │   ├── snow_accumulation_alert.py
│   │   └── slippery_roads_alert.py
│   └── utils/                      # Utility scripts
│       ├── fetch_netatmo_data.py
│       ├── generate_weather_map.py
│       ├── extract_dates.py
│       ├── plot_snowdrift_timeline.py
│       ├── plow_planning.py
│       ├── precipitation_type.py
│       └── check_last_plowing.py
│
├── config/                         # Configuration files
│   ├── test_config.json           # Test configuration
│   └── alert_config.json          # Alert settings
│
├── data/                          # Data storage
│   ├── analyzed/                  # Analysis results
│   ├── db/                        # Database files
│   ├── graphs/                    # Generated plots
│   ├── maps/                      # Map files
│   ├── models/                    # ML models
│   └── raw/                       # Raw data files
│
├── logs/                          # Application logs
├── models/                        # ML model artifacts
├── tests/                         # Test files
├── archive/                       # Archived/legacy files
│   ├── legacy_root_files/         # Old root directory files
│   ├── legacy_data_src/           # Old src structure
│   ├── arkivert/                  # Archived scripts
│   ├── data/                      # Archived data
│   └── logs/                      # Archived logs
│
├── venv/                          # Python virtual environment
├── requirements.txt               # Python dependencies
├── .env                          # Environment variables (not in git)
├── .gitignore                    # Git ignore rules
└── README.md                     # Project documentation
```

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
