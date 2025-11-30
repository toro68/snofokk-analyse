# Fremgangsmåte for videre analyser (LLM + Gullingen data)

Denne veiledningen dokumenterer hvordan analysene som ble kjørt 29. november 2025 ble gjennomført, og hvordan en senere (bedre) LLM bør reprodusere eller utvide dem. Fokus er å beskrive hele kjeden fra datagrunnlag til leveransefiler, med eksplisitte sjekkpunkter og filnavn.

---

## 1. Datagrunnlag

1. **Primærkilde:** `data/analyzed/Rapport 2022-2025.csv` – manuelt beriket brøyte-logg (166 episoder).
2. **Værdata:** Frost API stasjon `SN46220 Gullingen` – elementer som listet i `src/config.py:StationConfig.CORE_ELEMENTS` (temp, bakke, vind, kast, nedbør, snø, fukt, duggpunkt).
3. **Aux-data:** `plowing_data.json` (sanntids brøyting) og Netatmo (valgfritt). Ikke nødvendig for historiske analyser.

### Minimumsfiltrering
- Tidsvindu: 2022-12-01 → 2025-04-30
- Aggregasjoner: 6-timers ruller for snøøkning, 1-timers for nedbør/vind, 24-timers for fersk-snø sjekk.

---

## 2. Forhåndsprosessering

1. **Synkroniser tid**
   - Konverter alle tidsstempler til `Europe/Oslo`.
   - Lag `reference_time` kolonne i pandas (datetime64[ns]).

2. **Feature-berikelse**
   - `temp_diff = air_temperature - surface_temperature`
   - `wind_chill = BaseAnalyzer.calculate_wind_chill()`
   - `snow_change = surface_snow_thickness.diff(window=6h)`
   - `fresh_snow_24h = rolling_sum(surface_snow_thickness.diff, 24h)`

3. **Scenario-tagging** (bruk eksisterende etiketter fra `Rapport 2022-2025.csv` når mulig)
   - Alternativt: kjør `src/analyzers/*` mot dataframes for å gjenbruke logikk.

---

## 3. Analysefiler (29. nov 2025)

Filer generert denne datoen ligger i `data/analyzed/` og inkluderer:

| Fil | Innhold | Formål |
|-----|---------|--------|
| `broyting_weather_correlation_2025.csv` | Rå sammenslått tabell (vær + brøyting) | Basis for videre korrelasjoner |
| `maintenance_weather_analysis.json` | Oppsummering per vedlikeholdstype (snø, slaps, is, inspeksjon) | Grunnlag for terkselvalg |

### Validering
- Kryss-sjekk antall rader mot `Rapport 2022-2025.csv` (166 episoder).
- Verifiser at alle scenariokoder (`NYSNØ`, `SNØFOKK`, `SLAPS`, `FRYSEFARE`, `ANNET`) er representert.

---

## 4. Analysetrinn (reproduserbar pipeline)

1. **Last data** (Python/Notebook/LLM-kode):
   ```python
   df = pd.read_csv('data/analyzed/broyting_weather_correlation_2025.csv', parse_dates=['datetime'])
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
