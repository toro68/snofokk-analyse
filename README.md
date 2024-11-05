# Snøfokk-analyse

En Streamlit-applikasjon for analyse av snøfokk-risiko basert på værdata fra Frost API.

## Funksjoner

- Henter værdata fra Frost API
- Analyserer risiko for snøfokk basert på multiple parametere
- Visualiserer kritiske perioder og værforhold
- Lagrer og administrerer analyseinnstillinger
- Støtter detaljert analyse av vindretninger og værforhold

## Installasjon

1. Klon repositoriet:

    ```bash
    git clone https://github.com/dittbrukernavn/snofokk-analyse.git
    cd snofokk-analyse
    ```

2. Sett opp et virtuelt miljø og installer avhengigheter:

    ```bash
    python -m venv venv
    source venv/bin/activate  # For Unix/Linux/Mac
    # eller
    .\venv\Scripts\activate  # For Windows

    pip install -r requirements.txt
    ```

3. Konfigurer hemmeligheter ved å opprette en `.streamlit/secrets.toml`-fil:

    ```toml
    [general]
    FROST_CLIENT_ID = "din-frost-api-nøkkel"
    FROST_STATION_ID = "SN46220"
    ```

4. Kjør applikasjonen:

    ```bash
    streamlit run app.py
    ```

## Feilsøking

Hvis du opplever problemer:

1. **Sjekk Filrettigheter:** Sørg for at `app.py` har nødvendige rettigheter til å bli kjørt.
2. **Loggfilanalyse:** Sjekk `logs/snofokk_debug.log` for detaljerte feilmeldinger.
3. **Miljøvariabler:** Forsikre deg om at alle nødvendige miljøvariabler er satt korrekt, enten via `secrets.toml` eller direkte i miljøet.
4. **Kjør Lokalt:** Prøv å kjøre applikasjonen lokalt for å se om feilen kan reproduseres:
    ```bash
    streamlit run app.py
    ```
5. **Dependencies:** Sørg for at alle avhengigheter er korrekt installert:
    ```bash
    pip install --upgrade --force-reinstall -r requirements.txt
    ```
6. **Streamlit Cloud Konfigurasjon:** Når du deployerer til Streamlit Cloud, sørg for at:
    - Repositoriet er korrekt koblet.
    - `app.py` er valgt som hovedmodulen.
    - Hemmeligheter (`secrets.toml`) er korrekt konfigurert i Streamlit Cloud dashboard.

## Licens

[MIT](LICENSE)
