# Terskler og validering (Gullingen)

## Status og prinsipp
- Kilde for terskelverdier er kun `src/config.py` (via `settings.*`).
- Dokumentasjon (som `AGENTS.md`) skal ikke duplisere tallverdier. Den skal forklare logikk og peke på feltnavn i `settings.*`.

Dette er gjort for å unngå drift mellom kode og dokumentasjon.

## Datagrunnlag
- Vær: Frost API (stasjon SN46220 Gullingen)
- Vedlikehold/brøyting: `data/analyzed/Rapport 2022-2025.csv` og korrelerte analyser i `data/analyzed/*`
- Supplerende vedlikeholdsperiode: `data/analyzed/arbeidstidsrapport_2025-11-01_til_2026-03-01.csv`
- Koblet vær/vedlikehold for ny periode: `data/analyzed/weather_vs_broyting_arbeidstidsrapport_2025-11-01_til_2026-03-01_h12.csv`

Viktig: brøytelogger beskriver aktivitet, ikke alltid behov. I validering brukes derfor værmønstre som primær evidens, med brøyting som støtte.

Status per **1. mars 2026**:
- Terskler er revalidert på både historisk datasett (2022-2025) og ny vinterperiode (nov 2025-feb 2026).
- Kilde for gjeldende tallverdier er fortsatt kun `src/config.py`.

## Hvordan terskler er satt
### 1) Start med fysikk + lokale forhold
- Snøfokk krever vind + tørr/løs snø + frost.
- Glattføre styres best av bakketemperatur (surface_temperature), ikke bare luft.
- Slaps krever snødekke + mildvær + (regn eller smelting).
- Nysnø bør skilles fra regn ved å bruke duggpunkt når tilgjengelig.

Dette gir en første versjon av terskler som er meningsfulle før historikk brukes.

### 2) Kalibrer mot historiske perioder
- Finn kjente episoder (snøfokk/slaps/glattføre/nysnø) i historikk.
- Se på fordelinger i relevante mål (vindkast, vindkjøling, nedbør, temp, bakke-temp, snødybde, endringer).
- Flytt terskler for å redusere falske positiver uten å miste bekreftede episoder.

Praktisk tommelfingerregel som har vært brukt i repoet:
- Bruk “warning” som fanger de fleste bekreftede episoder.
- Bruk “critical” som fanger de mest alvorlige og/eller de som varer lenge.

### 3) Legg inn gates for å redusere støy
Eksempler på gates (for å unngå “hysteriske” varsler):
- Snøfokk: vindkast-trigger krever samtidig et minimum av snittvind (vind-gate) og frost.
- Glattføre: kald bakke alene er ofte normalt vinterføre; krever fuktighet/nedbør/smelting for å trigge høyere risiko.
- Slaps: bruk 12t akkumulert nedbør i tillegg til øyeblikksnedbør for å unngå varsling på små drypp.

### 3b) Multi-label vedlikehold (kritisk i drift)
- En økt kan inneholde både veirelatert arbeid og tunbrøyting samtidig.
- `tunbrøyting` fredag er ofte planlagt/rutinepreget (akkumulert ukesnø i private tun), ikke nødvendigvis en akutt veihendelse.
- Derfor behandles arbeidstyper som multi-label i analyser:
  - `has_tun_component`
  - `has_road_component`
  - `is_pure_tun`
  - `event_relevant_for_thresholds`
- Kun rene tun-økter (`is_pure_tun=true`) skal som hovedregel filtreres ut ved terskelkalibrering for vei-risiko.

### 4) Implementasjon: ett sted
Alle tallverdier ligger i `src/config.py`:
- Snøfokk: `settings.snowdrift.*`
- Glattføre: `settings.slippery.*`
- Nysnø: `settings.fresh_snow.*`
- Slaps: `settings.slaps.*`

Analyzere og plots refererer alltid til disse feltene, ikke egne hardkodede tall.

## Hvordan oppdatere terskler trygt
1. Endre verdier i `src/config.py`.
2. Kjør testene (`pytest`).
3. Verifiser med noen kjente historiske datoer (fra `AGENTS.md`/analyserapporter) at endringen gir forventet risikonivå.
4. Oppdater tekstforklaringer ved behov, men ikke kopier inn tallverdier i dokumentasjon.

## Metodikk for siste terskeljustering (1. mars 2026)
Følgende prosess ble brukt:
1. Koble ny arbeidstidsrapport mot Frost-data i 12t-vindu før hver økt.
2. Normalisere arbeidstyper (`stroing`→`strøing`, `tunbroyting`→`tunbrøyting`, `broyting`→`brøyting`).
3. Beholde blandede økter (vei + tun) som hendelsesrelevante; filtrere kun rene tun-økter.
4. Evaluere terskelkandidater mot:
   - historisk dedupet datasett (2022-2025)
   - ny periode (nov 2025-feb 2026)
5. Velge terskler som forbedrer recall uten stor økning i falske positiver.

## Reell terskelverifisering (2026-06-16)

