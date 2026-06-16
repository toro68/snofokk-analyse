# Snøfokk & Glatt Vei Analyse - Empirisk Validert System

## 🎯 **APP-FORMÅL: OPERASJONELL BESLUTNINGSSTØTTE FOR BRØYTEOPERATØRER**

**Appen gir brøyteoperatøren kunnskapsgrunnlag for vintervedlikehold-beslutninger:**

### 📊 **RASK OVERSIKT:**
- **Mengde nysnø**: Hvor mye snø har falt?
- **Risiko for snøfokk**: Vind + løssnø = driftproblemer?
- **Risiko for glatte veier**: Regn på snø/rimfrost?

### 📈 **GRUNDIG BELYSNING:**
- **Detaljerte grafer** for dypere væranalyse
- **Historiske sammenhenger** og trender

### ⚖️ **OPERASJONELLE TERSKLER:**

#### ❄️ **Nysnø-brøyting:**
- **6 cm våt snø** ELLER **12 cm lett tørr snø** → Brøyting iverksettes

#### 🌪️ **Snøfokk-brøyting:**
- **Vindblåst løssnø** → Veier blåser igjen
- **KRITISK**: Vinden kan blåse snøen vekk fra punktet under snøradaren
- **Løsning**: Kombinere snødybde + vinddata + værradar

#### 🧂 **Glattføre-strøing:**
- **Regn på snøkappe** → Glatte veier
- **Rimfrost** → Strøing nødvendig

#### 🚚 **Tunbrøyting:**
- **Akkumulert snø siste uke** → Tunbrøyting fredag (40-50 hytter)

---

Et norsk væranalysesystem for realistisk snøfokk- og glatt vei-risikovurdering basert på **empirisk validerte kriterier** og operasjonell relevans.

**SISTE OPPDATERING**: 22. februar 2026 - terskler revalidert mot `data/analyzed/broyting_weather_correlation_2025.csv` (166 hendelser)

## Status 2026-02 (kort)

- Aktiv app-entrypoint: `src/gullingen_app.py` (historisk referanse til `src/live_conditions_app.py` er utdatert).
- Terskler justert konservativt i `src/config.py` etter datagjennomgang:
  - `snowdrift.wind_speed_gust_warning_gate`: 9.0 → 8.5 → 7.0 (revalidert 22. feb 2026: 7.0 fanger 94% av bekreftede episoder + 2 tidligere missede)
- Prinsipp videre: warning-nivå kan finjusteres for recall, critical-nivå holdes konservativt.

## Siste kalibrering (1. mars 2026)

- Terskler er revalidert mot:
  - historisk datasett (`data/analyzed/broyting_weather_correlation_2025.csv`)
  - ny driftsperiode (`data/analyzed/arbeidstidsrapport_2025-11-01_til_2026-03-01.csv`) koblet mot Frost 1H.
- Arbeidstyper behandles som multi-label i analyse (vei + tun kan skje i samme økt).
- Kun `src/config.py` er autoritativ kilde for tallverdier (`settings.*`).

Metodikk og validering:
- `docs/terskler_og_validering.md`
- `data/analyzed/ANALYSIS_METHOD_GUIDE.md`

### Reell terskelverifisering (2026-06-16)

Tersklene er uavhengig revalidert mot empiriske vær- og brøytedata. Sentralt
prinsipp: **brøyting er reaktivt og ikke synkront med været** – derfor evalueres
været i et 12-timers vindu *før* hver vedlikeholdsøkt, ikke på brøytetidspunktet.
Brøyting brukes som støtteevidens for operasjonell relevans, ikke som synkron fasit.

Verifisert mot 163 episoder (`broyting_weather_correlation_2025.csv`) som binære
klassifikatorer (scenario vs. resten):

|Hendelse|Terskel (`settings.*`)|TPR|FPR|
|---|---|---|---|
|SNØFOKK|gust ≥ 14 + vind-gate ≥ 7 + frost + snø ≥ 3 cm|0.89|0.02|
|SLAPS|precip₁₂ₕ ≥ 5 mm + temp ∈ [0, 4] °C|0.92|0.00|
|FRYSEFARE|bakke < 0 °C + luft ∈ [0, 3] °C|0.89|0.13|
|NYSNØ|snøøkning ≥ 4 cm eller precip ≥ 5 mm ved frost|0.76|0.11|

