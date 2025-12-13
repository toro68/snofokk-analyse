from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_broyting_weather_correlation_contract_exists_and_has_columns() -> None:
    path = REPO_ROOT / "data" / "analyzed" / "broyting_weather_correlation_2025.csv"
    if not path.exists():
        pytest.skip(f"Missing data file: {path}")

    df = pd.read_csv(path)

    required_cols = {
        "dato",
        "datetime",
        "air_temp_avg",
        "air_temp_min",
        "surface_temp_avg",
        "surface_temp_min",
        "temp_diff",
        "wind_avg",
        "wind_max",
        "gust_max",
        "precip_total",
        "precip_duration",
        "snow_depth",
        "snow_change",
        "humidity_avg",
        "dew_point_avg",
        "scenario",
    }

    missing = required_cols - set(df.columns)
    assert not missing, f"Missing required columns: {sorted(missing)}"

    # Keep this tolerant: the exact row count can change with new seasons.
    assert len(df) >= 150, f"Unexpectedly small dataset: {len(df)} rows"

    scenarios = set(df["scenario"].dropna().unique())
    expected = {"NYSNØ", "SNØFOKK", "SLAPS", "FRYSEFARE", "ANNET"}
    assert expected.issubset(scenarios), f"Missing scenarios: {sorted(expected - scenarios)}"


def test_plowing_report_is_semicolon_separated_and_dedupable() -> None:
    path = REPO_ROOT / "data" / "analyzed" / "Rapport 2022-2025.csv"
    if not path.exists():
        pytest.skip(f"Missing data file: {path}")

    plow = pd.read_csv(path, sep=";", encoding="utf-8")
    event_key = ["Dato", "Starttid", "Sluttid", "Rode"]

    assert all(k in plow.columns for k in event_key)

    plow_events = plow.drop_duplicates(subset=event_key)
    assert len(plow_events) >= 150
