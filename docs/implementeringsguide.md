# Implementeringsguide: Snødybde-Dynamisk Snøfokk-Deteksjon

## Oversikt

Denne guiden beskriver implementeringen av forbedret snøfokk-deteksjon som tar hensyn til snødybde-dynamikk. Løsningen inkluderer både en live web-app og research analyzer.

## Systemarkitektur

```
Frost API → Data Processing → Analysis Engine → User Interface
    ↓              ↓              ↓              ↓
 Værdata → Snødynamikk-features → Risikovurdering → Live app/Rapporter
```

## Kjernefunksjoner

### 1. Snødybde-Endring Beregning

```python
def calculate_snow_dynamics(df: pd.DataFrame) -> pd.DataFrame:
    """Beregn snødybde-endringer for snødynamikk-analyse."""
    
    # Grunnleggende endringer
    df['snow_change_1h'] = df['surface_snow_thickness'].diff()
    df['snow_change_3h'] = df['surface_snow_thickness'].diff(3)
    df['snow_change_6h'] = df['surface_snow_thickness'].diff(6)
    
    # Klassifisering
    df['fresh_snow_1h'] = (df['snow_change_1h'] >= 0.3).astype(int)
    df['snow_transport_1h'] = (df['snow_change_1h'] <= -0.2).astype(int)
    
    # Dynamikk-faktor
    df['snow_dynamics_factor'] = 1.0
    df.loc[df['fresh_snow_1h'] == 1, 'snow_dynamics_factor'] = 1.2
    df.loc[df['snow_transport_1h'] == 1, 'snow_dynamics_factor'] = 1.3
    
    return df
```

### 2. Dynamiske Vindterskler

```python
def get_wind_threshold(snow_conditions: dict) -> float:
    """Beregn vindterskel basert på snøforhold."""
    
    if snow_conditions['fresh_snow']:
        return 5.0  # Senket ved nysnø
    elif snow_conditions['snow_transport']:
        return 6.0  # Standard med transport-bekreftelse
    else:
        return 6.0  # Standard terskel
```

### 3. Forbedret Løssnø-Logikk

```python
def enhanced_loose_snow_gate(df: pd.DataFrame) -> pd.Series:
    """Forbedret løssnø-vurdering med nysnø-override."""
    
    # Standard kriterier
    no_mild_weather = df['temp_above_zero_last_24h'] == 0
    continuous_frost = df['continuous_frost_12h'] == 1
    
    # Snødynamikk-override
    fresh_snow = df['fresh_snow_1h'] == 1
    fresh_snow_period = df['fresh_snow_6h'] == 1
    
    # Kombinert logikk
    loose_snow = (
        no_mild_weather |
        continuous_frost |
        fresh_snow |
        fresh_snow_period
    )
    
    return loose_snow.astype(int)
```

## Live App Implementering

### Hovedkomponenter

**1. LiveConditionsChecker klasse**
- Håndterer API-kall til Frost
- Beregner snødybde-endringer
- Utfører risikovurdering med dynamiske kriterier

**2. Snødynamikk-features**
- Sanntids beregning av snøendringer
- Visuell indikasjon av nysnø/transport
- Dynamisk tilpasning av vindterskler

**3. Brukergrensesnitt**
- Snøendring-indikatorer med emojis
- Utvidede kriterier-forklaringer
- Info-boks for snødynamikk

### Konfigurasjon

```python
# Konfigurerbare parametere
FRESH_SNOW_THRESHOLD = 0.3    # cm/h
TRANSPORT_THRESHOLD = -0.2    # cm/h
WIND_BASE_THRESHOLD = 6.0     # m/s
WIND_FRESH_SNOW_THRESHOLD = 5.0  # m/s
TEMP_THRESHOLD = -1.0         # °C
SNOW_DEPTH_THRESHOLD = 3.0    # cm
```

## Research Analyzer

### Enhanced Features

**1. Utvidede snødynamikk-variabler:**
- `snow_change_1h`, `snow_change_3h`, `snow_change_6h`
- `fresh_snow_1h`, `snow_transport_1h`
- `snow_dynamics_factor`
- `wind_persistent_3h`