Konklusjon: tersklene er empirisk konsistente; ingen endring anbefalt. SNØFOKK/SLAPS
er svært godt kalibrert. NYSNØ/FRYSEFARE har lavere presisjon av iboende fysiske
årsaker (vindtransport på snømåler; sikkerhetskritisk recall-prioritering), ikke
feil terskelverdier. Full metodikk + reproduksjon: `docs/terskler_og_validering.md`.

## 🎯 **VÆRELEMENTER: 11 HENTES I PRODUKSJON**

> ⚠️ **VIKTIG FOR FREMTIDIGE GJENNOMGANGER (verifisert 2026-06-16):**
> Elementlisten under stammer fra en **ML-feature-importance-analyse**. Den
> rangeringen holder **ikke** når elementene testes som faktiske
> terskel-/scenariodiskriminatorer. Appen henter bevisst kun **11 elementer**
> (`StationConfig.CORE_ELEMENTS` + `EXTENDED_ELEMENTS` i `src/config.py`).
>
> SN46220 tilbyr 107 elementer (sjekk: `curl` mot
> `observations/availableTimeSeries/v0.jsonld?sources=SN46220`). De tre
> høyt rangerte elementene som **ikke** hentes ble empirisk testet mot alle 163
> scenario-merkede episoder (12t-vindu før brøyting) og **forkastet** – ikke
> gjenta denne undersøkelsen uten ny data:
>
> |Element|Hvorfor forkastet|
> |---|---|
> |`accumulated(precipitation_amount)`|Løpende akkumulator (monotont økende, reset-er); redundant med `sum(precipitation_amount PT1H)` som gir timesdeltaet direkte|
> |`max_wind_speed(wind_from_direction PT1H)`|SNØFOKK-sektor TPR 0.72/FPR 0.42 – likt/dårligere enn `wind_from_direction` (0.78/0.43) som allerede hentes|
> |`sum(duration_of_precipitation PT1H)`|Som tilleggsfilter på dagens precip-terskel **senker** recall (SLAPS 0.92→0.88) uten å redusere FPR (allerede 0.00)|
>
> Konklusjon: de 11 hentede elementene er tilstrekkelige; tersklene er allerede
> godt validerte med dem. Se `docs/terskler_og_validering.md`.

**Rangering nedenfor: historisk ML-feature-importance (ikke prioritet for innhenting). ✅ = hentes i `CORE_ELEMENTS`/`EXTENDED_ELEMENTS`; ❌ = tilgjengelig men forkastet (se boks over).**

### ⭐ **KRITISKE ELEMENTER** (ML-viktighet):
1. ❌ `accumulated(precipitation_amount)` - Akkumulert nedbør (viktighet: 7468.9-7721.4) — *forkastet, se boks*
2. ✅ `wind_from_direction` - Vindretning (viktighet: 1582.1-2160.3)
3. ❌ `max_wind_speed(wind_from_direction PT1H)` - Maks vind per retning (viktighet: 1555.9-1980.5) — *forkastet, se boks*
4. ✅ `surface_snow_thickness` - Snødybde (viktighet: 1381.0-1442.2)
5. ✅ **`surface_temperature`** ✨ - Veioverflate-temperatur (viktighet: 1225.1-1226.8) - **REVOLUSJONERENDE**
6. ✅ `air_temperature` - Lufttemperatur (viktighet: 1197.3-1209.6)
7. ❌ **`sum(precipitation_amount PT10M)`** - 10-min nedbør (viktighet: 1037.7-1073.5) — *tilgjengelig, men ikke i bruk; PT1H dekker behovet*

### 🔥 **HØY PRIORITET** (ML-viktighet):
8. ✅ **`dew_point_temperature`** ✨ - Rimfrost-varsling - **FROST-SPESIALIST**
9. ✅ `relative_humidity` - Fuktighet
10. ❌ `sum(duration_of_precipitation PT1H)` - Nedbørsvarighet — *forkastet, se boks*
11. ✅ `wind_speed` - Vindhastighet
12. ✅ `sum(precipitation_amount PT1H)` - Timenedbør

