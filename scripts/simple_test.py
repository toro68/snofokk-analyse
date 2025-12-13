#!/usr/bin/env python3
"""Deprecated legacy test script.

Dette skriptet testet en eldre "scripts/utils/weather_config.py"-basert konfig.
Prosjektet bruker nå `src/config.py` (`settings`) + pytest som primær verifisering.
"""


def main() -> None:
    raise SystemExit(
        "scripts/simple_test.py er deprecated. Kjør `pytest` (evt via .venv) og bruk src/config.py (settings)."
    )


if __name__ == "__main__":
    main()
