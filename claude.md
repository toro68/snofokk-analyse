# Claude AI Assistant Documentation

## Project Context
This is a Norwegian weather analysis system for realistic snowdrift and slippery road risk assessment.

## Key Information

### Station Details
- **Primary Station**: Gullingen Skisenter (SN46220)  
- **Location**: 639m above sea level
- **Data Source**: Norwegian Meteorological Institute (Frost API)
- **Available Elements**: 116 weather elements across 20 categories
- **Data History**: February 2018 onwards

### Core Weather Elements (FULLY VALIDATED - 15 elements)
**Based on empirical analysis of 19 critical elements tested against actual maintenance events**

#### ⭐ CRITICAL ELEMENTS (7 - must have):
1. `accumulated(precipitation_amount)` - Accumulated precipitation (7468.9 importance score)
2. `wind_from_direction` - Wind direction (1582.1-2160.3 score range)
3. `max_wind_speed(wind_from_direction PT1H)` - Max wind per direction (1555.9-1980.5 score)
4. `surface_snow_thickness` - Snow depth (1381.0-1442.2 score)
5. **`surface_temperature`** ✨ - Road surface temperature (1225.1-1226.8 score) - REVOLUTIONARY for slippery roads
6. `air_temperature` - Air temperature (1197.3-1209.6 score)
7. **`sum(precipitation_amount PT10M)`** ✨ - 10-min precipitation (1037.7-1073.5 score) - 6x better resolution

#### 🔥 HIGH PRIORITY (5 - improves precision):
8. **`dew_point_temperature`** ✨ - Frost warning specialist (24 obs/day)
9. `relative_humidity` - Humidity analysis (24 obs/day)
10. `sum(duration_of_precipitation PT1H)` - Precipitation duration
11. `wind_speed` - Basic wind speed (24 obs/day)
12. `sum(precipitation_amount PT1H)` - Hourly precipitation

#### 📊 MEDIUM PRIORITY (3 - specialized measurements):
13. `max(wind_speed_of_gust PT1H)` - Wind gusts (24 obs/day)
14. **`max(air_temperature PT1H)`** ✨ - Hourly maximum temperature (24 obs/day)
15. **`min(air_temperature PT1H)`** ✨ - Hourly minimum temperature (24 obs/day)

### 🚀 CRITICAL BREAKTHROUGHS FROM 19-ELEMENT ANALYSIS:

#### 🌡️ **`surface_temperature`** - GAME CHANGER:
- **Importance**: #5-6 across ALL operational categories
- **Data Quality**: 168 observations/day (HIGHEST frequency!)
- **Operational Value**: Direct road surface measurement = exact slippery road risk
- **Unique Value**: Distinguishes between air frost and actual road ice

#### ⏱️ **`sum(precipitation_amount PT10M)`** - PRECISION BOOST:
- **Importance**: #7 across ALL categories
- **Data Quality**: 144 observations/day (6x higher than hourly measurements)
- **Operational Value**: 10-minute resolution = precise timing of snowfall
- **Unique Value**: Captures short, intense snow bursts

#### 💧 **`dew_point_temperature`** - FROST SPECIALIST:
- **Data Quality**: 24 observations/day
- **Operational Value**: Dew point vs air temperature = frost prediction
- **Unique Value**: Predicts when humidity condenses to ice

**CRITICAL**: Wind can blow snow away from the point under the snow radar - therefore the combination of snow depth + wind data + weather radar is essential.

--- 

## 🔄 **KRITISK FORSTÅELSE: VINTERVEDLIKEHOLD ER REAKTIVT**

### 🌨️ **Fundamental Logikk: VÆR → VEDLIKEHOLD**

**Vintervedlikehold er alltid en reaksjon på værhendelser - dette er KRITISK for all analyse:**

#### ❄️ **Brøyting:** Reagerer på snøfall
- **Snø må falle først** → deretter brøytes veiene
- **Langvarig snøfall** → brøyting kan pågå UNDER værhendelsen  
- **Snøfokk** → veier blåser igjen og må gjenåpnes
- **Timing**: Ofte tidlig morgen etter natts snøfall

##### 🏠 **Tunbrøyting (Spesialisert):**
- **Fredager**: Tunbrøyting av ca 40-50 hytter som respons på snøfall siste uke
- **Ellers i sesongen**: Enkeltbestillinger ved behov (ofte under 10 hytter) 
- **Reaktivt system**: Basert på akkumulert snøfall siden forrige fredag
- **Ukentlig syklus**: Fast fredag-rytme for største operasjoner

#### 🧂 **Strøing:** Reagerer på glattføre-forhold
- **Regn på snøkappe** → skaper glatte veier → strøing
- **Rimfrost** → strøing nødvendig
- **Naturlig løsning**: Nysnø kan dekke glatte veier
- **Timing**: Reaktivt når glatte forhold oppstår

##### 🧊 **Glattføre-definisjoner:**
- **Rimfrost**: Sjeldent problem på snødekte fjellveier - luftfuktighet kondenserer til is på veioverflate ved klar himmel og frost
- **Freezing rain**: Regn som fryser ved kontakt med kald veioverflate
- **Regn på snøkappe**: Regn smelter snø og refryser til is - HOVEDPROBLEMET  
- **Freezing_hours**: Timer med stabil frost under 0°C - gir GODE kjøreforhold på snø (jo kaldere, desto bedre)

#### 🌨️ **Snøfokk-håndtering:** Reagerer på vindblåst snø
- **Løssnø + vindkjøling** må oppstå først
- **Veier blåser igjen** → må gjenåpnes
- **Forutsetninger**: Sammenhengende frost + tilgjengelig løssnø
- **Timing**: Under og etter vindstorme

### ⏰ **Temporal Sammenheng**

#### 🔄 **Reaktivt System:**
- **Kortvarige hendelser**: Vedlikehold skjer ETTER værhendelse
- **Langvarige hendelser**: Vedlikehold kan pågå UNDER værhendelse  
- **Forebyggende tiltak**: Minimal - hovedsakelig reaktivt system

#### 📊 **Dataimplementasjon:**
- **Brøyting-mønstre** indikerer hvor/når værhendelser skjer
- **Temporal clustering** viser reaktiv respons
- **Tidsmønstre** (morgen-aktivitet) bekrefter reaktiv logikk

### 🎯 **Betydning for Analyse**

#### 📈 **Korrelasjon:**
- **Høy korrelasjon** forventes mellom vær og påfølgende vedlikehold
- **Tidsforsinkelse** mellom værhendelse og respons
- **Clustering** av operasjoner indikerer samme værhendelse

#### 🤖 **Prediktive Modeller:**
- **Værhendelser** kan predikere fremtidig vedlikeholdsbehov
- **Reaktive mønstre** gir lavere datakrav enn proaktive systemer
- **Vintersesong** er hovedfokus for modellering

### 💡 **Praktiske Implikasjoner**

#### 🔍 **Dataanalyse:**
- **Brøyting-data** er en proxy for værhendelser
- **Operasjonsmønstre** reflekterer værmønstre
- **Temporal gap** mellom operasjoner indikerer værpause

#### 🚀 **Systremutvikling:**
- **Real-time værovervåking** kan forbedre responstid
- **Prediktive varsler** kan optimalisere ressursplanlegging
- **Automatisk triggering** basert på værkriterier

---
*Dokumentert 16. august 2025 - Fundamental forståelse for alle værbørte systemer*
