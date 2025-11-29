# Agent: Føreforhold Gullingen

## 🎯 Formål

Varslingssystem for **brøytemannskaper** og **hytteeiere** ved Gullingen Skisenter.

Systemet skal gi tidlig varsling om:
1. **Nysnø** - Behov for brøyting
2. **Snøfokk** - Redusert sikt, snødrev på veier
3. **Slaps** - Tung snø/vann-blanding, vanskelig fremkommelighet
4. **Glatte veier** - Regn på snø, is, rimfrost

> **Kilde**: Kriterier validert mot historiske værdata (Frost API) og brøyterapporter 2022-2025.

---

## 🔗 Live ressurser

### Brøytekart (sanntid)
**URL**: https://plowman-new.snøbrøyting.net/nb/share/Y3VzdG9tZXItMTM=

Viser:
- GPS-posisjon for brøytebiler
- Brøytet vs ubrøytet vei
- Tidspunkt for siste brøyting

### Værstasjoner
| Stasjon | Type | Koordinat | Høyde |
|---------|------|-----------|-------|
| SN46220 Gullingen | Frost API | 59.1822°N, 6.0789°Ø | 639 moh |
| Fjellbergsskardet | Netatmo | 59.39205°N, 6.42667°Ø | 607 moh |

---

## 🎨 Designprinsipper

### Emoji-bruk
- ✅ Enkle statusikoner: 🟢 🟡 🔴 ⚠️ ✅ ❌
- ✅ Enkle værikoner: ❄️ 🌬️ 🧊
- ❌ Ikke bruk: Hytter, biler, komplekse symboler, flagg, figurer
- Hold det profesjonelt og lesbart

---

## 📊 Datagrunnlag for validering

### Brøytedata
- **Kilde**: `data/analyzed/Rapport 2022-2025.csv`
- **Periode**: Desember 2022 - April 2025
- **166 brøyteepisoder** analysert
- **Fordeling**: Januar (52), Desember (45), Februar (44), Mars (16)

### Værdata  
- **Kilde**: Frost API, stasjon SN46220 Gullingen (639 moh)
- **Elementer**: Temperatur, vind, nedbør, snødybde, fuktighet
- **Korrelert mot brøytinger**: 6 timer før/under/etter

### Hovedutløsere for brøyting (korrelasjon)
| Faktor | Korrelasjon | Kommentar |
|--------|-------------|-----------|
| Frysetimer | 0.28 | Sterkest utløser |
| Snødybdeendring | 0.20 | Nysnø-indikator |
| Snøtimer | 0.20 | Aktiv nedbør |
| Vindkjøling | 0.15 | Snøfokk-risiko |
| Temperaturfall | 0.10 | Frysefare |

### Vedlikeholdskategorier (166 episoder)
| Type | Andel | Typisk scenario |
|------|-------|-----------------|
| Snøbrøyting | 46% | Nysnø > 5cm |
| Slaps-skraping | 33% | Temp 0-2°C + nedbør |
| Fryse/tine-strøing | 16% | Temperatursvingninger |
| Inspeksjon | 4% | Rutinekontroll |

### ⚠️ Viktig om brøytedata-kvalitet

Brøytedata reflekterer **faktisk aktivitet**, ikke nødvendigvis **faktisk behov**:

| Situasjon | Konsekvens for data |
|-----------|---------------------|
| Lite å gjøre | Overbrøyting - flere operasjoner enn nødvendig (fyller arbeidsdagen) |
| Mye å gjøre | Underbrøyting - færre operasjoner enn behov (kapasitetsmangel) |

**Implikasjoner for kriterievalidering:**
- Falske positiver: Brøyting uten værgrunnlag = overestimerer behov
- Falske negativer: Kritisk vær uten brøyting = underestimerer behov
- **Løsning**: Vekter værdata høyere enn brøytefrekvens ved validering

**Inspeksjonsandel: 10.2%** - Indikerer at ~10% av aktiviteten er tilsyn/rutine, ikke værrelatert.

---

## 👥 Målgrupper

### Brøytemannskaper
- Trenger varsling om **nysnø > 5 cm** for å planlegge utrykning
- Må vite om **snøfokk** som blokkerer veier
- Trenger varsling om **slaps** for å vurdere skraping/fresing

### Hytteeiere
- Trenger varsling før reise til hytta
- Vil vite om veien er **trygg å kjøre**
- Ønsker å forberede seg på **vanskelige forhold**