**2. Forbedret risikoklassifisering:**
```python
def enhanced_risk_classification(row: pd.Series) -> tuple:
    """Klassifiser risiko med snødynamikk."""
    
    # Grunndata
    wind = row['wind_speed']
    temp = row['air_temperature']
    fresh_snow = row['fresh_snow_1h']
    transport = row['snow_transport_1h']
    
    # Dynamiske terskler
    if fresh_snow:
        threshold = 5.0
        multiplier = 1.2
    elif transport:
        threshold = 6.0
        multiplier = 1.3
    else:
        threshold = 6.0
        multiplier = 1.0
    
    # Risikovurdering
    effective_wind = wind * multiplier
    
    if effective_wind >= 8.0 and temp <= -1:
        return 'high', ['Enhanced criteria met']
    elif effective_wind >= threshold and temp <= -1:
        return 'medium', ['Basic criteria met']
    else:
        return 'low', ['Criteria not met']
```

## Dataflyt og Prosessering

### 1. Data Innhenting
```
Frost API → JSON respons → DataFrame konvertering → Tidssortering
```

### 2. Feature Engineering
```
Rådata → Snødybde-diff → Klassifisering → Dynamikk-faktorer
```

### 3. Risikovurdering
```
Features → Dynamiske terskler → Risikoklassifisering → Output
```

### 4. Brukergrensesnitt
```
Risikodata → Visuell presentasjon → Interaktive elementer
```

## Testing og Validering

### Enhetstester

```python
def test_snow_dynamics_calculation():
    """Test snødybde-endring beregning."""
    
    # Test data
    df = pd.DataFrame({
        'surface_snow_thickness': [10, 10.5, 9.8, 10.2]
    })
    
    # Beregn endringer
    result = calculate_snow_dynamics(df)
    
    # Verifiser
    assert result['snow_change_1h'].iloc[1] == 0.5
    assert result['fresh_snow_1h'].iloc[1] == 1
    assert result['snow_transport_1h'].iloc[2] == 0
```

### Integrasjonstester

```python
def test_live_app_integration():
    """Test full live app workflow."""
    
    checker = LiveConditionsChecker()
    df = checker.get_current_weather_data(hours_back=6)
    
    if df is not None:
        result = checker.analyze_snowdrift_risk(df)
        assert 'risk_level' in result
        assert 'dynamics' in result
```

## Feilhåndtering

### API-robusthet
- Timeout håndtering (30s)
- Retry-logikk ved feil
- Graceful degradation ved manglende data

### Data-validering
- Negative snødybder → 0
- Outlier-deteksjon
- Temporal konsistens-sjekk

### Brukervennlig feilmeldinger
```python
if df is None or len(df) == 0:
    return {
        "risk_level": "unknown", 
        "message": "Ingen data tilgjengelig - sjekk nettverkstilkobling"
    }
```

## Performance Optimalisering

### Caching
```python
@lru_cache(maxsize=10)
def get_current_weather_data(hours_back: int) -> pd.DataFrame:
    """Cached weather data retrieval."""
    # Implementation med 1-time cache
```

### Effektiv databehandling
- Pandas vectorized operasjoner
- Minimal memory footprint
- Batch processing for store datasett

## Deployment

### Krav
```txt
streamlit>=1.28.0
pandas>=2.0.0
numpy>=1.24.0
requests>=2.28.0
python-dotenv>=1.0.0
matplotlib>=3.7.0
```

### Miljøvariabler
```env
FROST_CLIENT_ID=your_frost_api_key
WEATHER_STATION=SN46220
```

### Kjøring
```bash
# Aktiver miljø
source venv/bin/activate

# Start live app
streamlit run src/live_conditions_app.py

# Kjør research analyzer
python scripts/analysis/enhanced_snowdrift_analyzer.py --days 30
```

## Vedlikehold

### Overvåking
- API responstider
- Dataoppsett og -kvalitet
- Brukerinteraksjon og ytelse

### Oppdateringer
- Kalibrering av terskelverdier
- Tilleggsstasjoner og terrengtyper
- UI/UX forbedringer basert på feedback

### Logging
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='snowdrift_analysis.log'
)
```

---

**Implementeringsguide versjon:** 1.0  
**Siste oppdatering:** 9. august 2025
