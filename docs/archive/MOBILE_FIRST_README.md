# 📱 Mobil-First Værapp for Gullingen Skisenter

En komplett mobil-optimalisert værvarslingsapp med fokus på operative beslutninger for Gullingen Skisenter.

## 🎯 Prioritering

Appen er designet med klar prioritering av værforhold som er viktigst for skisenterets drift:

1. **🆕 NYSNØ** - Første prioritet
   - Automatisk deteksjon av nysnømengde
   - Basert på nedbør og temperatur siste 6 timer
   - Kritisk for kjøreopplevelse og sikkerhet

2. **🧊 GLATTE VEIER** - Andre prioritet  
   - Analyser overflatetemperatur og luftfuktighet
   - Detekterer rim, undervann og regn på kald vei
   - Viktig for tilkomst og parkeringsområder

3. **🌪️ SNØFOKK** - Tredje prioritet
   - ML-basert risikovurdering når tilgjengelig
   - Fallback til validerte heuristikker
   - Påvirker sikt og kjøreforhold

## 🚀 Kjøring

### Enkel start:
```bash
./run_mobile_first_app.sh
```

### Manuell start:
```bash
streamlit run mobile_first_weather_app.py
```

## 📋 Krav

### Miljøvariabler (.env fil):
```
FROST_CLIENT_ID=din_api_nøkkel_fra_frost.met.no
WEATHER_STATION=SN59300  # Gullingen (valgfri)
```

### Python-pakker:
```
streamlit
pandas
requests
python-dotenv
```

Installer med:
```bash
pip install streamlit pandas requests python-dotenv
```

## 📱 Mobile-First Funksjoner

### Design:
- **Mobil-først tilnærming** - Optimalisert for telefon og nettbrett
- **Responivt design** - Tilpasser seg alle skjermstørrelser
- **Touch-optimalisert** - Store berøringsområder og enkle gester
- **PWA-støtte** - Kan installeres som app på mobil

### Ytelse:
- **Progressiv lasting** - Kritiske data lastes først
- **Smart caching** - Reduserer API-kall og laster raskere
- **Skeleton loaders** - Visuell feedback under lasting
- **Feilhåndtering** - Graceful degradation ved problemer

### Tilgjengelighet:
- **Høy kontrast** - Lesbart i sollys
- **Store fonter** - Lett å lese på mobil
- **Tydelige indikatorer** - Umiddelbar forståelse av risiko
- **Offline-indikasjon** - Vet når data er gammelt

## 🎨 Brukergrensesnitt

### Hovedskjerm:
1. **Øverst**: Værselskort for høy-risiko situasjoner
2. **Prioriterte kort**: Store kort for nysnø, glattføre, snøfokk
3. **Nåværende forhold**: Kompakte målinger (temp, vind, snø, nedbør)
4. **Værtrend**: Interaktive charts (temperatur, vind, snø, nedbør)

### Informasjonsnivåer:
- **Kritisk**: Varsler og høy-risiko situasjoner
- **Viktig**: Nåværende målinger og trender
- **Detaljert**: Ekspandbare seksjoner med analysedetaljer
- **Teknisk**: Debug-info og datakvalitet (skjult som standard)

## 🔧 Tekniske Detaljer

### Datakilder:
- **Primær**: Frost API (frost.met.no) - Meteorologisk institutt
- **Stasjon**: SN59300 (Gullingen, 639 moh)
- **Oppdateringsfrekvens**: Hvert 5. minutt for kritiske data

### Analysealgoritmer:

#### Nysnø:
- Kombinerer 6-timers nedbør med temperatur
- Høy risiko: ≥10mm nedbør ved ≤1°C
- Moderat risiko: ≥5mm nedbør ved ≤1°C
- Estimerer snødjupde basert på nedbørsmengde

#### Glattføre:
- Kritisk temperaturområde: -3°C til +3°C
- Høy risiko: >90% luftfuktighet eller regn på kald vei
- Bruker overflatetemperatur når tilgjengelig
- Spesiell logikk for rim og undervann

#### Snøfokk:
- ML-modell når tilgjengelig (høyeste presisjon)
- Fallback til validerte heuristikker
- Kombinerer temperatur, vindstyrke og snøtilgjengelighet
- Høy risiko: ≤-5°C + ≥12 m/s vind

### Fallback-strategier:
1. **ML ikke tilgjengelig**: Bruk validerte heuristikker
2. **Komponenter ikke tilgjengelig**: Bruk innebygde algoritmer
3. **API-feil**: Vis sist kjente data med aldersindikasjon
4. **Ingen data**: Tydelige feilmeldinger med løsningsforslag

## 📊 Datakvalitet

Appen validerer datakvalitet og varsler ved:
- **Manglende målinger**: >50% av kritiske parametre mangler
- **Gamle data**: Siste måling er >6 timer gammel
- **API-problemer**: Forbindelsesproblemer eller feil

Kvalitetsscore vises alltid (0-100%) med tiltak ved lav kvalitet.

## 🔄 Auto-refresh

- **Kritiske data**: Hvert minutt når høy risiko
- **Normal drift**: Hvert 5. minutt
- **Lokasjonbasert**: Økt frekvens nær Gullingen
- **Manuel oppdatering**: Alltid tilgjengelig

## 📱 PWA-funksjonalitet

Appen kan installeres som en native app:

### Chrome/Edge:
1. Trykk meny (⋮)
2. Velg "Installer app" eller "Legg til startskjerm"

### Safari (iOS):
1. Trykk del-knappen (□↗)
2. Velg "Legg til på startskjerm"

### Fordeler ved PWA:
- Raskere oppstart
- Offline-støtte (cached data)
- Fullskjerm-visning uten nettleser-UI
- Push-notifikasjoner (fremtidig funksjon)

## 🚨 Viktiger merknader

### Bruk:
- **Kun veiledning**: Data er veiledende, ikke erstatning for profesjonell vurdering
- **Kombiner kilder**: Bruk sammen med andre værkilder
- **Oppdater ofte**: Værforhold endres raskt i fjellet

### Begrensninger:
- **Avhengig av internett**: Krever tilkobling for oppdateringer
- **Én stasjon**: Kun data fra Gullingen værstasjon
- **Automatisk analyse**: Kan ikke erstatte lokal kunnskap

### Sikkerhet:
- **Ingen sensitive data**: Kun offentlige værdata lagres
- **HTTPS**: All kommunikasjon er kryptert
- **Lokal lagring**: Cache er kun midlertidig

## 📞 Support

- **GitHub**: [snofokk-analyse repository](https://github.com/toro68/snofokk-analyse)
- **Issues**: Rapporter bugs via GitHub Issues
- **API-problemer**: Sjekk frost.met.no status

## 📈 Fremtidige funksjoner

- **Push-notifikasjoner**: Automatiske varsler ved høy risiko
- **Historiske data**: Sammenlign med tidligere år
- **Flere stasjoner**: Utvidet dekningsområde
- **Avanserte prognoser**: Varsler 6-24 timer frem
- **Brukertilpasning**: Personlige risikogrenser

---

**Utviklet for Gullingen Skisenter** | **Data fra Meteorologisk institutt** | **Mobile-first design**
