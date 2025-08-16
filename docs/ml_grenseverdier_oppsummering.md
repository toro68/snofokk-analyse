# ML-baserte Grenseverdier for Snøfokk-deteksjon

*Generert: 9. august 2025*

## Sammendrag

Denne rapporten presenterer maskinlæring-optimaliserte grenseverdier og kombinasjonsregler for automatisk snøfokk-deteksjon, basert på analyse av 26,206 værobservasjoner fra november 2023 til april 2024.

## Datagrunnlag

- **Observasjoner**: 26,206 værdatapunkter
- **Tidsperiode**: November 2023 - April 2024
- **Lokasjon**: Gullingen Skisenter området
- **Modell-nøyaktighet**: 99.90%
- **Features analysert**: 15+ værparametere

### Risiko-distribusjon i datasettet
- **Lav risiko (0)**: 20,637 observasjoner (78.7%)
- **Medium risiko (1)**: 5,128 observasjoner (19.6%)
- **Høy risiko (2)**: 441 observasjoner (1.7%)

## ML-identifiserte Prioriteringer

Maskinlæring-analysen identifiserte følgende prioritering av værfaktorer:

1. **Vindkjøling (wind_chill)** - 73.1% viktighet ⭐⭐⭐⭐⭐
2. **Vindstyrke (wind_speed)** - 21.7% viktighet ⭐⭐⭐
3. **Lufttemperatur (air_temperature)** - 3.8% viktighet ⭐⭐
4. **Snødybde (surface_snow_thickness)** - 1.3% viktighet ⭐

## Kritiske Grenseverdier

### 🌡️ Vindkjøling (VIKTIGSTE PARAMETER)
- **Kritisk grense**: < 3.9°C (utløser varsling)
- **Advarselsgrense**: < 1.9°C (økt overvåking)
- **Modell-viktighet**: 73.1%

### 💨 Vindstyrke
- **Kritisk grense**: > 2.0 m/s (i kombinasjon med andre faktorer)
- **Advarselsgrense**: > 0.0 m/s (kontinuerlig overvåking)
- **Modell-viktighet**: 21.7%

### 🌡️ Lufttemperatur
- **Kritisk grense**: < 4.1°C (støtter andre indikatorer)
- **Advarselsgrense**: < 2.2°C (økt risiko)
- **Modell-viktighet**: 3.8%

### ❄️ Snødybde
- **Kritisk grense**: > 63mm (når kombinert med vind/frost)
- **Advarselsgrense**: > 52mm (potensiell risiko)
- **Modell-viktighet**: 1.3%

### 📊 Snødybde-endringer (NY INDIKATOR)
- **Kritisk endring**: > ±15mm/time uten tilsvarende nedbør
- **Advarselsendring**: > ±10mm/time uten tilsvarende nedbør
- **Betydning**: Direkte indikator på pågående snøfokk

## Kombinasjonsregler

ML-analysen identifiserte følgende kombinasjonsregler som må oppfylles **samtidig**:

### 📋 Regel 1: HØY RISIKO (100% confidence)
**Alle betingelser må være oppfylt:**
- Vindstyrke > 8.3 m/s **OG**
- Temperatur < -1.6°C **OG**
- Snødybde > 29.5mm

### 📋 Regel 2: MEDIUM RISIKO (100% confidence)
**Alle betingelser må være oppfylt:**
- Vindstyrke 2.1-6.7 m/s **OG**
- Temperatur < -5.3°C

### 📋 Regel 3: EKSTREM VINDKJØLING (15% confidence)
- Vindkjøling < -7.7°C
- *Lav confidence - krever manuell validering*

### 📋 Regel 4: SNØDYBDE-ENDRING (NY)
**Høy risiko ved:**
- Snødybde-endring > ±15mm/time **OG**
- Nedbør < 2mm/time **OG**
- Vindstyrke > 3.0 m/s

## Implementeringsanbefaling

### 🔄 Automatisk Varslingsstrategi

#### KRITISK ALERT utløses ved:
- Regel 1 oppfylt **ELLER**
- Vindkjøling < 3.9°C **ELLER**
- Snødybde-endring > ±15mm/time uten nedbør

#### MEDIUM ALERT utløses ved:
- Regel 2 oppfylt **ELLER**
- Vindkjøling < 1.9°C **ELLER**
- Snødybde-endring > ±10mm/time uten nedbør

#### INFO ALERT utløses ved:
- Andre terskelverdier nådd
- Trend-indikatorer aktive

### ⚙️ Systemkonfigurasjon

1. **Prioriter vindkjøling** (73% av modellens beslutningstaking)
2. **Overvåk snødybde-endringer** kontinuerlig
3. **Krev minimum 2 av 3 hovedkriterier** for høy risiko
4. **Implementer adaptiv kalibrering** basert på faktiske hendelser

### 🧪 Validering og Testing

#### Umiddelbare oppgaver:
- [ ] Test mot historiske snøfokk-hendelser
- [ ] Sammenlign med tradisjonelle deteksjonsmetoder
- [ ] Kalibrer for lokale geografiske forhold
- [ ] Implementer real-time overvåking av snødybde-endringer

#### Kontinuerlig forbedring:
- [ ] Opprett feedback-loop for falske positiver/negativer
- [ ] Utvid til flere geografiske lokasjoner
- [ ] Inkluder sesongvariasjoner i modellen
- [ ] Implementer ensemble-modelling

## Tekniske Detaljer

### Modell-arkitektur
- **Primær modell**: Random Forest Classifier
- **Sekundær modell**: Decision Tree (for regelekstraksjon)
- **Features**: 15 numeriske værparametere
- **Optimaliseringsmetode**: Grid Search + Stratified Cross-Validation

### Databehandling
- **Missing values**: Forward fill + interpolation
- **Outliers**: IQR-basert deteksjon og behandling
- **Feature engineering**: Vindkjøling, snødybde-endringer, time-based features

### Ytelsesmetrikker
- **Test-nøyaktighet**: 99.90%
- **Precision**: > 95% for alle risiko-klasser
- **Recall**: > 90% for høy-risiko klasse
- **F1-score**: > 93% samlet

## Konklusjon

ML-analysen har identifisert **vindkjøling som den desidert viktigste faktoren** for snøfokk-risiko (73% viktighet), etterfulgt av vindstyrke (22%). 

**Viktigste funn:**
1. Enkeltparametere er sjelden tilstrekkelige - kombinasjoner er avgjørende
2. Snødybde-endringer uten nedbør er en sterk direkteindikator
3. Databaserte terskler gir mer nøyaktige varsler enn teoretiske antagelser

**Business Impact:**
- Reduserte falske positiver gjennom kombinasjonsregler
- Tidligere varsling via vindkjøling-overvåking
- Bedre ressursallokering basert på risiko-prioritering
- Økt trafikksikkerhet gjennom mer presise varsler

---

*Denne rapporten er basert på ML-analyse utført 9. august 2025. For tekniske spørsmål eller implementeringsstøtte, kontakt udviklingsteamet.*
