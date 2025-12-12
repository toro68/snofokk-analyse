#!/usr/bin/env python3
"""Calibrate simple event-level thresholds against plowing log.

This is a pragmatic calibration step to suggest threshold values that produce
useful *indications* with minimal alert noise.

Inputs
- A weather-vs-plowing event report produced by scripts/analyze_broyting_correlation.py
  (recommended: 12h window):
    data/analyzed/weather_vs_broyting_<stem>_h12.csv

Labeling ("need" proxy)
- A plowing event is considered "need" if it looks like real work:
    duration_minutes > need_duration_min  OR  distance_km > need_distance_km
- A plowing event is considered "no_need" if it looks like a short run:
    duration_minutes <= need_duration_min AND distance_km <= need_distance_km

Grid search
- Searches a small set of thresholds for snowdrift / fresh snow / slaps / freezing.
- Scores with weighted penalties (false positives on no-need are expensive).

Output
- Prints best parameters and writes a CSV with top candidates.

Usage:
  python scripts/reports/calibrate_event_thresholds.py \
    --report data/analyzed/weather_vs_broyting_historical_winter_all_h12.csv
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class Params:
    snow_change_cm: float
    slaps_precip_mm: float
    slaps_temp_min: float
    slaps_temp_max: float
    gust_mps: float
    wind_mps: float
    drift_temp_max: float
    freeze_surface_max: float
    freeze_air_min: float
    freeze_air_max: float
    freeze_precip_mm: float


def derive_labels(df: pd.DataFrame, need_duration_min: float, need_distance_km: float) -> pd.DataFrame:
    out = df.copy()

    out["duration_minutes"] = pd.to_numeric(out.get("duration_minutes"), errors="coerce")
    out["distance_km"] = pd.to_numeric(out.get("distance_km"), errors="coerce")

    dur = out["duration_minutes"]
    dist = out["distance_km"]

    out["need_event"] = (dur > need_duration_min) | (dist > need_distance_km)
    out["no_need_event"] = (dur <= need_duration_min) & (dist <= need_distance_km)

    # Unknown if we are missing either metric
    out.loc[dur.isna() | dist.isna(), ["need_event", "no_need_event"]] = False

    return out


def predict_trigger(df: pd.DataFrame, p: Params) -> pd.Series:
    air = pd.to_numeric(df.get("air_temp_avg"), errors="coerce")
    surface = pd.to_numeric(df.get("surface_temp_avg"), errors="coerce")
    wind = pd.to_numeric(df.get("wind_avg"), errors="coerce")
    gust = pd.to_numeric(df.get("gust_max"), errors="coerce")
    precip = pd.to_numeric(df.get("precip_total"), errors="coerce").fillna(0.0)
    snow_change = pd.to_numeric(df.get("snow_change"), errors="coerce")

    fresh_snow = snow_change.notna() & (snow_change >= p.snow_change_cm)

    slaps = (
        air.notna()
        & (air >= p.slaps_temp_min)
        & (air <= p.slaps_temp_max)
        & (precip >= p.slaps_precip_mm)
    )

    freezing = (
        air.notna()
        & surface.notna()
        & (air >= p.freeze_air_min)
        & (air <= p.freeze_air_max)
        & (surface <= p.freeze_surface_max)
        & (precip >= p.freeze_precip_mm)
    )

    snowdrift = (
        gust.notna()
        & wind.notna()
        & air.notna()
        & (gust >= p.gust_mps)
        & (wind >= p.wind_mps)
        & (air <= p.drift_temp_max)
    )

    return (fresh_snow | slaps | freezing | snowdrift).astype(bool)


def score(df: pd.DataFrame, pred: pd.Series, w_fn: float, w_fp: float, w_fp_no_need: float) -> dict:
    need = df["need_event"].astype(bool)
    no_need = df["no_need_event"].astype(bool)

    tp = int((pred & need).sum())
    fn = int((~pred & need).sum())
    fp = int((pred & ~need).sum())
    fp_no_need = int((pred & no_need).sum())

    # Basic rates
    alert_rate = float(pred.mean() * 100)
    hit_rate = float((pred[need].mean() * 100) if int(need.sum()) else 0.0)

    # Weighted loss (lower is better)
    loss = (w_fn * fn) + (w_fp * fp) + (w_fp_no_need * fp_no_need)

    return {
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "fp_no_need": fp_no_need,
        "need_n": int(need.sum()),
        "no_need_n": int(no_need.sum()),
        "alert_rate_pct": alert_rate,
        "hit_rate_pct": hit_rate,
        "loss": float(loss),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True, help="Event report CSV (from analyze_broyting_correlation.py)")
    parser.add_argument("--need-duration", type=float, default=45.0, help="Minutes: > this implies need")
    parser.add_argument("--need-distance", type=float, default=8.0, help="Km: > this implies need")

    parser.add_argument("--w-fn", type=float, default=3.0, help="Weight for false negatives")
    parser.add_argument("--w-fp", type=float, default=1.0, help="Weight for false positives")
    parser.add_argument("--w-fp-no-need", type=float, default=4.0, help="Extra weight for alerts on short/no-need runs")

    parser.add_argument(
        "--target-alert-rate",
        type=float,
        default=30.0,
        help="Preferred max alert rate (percent) across labeled events",
    )
    parser.add_argument(
        "--w-alert-rate",
        type=float,
        default=6.0,
        help="Penalty weight for exceeding target alert rate",
    )

    parser.add_argument("--top", type=int, default=25, help="How many top parameter sets to write")
    parser.add_argument("--out", type=Path, default=None, help="Output CSV (default: alongside report)")

    args = parser.parse_args()

    df = pd.read_csv(args.report)
    df = derive_labels(df, args.need_duration, args.need_distance)

    # Keep only rows with labels (need or no-need). Others are ignored for scoring.
    mask = df["need_event"] | df["no_need_event"]
    df = df.loc[mask].copy()

    if len(df) == 0:
        raise SystemExit("No labeled rows after applying duration/distance rules")

    candidates: list[dict] = []

    for snow_change_cm in [3.0, 4.0, 5.0, 6.0, 7.0]:
        for slaps_precip_mm in [3.0, 4.0, 5.0, 6.0, 7.0, 8.0]:
            for slaps_temp_max in [2.0, 3.0, 4.0, 5.0]:
                for gust_mps in [13.0, 15.0, 17.0, 19.0, 21.0]:
                    for wind_mps in [6.0, 8.0, 10.0, 12.0]:
                        for freeze_surface_max in [-0.5, -1.0, -1.5, -2.0]:
                            for freeze_air_max in [1.0, 2.0, 3.0]:
                                for freeze_precip_mm in [0.0, 0.5, 1.0, 2.0]:
                                    p = Params(
                                        snow_change_cm=snow_change_cm,
                                        slaps_precip_mm=slaps_precip_mm,
                                        slaps_temp_min=-1.0,
                                        slaps_temp_max=slaps_temp_max,
                                        gust_mps=gust_mps,
                                        wind_mps=wind_mps,
                                        drift_temp_max=-1.0,
                                        freeze_surface_max=freeze_surface_max,
                                        freeze_air_min=0.0,
                                        freeze_air_max=freeze_air_max,
                                        freeze_precip_mm=freeze_precip_mm,
                                    )
                                    pred = predict_trigger(df, p)
                                    s = score(df, pred, args.w_fn, args.w_fp, args.w_fp_no_need)

                                    # Additional penalty if the model alerts too often.
                                    over = max(0.0, s["alert_rate_pct"] - float(args.target_alert_rate))
                                    s["alert_rate_over_pct"] = over
                                    s["loss"] = float(s["loss"] + (args.w_alert_rate * (over ** 2)))

                                    candidates.append({**p.__dict__, **s})

    res = pd.DataFrame(candidates).sort_values(["loss", "alert_rate_pct", "fn", "fp_no_need", "fp"])

    best = res.iloc[0].to_dict()
    print("Best params (event-level):")
    for k in [
        "snow_change_cm",
        "slaps_precip_mm",
        "slaps_temp_max",
        "gust_mps",
        "wind_mps",
        "freeze_surface_max",
        "freeze_air_max",
        "freeze_precip_mm",
        "loss",
        "need_n",
        "no_need_n",
        "tp",
        "fn",
        "fp",
        "fp_no_need",
        "alert_rate_pct",
        "alert_rate_over_pct",
        "hit_rate_pct",
    ]:
        print(f"  {k}: {best.get(k)}")

    out_path = args.out or (args.report.parent / f"calibration_top_{args.report.stem}.csv")
    res.head(int(args.top)).to_csv(out_path, index=False)
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
