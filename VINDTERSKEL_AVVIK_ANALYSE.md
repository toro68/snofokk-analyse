# 🚨 KRITISK AVVIK I VINDTERSKLER

## ⚠️ PROBLEM IDENTIFISERT

Det er store avvik mellom ML-kriteriene for snøfokk og vår empiriske vindblåst snø-forskning:

### 📊 SAMMENLIGNING AV VINDTERSKLER

| Kriterium | ML Snøfokk | Empirisk Vindblåst Snø | Avvik |
|-----------|------------|-------------------------|-------|
| **Kritisk vind** | `5.0 m/s` | `12.2 m/s (median)` | **143% for lav!** |
| **Advarsel vind** | `4.0 m/s` | `10 m/s (minimum)` | **150% for lav!** |
| **Empirisk grunnlag** | Grid Search | 149 episoder + 29 vindblåst snø | Real data |

### 🧪 EMPIRISKE FUNN

**Fra 149 episoder med vinddata:**
- **Median vindterskel**: 12.2 m/s for snømengde-reduksjon
- **Kritisk vindstyrke**: > 10 m/s for snow drift
- **29 vindblåst snø-episoder** alle med vind > 9 m/s

**Eksempler på empiriske vindblåst snø-episoder:**
- 30. des 2022: **11.6 m/s** vind, -9cm snø-reduksjon
- 6. jan 2023: **16.3 m/s** vind, -102cm snø-reduksjon  
- 10. feb 2024: **14.3 m/s** vind, -698cm snø-reduksjon

### 🎯 PROBLEM MED ML-KRITERIER

**ML Grid Search basert på:**
- Snøfokk-dager 2023-2024 (9 dager)
- Målsetning: 8-10 dager per sesong
- **Problem**: Inkluderer sannsynligvis ikke vindblåst snø-transport

**Empirisk validering viser:**
- Vind 4-5 m/s gir **IKKE** signifikant snø-transport
- Vindblåst snø krever **minimum 10 m/s**
- Median terskel er **12.2 m/s**

### 🔧 ANBEFALING

**Oppdater snøfokk-kriteriene:**

```python
# GAMMEL (ML-basert, for lav)
if (wind_chill < -15.0 and wind_speed > 5.0 and snow_depth > 0.26):
    return "kritisk"
elif (wind_chill < -12.0 and wind_speed > 4.0 and snow_depth > 0.20):
    return "advarsel"

# FORESLÅTT (empirisk validert)
if (wind_chill < -15.0 and wind_speed > 10.0 and snow_depth > 0.26):
    return "kritisk"
elif (wind_chill < -12.0 and wind_speed > 8.0 and snow_depth > 0.20):
    return "advarsel"
```

### 🎯 KONSEKVENSER AV NÅVÆRENDE KRITERIER

- **For mange falske alarmer** ved 4-6 m/s vind
- **Undervurderer** real vindblåst snø-risiko
- **Ikke i samsvar** med empiriske funn

**Status**: Kritisk behov for oppdatering av vindterskler! 🚨
