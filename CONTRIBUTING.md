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
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -r requirements-lock.txt  # For exact reproducible builds
   ```

3. **Install development dependencies**:
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
├── src/                    # Main application code
│   ├── snofokk/           # Core package
│   │   ├── services/      # Service layer (weather, analysis, plotting)
│   │   ├── config.py      # Pydantic configuration
│   │   └── models.py      # Data models
│   └── live_conditions_app.py  # Main Streamlit app
├── tests/                 # Test suite
├── data/                  # Data files
├── docs/                  # Documentation
├── scripts/               # Analysis scripts
└── config/                # Configuration files
```

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
