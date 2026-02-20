# Agent: Føreforhold Gullingen

## Formål

Varslingssystem for **brøytemannskaper** og **hytteeiere** ved Gullingen Skisenter.

Systemet skal gi tidlig varsling om:
1. **Nysnø** - Behov for brøyting
2. **Snøfokk** - Redusert sikt, snødrev på veier
3. **Slaps** - Tung snø/vann-blanding, vanskelig fremkommelighet
4. **Glatte veier** - Regn på snø, is, rimfrost

> **Kilde**: Kriterier validert mot historiske værdata (Frost API) og brøyterapporter 2022-2025.

---

## Live ressurser

### Brøytekart (sanntid)
**URL**: https://plowman-new.snøbrøyting.net/nb/share/Y3VzdG9tZXItMTM=

Viser:
- GPS-posisjon for brøytebiler
- Brøytet vs ubrøytet vei
- Tidspunkt for siste brøyting

**Siste brøyting - teknisk implementasjon:**
- **Klient**: `src/plowman_client.py`
- **Metode**: Hent JSON fra vedlikeholds-API (Vintervakt)
- **Endepunkt**: `GET {MAINTENANCE_API_BASE_URL}/v1/maintenance/latest`
- **Auth**: `Authorization: Bearer {MAINTENANCE_API_TOKEN}`
- **Tolkning**: `timestamp_utc` brukes som "siste brøyting/vedlikehold" (UTC)

### Værstasjoner
| Stasjon | Type | Koordinat | Høyde |
|---------|------|-----------|-------|
| SN46220 Gullingen | Frost API | 59.4128°N, 6.4697°Ø | 639 moh |
| Fjellbergsskardet | Netatmo | 59.39205°N, 6.42667°Ø | 607 moh |

---

## Designprinsipper

### Emoji
- Ikke bruk emoji i app-UI, varsler eller analyseresultater.
- Hold teksten profesjonell og lesbar.

---

## Datagrunnlag for validering

For metodikk og prinsipper for terskler (og hvorfor tallverdiene kun ligger i kode), se `docs/terskler_og_validering.md`.

### Brøytedata
- **Kilde**: `data/analyzed/Rapport 2022-2025.csv`
- **Periode**: Desember 2022 - April 2025
- **166 brøyteepisoder** analysert
- **Fordeling**: Januar (52), Desember (45), Februar (44), Mars (16)

**Siste analyser (29. november 2025):**
- `data/analyzed/broyting_weather_correlation_2025.csv`
- `data/analyzed/maintenance_weather_analysis.json`

Guiden i `data/analyzed/ANALYSIS_METHOD_GUIDE.md` beskriver hele kjøringen og oppdateres ved nye analyser.

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
| Snøbrøyting | 46% | Nysnø over terskel (se `settings.fresh_snow.snow_increase_*`) |
| Slaps-skraping | 33% | Mildvær i slaps-området + nedbør (se `settings.slaps.temp_min/temp_max` og `settings.slaps.precipitation_12h_*`) |
| Fryse/tine-strøing | 16% | Temperatursvingninger |
| Inspeksjon | 4% | Rutinekontroll |

### Viktig om brøytedata-kvalitet

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

## Målgrupper

### Brøytemannskaper
- Trenger varsling om **nysnø over terskel** (se `settings.fresh_snow.snow_increase_*`) for å planlegge utrykning
- Må vite om **snøfokk** som blokkerer veier
- Trenger varsling om **slaps** for å vurdere skraping/fresing

### Hytteeiere
- Trenger varsling før reise til hytta
- Vil vite om veien er **trygg å kjøre**
- Ønsker å forberede seg på **vanskelige forhold**

---

## Kritiske værsituasjoner

### 1. Nysnø
**Når:** Snødybde øker merkbart over et definert vindu (styres av `settings.fresh_snow.lookback_hours` i `src/config.py`).

Viktig ved vind:
- Ved snøfokk/vindtransport kan snødybdemåleren gå ned selv om det snør (snø blåser vekk fra målepunktet).
- Derfor brukes også nedbør som støtte/fallback for nysnø når det er vind og forholdene tilsier snø (se `settings.fresh_snow.precipitation_6h_*`).

