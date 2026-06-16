"""Tester for normalisering av surface_snow_thickness i FrostClient.

Frost bruker -1 som sentinel for "snøfri/bar mark". Den skal tolkes som 0 cm,
ikke som en reell snødybde på -1 cm, slik at snøendrings-beregninger i
analysatorene ikke får falske utslag på overgangen bar mark <-> snø.
"""

from __future__ import annotations

import pandas as pd

from src.frost_client import FrostClient


def test_sentinel_minus_one_becomes_zero() -> None:
    df = pd.DataFrame(
        {
            "reference_time": pd.to_datetime(
                ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"], utc=True
            ),
            "surface_snow_thickness": [-1.0, 3.3],
        }
    )

    out = FrostClient._normalize_snow_depth(df)

    assert out["surface_snow_thickness"].iloc[0] == 0.0
    assert out["surface_snow_thickness"].iloc[1] == 3.3


def test_other_negative_values_become_nan() -> None:
    df = pd.DataFrame(
        {
            "reference_time": pd.to_datetime(
                ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"], utc=True
            ),
            "surface_snow_thickness": [-5.0, 12.0],
        }
    )

    out = FrostClient._normalize_snow_depth(df)

    assert pd.isna(out["surface_snow_thickness"].iloc[0])
    assert out["surface_snow_thickness"].iloc[1] == 12.0


def test_snow_change_not_inflated_by_sentinel() -> None:
    """Overgang -1 (bar mark) -> 7.6 cm skal gi +7.6 cm, ikke +8.6 cm."""
    df = pd.DataFrame(
        {
            "reference_time": pd.to_datetime(
                ["2026-01-01T00:00:00Z", "2026-01-01T12:00:00Z"], utc=True
            ),
            "surface_snow_thickness": [-1.0, 7.6],
        }
    )

    out = FrostClient._normalize_snow_depth(df)
    delta = out["surface_snow_thickness"].iloc[-1] - out["surface_snow_thickness"].iloc[0]

    assert delta == 7.6


def test_missing_column_is_noop() -> None:
    df = pd.DataFrame({"air_temperature": [-2.0, -1.5]})
    out = FrostClient._normalize_snow_depth(df)
    assert "surface_snow_thickness" not in out.columns
