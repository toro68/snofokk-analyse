# Fremgangsmåte for videre analyser (LLM + Gullingen data)

Denne veiledningen dokumenterer hvordan analysene som ble kjørt 29. november 2025 ble gjennomført, og hvordan en senere (bedre) LLM bør reprodusere eller utvide dem. Fokus er å beskrive hele kjeden fra datagrunnlag til leveransefiler, med eksplisitte sjekkpunkter og filnavn.

---

## 1. Datagrunnlag

1. **Primærkilde:** `data/analyzed/Rapport 2022-2025.csv` – manuelt beriket brøyte-logg.
2. **Værdata:** Frost API stasjon `SN46220 Gullingen` – elementer som listet i `src/config.py:StationConfig.CORE_ELEMENTS` (temp, bakke, vind, kast, nedbør, snø, fukt, duggpunkt).
3. **Aux-data:** `plowing_data.json` (sanntids brøyting) og Netatmo (valgfritt). Ikke nødvendig for historiske analyser.

### Viktig: filformat og deduplisering

- `Rapport 2022-2025.csv` er *semikolon-separert* og må leses med `sep=';'`.
- `Dato` er lagret som norsk dato-tekst (typisk `21. des. 2022` / `9. mars 2023`), ikke `dd.mm.yyyy`.
- Per 13. des 2025:
   - Rader i fil: **167**
   - Unike brøytehendelser: **166**, der en hendelse finnes flere ganger (typisk flere enheter/"Enhet").
- Unik hendelse defineres som nøkkelen: `(Dato, Starttid, Sluttid, Rode)`.

Eksempel:

```python
import pandas as pd

plow = pd.read_csv('data/analyzed/Rapport 2022-2025.csv', sep=';', encoding='utf-8')
event_key = ['Dato','Starttid','Sluttid','Rode']
plow_events = plow.drop_duplicates(subset=event_key).copy()
print('raw rows', len(plow), 'unique events', len(plow_events))

# Hvis du trenger ukedag/rutiner (fredager), må `Dato` parses eksplisitt.
# Se også `scripts/validate_config_against_history.py`.
```

### Minimumsfiltrering
- Tidsvindu: 2022-12-01 → 2025-04-30
- Aggregasjoner: 6-timers ruller for snøøkning, 1-timers for nedbør/vind, 24-timers for fersk-snø sjekk.

### Kritisk: brøyteloggen er ikke “fasit” (label-noise)

Brøytedata reflekterer faktisk aktivitet, men er en ufullkommen proxy for behov. Dette gir tre viktige bias som må tas hensyn til når terskler i `src/config.py` valideres:

1. **Inspeksjon/korte turer**
   - Korte turer (få kilometer og/eller svært kort varighet) kan være ren sjekk/takst uten reelt vedlikeholdsbehov.
   - Konsekvens: kan gi falske “positiver” hvis man tolker alle hendelser som vær-drevet.

2. **Kapasitetsforsinkelse ved store snøfall**
   - Under de største hendelsene kan brøyting starte sent (kapasitetsmangel), dvs. logget starttid ligger etter at været har vært kritisk i en stund.
   - Konsekvens: naive “før/under/etter”-vinduer kan undervurdere vær som driver brøyting (falske “negativer” hvis man forventer at brøyting skjer tidlig).

3. **Ujevn strøing mellom sesonger**
   - Enkelte sesonger kan ha mindre strøing enn nødvendig (praktiske forhold/kapasitet/økonomi).
   - Konsekvens: glattføre kan være under-representert i vedlikeholdshendelser, selv om været tilsier behov.

4. **Ukedagsrutiner (tunbrøyting fredager)**
   - I brøyteloggen finnes et tydelig ukedagsmønster der fredager skiller seg ut med mange og lange turer.
   - Per 13. des 2025 (166 unike hendelser): **Fredag = 27 hendelser**, median **19.3 km** og **~209 min** (fra `Rapport 2022-2025.csv`).
   - Tolkning: dette kan være rutine/tunbrøyting (planlagt “runde”) og ikke nødvendigvis direkte vær-drevet.
   - Konsekvens: når du kalibrerer terskler for “behov for brøyting/strøing”, må du ikke bruke ukritisk antall hendelser som fasit. Valider terskler primært mot værindikatorene, og bruk brøyting som støtte.