**Kriterier (forbedret):**

| Metode | Kriterium | Forklaring |
|--------|-----------|------------|
| Primær | `settings.fresh_snow.dew_point_max` | Nedbør faller som snø selv ved mild lufttemp |
| Sekundær | `settings.fresh_snow.air_temp_max` | Brukes hvis duggpunkt mangler |
| Snøøkning | `settings.fresh_snow.snow_increase_warning` / `settings.fresh_snow.snow_increase_critical` | Målt via `surface_snow_thickness` |

> **Hvorfor duggpunkt?** Duggpunkt brukes som primær indikator for snø vs regn.
> Se `settings.fresh_snow.dew_point_max` og fallback `settings.fresh_snow.air_temp_max`.

**Tilgjengelige elementer fra Frost API:**
- `dew_point_temperature` - Duggpunkt (PT10M, PT1H, P1D)
- `surface_snow_thickness` - Snødybde (PT10M, PT1H)
- `air_temperature` - Lufttemperatur
- `precipitation_type` - Ikke tilgjengelig på SN46220

**Logikk:**
```
HVIS nedbør >= settings.fresh_snow.precipitation_min OG (duggpunkt < settings.fresh_snow.dew_point_max ELLER lufttemp < settings.fresh_snow.air_temp_max):
    → Snøfall pågår

HVIS snødybde øker >= settings.fresh_snow.snow_increase_critical over settings.fresh_snow.lookback_hours timer:
    → Varsle høy nysnø
ELLERS HVIS snødybde øker >= settings.fresh_snow.snow_increase_warning over settings.fresh_snow.lookback_hours timer:
    → Varsle moderat nysnø
```

**Varsel til:**
- Brøytemannskaper: "Nysnø registrert - vurder brøyting"
- Hytteeiere: "Nysnø på vei - planlegg ekstra tid"

---

### 2. Snøfokk
**Når:** Løs snø blåser og reduserer sikt/blokkerer veier

> **KRITISK FUNN**: 100% av snøfokk-episoder på Gullingen er "usynlig snøfokk" - 
> snø som blåser horisontalt uten å endre målt snødybde. Veier kan blokkeres 
> uten at snøsensorer varsler!

### Viktig om snømåling ved vind

**Problem**: Snødybdemåleren på Gullingen måler ett punkt. Ved vind:
- Snø blåser VEKK fra måleren → snødybde synker/uendret
- Snø samler seg i lesider, grøfter, på veier → må brøytes
- Brøytet vei = snødybde 0 (snøen er fjernet)

**Konsekvens**: Vi kan IKKE stole på snødybdeendring for snøfokk-varsling!

### Krav om løssnø

**Kritisk forutsetning**: Snøfokk krever FERSK, LØS SNØ som kan transporteres av vind.

**Når snø IKKE kan blåse:**
- Gammel, pakket snø (sintrert/sammenbundet)
- Snø med isskorpe på toppen
- Våt snø (mildvær; se `settings.snowdrift.loose_snow_mild_temp_min_c`)
- Snø eldre enn definert løssnø-vindu uten ny nedbør (se `settings.snowdrift.loose_snow_lookback_hours`)

**Løssnø-tilgjengelighet (implementert):**
- Basert på lufttemperatur over `settings.snowdrift.loose_snow_lookback_hours` timer:
    - Kontinuerlig frost (alle målinger ≤ `settings.snowdrift.loose_snow_continuous_frost_temp_max_c`) → løssnø antas tilgjengelig
    - Mildvær (≥ `settings.snowdrift.loose_snow_mild_hours_min` timer over `settings.snowdrift.loose_snow_mild_temp_min_c`) → løssnø antas ikke tilgjengelig
    - Delvis mildvær → løssnø kan være tilgjengelig (usikkert)

