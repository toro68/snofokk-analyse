# Terskler og validering (Gullingen)

## Status og prinsipp
- Kilde for terskelverdier er kun `src/config.py` (via `settings.*`).
- Dokumentasjon (som `AGENTS.md`) skal ikke duplisere tallverdier. Den skal forklare logikk og peke på feltnavn i `settings.*`.

Dette er gjort for å unngå drift mellom kode og dokumentasjon.

## Datagrunnlag
- Vær: Frost API (stasjon SN46220 Gullingen)
- Vedlikehold/brøyting: `data/analyzed/Rapport 2022-2025.csv` og korrelerte analyser i `data/analyzed/*`

Viktig: brøytelogger beskriver aktivitet, ikke alltid behov. I validering brukes derfor værmønstre som primær evidens, med brøyting som støtte.

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