### 📊 **MEDIUM PRIORITET** (ML-viktighet):
13. ✅ `max(wind_speed_of_gust PT1H)` - Vindkast
14. ✅ **`max(air_temperature PT1H)`** ✨ - Time-maksimum
15. ✅ **`min(air_temperature PT1H)`** ✨ - Time-minimum

### 🚀 **REELL NYTTE AV DE HENTEDE ELEMENTENE**:
- **`surface_temperature`**: høy frekvens = direkte måling av veioverflate for eksakt glattføre-risiko
- **`dew_point_temperature`**: Duggpunkt vs lufttemperatur = profesjonell rimfrost-prediksjon (snø vs regn)
- **`max/min(air_temperature PT1H)`**: Fanger korte tineperioder og frostepisoder innen hver time

**KRITISK**: Vinden kan blåse snøen vekk fra punktet under snøradaren - derfor er kombinasjonen av snødybde + vinddata + værradar essensiell.

---

## 🌐 **LIVE VÆRAPP - PRODUKSJONSKLART**

**Hovedapp (Streamlit)**: `src/gullingen_app.py` (entry point via `app.py`)
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
# Automatisk .venv-aktivering og oppdatering
./activate_env.sh

# Eller manuelt:
source .venv/bin/activate
streamlit run app.py
```

### Operasjonell logging (MEDIUM/HIGH)

Når du vil kjøre appen i flere dager og samle «treff» (kun `MEDIUM/HIGH`) sammen med hva vedlikehold faktisk var (brøyting/strøing), logger appen dette til CSV.

- Standard loggfil: `data/logs/operational_alerts.csv`
- Dedupe-state: `data/logs/operational_alerts_state.json` (hindrer duplikater ved Streamlit-reruns)

Styring via env/secrets:
- `OPERATIONAL_LOG_ENABLED` (default: `true`)
- `OPERATIONAL_LOG_PATH` (default: `data/logs/operational_alerts.csv`)
- `OPERATIONAL_LOG_STATE_PATH` (default: `data/logs/operational_alerts_state.json`)
- `FROST_CACHE_MAX_AGE_HOURS` (default: `12`) – maks alder på bufrede Frost-data ved fallback

Stans farevarsel ved nylig vedlikehold (via vedlikeholds-endepunktet):
- `MAINTENANCE_SUPPRESS_HOURS` (default: `3.0`) – hvis siste vedlikehold ser ut som brøyting/strøing og er nyere enn dette vinduet, settes alle kategorier til `LOW` (situasjonen «nullstilles» mens det brøytes/nylig er gjort).

Tips for «kjør i bakgrunnen» lokalt (macOS/Linux):
```bash
nohup streamlit run app.py --server.headless true --server.port 8501 > data/logs/streamlit.out 2>&1 &
tail -f data/logs/streamlit.out
```

## 🔗 Integrasjon: Vedlikeholds-API (Vintervakt)

For å nedjustere glattføre når veier er strødd/brøytet nylig:
- Se [docs/vintervakt_vedlikeholds_api.md](docs/vintervakt_vedlikeholds_api.md)

**Windows (PowerShell):**
```powershell
# Automatisk .venv-aktivering og oppdatering
.\activate_env.ps1

# Eller manuelt:
.venv\Scripts\Activate.ps1
streamlit run app.py
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

## � **VINTERVEDLIKEHOLD: REAKTIVT SYSTEM**

### 🔄 **FUNDAMENTAL FORSTÅELSE: VÆR → VEDLIKEHOLD**

**Vintervedlikehold er alltid en reaksjon på værhendelser:**

#### ❄️ **Brøyting:** Reagerer på snøfall
- **Snø må falle først** → deretter brøytes veiene
- **Langvarig snøfall** → brøyting kan pågå UNDER værhendelsen
- **Snøfokk** → veier blåser igjen og må gjenåpnes

##### 🏠 **Tunbrøyting (Spesialisert):**
- **Fredager**: Tunbrøyting av ca 40-50 hytter som respons på snøfall siste uke
- **Ellers i sesongen**: Enkeltbestillinger ved behov (ofte under 10 hytter)
- **Reaktivt system**: Basert på akkumulert snøfall siden forrige fredag