> **Fysisk forklaring**: Snøkrystaller binder seg sammen (sintrer) over tid. 
> Etter en periode uten ny snø (se `settings.snowdrift.loose_snow_lookback_hours`) er overflaten ofte for hard til å blåse, selv i sterk vind.
> Vind uten fersk snø = ingen snøfokk, bare kald vind.

**Løsning i kode**: Snøfokk varsles basert på:
1. Vindkast som primær trigger med vind-gating (`settings.snowdrift.wind_gust_warning` / `settings.snowdrift.wind_gust_critical`)
2. Vindkjøling (`settings.snowdrift.wind_chill_warning` / `settings.snowdrift.wind_chill_critical`)
3. Minimum snødekke (`settings.snowdrift.snow_depth_min_cm`)
4. Temperatur (`settings.snowdrift.temperature_max`)
5. Løssnø-tilgjengelighet (basert på temperatur over `settings.snowdrift.loose_snow_lookback_hours`; langvarig mildvær reduserer risiko)

**Snødybdeendring**: Brukes kun som støttefaktor (ikke som hovedtrigger), fordi den kan være upålitelig ved vind.

**Validerte kriterier (sesong 2023-2024):**

| Nivå | Vindkjøling | Vind | Vindkast | Snødybde | Fersk snø | Vindretning |
|------|-------------|------|----------|----------|-----------|-------------|
| Advarsel | `settings.snowdrift.wind_chill_warning` | `settings.snowdrift.wind_speed_gust_warning_gate` (gate) | `settings.snowdrift.wind_gust_warning` | `settings.snowdrift.snow_depth_min_cm` | Løssnø tilgjengelig | Alle |
| Kritisk | `settings.snowdrift.wind_chill_critical` | `settings.snowdrift.wind_speed_warning` (gate) | `settings.snowdrift.wind_gust_critical` | `settings.snowdrift.snow_depth_min_cm` | Løssnø tilgjengelig | SE-S (`settings.snowdrift.critical_wind_dir_min`–`settings.snowdrift.critical_wind_dir_max`) |

Merk: `wind_speed_median` ble fjernet (var deprecated alias for `wind_speed_gust_warning_gate`).

**Ny innsikt: Vindkast er bedre trigger enn snittwind!**
- Snøfokk-episoder: snittwind 10.3 m/s, vindkast **21.9 m/s**
- 36 brøyteepisoder hadde vindkast > 15 m/s
- Bruk vindkast som primær snøfokk-indikator

**Kalibrering mot historikk:**
- 447 snøfokk-perioder identifisert (nov 2023 - apr 2024)
- **73% fra kritisk vindsektor** (se `settings.snowdrift.critical_wind_dir_min` og `settings.snowdrift.critical_wind_dir_max`) - spesielt kritisk for Gullingen
- **92.2% klassifisert som høy faregrad**
- Mest aktive måneder: Desember (27%), Februar (26%), Januar (20%)

**Varsel til:**
- Brøytemannskaper: "Snøfokk"
- Hytteeiere: "Snøfokk"

---

### 3. Slaps
**Hva:** Tung blanding av snø og vann som gir dårlig fremkommelighet

**Når slaps oppstår:**
- Snø smelter ved mildvær (se `settings.slaps.temp_min` og `settings.slaps.temp_max`)
- Regn faller på eksisterende snødekke

**Problemet med slaps:**
- Tung, ustabil masse som gir sporing
- Vanskelig for 2WD-biler å komme frem
- Krever skraping eller fresing (avhengig av temperatur)

**Validerte kriterier (ML-analyse):**

| Faktor | Terskel | Kilde |
|--------|---------|-------|
| Temperatur | `settings.slaps.temp_min` til `settings.slaps.temp_max` | Kalibrert for slaps-detektor |
| Nedbør | `settings.slaps.precipitation_12h_min` (12t akkumulert) | Brukes for å unngå varsling på små drypp |
| Snødekke | `settings.slaps.snow_depth_min` | Fysisk forutsetning |

**Historiske slaps-episoder (42 bekreftet):**
- Gjennomsnittstemperatur: **1.2°C** (ideelt for slaps)
- Gjennomsnittlig nedbør: **29.9mm**
- Gjennomsnittlig varighet: 2.0 timer

