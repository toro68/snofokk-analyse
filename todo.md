# TODO – Føreforhold Gullingen (2025-11-30)

## ✅ Utført nylig
- Oppdatert analyser og dokumentasjon 12. og 29. november 2025
- Migrert historiske script til `archive/` og ryddet dokumentstruktur
- Sikret at plowman-scraperen caches og brukes i dashboardet

## 🔥 Kritiske prioriteringer
1. Integrere brøyte/strø-data i analyser
   - Bruke `PlowingInfo`/`HistoricalWeatherService` slik at snøfokk/nysnø/slaps/glattføre nullstilles ved nylig tiltak
   - Legge inn felt for manuelt registrerte strø-hendelser
2. Netatmo-integrasjon
   - Fullføre klientauth i `src/netatmo_client.py`
   - Sammenligne Gullingen vs Fjellbergsskardet for inversjon og lokalt vinddekke
3. Robusthet rundt Frost API
   - Implementere fallback til lagrede data ved 5xx / rate limit
   - Varsle i UI hvis viktige elementer mangler (eks. surface_temperature)

## 🧠 Analyseforbedringer
- **SnowdriftAnalyzer**: Vurdere å kombinere vindkast + nysnø-siden-brøyting for å unngå falske alarmer når veier nettopp er ryddet
- **FreshSnowAnalyzer**: Bruk `dew_point` som hovedregel men legg til snøpartikler fra Netatmo når Frost-målinger mangler
- **SlapsAnalyzer**: Kalibrere snøsmelte-terskel på 6t vindu mot `maintenance_weather_analysis.json`
- **SlipperyRoadAnalyzer**: Utnytte `surface_temperature` tidsserie for å se hvor lenge bakken har vært under 0°C

## 🖥️ App & UI
- Vise "snø siden siste brøyting" i hovedpanelet (krever kumulert snødybde + brøyteevent)
- Legge til statuskort for Netatmo når data er tilgjengelig
- Bedre loggpanel for feilmeldinger (Frost/Plowman)

## 🧪 Testing & validering
- Utvide `tests/test_weather_event_detection.py` med scenarier som inkluderer brøyting/strøing
- Legge på regresjonstester mot datasett i `data/analyzed/maintenance_weather_analysis.json`
- Automatisere scraping-test for `plowman_client`

## 📄 Dokumentasjon
- Oppdatere `README.md` og `docs/implementeringsguide.md` med nye analyseresultater fra november 2025
- Dokumentere planlagt Netatmo-integrasjon (arkitektur + API-keys)

## 🔭 Videre muligheter
- Kombinert risiko-score som vekter nysnø + snøfokk + glattføre
- Push-varsler / SMS når risikonivå går til 🔴
- Historiske sammenligninger i Streamlit (uke/måned)
