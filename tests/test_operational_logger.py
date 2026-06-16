from __future__ import annotations

import csv
from datetime import UTC, datetime

import pandas as pd

from src.operational_logger import (
    OPERATIONAL_LOG_FIELDS,
    _ensure_log_file,
    log_medium_high_alerts,
)
from src.plowing_service import PlowingInfo


def test_operational_logger_bootstraps_csv_without_alert_rows(monkeypatch, tmp_path) -> None:
    log_path = tmp_path / "operational_alerts.csv"
    state_path = tmp_path / "operational_alerts_state.json"

    monkeypatch.setenv("OPERATIONAL_LOG_ENABLED", "true")
    monkeypatch.setenv("OPERATIONAL_LOG_PATH", str(log_path.relative_to(tmp_path)))
    monkeypatch.setenv("OPERATIONAL_LOG_STATE_PATH", str(state_path.relative_to(tmp_path)))

    import src.operational_logger as operational_logger

    monkeypatch.setattr(operational_logger, "_project_root", lambda: tmp_path)

    df = pd.DataFrame(
        {
            "reference_time": [datetime(2026, 3, 6, 10, 0, tzinfo=UTC)],
            "air_temperature": [-2.0],
        }
    )

    class DummyResult:
        risk_level = None

    log_medium_high_alerts(
        results={"Snøfokk": DummyResult()},
        df=df,
        plowing_info=PlowingInfo(
            last_plowing=None,
            hours_since=None,
            is_recent=False,
            all_timestamps=[],
            source="none",
        ),
    )

    assert log_path.exists()
    with open(log_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert len(rows) == 1
    assert rows[0] == OPERATIONAL_LOG_FIELDS


def test_ensure_log_file_migrates_outdated_header(tmp_path) -> None:
    """En CSV skrevet med en eldre, smalere header skal migreres til full header
    slik at etterfølgende append ikke gir kolonne-mismatch i pandas.read_csv."""
    log_path = tmp_path / "operational_alerts.csv"

    old_fields = OPERATIONAL_LOG_FIELDS[:-1]  # mangler nyeste kolonne (quality_guard_note)
    with open(log_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=old_fields)
        writer.writeheader()
        writer.writerow(dict.fromkeys(old_fields, "x"))

    _ensure_log_file(log_path)

    with open(log_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == OPERATIONAL_LOG_FIELDS
    # Eksisterende rad bevares, manglende felt fylles tomt.
    assert len(rows) == 2
    assert rows[1][-1] == ""

    # Filen kan nå leses uten ParserError.
    df = pd.read_csv(log_path)
    assert list(df.columns) == OPERATIONAL_LOG_FIELDS