**Typiske slaps-datoer fra data:**
- 22. jan 2024: 1.8°C, 97.5mm nedbør
- 25. jan 2025: 0.6°C, 81.8mm nedbør  
- 15. des 2024: 1.6°C, 77.4mm nedbør

**Beskyttende faktor:**
- Fersk nysnø kan gi økt friksjon ("naturlig strøing"), se `settings.slippery.recent_snow_relief_hours` og `settings.slippery.recent_snow_relief_cm`
- Reduserer slaps-risiko betydelig

**Varsel til:**
- Brøytemannskaper: "Slaps på veien - vurder skraping"
- Hytteeiere: "Slaps - vanskelig fremkommelighet for 2WD"

**Merk:** Hvis slaps fryser, blir det is/hålke - da gjelder "Glatte veier"-varsling.

---

### 4. Glatte veier
**Når:** Is eller glatt føre på veien

**Validerte scenarier (sesong 2023-2024):**

| Type | Andel | Kriterier |
|------|-------|-----------|
| Regn på snø | Vanlig | `settings.slippery.mild_temp_min`–`settings.slippery.mild_temp_max` + `settings.slippery.rain_threshold_mm` + `settings.slippery.snow_depth_min_cm` |
| Underkjølt regn / frysing | Vanlig | `settings.slippery.surface_temp_freeze` + `settings.slippery.freezing_precip_warning_mm`/`settings.slippery.freezing_precip_critical_mm` + nær frysepunkt (`settings.slippery.near_freezing_temp_min`–`settings.slippery.near_freezing_temp_max`) |
| Rimfrost | Vanlig | `settings.slippery.rimfrost_humidity_min` og `settings.slippery.rimfrost_wind_max` + duggpunkt nær lufttemp |
| Skjult frysefare | Viktig | `settings.slippery.hidden_freeze_surface_max` + `settings.slippery.hidden_freeze_air_min`–`settings.slippery.hidden_freeze_air_max` + `settings.slippery.hidden_freeze_precip_12h_min` |

**Kalibrering mot historikk (nov 2023 - apr 2024):**
- 420 glatt vei-perioder identifisert
- **52% ekstrem faregrad**, 47% høy faregrad
- Mest aktive måneder: Februar (26%), Januar/Desember (19% hver)
- ML-modell F1-score: 1.0 (svært høy presisjon)

**Ny innsikt: Bakketemperatur er nøkkelen!**
- 28 av 166 brøyteepisoder hadde luft over frysepunktet men bakke under frysepunktet (se `settings.slippery.hidden_freeze_*`)
- Bruk `surface_temperature <= settings.slippery.surface_temp_freeze` som primær is-indikator
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
- Fersk nysnø kan gi økt friksjon (se `settings.slippery.recent_snow_relief_hours` og `settings.slippery.recent_snow_relief_cm`)
- Strøing kun effektivt på klink is, IKKE på snø

**Varsel til:**
- Brøytemannskaper: "Glatte veier - strøing nødvendig"
- Hytteeiere: "Glatte veier - bruk vinterdekk, kjør forsiktig"

---

## Varslingsnivåer

| Nivå | Farge | Betydning |
|------|-------|-----------|
| LAV | Grønn | Normale forhold - trygt å kjøre |
| MODERAT | Gul | Vær oppmerksom - mulig forverring |
| HØY | Rød | Kritiske forhold - vurder å utsette reisen |

---

## Varslingsfunksjoner (fremtidig)

### Push-varsler
- [ ] SMS til brøytemannskaper ved kritisk nysnø (se `settings.fresh_snow.snow_increase_critical`)
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

## Teknisk implementasjon

### Datakilder

#### 1. Frost API (Meteorologisk institutt)
- **Stasjon**: SN46220 Gullingen (639 moh)
- **Dokumentasjon**: https://frost.met.no/
- **Status**: Implementert

