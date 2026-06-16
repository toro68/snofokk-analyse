"""Tester for plausibilitetsguarden på brøytestempler.

Dekker funn fra krysssjekk brøytedata vs værdata:
- Funn 1: metadataløse stempler i fremtiden / nær nå (share-fallback-artefakter)
- Funn 2: tette pings fra ett brøyteløp som kollapses til én hendelse
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.plowing_service import (
    _collapse_clustered_timestamps,
    _drop_future_timestamps,
    _is_metadata_artifact,
)


def test_drop_future_timestamps_removes_far_future() -> None:
    now = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
    past = now - timedelta(hours=5)
    near_future = now + timedelta(minutes=30)  # innenfor toleranse
    far_future = now + timedelta(days=2)

    kept = _drop_future_timestamps([past, near_future, far_future], now=now)

    assert past in kept
    assert near_future in kept
    assert far_future not in kept


def test_collapse_clustered_keeps_one_per_run() -> None:
    base = datetime(2025, 12, 13, 5, 0, tzinfo=UTC)
    # Ett løp: 8 pings innenfor 20 min
    run = [base + timedelta(minutes=m) for m in (0, 2, 5, 9, 12, 15, 18, 20)]
    # Et separat løp ~3t senere
    later = base + timedelta(hours=3)

    collapsed = _collapse_clustered_timestamps(run + [later])

    assert len(collapsed) == 2
    # Nyeste i hver klynge beholdes
    assert collapsed[0] == later
    assert collapsed[1] == base + timedelta(minutes=20)


def test_metadata_artifact_detected_when_no_metadata_near_now() -> None:
    now = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)
    near = now - timedelta(hours=5)

    assert _is_metadata_artifact(near, has_metadata=False, now=now) is True


def test_metadata_artifact_not_flagged_when_metadata_present() -> None:
    now = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)
    near = now - timedelta(hours=5)

    assert _is_metadata_artifact(near, has_metadata=True, now=now) is False


def test_metadata_artifact_not_flagged_when_old() -> None:
    now = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)
    old = now - timedelta(days=3)

    assert _is_metadata_artifact(old, has_metadata=False, now=now) is False