---

## 📊 Kritiske værsituasjoner

### 1. Nysnø ❄️
**Når:** Snødybde øker med ≥ 5 cm over 6 timer

**Kriterier (forbedret):**

| Metode | Kriterium | Forklaring |
|--------|-----------|------------|
| Primær | Duggpunkt < 0°C | Nedbør faller som snø selv ved +2°C lufttemp |
| Sekundær | Lufttemp < 1°C | Brukes hvis duggpunkt mangler |
| Snøøkning | ≥ 5 cm / 6 timer | Målt via `surface_snow_thickness` |

> **Hvorfor duggpunkt?** Ved +1.5°C lufttemperatur kan det like gjerne 
> falle regn som snø. Men hvis duggpunktet er under 0°C, sublimerer 
> fuktigheten til snøkrystaller - uavhengig av lufttemperatur opptil +2°C.

**Tilgjengelige elementer fra Frost API:**
- ✅ `dew_point_temperature` - Duggpunkt (PT10M, PT1H, P1D)
- ✅ `surface_snow_thickness` - Snødybde (PT10M, PT1H)
- ✅ `air_temperature` - Lufttemperatur
- ❌ `precipitation_type` - Ikke tilgjengelig på SN46220

**Logikk:**
```
HVIS nedbør > 0 OG (duggpunkt < 0°C ELLER lufttemp < 1°C):
    → Nedbør er snø
    HVIS snødybde øker ≥ 5 cm over 6 timer:
        → Varsle nysnø
```

**Varsel til:**
- Brøytemannskaper: "Nysnø registrert - vurder brøyting"
- Hytteeiere: "Nysnø på vei - planlegg ekstra tid"

---

### 2. Snøfokk 🌬️
**Når:** Løs snø blåser og reduserer sikt/blokkerer veier

> **KRITISK FUNN**: 100% av snøfokk-episoder på Gullingen er "usynlig snøfokk" - 
> snø som blåser horisontalt uten å endre målt snødybde. Veier kan blokkeres 
> uten at snøsensorer varsler!

### ⚠️ Viktig om snømåling ved vind

**Problem**: Snødybdemåleren på Gullingen måler ett punkt. Ved vind:
- Snø blåser VEKK fra måleren → snødybde synker/uendret
- Snø samler seg i lesider, grøfter, på veier → må brøytes
- Brøytet vei = snødybde 0 (snøen er fjernet)

**Konsekvens**: Vi kan IKKE stole på snødybdeendring for snøfokk-varsling!

**Løsning i kode**: Snøfokk varsles basert på:
1. Vindkast ≥ 15 m/s (primær trigger)
2. Vindkjøling ≤ -12°C
3. Eksisterende snødekke ≥ 3 cm (et sted i området)
4. Temperatur < -1°C (løssnø bevares)

**IKKE brukt**: Snødybdeendring - denne er upålitelig ved vind.

**Validerte kriterier (sesong 2023-2024):**

| Nivå | Vindkjøling | Vind | Vindkast | Snødybde | Vindretning |
|------|-------------|------|----------|----------|-------------|
| Advarsel | ≤ -12°C | ≥ 8 m/s | ≥ 15 m/s | ≥ 3 cm | Alle |
| Kritisk | ≤ -15°C | ≥ 10 m/s | ≥ 20 m/s | ≥ 3 cm | SE-S (135-225°) |

**Ny innsikt: Vindkast er bedre trigger enn snittwind!**
- Snøfokk-episoder: snittwind 10.3 m/s, vindkast **21.9 m/s**
- 36 brøyteepisoder hadde vindkast > 15 m/s
- Bruk `wind_speed_gust > 15` som primær snøfokk-indikator

**Kalibrering mot historikk:**
- 447 snøfokk-perioder identifisert (nov 2023 - apr 2024)
- **73% fra SE-S vindretninger** (135-225°) - spesielt kritisk for Gullingen
- **92.2% klassifisert som høy faregrad**
- Mest aktive måneder: Desember (27%), Februar (26%), Januar (20%)

**Varsel til:**
- Brøytemannskaper: "Snøfokk - veier kan blokkeres raskt"
- Hytteeiere: "Snøfokk - vurder å utsette reisen"

---

### 3. Slaps 🌧️❄️
**Hva:** Tung blanding av snø og vann som gir dårlig fremkommelighet