#### 2. Netatmo Weather API (planlagt)
- **Stasjon**: Fjellbergsskardet Hyttegrend
- **Koordinat**: 59.39205°N, 6.42667°Ø
- **Høyde**: 607 moh
- **Dokumentasjon**: https://dev.netatmo.com/apidocumentation/weather
- **Status**: Ikke implementert

**Fordel med Netatmo**:
- Gir temperaturdata fra et annet punkt i området
- Kan avdekke lokale variasjoner (inversjon, leforhold)
- Supplerer Gullingen-data for bedre varsling

#### 3. Brøytekart (live GPS)
- **URL**: https://plowman-new.snøbrøyting.net/nb/share/Y3VzdG9tZXItMTM=
- **Viser**: Brøytebilposisjon, brøytet/ubrøytet vei
- **Status**: Ekstern lenke (ikke integrert)

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
- **28 episoder** med luft over frysepunktet men bakke under frysepunktet = FRYSEFARE (se `settings.slippery.hidden_freeze_*`)
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

### Analysemoduler (per 30. november 2025)
1. `SnowdriftAnalyzer` – Snøfokk-risiko (live i `src/analyzers/snowdrift.py`)
2. `SlipperyRoadAnalyzer` – Glattføre-risiko (live i `src/analyzers/slippery_road.py`)
3. `FreshSnowAnalyzer` – Nysnø-deteksjon (live i `src/analyzers/fresh_snow.py`)
4. `SlapsAnalyzer` – Slaps-deteksjon (live i `src/analyzers/slaps.py`)

> **Merk:** Alle fire analysatorene kjøres direkte på ferske Frost-data i `src/gullingen_app.py` og bruker terskler fra `src/config.py`. Historiske ML-prototyper ligger i `archive/analysis_py/` og er ikke i aktiv bruk.

---

## Prioritert backlog

### Fase 1: MVP (Nå)
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

## Testscenarier (validert mot historikk)

### Slaps - november 2025 (bekreftet)
```
Dato: 22. november 2025
Temperatur: 0.7 til 2.4°C (snitt 1.6°C)
Nedbør: 20.4mm regn
Snødybde: Sank fra 15cm → 7cm
Duggpunkt: 0.6 til 2.5°C (over frysepunktet = regn, ikke snø)
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
→ Resultat: HØY risiko - 8 perioder, 80 timer med snøfokk
```

### Regn på snø - kritisk
```
Dato: 22. november 2023
Temperatur: -0.2°C til -0.3°C
Fuktighet: 97%
Nedbør: 2.4 mm/t
→ Resultat: EKSTREM risiko - underkjølt regn
```

### Slaps (regn på snø / smelting)
```
Temperatur: +3°C
Nedbør: 1.2 mm/t (regn)
Snødybde: 15 cm
→ Forventet: HØY risiko - vanskelig fremkommelighet
```

### Slaps → is (frysefare)
```
Temperatur: +1°C → synkende mot 0°C
Slaps på veien
→ Forventet: MODERAT risiko slaps + frysevarsel
```

### Stabile vinterforhold
```
Temperatur: -12°C
Vind: 3 m/s
Snødybde: 40 cm
Ingen nedbør
→ Forventet: LAV risiko
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

## Kontakt

For spørsmål om systemet eller tilgang til varsler, kontakt administrator.

---

## Datakilder

### Analyserapporter (oppdatert 29. november 2025)
- `data/analyzed/broyting_weather_correlation_2025.csv` – Vær + brøyting (166 episoder, 2022-2025)
- `data/analyzed/maintenance_weather_analysis.json` – Oppsummering pr. vedlikeholdstype
- `data/analyzed/ANALYSIS_METHOD_GUIDE.md` – Dokumentert fremgangsmåte for siste kjøring

> Historiske rapporter og ML-filer ligger i `archive/analysis_*` for referanse. Kun filene over brukes som grunnlag akkurat nå.

### Rådata
- `data/analyzed/Rapport 2022-2025.csv` – Manuellt beriket brøyte-logg (166 episoder)
- Frost API stasjon SN46220 – Live værdata til appen