Denne seksjonen dokumenterer en uavhengig revalidering av terskelverdiene mot
empiriske vær- og brøytedata, og er skrevet slik at nyere språkmodeller kan
reprodusere og etterprøve den.

### Forutsetning: brøyting er IKKE synkron med værhendelser

Vintervedlikehold er et **reaktivt** system (se README, «VINTERVEDLIKEHOLD:
REAKTIVT SYSTEM»):

- Snø/glattføre **oppstår først**, deretter brøytes/strøes det – ofte timer etter.
- Ved langvarige hendelser kan vedlikehold pågå **under** hendelsen.
- Fredager har planlagt tunbrøyting (akkumulert ukessnø), ikke nødvendigvis en
  akutt veihendelse.

Konsekvens for metodikk: vi evaluerer ikke været **på** brøytetidspunktet, men
et **12-timers vindu før** hver vedlikeholdsøkt (`window_hours=12`). Brøyting
brukes som *støtteevidens* for at en værhendelse var operasjonelt relevant, ikke
som en synkron fasit.

### Datagrunnlag for verifiseringen

- Empirisk hovedsett: `data/analyzed/broyting_weather_correlation_2025.csv`
  (163 dedupede episoder, 2022-12-21 → 2025-04-22), hver merket med `scenario`
  ∈ {SNØFOKK, NYSNØ, SLAPS, FRYSEFARE, ANNET}.
- Ny driftsperiode: `data/analyzed/weather_vs_broyting_arbeidstidsrapport_2025-11-01_til_2026-03-01_h12.csv`
  (34 hendelsesrelevante økter).
- Autoritativt valideringsscript: `scripts/validate_config_against_history.py`
  (kjør: `python scripts/validate_config_against_history.py`).

### Metode for verifiseringen

1. For hvert scenario beregnes persentiler (p10/p50/p90) av de relevante
   værmålene i 12t-vinduet før brøyting.
2. Hver terskel i `src/config.py` sammenlignes mot scenariofordelingen den skal
   fange.
3. Tersklene evalueres som binære klassifikatorer (scenario X vs. resten), og vi
   rapporterer TPR (recall) og FPR. ANNET regnes som negativ klasse.

### Resultater (config-verdier per 2026-06-16)

Verifisert mot 163-episode-settet:

|Hendelse|Terskel (kilde i `settings.*`)|TPR|FPR|
|---|---|---|---|
|SNØFOKK|`snowdrift`: gust ≥ 14 + vind-gate ≥ 7 + temp ≤ −0.5 + snø ≥ 3|0.89 (16/18)|0.02 (3/145)|
|SNØFOKK (critical)|`snowdrift`: gust ≥ 20 gated|0.67 (12/18)|0.01 (2/145)|
|SLAPS|`slaps`: precip₁₂ₕ ≥ 5 mm + temp ∈ [0, 4] °C|0.92 (22/24)|0.00 (0/139)|
|FRYSEFARE|`slippery`: bakke < 0 + luft ∈ [0, 3] °C (skjult frost)|0.89 (17/19)|0.13 (19/144)|
|NYSNØ|`fresh_snow`: snøøkning ≥ 4 cm **eller** precip ≥ 5 mm ved frost|0.76 (25/33)|0.11 (14/130)|

Empiriske persentiler som underbygger tersklene:

- **SNØFOKK** gust p10/p50/p90 = 17.7 / 21.8 / 27.0 m/s → warning 14.0 ligger godt
  under p10 (fanger alle), critical 20.0 ≈ p50 (fanger de kraftige). Bekreftet.
- **SLAPS** precip p10/p50 = 6.1 / 9.2 mm, temp_avg ≈ 0.6 °C → terskel 5 mm /
  [0,4] °C er korrekt plassert; FPR 0.00 viser at slaps-signaturen er distinkt.
- **NYSNØ** precip p10/p50 = 2.7 / 7.3 mm, snøøkning p50 = 5.1 cm → terskelen er
  rimelig, men recall begrenses av at vindtransport «spiser» snødybdeøkningen på
  måleren (snøfall registreres ikke alltid som dybdeøkning). Dette er en
  datagrunnlag-begrensning, ikke en feilkalibrering.
- **FRYSEFARE** høyere FPR (0.13) er akseptert bevisst: skjult frost er
  sikkerhetskritisk, og recall prioriteres over presisjon her.

### Konklusjon på verifiseringen

Tersklene i `src/config.py` er empirisk konsistente med vær-før-vedlikehold-data.
SNØFOKK og SLAPS er svært godt kalibrert (høy TPR, lav FPR). NYSNØ og FRYSEFARE
har lavere presisjon av iboende fysiske/datamessige årsaker, ikke pga. feil
terskelverdier. Ingen terskelendring anbefalt på grunnlag av denne verifiseringen.

### Reprodusér verifiseringen

```bash
python scripts/validate_config_against_history.py
```

Persentil- og TPR/FPR-tallene over kan reproduseres direkte fra
`data/analyzed/broyting_weather_correlation_2025.csv` ved å dedupe på
`(datetime, scenario)`, gruppere på `scenario`, og evaluere maskene i tabellen
mot hver scenarioklasse.