Prinsipp:
- Bruk værdata som primær sannhet for “fare/risiko”, og brøytedata som sekundær observasjon for plausibilitet og kalibrering.

---

## 2. Forhåndsprosessering

1. **Synkroniser tid**
   - Konverter alle tidsstempler til `Europe/Oslo`.
   - Lag `reference_time` kolonne i pandas (datetime64[ns]).

2. **Feature-berikelse**
   - `temp_diff = air_temperature - surface_temperature`
   - `wind_chill = BaseAnalyzer.calculate_wind_chill()`
    - `snow_change_6h_cm` (netto endring siste 6 timer, i cm):

       ```python
       # Forutsetter time-oppløst df (1H) og snow_depth_cm
       df['snow_change_6h_cm'] = df['snow_depth_cm'] - df['snow_depth_cm'].shift(6)
       ```

    - `fresh_snow_24h_cm` (akkumulert *positiv* snøøkning siste 24 timer, i cm):

       ```python
       snow_diff_1h = df['snow_depth_cm'].diff()
       df['fresh_snow_24h_cm'] = snow_diff_1h.clip(lower=0).rolling(24, min_periods=6).sum()
       ```

   Notat:
   - “diff over 6 timer” finnes ikke direkte i pandas som `diff(window=...)`; bruk `shift(n)` eller resampling til fast frekvens.
    - Hvis du bruker netto endring (kan være negativ ved vind), skill dette fra “fresh snow” (kun positiv økning).

   Viktig for nysnø ved vind:
   - Ved vindtransport/snøfokk kan snødybdemåleren gå ned selv om det faktisk snør (snø blåser vekk fra målepunktet).
   - Derfor må nysnø ikke valideres kun på `snow_change_6h_cm` i vind-situasjoner.
   - I app-koden brukes nedbør som støtte/fallback ved vind (`settings.fresh_snow.precipitation_6h_warning_mm` / `settings.fresh_snow.precipitation_6h_critical_mm`) når `wind_speed` er over vind-gate.

3. **Scenario-tagging** (bruk eksisterende etiketter fra `Rapport 2022-2025.csv` når mulig)
   - Alternativt: kjør `src/analyzers/*` mot dataframes for å gjenbruke logikk.

---

## 3. Analysefiler (29. nov 2025)

Filer generert denne datoen ligger i `data/analyzed/` og inkluderer:

| Fil | Innhold | Formål |
|-----|---------|--------|
| `broyting_weather_correlation_2025.csv` | Rå sammenslått tabell (vær + brøyting) | Basis for videre korrelasjoner |
| `maintenance_weather_analysis.json` | Oppsummering per vedlikeholdstype (snø, slaps, is, inspeksjon) | Grunnlag for terskelvalg |

### Validering
- Kryss-sjekk antall rader mot unike hendelser i `Rapport 2022-2025.csv` (per 13. des 2025: **166** unike).
- Verifiser at alle scenariokoder (`NYSNØ`, `SNØFOKK`, `SLAPS`, `FRYSEFARE`, `ANNET`) er representert.

### Data-kontrakt: `broyting_weather_correlation_2025.csv`

Per 13. des 2025 har filen **166 rader** og kolonnene:

```text
dato
datetime
air_temp_avg
air_temp_min
surface_temp_avg
surface_temp_min
temp_diff
wind_avg
wind_max
gust_max
precip_total
precip_duration
snow_depth
snow_change
humidity_avg
dew_point_avg
scenario
```

Anbefalt praksis:
- Bruk `datetime` som primærnøkkel for tidsanalyse.
- `dato` er kun presentasjon/rapport (norsk format) og bør ikke brukes som nøkkel.
- Kjør alltid en dupe-sjekk. Per 13. des 2025 finnes **6** dupliserte rader på `(datetime, scenario)`.
   - For statistikk/terskelvalidering bør disse normalt dedupliseres med `drop_duplicates(['datetime','scenario'])`.

---

## 4. Analysetrinn (reproduserbar pipeline)