**Når slaps oppstår:**
- Snø smelter ved varmegrader (temperatur > 0°C)
- Regn faller på eksisterende snødekke

**Problemet med slaps:**
- Tung, ustabil masse som gir sporing
- Vanskelig for 2WD-biler å komme frem
- Krever skraping eller fresing (avhengig av temperatur)

**Validerte kriterier (ML-analyse):**

| Faktor | Terskel | Kilde |
|--------|---------|-------|
| Temperatur | -1°C til +4°C | ML-modell F1=0.98 |
| Nedbør | > 1.0 mm/t | Korrelert med brøyting |
| Snødekke | ≥ 5 cm | Fysisk forutsetning |

**Historiske slaps-episoder (42 bekreftet):**
- Gjennomsnittstemperatur: **1.2°C** (ideelt for slaps)
- Gjennomsnittlig nedbør: **29.9mm**
- Gjennomsnittlig varighet: 2.0 timer

**Typiske slaps-datoer fra data:**
- 22. jan 2024: 1.8°C, 97.5mm nedbør
- 25. jan 2025: 0.6°C, 81.8mm nedbør  
- 15. des 2024: 1.6°C, 77.4mm nedbør

**Beskyttende faktor:**
- Nysnø > 2mm ved temp < 1°C fungerer som "naturlig strøing"
- Reduserer slaps-risiko betydelig

**Varsel til:**
- Brøytemannskaper: "Slaps på veien - vurder skraping"
- Hytteeiere: "Slaps - vanskelig fremkommelighet for 2WD"

**Merk:** Hvis slaps fryser, blir det is/hålke - da gjelder "Glatte veier"-varsling.

---

### 4. Glatte veier 🧊
**Når:** Is eller glatt føre på veien

**Validerte scenarier (sesong 2023-2024):**

| Type | Andel | Kriterier |
|------|-------|-----------|
| Underkjølt regn | 80% | Temp -1°C til +1°C + nedbør > 0.1 mm/t |
| Rimfrost | 19% | Temp -2°C til 0°C + fuktighet ≥ 90% + vindstille + natt |
| Is-dannelse | 0.2% | Temp ≤ -1°C + fuktighet ≥ 80% + tempfall > 1°C/t |
| Refryzing | 0.7% | Tidligere smelting + temp ≤ 0°C + natt |

**Kalibrering mot historikk (nov 2023 - apr 2024):**
- 420 glatt vei-perioder identifisert
- **52% ekstrem faregrad**, 47% høy faregrad
- Mest aktive måneder: Februar (26%), Januar/Desember (19% hver)
- ML-modell F1-score: 1.0 (svært høy presisjon)

**Ny innsikt: Bakketemperatur er nøkkelen!**
- 28 av 166 brøyteepisoder hadde luft > 0°C men bakke < 0°C
- Bruk `surface_temperature < 0` som primær is-indikator
- Luft-bakke differanse snitt: 2.1°C

**Regn på snø-episoder (15 bekreftet):**
| Dato | Temp | Nedbør |
|------|------|--------|
| 25. des 2023 | -0.2°C | 34.3mm |
| 21. jan 2024 | 0.0°C | 24.6mm |
| 4. feb 2024 | -0.6°C | 24.8mm |
| 21. des 2024 | -0.2°C | 28.2mm |

**Tining/frysing-sykluser (3 bekreftet):**
- 18. feb 2023: -3.5°C til 2.3°C
- 10. jan 2024: -1.1°C til 4.3°C
- 28. jan 2025: -1.3°C til 2.2°C

**Beskyttende faktor:**
- Nysnø > 2mm ved temp < 1°C = "naturlig strøing"
- Strøing kun effektivt på klink is, IKKE på snø

**Varsel til:**
- Brøytemannskaper: "Glatte veier - strøing nødvendig"
- Hytteeiere: "Glatte veier - bruk vinterdekk, kjør forsiktig"

---

## 🔔 Varslingsnivåer

| Nivå | Farge | Betydning |
|------|-------|-----------|
| 🟢 LAV | Grønn | Normale forhold - trygt å kjøre |
| 🟡 MODERAT | Gul | Vær oppmerksom - mulig forverring |
| 🔴 HØY | Rød | Kritiske forhold - vurder å utsette reisen |

---

## 📱 Varslingsfunksjoner (fremtidig)

