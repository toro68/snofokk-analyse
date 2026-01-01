#!/usr/bin/env python3
"""
Evaluate `src/config.py` thresholds against the precomputed per-plowing-event dataset.

This script is intentionally dependency-light (stdlib only) so it can run in
restricted environments without pandas/numpy.

Data source (default):
  data/analyzed/broyting_weather_correlation_2025.csv

Important limitations:
- The `scenario` column in the CSV is a heuristic label (not ground truth).
- Weather features are aggregated over a window around plowing; some thresholds
  in `settings.*` operate on per-hour snapshots, so results are indicative only.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import settings


def _as_float(row: dict[str, str], key: str) -> float | None:
    try:
        v = row.get(key)
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _clean_snow_depth_cm(value: float | None) -> float | None:
    # Frost sentinel
    if value is None or value <= -0.5:
        return None
    return value


def _wind_chill_c(temp_c: float, wind_ms: float) -> float:
    """Canadian wind chill. Returns `temp_c` outside formula validity window."""
    vis = settings.viz
    if temp_c > vis.wind_chill_valid_temp_max_c or wind_ms < vis.wind_chill_valid_wind_min_ms:
        return temp_c
    v_kmh = wind_ms * 3.6
    return 13.12 + 0.6215 * temp_c - 11.37 * (v_kmh**0.16) + 0.3965 * temp_c * (v_kmh**0.16)


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    idx = int(round((len(s) - 1) * q))
    idx = max(0, min(len(s) - 1, idx))
    return float(s[idx])


def _pct(n: int, d: int) -> float:
    return (n / d * 100.0) if d else 0.0


@dataclass
class Confusion:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    def f1(self) -> float:
        p = self.precision()
        r = self.recall()
        return (2 * p * r / (p + r)) if (p + r) else 0.0


def _update(conf: Confusion, *, truth: bool, pred: bool) -> None:
    if truth and pred:
        conf.tp += 1
    elif (not truth) and pred:
        conf.fp += 1
    elif truth and (not pred):
        conf.fn += 1
    else:
        conf.tn += 1


def _pred_snowdrift(row: dict[str, str], *, wind_chill_warning_c: float | None = None) -> str:
    """A conservative per-event approximation of SnowdriftAnalyzer (MEDIUM/HIGH/LOW)."""
    th = settings.snowdrift
    wc_warn = th.wind_chill_warning if wind_chill_warning_c is None else float(wind_chill_warning_c)

    snow = _clean_snow_depth_cm(_as_float(row, "snow_depth"))
    if snow is None or snow < th.snow_depth_min_cm:
        return "LOW"

    tmin = _as_float(row, "air_temp_min")
    if tmin is None or tmin > th.temperature_max:
        return "LOW"

    wind = _as_float(row, "wind_avg") or 0.0
    gust = _as_float(row, "gust_max") or 0.0
    wc = _wind_chill_c(tmin, wind)

    if gust >= th.wind_gust_critical and wind >= th.wind_speed_warning and wc <= th.wind_chill_critical:
        return "HIGH"

    if gust >= th.wind_gust_warning and wind >= th.wind_speed_gust_warning_gate and wc <= wc_warn:
        return "MEDIUM"

    return "LOW"


def _pred_slaps(row: dict[str, str]) -> str:
    """Per-event approximation of SlapsAnalyzer (MEDIUM/HIGH/LOW)."""
    th = settings.slaps

    temp = _as_float(row, "air_temp_avg")
    if temp is None:
        return "LOW"

    snow = _clean_snow_depth_cm(_as_float(row, "snow_depth")) or 0.0
    if snow < th.snow_depth_min:
        return "LOW"

    precip_total = _as_float(row, "precip_total") or 0.0
    in_range = th.temp_min <= temp <= th.temp_max

    if not in_range:
        return "LOW"

    if precip_total >= th.precipitation_12h_heavy:
        return "HIGH"
    if precip_total >= th.precipitation_12h_min:
        return "MEDIUM"

    # Snow melt signal (often noisy in aggregated data) is intentionally not used here.
    return "LOW"


def _pred_fresh_snow(row: dict[str, str]) -> str:
    """Per-event approximation of FreshSnowAnalyzer (MEDIUM/HIGH/LOW).

    NOTE: The CSV's `snow_change` window may differ from `settings.fresh_snow.lookback_hours`.
    """
    th = settings.fresh_snow
    snow_change = _as_float(row, "snow_change") or 0.0

    if snow_change >= th.snow_increase_critical:
        return "HIGH"
    if snow_change >= th.snow_increase_warning:
        return "MEDIUM"
    return "LOW"


def _pred_hidden_freeze(row: dict[str, str], *, surface_max_c: float | None = None, air_max_c: float | None = None) -> str:
    """Approximate the hidden-freeze sub-scenario (MEDIUM/HIGH/LOW)."""
    th = settings.slippery
    surface_max = th.hidden_freeze_surface_max if surface_max_c is None else float(surface_max_c)
    air_max = th.hidden_freeze_air_max if air_max_c is None else float(air_max_c)

    temp = _as_float(row, "air_temp_avg")
    surface_min = _as_float(row, "surface_temp_min")
    if temp is None or surface_min is None:
        return "LOW"

    hidden_freeze = (th.hidden_freeze_air_min <= temp <= air_max) and (surface_min <= surface_max)
    if not hidden_freeze:
        return "LOW"

    precip_total = _as_float(row, "precip_total") or 0.0
    humidity = _as_float(row, "humidity_avg")
    snow_change = _as_float(row, "snow_change")
    melt_indicator = snow_change is not None and snow_change <= th.melt_snow_change_6h_cm
    moisture_likely = (
        precip_total >= th.hidden_freeze_precip_12h_min
        or melt_indicator
        or (humidity is not None and humidity >= th.rimfrost_humidity_min)
    )

    return "HIGH" if moisture_likely else "MEDIUM"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("data/analyzed/broyting_weather_correlation_2025.csv"),
        help="CSV file with per-plowing weather context + scenario.",
    )
    args = parser.parse_args()

    path: Path = args.csv
    if not path.exists():
        raise SystemExit(f"Missing: {path}")

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row.get("datetime", "").strip(), row.get("scenario", "").strip())
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)

    scenarios = sorted({(r.get("scenario") or "").strip() for r in rows})
    counts = {s: 0 for s in scenarios}
    for r in rows:
        counts[(r.get("scenario") or "").strip()] += 1

    print(f"Source: {path}")
    print(f"Rows (deduped on datetime+scenario): {len(rows)}")
    print(f"Scenario counts: {counts}")

    # Feature distribution summaries
    key_fields = [
        "gust_max",
        "wind_avg",
        "air_temp_min",
        "snow_depth",
        "snow_change",
        "precip_total",
        "precip_duration",
        "surface_temp_min",
        "temp_diff",
    ]

    def _scenario_values(sc: str) -> dict[str, list[float]]:
        vals = {k: [] for k in key_fields}
        wind_chills: list[float] = []
        precip_rates: list[float] = []
        for r in rows:
            if (r.get("scenario") or "").strip() != sc:
                continue

            for k in key_fields:
                v = _as_float(r, k)
                if k == "snow_depth":
                    v = _clean_snow_depth_cm(v)
                if v is not None:
                    vals[k].append(v)

            tmin = _as_float(r, "air_temp_min")
            wavg = _as_float(r, "wind_avg")
            if tmin is not None and wavg is not None:
                wind_chills.append(_wind_chill_c(tmin, wavg))

            pt = _as_float(r, "precip_total")
            pdur = _as_float(r, "precip_duration")
            if pt is not None and pdur is not None and pdur > 0:
                precip_rates.append(pt / (pdur / 60.0))

        vals["wind_chill"] = wind_chills
        vals["precip_rate"] = precip_rates
        return vals

    print("\nKey distributions (median / p90):")
    for sc in scenarios:
        vals = _scenario_values(sc)

        def fmt(x: float | None) -> str:
            return "NA" if x is None else f"{x:.2f}"

        print(f"\n- {sc} (n={counts[sc]})")
        for label, col in [
            ("gust_max", "gust_max"),
            ("wind_avg", "wind_avg"),
            ("air_temp_min", "air_temp_min"),
            ("wind_chill(min+avgwind)", "wind_chill"),
            ("snow_depth", "snow_depth"),
            ("snow_change", "snow_change"),
            ("precip_total", "precip_total"),
            ("precip_rate(mm/h, total/dur)", "precip_rate"),
        ]:
            med = _quantile(vals[col], 0.5)
            p90 = _quantile(vals[col], 0.9)
            print(f"  {label:26s} med={fmt(med):>7s} p90={fmt(p90):>7s}")

    # Confusion-style evaluation against the heuristic scenario labels
    def eval_binary(*, positive_scenario: str, predictor) -> Confusion:
        conf = Confusion()
        for r in rows:
            truth = (r.get("scenario") or "").strip() == positive_scenario
            level = predictor(r)
            pred = level in {"MEDIUM", "HIGH"}
            _update(conf, truth=truth, pred=pred)
        return conf

    print("\nEvaluation (positive scenario vs others; pred=MEDIUM/HIGH):")

    c_sd = eval_binary(positive_scenario="SNØFOKK", predictor=lambda r: _pred_snowdrift(r))
    print(f"- snowdrift: TP={c_sd.tp} FP={c_sd.fp} FN={c_sd.fn} TN={c_sd.tn} | P={c_sd.precision():.2f} R={c_sd.recall():.2f} F1={c_sd.f1():.2f}")

    c_fs = eval_binary(positive_scenario="NYSNØ", predictor=lambda r: _pred_fresh_snow(r))
    print(f"- fresh_snow (rough): TP={c_fs.tp} FP={c_fs.fp} FN={c_fs.fn} TN={c_fs.tn} | P={c_fs.precision():.2f} R={c_fs.recall():.2f} F1={c_fs.f1():.2f}")

    c_sl = eval_binary(positive_scenario="SLAPS", predictor=lambda r: _pred_slaps(r))
    print(f"- slaps: TP={c_sl.tp} FP={c_sl.fp} FN={c_sl.fn} TN={c_sl.tn} | P={c_sl.precision():.2f} R={c_sl.recall():.2f} F1={c_sl.f1():.2f}")

    c_hf = eval_binary(positive_scenario="FRYSEFARE", predictor=lambda r: _pred_hidden_freeze(r))
    print(f"- slippery.hidden_freeze: TP={c_hf.tp} FP={c_hf.fp} FN={c_hf.fn} TN={c_hf.tn} | P={c_hf.precision():.2f} R={c_hf.recall():.2f} F1={c_hf.f1():.2f}")

    # Simple search: snowdrift wind_chill_warning sensitivity (keep other gates)
    print("\nSensitivity: `settings.snowdrift.wind_chill_warning` (others fixed)")
    sd_th = settings.snowdrift
    for wc_warn in [-12.0, -11.0, -10.5, -10.0, -9.5]:
        conf = eval_binary(
            positive_scenario="SNØFOKK",
            predictor=lambda r, _wc=wc_warn: _pred_snowdrift(r, wind_chill_warning_c=_wc),
        )
        print(f"  wc_warn={wc_warn:5.1f}: TP={conf.tp:2d} FP={conf.fp:2d} FN={conf.fn:2d} | P={conf.precision():.2f} R={conf.recall():.2f}")

    # Simple search: hidden_freeze surface threshold
    print("\nSensitivity: `settings.slippery.hidden_freeze_surface_max` (air_min fixed, air_max fixed)")
    sp_th = settings.slippery
    for surface_max in [-2.0, -1.5, -1.0, -0.5]:
        conf = eval_binary(
            positive_scenario="FRYSEFARE",
            predictor=lambda r, _s=surface_max: _pred_hidden_freeze(r, surface_max_c=_s),
        )
        print(f"  surface_max={surface_max:5.1f}: TP={conf.tp:2d} FP={conf.fp:2d} FN={conf.fn:2d} | P={conf.precision():.2f} R={conf.recall():.2f}")

    print("\nNotes:")
    print("- `fresh_snow` evaluation is not window-aligned unless the CSV was computed over `settings.fresh_snow.lookback_hours`.")
    print("- `slippery.hidden_freeze` is only one sub-scenario of the full SlipperyRoadAnalyzer logic.")
    print("- For authoritative evaluation, re-generate the CSV with the exact time windows used by the analyzers, then re-run.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
