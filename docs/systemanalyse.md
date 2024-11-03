# Snøfokk-analysator
1. Hovedfunksjonalitet:
- Henter værdata fra Frost API (stasjon SN46220)
- Beregner snøfokk-risiko basert på flere faktorer
- Identifiserer sammenhengende risikoperioder
- Visualiserer data og kritiske perioder
2. Nøkkelparametre:
python
# Vindterskler
sustained_wind >= 8.0  # Høy risiko
sustained_wind >= 6.5  # Moderat risiko
windgust >= 15.0      # Forsterkende faktor
# Temperaturterskler
temp <= -2.0  # Høy risiko
temp <= 0.0   # Moderat risiko
# Snøforhold
unexplained_snow_change >= 1.5  # Høy risiko
unexplained_snow_change >= 0.8  # Moderat risiko
unexplained_snow_change >= 0.3  # Lav risiko

3. Risikoberegning:
- Vektet scoring-system (0-100)
- Krav om både vind og enten temperatur eller snøforhold
- Tar hensyn til løs snø i terrenget
- Skiller mellom nedbør og vindtransportert snø
4. Periodeidentifisering:
- Minimum 2 timers varighet
- Sammenhengende perioder med score > 30
- Fire risikonivåer: Lav, Moderat, Høy, Kritisk
5. Visualiseringer:
- Standardvisning med 5 grafer (risiko, vind, temperatur, snø, nedbør)
- Spesialisert visning for kritiske perioder
- Interaktive Plotly-grafer
6. Input-data som brukes:
python
elements = [
    "surface_snow_thickness",
    "wind_speed",
    "max(wind_speed_of_gust PT1H)",
    "wind_from_direction",
    "air_temperature",
    "sum(precipitation_amount PT1H)"
]

7. Hovedfunksjoner:
python
fetch_frost_data()           # Henter værdata
calculate_snow_drift_risk()  # Beregner risiko
identify_risk_periods()      # Identifiserer perioder
plot_risk_analysis()        # Standard visualisering
plot_critical_periods()     # Kritiske perioder
analyze_risk_patterns()     # Statistisk analyse

For å bruke systemet i en ny implementasjon trenger du:
1. Alle importerte biblioteker (pandas, numpy, plotly, requests)
2. API-nøkkel for Frost
3. Alle hovedfunksjoner fra koden
4. Kjøre main()-funksjonen for å starte analysen


Hovedforbedringene inkluderer:

Nye værfaktorer:


Bakketemperatur vs. lufttemperatur (temp_gradient)
Luftfuktighet som påvirkningsfaktor
Nedbørintensitet
Temperaturstabilitet


Forbedret risikovurdering:


Tar hensyn til temperaturgradienter
Inkluderer luftfuktighet som forsterkende faktor
Vurderer temperaturstabilitet
Mer nyansert vindanalyse med maksimal vindhastighet


Nye beregnede parametere:


Temperaturstabilitet
Overflatenedkjøling
Fuktighetsfaktor
Nedbørintensitet
