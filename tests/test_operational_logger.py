from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from src.operational_logger import OPERATIONAL_LOG_FIELDS, log_medium_high_alerts
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
    content = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(content) == 1
    assert content[0].split(",") == OPERATIONAL_LOG_FIELDS