1. **Last data** (Python/Notebook/LLM-kode):
   ```python
   df = pd.read_csv('data/analyzed/broyting_weather_correlation_2025.csv', parse_dates=['datetime'])
   ```

   Dupe-sjekk (må alltid kjøres):

   ```python
   dup = df.duplicated(subset=['datetime','scenario'], keep=False)
   print('dup rows', int(dup.sum()))
   # For terskelvalidering anbefales dedupe:
   df = df.drop_duplicates(subset=['datetime','scenario']).copy()
   ```
2. **Segmenter per scenario**
   ```python
   groups = df.groupby('scenario')
   stats = groups[['air_temp_avg','surface_temp_avg','wind_avg','gust_max','precip_total','snow_change']].agg(['mean','median','max'])
   stats.to_json('data/analyzed/maintenance_weather_analysis.json', orient='index', indent=2)
   ```
3. **Korrelasjoner**
   - Både Pearson og Spearman mellom `scenario` (one-hot) og værfeatures.
   - Lag topp 5 drivere per scenario og skriv til Markdown/JSON.
4. **Terskel-sjekk**
   - Sammenlign faktiske målinger mot `settings.*` terskler.
   - Rapporter avvik (f.eks. snøfokk episoder med vindkast < 15 m/s).

   Bias-kontroller (må gjøres):
    - Flagge sannsynlige inspeksjoner: bruk `Distanse (km)` og `Varighet` i `Rapport 2022-2025.csv` og lag en enkel “inspection_candidate” indikator.

       Konkret (kvantil-basert, slik at heuristikken følger datasettet):

       ```python
       import pandas as pd

       plow = pd.read_csv('data/analyzed/Rapport 2022-2025.csv', sep=';', encoding='utf-8')
       event_key = ['Dato','Starttid','Sluttid','Rode']
       plow_events = plow.drop_duplicates(subset=event_key).copy()

       plow_events['duration'] = pd.to_timedelta(plow_events['Varighet'], errors='coerce')
       plow_events['duration_minutes'] = plow_events['duration'].dt.total_seconds() / 60
       plow_events['distance_km'] = pd.to_numeric(plow_events['Distanse (km)'], errors='coerce')

       q_dist = plow_events['distance_km'].quantile(0.10)
       q_dur = plow_events['duration_minutes'].quantile(0.10)
       plow_events['inspection_candidate'] = (plow_events['distance_km'] <= q_dist) & (plow_events['duration_minutes'] <= q_dur)

       print('q10 thresholds:', float(q_dist), 'km and', float(q_dur), 'minutes')
       print('inspection candidates:', int(plow_events['inspection_candidate'].sum()), 'of', len(plow_events))
       ```
   - Robusthet mot forsinkelse: test terskler med to vinduer:
     - “On-time” vindu: 6t før → 0t etter
     - “Delayed response” vindu: 12t før → 6t etter
     Hvis terskelen kun “fungerer” i delayed-vindu, tyder det på kapasitetsforsinkelse og at terskelen i seg selv kan være riktig selv om loggtidspunkt er sent.
   - For glattføre: ikke krev at vedlikehold (strøing) finnes for å si at værterskler er riktige. Valider primært mot værindikatorer (surface_temperature, nedbør, duggpunkt) og bruk vedlikeholdshendelser kun som støtte.
5. **Visualisering**
   - Eksporter figur/CSV for alle scenarioer (f.eks. `matplotlib` + `df.plot()`), navngi med tidsstempel.

---

## 5. Output-struktur (etter analyse)

Oppdater `data/analyzed/` med følgende mønster:

- `*_weather_correlation_YYYY.csv` – rå datasett for spesifikk kjøring.
- `*_analysis_YYYY.json` – strukturerte sammendrag (mean/median/korrelasjoner).
- `*_report_YYYY.md` – menneskevennlig konklusjon som peker til JSON/CSV.
- Visualiseringer (`*.png`/`*.html`) i `archive/plots/` (opprett mappe ved behov).

### Arkivering
- Flytt eldre Markdown-rapporter til `archive/analysis_docs/` (gjort nå).
- Behold siste `*_report_CURRENT.md` i `data/analyzed/` slik at dashboard/brukere har fersk referanse.

---

## 6. Videre arbeid for ny LLM

