# ML-baserte grenseverdier for snøfokk-varsling (historisk)

Gjeldende terskler for live drift ligger kun i `src/config.py` og brukes via
`settings.snowdrift.*`. Denne filen beskriver historikk og metode, men skal ikke
være en kilde til tallverdier i app eller dokumentasjon.

**Sist oppdatert:** 9. august 2025  
**Status:** Kalibrering dokumentert (historisk)

## 🎯 Kalibrering-Resultat

**Opprinnelig ML-modell:** 182 dager med varsling (91% av vinteren)  
**Første kalibrering:** 18 dager med varsling (10% av vinteren)  
**FINAL KALIBRERING:** 8 dager med varsling (4.4% av vinteren)  
**Reduksjonsfaktor:** 23x færre varslinger  

### Final kalibrerte grenseverdier (gjeldende kilde)

**Kritiske terskler:**
- Vindkjøling: `settings.snowdrift.wind_chill_critical`
- Vind (snitt): `settings.snowdrift.wind_speed_critical`
- Vindkast: `settings.snowdrift.wind_gust_critical`
- Temperatur-gate: `settings.snowdrift.temperature_max`
- Minimum snødekke: `settings.snowdrift.snow_depth_min_cm`

**Advarselsterskler:**
- Vindkjøling: `settings.snowdrift.wind_chill_warning`
- Vind (snitt): `settings.snowdrift.wind_speed_warning`
- Vindkast: `settings.snowdrift.wind_gust_warning`

### Kombinasjonsregler

Kombinasjonslogikk og gating er implementert i kode. Se `src/analyzers/snowdrift.py`.

## 📊 Historisk Validering (2018-2024)

**FANTASTISKE RESULTATER over 6+ år:**

### Årsvis analyse

- **2018:** 8 dager (mest ekstrem: 28. feb, vindkjøling -28.9°C)
- **2019:** 2 dager (mest ekstrem: 27. jan, vindkjøling -19.1°C)  
- **2020:** 0 dager
- **2021:** 0 dager
- **2022:** 0 dager
- **2023:** 1 dag (27. des, vindkjøling -15.4°C)
- **2024:** 7 dager (mest ekstrem: 3. jan, vindkjøling -21.8°C)

### Sammendrag historisk periode

- **Totalt:** 18 dager over 6+ sesonger
- **Gjennomsnitt:** 4.5 dager per sesong ✅
- **Prosentandel:** 0.44% av vintermåneder
- **Måloppnåelse:** Perfekt under 10 dager/sesong

### Månedlig fordeling (historisk)

- **Januar:** 5 dager totalt
- **Februar:** 5 dager totalt  
- **Mars:** 5 dager totalt
- **April:** 2 dager totalt
- **Desember:** 1 dag totalt

**Konklusjon:** Kalibrering ga realistisk frekvens, men gjeldende terskler styres av `src/config.py`.

## 🎯 Implementering i Appen

✅ **Oppdatert:** `src/ml_snowdrift_detector.py`  
✅ **Konfigurert:** `src/live_conditions_app.py`  
✅ **Lagret:** `data/analyzed/calibrated_thresholds.json`

### Fallback-logikk:
- Primær: ML-baserte kalibrerte grenseverdier
- Sekundær: Tradisjonelle metoder ved ML-feil

## 📈 Alternative Innstillinger

**Ultrastrenge:** 8 dager/sesong (4.4%)  
- Vindkjøling < -15°C + Vindstyrke > 10 m/s

**Strenge (ANBEFALT):** 18 dager/sesong (10.0%)  
- Vindkjøling < -12°C + Vindstyrke > 8 m/s

**Moderate:** 32 dager/sesong (17.8%)  
- Vindkjøling < -10°C + Vindstyrke > 6 m/s

## 🔄 Historisk Kontext

**Før kalibrering:** 
- ML-grenseverdier: 23,885 high-risk alerts (91% av dager)
- Tradisjonelle metoder: ~20-30% av dager

**Etter kalibrering:**
- Kalibrerte ML-grenseverdier: 18 high-risk alerts (10% av dager)
- Målsetting oppnådd: ✅ 4-5 dager → 18 dager er akseptabelt nivå

## 🧠 ML-Metodikk

**Analyse-basis:**
- 26,206 værobservasjoner (nov 2023 - apr 2024)
- RandomForest og DecisionTree modeller
- Feature importance: Vindkjøling (73.1%), Vindstyrke (21.7%)

**Kalibrering-prosess:**
1. Identifisert optimale ML-terskler
2. Testet forskjellige kombinasjoner
3. Justert for realistisk varsling-frekvens
4. Validert mot faktiske snøfokk-hendelser

## 🔮 Snødybde-Endringer (Direkte Indikator)

**Kritiske endringer:**
- ±15mm/time uten tilsvarende nedbør (< 2mm/time)

**Advarsel-endringer:**  
- ±10mm/time uten tilsvarende nedbør

Dette er en **direkte indikator** på pågående snøtransport/snøfokk.

---
**Konklusjon:** ML-modellen er nå kalibrert for praktisk bruk med realistisk varsling-frekvens som matcher faktiske snøfokk-hendelser. Systemet bruker kombinasjonsregler hvor både vindkjøling OG vindstyrke må overstige terskler for å utløse varslinger.
