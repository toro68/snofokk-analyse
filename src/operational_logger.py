"""Operational event logging.

Logs only MEDIUM/HIGH analyzer results to a CSV file, with deduplication, so the
app can be run continuously without spamming duplicate rows on every Streamlit
rerun.

The log is intended for real-world validation: what did we alert on, and what
maintenance (brøyting/strøing) actually happened.
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from src.analyzers import RiskLevel
from src.config import get_secret
from src.plowing_service import PlowingInfo

logger = logging.getLogger(__name__)


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _project_root() -> Path:
    return Path(__file__).parent.parent


def _default_log_path() -> Path:
    rel = get_secret("OPERATIONAL_LOG_PATH", "data/logs/operational_alerts.csv")
    return (_project_root() / rel).resolve()


def _default_state_path() -> Path:
    rel = get_secret("OPERATIONAL_LOG_STATE_PATH", "data/logs/operational_alerts_state.json")
    return (_project_root() / rel).resolve()


def _latest_reference_time_utc(df: pd.DataFrame) -> datetime | None:
    if df is None or df.empty:
        return None

    latest = df.iloc[-1]
    ts = latest.get("reference_time")
    if ts is None:
        return None

    # Pandas Timestamp or datetime
    if isinstance(ts, pd.Timestamp):
        if ts.tzinfo is None:
            ts = ts.tz_localize(UTC)
        return ts.to_pydatetime().astimezone(UTC)

    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return ts.astimezone(UTC)

    return None


def _load_state(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            # key -> logged_at_iso
            return {str(k): str(v) for k, v in data.items()}
    except (OSError, ValueError, TypeError) as e:
        logger.warning("Operational logger: failed to load state: %s", e)
    return {}


def _save_state(path: Path, state: dict[str, str]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        tmp.replace(path)
    except (OSError, TypeError, ValueError) as e:
        logger.warning("Operational logger: failed to save state: %s", e)


def _prune_state(state: dict[str, str], keep_for: timedelta) -> dict[str, str]:
    cutoff = datetime.now(UTC) - keep_for
    pruned: dict[str, str] = {}
    for key, logged_at_str in state.items():
        try:
            logged_at = datetime.fromisoformat(logged_at_str.replace("Z", "+00:00"))
            if logged_at.tzinfo is None:
                logged_at = logged_at.replace(tzinfo=UTC)
        except (ValueError, TypeError):
            # Keep unknown entries to avoid accidental spam
            pruned[key] = logged_at_str
            continue

        if logged_at >= cutoff:
            pruned[key] = logged_at_str

    return pruned


def log_medium_high_alerts(
    *,
    results: dict[str, Any],
    df: pd.DataFrame,
    plowing_info: PlowingInfo | None,
    suppressed_by_maintenance: bool = False,
    suppression_reason: str = "",
    quality_guard_note: str = "",
) -> None:
    """Append MEDIUM/HIGH analyzer results to a CSV (deduped).

    Always logs raw analyzer output (before quality-guard and suppression
    transformations) so that real risk events are captured even when
    data_quality_guard has downgraded them to UNKNOWN for display purposes.

    Controlled via:
    - OPERATIONAL_LOG_ENABLED (default: true)
    - OPERATIONAL_LOG_PATH (default: data/logs/operational_alerts.csv)
    - OPERATIONAL_LOG_STATE_PATH (default: data/logs/operational_alerts_state.json)
    """

    enabled = _parse_bool(get_secret("OPERATIONAL_LOG_ENABLED", "true"), default=True)
    if not enabled:
        return

    log_path = _default_log_path()
    state_path = _default_state_path()

    reference_time_utc = _latest_reference_time_utc(df)
    reference_time_iso = reference_time_utc.isoformat().replace("+00:00", "Z") if reference_time_utc else ""

    now_utc = datetime.now(UTC)
    logged_at_iso = now_utc.isoformat().replace("+00:00", "Z")

    latest: pd.Series | None = df.iloc[-1] if df is not None and not df.empty else None

    def _as_float(value: Any) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    air_temp = _as_float(latest.get("air_temperature")) if latest is not None else None
    surface_temp = _as_float(latest.get("surface_temperature")) if latest is not None else None
    wind = _as_float(latest.get("wind_speed")) if latest is not None else None
    gust = _as_float(latest.get("max_wind_gust")) if latest is not None else None
    precip_1h = _as_float(latest.get("precipitation_1h")) if latest is not None else None
    snow_depth = _as_float(latest.get("surface_snow_thickness")) if latest is not None else None

    maintenance_last_utc = ""
    maintenance_hours_since = None
    maintenance_source = ""
    maintenance_event_type = ""
    maintenance_work_types = ""
    maintenance_operator_id = ""
    maintenance_error = ""

    if plowing_info is not None:
        maintenance_source = plowing_info.source or ""
        maintenance_error = plowing_info.error or ""
        if plowing_info.last_plowing:
            maintenance_last_utc = plowing_info.last_plowing.astimezone(UTC).isoformat().replace("+00:00", "Z")
        if plowing_info.hours_since is not None:
            maintenance_hours_since = float(plowing_info.hours_since)
        maintenance_event_type = plowing_info.last_event_type or ""
        if plowing_info.last_work_types:
            maintenance_work_types = ",".join([str(x) for x in plowing_info.last_work_types])
        maintenance_operator_id = plowing_info.last_operator_id or ""

    state = _load_state(state_path)
    state = _prune_state(state, keep_for=timedelta(days=14))

    rows_to_append: list[dict[str, object]] = []

    for analyzer_name, result in results.items():
        risk_level = getattr(result, "risk_level", None)
        if risk_level not in (RiskLevel.MEDIUM, RiskLevel.HIGH):
            continue

        risk_name = getattr(risk_level, "name", str(risk_level))
        message = getattr(result, "message", "") or ""

        dedupe_key = f"{reference_time_iso}|{analyzer_name}|{risk_name}"
        if dedupe_key in state:
            continue

        rows_to_append.append(
            {
                "logged_at_utc": logged_at_iso,
                "reference_time_utc": reference_time_iso,
                "analyzer": analyzer_name,
                "risk_level": risk_name,
                "message": message,
                "air_temperature": air_temp,
                "surface_temperature": surface_temp,
                "wind_speed": wind,
                "wind_gust": gust,
                "precipitation_1h": precip_1h,
                "surface_snow_thickness": snow_depth,
                "maintenance_last_utc": maintenance_last_utc,
                "maintenance_hours_since": maintenance_hours_since,
                "maintenance_source": maintenance_source,
                "maintenance_event_type": maintenance_event_type,
                "maintenance_work_types": maintenance_work_types,
                "maintenance_operator_id": maintenance_operator_id,
                "maintenance_error": maintenance_error,
                "suppressed_by_maintenance": bool(suppressed_by_maintenance),
                "suppression_reason": suppression_reason,
                "quality_guard_note": quality_guard_note,
            }
        )
        state[dedupe_key] = logged_at_iso

    if not rows_to_append:
        _save_state(state_path, state)
        return

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_exists = log_path.exists()

        with open(log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows_to_append[0].keys()))
            if not file_exists:
                writer.writeheader()
            writer.writerows(rows_to_append)

        _save_state(state_path, state)

        logger.info(
            "Operational logger: wrote %s rows to %s",
            len(rows_to_append),
            log_path,
        )
    except (OSError, csv.Error, TypeError, ValueError) as e:
        logger.warning("Operational logger: failed to write csv: %s", e)
