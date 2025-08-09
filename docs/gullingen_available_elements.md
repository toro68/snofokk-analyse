# Gullingen Skisenter (SN46220) - Tilgjengelige Værelementer

**Generert:** 9. august 2025  
**Stasjon:** SN46220 (Gullingen Skisenter)  
**Høyde:** ~400 moh  
**Datakilde:** Meteorologisk institutt (Frost API)

## Oversikt

Gullingen Skisenter har **116 tilgjengelige værelementer** fordelt på **20 hovedkategorier**. Data er tilgjengelig fra **februar 2018** og frem til i dag.

## Hovedkategorier for Væranalyse

### 🌡️ **Temperatur (air_temperature)**
| Element | Enhet | Oppløsning | Tilgjengelig fra | Høyde |
|---------|-------|------------|------------------|-------|
| `air_temperature` | °C | PT1H, PT10M | 2018-02-07 | 2m |

### 💨 **Vind (wind_speed, wind_from_direction)**
| Element | Enhet | Oppløsning | Tilgjengelig fra | Høyde |
|---------|-------|------------|------------------|-------|
| `wind_speed` | m/s | PT1H | 2018-02-07 | 10m |
| `wind_from_direction` | grader | PT1H | 2018-02-07 | 10m |

### ❄️ **Snø (surface_snow_thickness)**
| Element | Enhet | Oppløsning | Tilgjengelig fra |
|---------|-------|------------|------------------|
| `surface_snow_thickness` | cm | PT1H, PT10M, P1D | 2018-02-11 |

### 🌧️ **Nedbør og Fuktighet**
| Element | Enhet | Oppløsning | Tilgjengelig fra | Høyde |
|---------|-------|------------|------------------|-------|
| `relative_humidity` | % | PT1H | 2018-02-07 | 2m |
| `dew_point_temperature` | °C | PT1H | 2018-02-07 | 2m |

### 🌡️ **Overflatetemperatur**
| Element | Enhet | Oppløsning | Tilgjengelig fra |
|---------|-------|------------|------------------|
| `surface_temperature` | °C | PT1H, PT10M | 2018-02-11 |

### 🔋 **Stasjonsstatus**
| Element | Enhet | Oppløsning | Tilgjengelig fra |
|---------|-------|------------|------------------|
| `battery_voltage` | V | PT1H | 2018-02-07 |

## Avledede Elementer (Statistikk)

### 📊 **Maksimumsverdier (max)**
- `max(air_temperature P1D)` - Døgnmaks temperatur
- `max(wind_speed P1D)` - Døgnmaks vindstyrke  
- `max(wind_speed_of_gust P1D)` - Døgnmaks vindkast
- `max(surface_snow_thickness P1D)` - Døgnmaks snødybde
- Plus 16 andre maksimumsvarianter

### 📉 **Minimumsverdier (min)**
- `min(air_temperature P1D)` - Døgnmin temperatur
- `min(wind_speed P1D)` - Døgnmin vindstyrke
- `min(surface_snow_thickness P1D)` - Døgnmin snødybde  
- Plus 14 andre minimumsvarianter

### 📈 **Gjennomsnittsverdier (mean)**
- `mean(air_temperature P1D)` - Døgnmiddeltemperatur
- `mean(wind_speed P1D)` - Døgnmiddel vindstyrke
- `mean(relative_humidity P1D)` - Døgnmiddel luftfuktighet
- Plus 26 andre gjennomsnittsvarianter

### ➕ **Sumverdier (sum)**
- `sum(precipitation_amount P1D)` - Døgnnedbør
- `sum(duration_of_sunshine P1D)` - Døgnsol
- Plus 11 andre sumvarianter

## Spesialberegninger

### 🧮 **Graddager (integral_of_excess/deficit)**
- `integral_of_excess(mean(air_temperature P1D) P1D 5.0)` - Vekstgraddager (>5°C)
- `integral_of_deficit(mean(air_temperature P1D) P1D 0.0)` - Frostgraddager (<0°C)
- `integral_of_deficit(mean(air_temperature P1D) P1D 17.0)` - Oppvarmingsgraddager (<17°C)

### 📅 **Tidspunkter (over_time)**
- `over_time(time_of_maximum_wind_speed P1M)` - Tidspunkt for maks vindstyrke
- `over_time(time_of_minimum_air_temperature P1D)` - Tidspunkt for min temperatur

### 🔢 **Telleverdier (number_of_days_gte)**
- `number_of_days_gte(mean(air_temperature P1D) P1M 0.0)` - Antall dager med temp ≥0°C

## Tidsoppløsninger

| Kode | Betydning | Beskrivelse |
|------|-----------|-------------|
| PT1H | 1 time | Timesverdier |
| PT10M | 10 minutter | 10-minuttersverdier |
| P1D | 1 døgn | Døgnverdier |
| P1M | 1 måned | Månedsverdier |

## Anbefalt Elementbruk for Væranalyse

### 🔥 **Live Væranalyse (PT1H oppløsning)**
```
air_temperature        # Temperatur (°C)
wind_speed            # Vindstyrke (m/s)  
wind_from_direction   # Vindretning (grader)
surface_snow_thickness # Snødybde (cm)
relative_humidity     # Luftfuktighet (%)
surface_temperature   # Bakketemperatur (°C)
```

### 📊 **Historisk Analyse (P1D oppløsning)**
```
mean(air_temperature P1D)    # Døgnmiddeltemperatur
max(air_temperature P1D)     # Døgnmakstemperatur  
min(air_temperature P1D)     # Døgnmintemperatur
max(wind_speed P1D)          # Døgnmaks vindstyrke
sum(precipitation_amount P1D) # Døgnnedbør
```

## API-eksempler

### Hent live værdata (siste 24 timer)
```bash
curl -u "API_KEY:" \
"https://frost.met.no/observations/v0.jsonld?sources=SN46220&elements=air_temperature,wind_speed,surface_snow_thickness,relative_humidity&referencetime=2025-08-08T12:00:00Z/2025-08-09T12:00:00Z"
```

### Hent historisk døgndata (februar 2018)
```bash
curl -u "API_KEY:" \
"https://frost.met.no/observations/v0.jsonld?sources=SN46220&elements=mean(air_temperature%20P1D),max(wind_speed%20P1D),sum(precipitation_amount%20P1D)&referencetime=2018-02-01T00:00:00Z/2018-02-28T23:59:59Z"
```

## Kvalitetskoder

| Kode | Beskrivelse |
|------|-------------|
| 0 | God kvalitet |
| 1 | Kontrollert, usikker |
| 2 | Korrigert |
| 3 | Ikke kontrollert |

## Ytelseskategorier

| Kategori | Beskrivelse |
|----------|-------------|
| A | Høyeste kvalitet |
| B | God kvalitet |  
| C | Akseptabel kvalitet |

## Eksponeringskategorier

| Kategori | Beskrivelse |
|----------|-------------|
| 1 | Beskyttet |
| 2 | Delvis eksponert |
| 3 | Fullt eksponert |

## Notater

- **Mest relevante elementer** for snøfokk og glatt vei-analyse: `air_temperature`, `wind_speed`, `surface_snow_thickness`, `relative_humidity`
- **Anbefalt oppløsning** for live analyse: PT1H (timesverdier)
- **Datahistorikk** går tilbake til februar 2018 for de fleste elementer
- **API-nøkkel** kreves for alle forespørsler til Frost API
- **Tidsoppløsning-filtrering** anbefales for konsistente resultater

---
*Dokumentet generert automatisk basert på Frost API metadata for SN46220 Gullingen Skisenter*