### Push-varsler
- [ ] SMS til brøytemannskaper ved nysnø > 5 cm
- [ ] Push-notifikasjon til app ved kritiske forhold
- [ ] E-post sammendrag hver morgen

### Dashboard
- [x] Sanntidsstatus på nett
- [x] Grafer med værhistorikk
- [ ] Kart med fargekodet risiko

### API
- [ ] Webhook for eksterne systemer
- [ ] JSON-endepunkt for integrasjon

---

## 🛠️ Teknisk implementasjon

### Datakilder

#### 1. Frost API (Meteorologisk institutt)
- **Stasjon**: SN46220 Gullingen (639 moh)
- **Dokumentasjon**: https://frost.met.no/
- **Status**: ✅ Implementert

#### 2. Netatmo Weather API (planlagt)
- **Stasjon**: Fjellbergsskardet Hyttegrend
- **Koordinat**: 59.39205°N, 6.42667°Ø
- **Høyde**: 607 moh
- **Dokumentasjon**: https://dev.netatmo.com/apidocumentation/weather
- **Status**: ⏳ Ikke implementert

**Fordel med Netatmo**:
- Gir temperaturdata fra et annet punkt i området
- Kan avdekke lokale variasjoner (inversjon, leforhold)
- Supplerer Gullingen-data for bedre varsling

#### 3. Brøytekart (live GPS)
- **URL**: https://plowman-new.snøbrøyting.net/nb/share/Y3VzdG9tZXItMTM=
- **Viser**: Brøytebilposisjon, brøytet/ubrøytet vei
- **Status**: 🔗 Ekstern lenke (ikke integrert)

### Elementer som overvåkes (Frost API)
```
air_temperature            - Lufttemperatur
surface_temperature        - Bakketemperatur (KRITISK for is!)
wind_speed                 - Vindstyrke
wind_speed_gust            - Vindkast (trigger snøfokk)
wind_from_direction        - Vindretning
surface_snow_thickness     - Snødybde
precipitation              - Nedbør siste time
duration_of_precipitation  - Nedbørsvarighet (minutter)
dew_point_temperature      - Duggpunkt
relative_humidity          - Luftfuktighet
```

### Ny innsikt: Bakketemperatur vs lufttemperatur
Analyse av 166 brøyteepisoder (2022-2025) viser:
- **Bakke er i snitt 2.1°C kaldere enn luft**
- **28 episoder** med luft > 0°C men bakke < 0°C = FRYSEFARE
- Bakketemperatur er bedre indikator for isdannelse enn lufttemperatur

### Ny innsikt: Vindkast vs snittwind  
- **Snittwind ved snøfokk**: 10.3 m/s
- **Vindkast ved snøfokk**: 21.9 m/s (over dobbelt!)
- 36 episoder med vindkast > 15 m/s
- Vindkast er bedre trigger for snøfokk enn snittwind

### Scenariofordeling (166 brøyteepisoder)
| Scenario | Andel | Lufttemp | Bakketemp | Nedbør | Vind |
|----------|-------|----------|-----------|--------|------|
| SLAPS | 16% | +1.5°C | +0.2°C | 12.1mm | 2.8 m/s |
| NYSNØ | 20% | -1.7°C | -2.2°C | 7.2mm | 3.9 m/s |
| FRYSEFARE | 11% | +1.1°C | -1.7°C | 0.9mm | 3.4 m/s |
| SNØFOKK | 11% | -3.9°C | -5.6°C | 0.2mm | 10.3 m/s |
| ANNET | 42% | - | - | - | - |

### Analysemoduler
1. `SnowdriftAnalyzer` - Snøfokk-risiko
2. `SlipperyRoadAnalyzer` - Glattføre-risiko
3. `FreshSnowDetector` - Nysnø-deteksjon (TODO)
4. `SlapsDetector` - Slaps-deteksjon (TODO)

---

## 📋 Prioritert backlog

### Fase 1: MVP (Nå) ✅
- [x] Snøfokk-varsling med ML-terskler
- [x] Glattføre-varsling (regn på snø, is, rimfrost)
- [x] Streamlit dashboard
- [x] Modulær arkitektur

### Fase 2: Utvidet varsling
- [ ] Dedikert nysnø-detektor
- [ ] Dedikert slaps-detektor
- [ ] Kombinert risiko-score
- [ ] Historisk sammenligning

### Fase 3: Varsling
- [ ] SMS-integrasjon (Twilio/46elks)
- [ ] Push-notifikasjoner
- [ ] E-post daglig sammendrag

