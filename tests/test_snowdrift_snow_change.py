"""Regresjonstester for snøfokk-analysatorens snøendring og NaN-fallback.

Dekker to feil funnet i terskel-audit:
1. _check_loose_snow brukte datetime.now(UTC) uten å importere datetime/UTC
   -> NameError på NaN-fallback-stien for reference_time.
2. _snow_change_over_window returnerte absolutt cm over vinduet men ble merket
   og sammenlignet som cm/h. Skal nå returnere ekte rate (cm/h).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from src.analyzers.snowdrift import SnowdriftAnalyzer


def test_snow_change_over_window_returns_rate_cm_per_hour() -> None:
    """6 cm økning over 6 timer skal gi 1.0 cm/h, ikke 6.0."""
    start = datetime(2024, 2, 8, 0, 0, tzinfo=UTC)
    df = pd.DataFrame(
        {
            "reference_time": [start + timedelta(hours=i) for i in range(7)],
            "surface_snow_thickness": [60.0 + i for i in range(7)],  # +1 cm/t
        }
    )

    rate = SnowdriftAnalyzer._snow_change_over_window(df)

    assert rate == 1.0


def test_snow_change_over_window_handles_negative_transport_rate() -> None:
    """-3 cm over 6 timer (vindtransport) skal gi -0.5 cm/h."""
    start = datetime(2024, 2, 8, 0, 0, tzinfo=UTC)
    df = pd.DataFrame(
        {
            "reference_time": [start + timedelta(hours=i) for i in range(7)],
            "surface_snow_thickness": [60.0 - 0.5 * i for i in range(7)],
        }
    )

    rate = SnowdriftAnalyzer._snow_change_over_window(df)

    assert rate == -0.5


def test_check_loose_snow_handles_unparseable_reference_time() -> None:
    """NaN/uparsbar reference_time skal ikke krasje (datetime.now-fallback)."""
    df = pd.DataFrame(
        {
            "reference_time": ["ikke-en-dato", "heller-ikke"],
            "air_temperature": [-5.0, -4.0],
        }
    )

    analyzer = SnowdriftAnalyzer()

    # Skal returnere en gyldig dict uten å kaste NameError.
    result = analyzer._check_loose_snow(df)

    assert isinstance(result, dict)
    assert "available" in result
