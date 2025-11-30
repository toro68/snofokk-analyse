# Contributing Guide for Alarm System

## Development Setup

1. **Clone repository**:
   ```bash
   git clone <repository-url>
   cd alarm-system
   ```

2. **Set up Python environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   # Bruk requirements-lock.txt kun ved behov for helt identiske builds
   ```

3. **Install development dependencies** (dersom ikke allerede i requirements):
   ```bash
   pip install pytest pytest-cov ruff black mypy
   ```

## Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_validert_glattfore.py

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test class
pytest tests/test_validert_glattfore.py::TestPrecipitationDetection
```

## Code Quality

```bash
# Lint code
ruff check .

# Auto-fix linting issues
ruff check --fix .

# Format code
black .

# Type checking
mypy src/
```

## CI/CD

The project uses GitHub Actions for continuous integration:
- **Linting**: Runs ruff for code quality checks
- **Testing**: Runs pytest with coverage reporting
- **Multi-Python**: Tests on Python 3.11 and 3.12
- **Security**: Placeholder for security scanning

## Project Structure

```
alarm-system/
├── src/                     # Hovedapplikasjon (Streamlit)
│   ├── gullingen_app.py     # Aktuell dashboard-app
│   ├── analyzers/           # Risikoanalyse-moduler (snøfokk, slaps, is, nysnø)
│   ├── visualizations/      # Matplotlib-grafer og PyDeck-kart
│   ├── config.py            # Dataclass-konfig (terskler, API)
│   ├── frost_client.py      # Frost API-klient
│   └── netatmo_client.py    # Netatmo-klient (valgfri)
├── tests/                  # Pytest-suite (f.eks. test_validert_glattfore.py)
├── data/                   # Aktive datasett (historiske CSV/JSON)
├── docs/                   # Dokumentasjon
├── scripts/                # Analyse-/hjelpeskript
├── archive/                # Historiske filer (analysis_data/docs/py/root_misc)
└── config/                 # Konfigurasjonsfiler og templates
```

> **Merk:** Flytt gamle resultater til `archive/analysis_*` eller `archive/root_misc/` i stedet for å slette. Disse mappene er ignorert i Git og holder repoet ryddig.

## Making Changes

1. **Create feature branch**: `git checkout -b feature/description`
2. **Write tests**: Add tests for new functionality
3. **Run quality checks**: `ruff check . && pytest`
4. **Commit changes**: Use conventional commit messages
5. **Create pull request**: CI will run automatically

## Testing Guidelines

- Write tests for all new functions
- Use meaningful test names
- Test both happy path and edge cases
- Maintain >80% test coverage for new code

## Code Style

- Line length: 100 characters
- Use type hints
- Follow PEP 8 via ruff and black
- Document complex functions with docstrings