### Fase 4: Avansert
- [ ] ML-prediksjon (varsle 6-24 timer frem)
- [ ] Integrasjon med yr.no prognoser
- [ ] Kart med risikosoner

---

## 🧪 Testscenarier (validert mot historikk)

### Slaps - november 2025 (bekreftet)
```
Dato: 22. november 2025
Temperatur: 0.7 til 2.4°C (snitt 1.6°C)
Nedbør: 20.4mm regn
Snødybde: Sank fra 15cm → 7cm
Duggpunkt: 0.6 til 2.5°C (over 0 = regn, ikke snø)
→ Resultat: Skraping 6t + Strøing 46m
→ SLAPS bekreftet: Regn på snø ved plusgrader
```

### Glatt vei etter slaps - november 2025 (bekreftet)
```
Dato: 23. november 2025
Temperatur: 0.0 til 2.2°C
Nedbør: 0mm
Duggpunkt: -1.9 til 0.4°C (nattfrost)
→ Resultat: Strøing 1t 25m
→ GLATT VEI bekreftet: Slaps fra dagen før frøs til is
```

### Kraftig slaps - november 2025 (bekreftet)
```
Dato: 27. november 2025
Temperatur: 1.8 til 5.5°C (snitt 3.8°C!)
Nedbør: 19.1mm regn
Snødybde: Sank fra 13cm → 8cm
→ Resultat: Skraping 4t 32m + Strøing 2t
→ SLAPS bekreftet: Kraftig regn ved +2-5°C
```

### Snøfokk - kritisk
```
Dato: 8-11. februar 2024 (bekreftet snøfokk-krise)
Temperatur: -10.5°C
Vindkjøling: -18°C
Vind: 15.9 m/s
Vindretning: SE (135°)
Snødybde: 25 cm
→ Resultat: 🔴 HØY risiko - 8 perioder, 80 timer med snøfokk
```

### Regn på snø - kritisk
```
Dato: 22. november 2023
Temperatur: -0.2°C til -0.3°C
Fuktighet: 97%
Nedbør: 2.4 mm/t
→ Resultat: 🔴 EKSTREM risiko - underkjølt regn
```

### Slaps (regn på snø / smelting)
```
Temperatur: +3°C
Nedbør: 1.2 mm/t (regn)
Snødybde: 15 cm
→ Forventet: 🔴 HØY risiko - vanskelig fremkommelighet
```

### Slaps → is (frysefare)
```
Temperatur: +1°C → synkende mot 0°C
Slaps på veien
→ Forventet: 🟡 MODERAT risiko slaps + ⚠️ frysevarsel
```

### Stabile vinterforhold
```
Temperatur: -12°C
Vind: 3 m/s
Snødybde: 40 cm
Ingen nedbør
→ Forventet: 🟢 LAV risiko
```

### Brøytemønster (typisk)
```
Mest aktive time: 09:00 (25 brøytinger)
Mest aktive måned: Januar (52 brøytinger)
Inspeksjonsandel: 10.2%
```

### Kapasitetsbias i data
```
Rolige perioder:
- Flere korte turer (inspeksjon, tunbrøyting)
- Lav korrelasjon med vær
→ Kan gi falsk alarm-terskel hvis brukt ukritisk

Travle perioder:  
- Færre, lengre operasjoner enn behov
- Høy korrelasjon med vær, men respons forsinket
→ Varsler bør trigge FØR brøytedata viser aktivitet
```

---

## 📞 Kontakt

For spørsmål om systemet eller tilgang til varsler, kontakt administrator.

---

## 📁 Datakilder

### Analyserapporter
- `data/analyzed/FINAL_CORRECTED_SEASON_ANALYSIS.md` - Snøfokk 2023-2024
- `data/analyzed/realistic_snowdrift_report.txt` - Snøfokk-statistikk
- `data/analyzed/realistic_slippery_road_report.txt` - Glatt vei-analyse
- `data/analyzed/ml_slush_slippery_criteria_20250810_0844.json` - ML-terskler
- `data/analyzed/final_calibrated_thresholds.json` - Kalibrerte grenseverdier
- `data/analyzed/broyting_weather_correlation_20250811_2007.json` - Brøytekorrelasjon

### Rådata
- `data/analyzed/Rapport 2022-2025.csv` - Brøyterapporter
- Frost API stasjon SN46220 - Historiske værdata