1. **Automatiser pipeline** i `scripts/` (f.eks. `scripts/run_weather_analysis.py`).
2. **Legg til tester** som validerer at nye analyser ikke gir færre enn 150 rader og at alle scenarier finnes.
3. **Sammenlign** nye terskler med `agent.md` og logg avvik.
4. **Dokumenter** alltid versjon, commit-hash og tidspunkt i rapportens topp.
5. **Generer diff** mellom ny og forrige analyse (tabell + tekst) for å kunne se trendendringer.

---

## 9. Validering av `src/config.py` mot historikk (må gjøres etter refaktor)

Problemet historisk har vært at “nye analyser” blir overskrevet av gamle verdier og at terskler drifter. Nå som terskler/guardrails er samlet i `src/config.py`, skal de valideres eksplisitt mot `broyting_weather_correlation_2025.csv`.

### 9.1 Hurtig validering (sanity)

Dette sjekker at nøkkeltall i historikken fortsatt stemmer med tersklene i `settings.*`.

Kjørbar variant ligger i scriptet:

```bash
python3 scripts/validate_config_against_history.py
```

Snøfokk (SNØFOKK) skal ikke valideres med “vind alene”. Scriptet printer derfor både
`gust-only` og “gated” regler som speiler `SnowdriftAnalyzer` sitt prinsipp:

- Vindkast-trigger (`gust_max >= settings.snowdrift.wind_gust_warning/critical`)
- Kaldt nok (`air_temp_avg <= settings.snowdrift.temperature_max`)
- Minimum snødekke (`snow_depth >= settings.snowdrift.snow_depth_min_cm`)
- Vind-gate for å filtrere ut korte kast uten vedvarende vind (`wind_avg >= settings.snowdrift.wind_speed_gust_warning_gate`, anbefalt gate ~8 m/s)

Per 13. des 2025 (dedupet `broyting_weather_correlation_2025.csv`) viser scriptet at:
- `gust-only` advarsel (≥ 13 m/s) gir høy treffrate, men mange falske triggere.
- En “gated” regel med `wind_avg >= 8 m/s` + frost + snødekke gir nesten samme treffrate for SNØFOKK, men langt lavere falsk trigger-rate.
- En for streng vind-gate (f.eks. `wind_avg >= 12 m/s`) er for streng i event-data (mister mange SNØFOKK-episoder).

Merk om navngivning i config:

- `settings.snowdrift.wind_speed_gust_warning_gate` er den eksplisitte vind-gaten som brukes i `SnowdriftAnalyzer`.
- `settings.snowdrift.wind_speed_median` er en deprecated alias for bakoverkompatibilitet.

Viktig:
- “Løssnø tilgjengelig” kan ikke valideres fullgodt fra `broyting_weather_correlation_2025.csv` alene (den er event-oppsummert).
   Den valideres best på timeserier (Frost 1H) med 24t lookback, slik `SnowdriftAnalyzer._check_loose_snow()` gjør.

```bash
python3 - <<'PY'
import pandas as pd
from src.config import settings

df = pd.read_csv('data/analyzed/broyting_weather_correlation_2025.csv', parse_dates=['datetime'])
df = df.drop_duplicates(subset=['datetime','scenario']).copy()

cols = ['gust_max','wind_avg','wind_max','precip_total','snow_depth','snow_change','air_temp_avg','surface_temp_avg','dew_point_avg']
q = df.groupby('scenario')[cols].quantile([0.5,0.9]).unstack(level=1)

sd = settings.snowdrift
fs = settings.fresh_snow
sl = settings.slaps

print('Scenariofordeling:', df['scenario'].value_counts().to_dict())

# Snøfokk: vindkast skal være høyt i SNØFOKK-gruppen
snowdrift_gust_p50 = float(q.loc['SNØFOKK', ('gust_max', 0.5)])
print('SNØFOKK gust p50:', snowdrift_gust_p50, '| critical threshold:', sd.wind_gust_critical)

# Separasjon: andre scenarioer bør typisk ligge lavere enn SNØFOKK på p90 gust
for sc in ['ANNET','FRYSEFARE','NYSNØ','SLAPS']:
   p90 = float(q.loc[sc, ('gust_max', 0.9)])
   print(sc, 'gust p90:', p90, '| critical threshold:', sd.wind_gust_critical)

# Nysnø: duggpunkt bør typisk være < 0 i NYSNØ-gruppen
dp_p90 = float(q.loc['NYSNØ', ('dew_point_avg', 0.9)])
print('NYSNØ dew_point_avg p90:', dp_p90, '| dew_point_max:', fs.dew_point_max)

# Slaps: overflaten rundt 0C og duggpunkt ofte > 0
st_p50 = float(q.loc['SLAPS', ('surface_temp_avg', 0.5)])
dp_slaps_p50 = float(q.loc['SLAPS', ('dew_point_avg', 0.5)])
print('SLAPS surface_temp_avg p50:', st_p50, '| slaps temp range:', (sl.temp_min, sl.temp_max))
print('SLAPS dew_point_avg p50:', dp_slaps_p50)
PY
```

