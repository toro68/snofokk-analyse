# ML-grenseverdier for snøfokk-deteksjon (peker-dokument)

Denne filen var tidligere en oppsummering med eksplisitte tallverdier. For å unngå
konfigurasjonsdrift er terskler nå definert kun i kode:

- `src/config.py` (bruk `settings.snowdrift.*`)
- `docs/terskler_og_validering.md` (metodikk, uten dupliserte tall)

Hvis du trenger historiske tall for analyseformål, bruk filene under `docs/archive/`
eller rådata i `data/analyzed/`. Ikke kopier terskler inn i app/varsling fra dokumenter.

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
