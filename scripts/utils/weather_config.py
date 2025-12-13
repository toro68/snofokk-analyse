#!/usr/bin/env python3
"""Deprecated legacy config helper.

Denne filen var et eldre konfigurasjonssystem med egne terskelverdier i kode og/eller JSON.
Prosjektet bruker nå `src/config.py` (`settings`) som eneste sannhetskilde for terskler.

Hvis du trenger å justere terskler: endre `src/config.py`.
Hvis du trenger hemmeligheter lokalt: bruk miljøvariabler eller `.streamlit/secrets.toml`.
"""


class ConfigManager:  # pragma: no cover
    """Bakoverkompatibel stub.

    Beholder navnet slik at gamle skript feiler tydelig uten å reintrodusere terskler.
    """

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "scripts/utils/weather_config.py er deprecated. Bruk src/config.py (settings) som sannhetskilde."
        )
