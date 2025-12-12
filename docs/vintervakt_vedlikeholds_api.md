# Gullingen-varsling: integrasjon mot Vintervakt vedlikeholds-API

Denne filen beskriver hvordan Gullingen-varsling (Streamlit) henter et maskinlesbart signal for «vedlikehold utført nylig» fra Vintervakt.

## Formål

Varslingssystemet trenger å vite når det nylig er utført brøyting/strøing/skraping, slik at glattførevarsler kan nedjusteres når forhold sannsynligvis er forbedret.

## Endepunkt (minimum)

### `GET /v1/maintenance/latest`

Returnerer siste arbeidsøkt (foretrekker sist **avsluttede** økt, ellers sist **startede** aktive).

- **Auth**: `Authorization: Bearer <TOKEN>`
- **Caching**: respons kan caches (server setter `Cache-Control`)
- **Tid**: `timestamp_utc` er alltid UTC (`ISO-8601`, med `Z`)

#### Eksempel (200)

```json
{
  "event_id": "abc123",
  "timestamp_utc": "2025-12-12T10:15:00.000Z",
  "event_type": "GRIT",
  "status": "COMPLETED",
  "work_types": ["stroing"],
  "session_id": "abc123",
  "operator_id": "operator_42"
}
```

#### Felt

- `event_id` (string): unik ID for event (i praksis workSession-id)
- `timestamp_utc` (string): ISO-8601 UTC
- `event_type` (string enum): `PLOW | GRIT | SCRAPE | OTHER`
  - Avledes fra `work_types`:
    - `stroing` → `GRIT`
    - `tunbroyting` → `PLOW`
    - `skraping` → `SCRAPE`
    - ellers → `OTHER`
- `status` (string enum): `COMPLETED | ACTIVE | PAUSED | UNKNOWN`
- `work_types` (string[]): rå «workTypes» fra Vintervakt (for debugging)
- `session_id` (string): samme som `event_id` (for fremtidig utvidelse)
- `operator_id` (string, valgfri): operatør

#### Feil

- `401 Unauthorized`: mangler/ugyldig `Authorization`-header
- `403 Forbidden`: token er feil
- `404 Not Found`: ingen arbeidsøkter funnet
- `500 Server Error`: feilkonfig eller intern feil

## URL (base)

Det finnes to praktiske måter å treffe endepunktet på:

1) Via Hosting-domenet (anbefalt hvis dere allerede har «friendly URL» der):
- `https://<hosting-domene>/v1/maintenance/latest`

2) Direkte Cloud Functions-URL:
- `https://<region>-<project>.cloudfunctions.net/v1MaintenanceLatest`

I begge tilfeller må dere sende samme Bearer-token.

## Konfig i Streamlit (secrets)

Legg inn disse verdiene i `st.secrets`:

- `MAINTENANCE_API_BASE_URL` (f.eks. `https://<hosting-domene>`)
- `MAINTENANCE_API_TOKEN` (Bearer-tokenet)

Eksempel `secrets.toml` lokalt:

```toml
MAINTENANCE_API_BASE_URL = "https://example.web.app"
MAINTENANCE_API_TOKEN = "<SETT_INN_TOKEN>"
```

## Streamlit: HTTP-kall kun når appen lastes

Streamlit re-kjører scriptet ved UI-interaksjoner. For å sikre **ett** kall per bruker-session ved «første load», bruk `st.session_state`.

```python
import requests
import streamlit as st

API_BASE = st.secrets["MAINTENANCE_API_BASE_URL"].rstrip("/")
API_TOKEN = st.secrets["MAINTENANCE_API_TOKEN"]


def fetch_latest_work_session():
    url = f"{API_BASE}/v1/maintenance/latest"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


if "latest_maintenance" not in st.session_state:
    try:
        st.session_state["latest_maintenance"] = fetch_latest_work_session()
    except requests.HTTPError as e:
        # Konservativ håndtering: vis feilen, men la appen laste
        st.session_state["latest_maintenance"] = {"error": str(e), "status_code": e.response.status_code if e.response else None}

st.write(st.session_state["latest_maintenance"])
```

### Alternativ: cache på tvers av brukere (valgfritt)

Hvis dere vil redusere antall kall ytterligere (innen samme Streamlit-prosess), bruk `st.cache_data(ttl=...)`.

```python
@st.cache_data(ttl=180)
def fetch_latest_cached():
    return fetch_latest_work_session()
```

## Anbefalt tolkning i varslingslogikk

- Bruk `timestamp_utc` som «sist vedlikehold»-tidspunkt.
- Bruk `event_type` for å skille mellom strøing/brøyting/skraping.
- Bruk `status` til å skille ferdig vs pågående.

## Rask validering med curl

```bash
curl -sS \
  -H "Authorization: Bearer <TOKEN>" \
  "https://<hosting-domene>/v1/maintenance/latest"
```