Forventet (per 13. des 2025, etter dedupe):
- `SNØFOKK` har `gust_max` p50 ≈ **21.8 m/s** og p90 ≈ **27.0 m/s**, som bør være over/omkring `settings.snowdrift.wind_gust_critical`.
- `NYSNØ` har `dew_point_avg` p90 < 0, som støtter `settings.fresh_snow.dew_point_max = 0.0`.

Hvis disse nøkkeltallene flytter seg betydelig etter en ny analyse, skal tersklene i `src/config.py` revurderes og endringen dokumenteres (dato + hvorfor).

### 9.2 Tolkning av avvik (hvordan unngå “overskriving med gamle sannheter”)

Når valideringen finner avvik mellom terskel og brøyteloggen:
- Sjekk først om avviket kan forklares av inspeksjon/kort tur (mulig falsk positiv i loggen).
- Sjekk deretter forsinkelse: om vær var kritisk før logget starttid (mulig falsk negativ hvis du forventer tidlig brøyting).
- For strøing: avvik kan skyldes under-utført vedlikehold i enkelte sesonger; værterskler kan fortsatt være korrekte.

Beslutningsregel:
- Ikke endre terskler i `src/config.py` basert på enkelteksempler.
- Krev konsistent forbedring på tvers av flere episoder/scenarioer (helst kvantiler/aggregat) før endring.

---

## 7. Hurtigsjekkliste før levering

- [ ] CSV og JSON oppdatert for dagens dato
- [ ] `ANALYSIS_METHOD_GUIDE.md` (denne filen) referert i Slack/README ved større analyser
- [ ] Nye rapporter lagret i `data/analyzed/` og kopiert til backup/S3 ved behov
- [ ] Arkiver gamle Markdown-rapporter for å holde katalogen ren

---

## 8. Validering 30. november 2025

### 8.1 Rask sanity-sjekk

```bash
python3 - <<'PY'
import pandas as pd
from collections import Counter
df = pd.read_csv('data/analyzed/broyting_weather_correlation_2025.csv', parse_dates=['datetime'])
print('Scenariofordeling:', Counter(df['scenario']))
print('Dato:', df['datetime'].min(), '→', df['datetime'].max())
print(df.groupby('scenario')[['air_temp_avg','surface_temp_avg','wind_avg','gust_max','precip_total','snow_change']].mean())
PY
```

Resultat 30. nov 2025:
- Rader: 166 (ANNET 70, NYSNØ 33, SLAPS 26, FRYSEFARE 19, SNØFOKK 18)
- Periode: 21.12.2022 → 22.04.2025
- Snitt per scenario stemmer med forventningene (snøfokk har gust 21.9 m/s, slaps temp +1.5 °C / 12 mm nedbør, nysnø +4.3 cm).

### 8.2 JSON-sammenfatning

```bash
python3 - <<'PY'
import json
with open('data/analyzed/maintenance_weather_analysis.json') as f:
    data = json.load(f)
print('Dato:', data['analysis_date'])
print('Indikatorer:', list(data['indicators'].keys()))
print('Anbefalinger (nysnø):', data['recommendations']['nysnø']['primary_indicators'])
PY
```

Resultat 30. nov 2025:
- `analysis_date`: 2025-11-29T20:59:28
- Indikatorer: nysnø, glatte_veier, snøfokk (22–45 hendelser hver)
- Nysnø toppindikatorer: akkumulert nedbør, vindretning (SE-S), relativ fuktighet → samsvarer med tersklene i koden.

✅ Dette bekrefter at filene fra 29. november er konsistente og kan brukes som autoritativt grunnlag før vi justerer tersklene i `src/config.py`.
