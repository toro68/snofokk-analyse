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