#### 🧂 **Strøing:** Reagerer på glattføre-forhold  
- **Regn på snøkappe** → skaper glatte veier → strøing
- **Rimfrost** → strøing nødvendig
- **Naturlig løsning**: Nysnø dekker glatte veier

##### 🧊 **Glattføre-typer:**
- **Rimfrost**: Sjeldent problem på snødekte fjellveier - luftfuktighet kondenserer til is på veioverflate ved klar himmel og frost
- **Freezing rain**: Regn som fryser ved kontakt med kald veioverflate  
- **Regn på snøkappe**: Regn smelter snø og refryser til is - HOVEDPROBLEMET
- **Freezing_hours**: Timer med stabil frost under 0°C - gir GODE kjøreforhold på snø (jo kaldere, desto bedre)

#### 🌨️ **Snøfokk-håndtering:** Reagerer på vindblåst snø
- **Løssnø + vindkjøling** må oppstå først
- **Veier blåser igjen** → må gjenåpnes
- **Forutsetninger**: Sammenhengende frost + tilgjengelig løssnø

#### ⏰ **Tidsmessig sammenheng:**
- **Kortvarige hendelser**: Vedlikehold ETTER værhendelse
- **Langvarige hendelser**: Vedlikehold kan pågå UNDER værhendelse
- **Forebyggende tiltak**: Minimal - hovedsakelig reaktivt system

## �🚨 **KRITISKE GLATTFØRE-KRITERIER**

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
- **`app.py`** - Streamlit Cloud entry point (kaller hovedapp)
- **`src/gullingen_app.py`** - Hovedapp (varsler + visualisering)
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
archive/                # Arkiverte filer (gamle script + data)
```

### 🗄️ **Arkiv-struktur:**
- **`archive/analysis_data/`** – Historiske analyseresultater (CSV/JSON/PNG) flyttet ut av `data/analyzed/`
- **`archive/analysis_docs/`** – Tidligere Markdown-rapporter og sammendrag
- **`archive/analysis_py/`** – Samlet katalog for eldre Python-skript (124 filer flyttet hit)
- **`archive/outdated_scripts/`** – Opprinnelig arkiv for utdaterte script (beholdt for historikk)
- **`archive/outdated_md_files/`** – 9 utdaterte MD-filer  
- **`archive/outdated_data/`** – Gamle data og logger
- **`archive/root_misc/`** – Opprydding fra rot (eldre logg-filer, plowman-prototyper, cache-mapper, osv.)

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Frost API access (Norwegian Meteorological Institute)

### Installation
```bash
# Clone and enter directory
cd alarm-system

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On macOS/Linux

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

# Run Streamlit app
streamlit run app.py
```

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
0 8 * * 5 cd /path/to/alarm-system && /path/to/.venv/bin/python scripts/reports/weekly_weather_report_v2_refactored.py
```

### LaunchD (Recommended)
See documentation for creating `.plist` files for more robust scheduling.

## 🌐 Web Deployment Options

1. **Streamlit Cloud** (Fastest)
2. **FastAPI + Docker** (Full control)
3. **Local server** (Internal use)

## Viktige funn fra dataanalyse

### Glatt vei
- Regn-pa-sno er hovedproblemet, ikke rimfrost
- Stabilt kaldt vaer gir gode kjoreforhold pa sno
- Temperaturoverganger skaper farlige forhold
- Snofall fungerer som naturlig stroing
- Bakketemperatur er bedre indikator enn lufttemperatur for is

### Snofokk
- Snofokk er sjeldnere enn tidligere antatt (kun 5% av sesongen)
- Mildvaer odelegger lossnoen og begrenser snofokk
- Vindkast er bedre trigger enn snittvind (21.9 vs 10.3 m/s)
- "Usynlig snofokk" (uten endring i malt snodybde) er den vanligste typen

### Metodikk
- Fysisk realisme over teoretiske modeller
- Operasjonell relevans over akademisk presisjon
- Terskler kalibrert mot 166 broytehistorikk-episoder (2022-2025)
- Se `docs/terskler_og_validering.md` for detaljer

## 📝 License

Internal use - Norwegian Weather Analysis System
