#!/usr/bin/env python3
"""Compare weather-vs-plowing reports across multiple lookback windows.

This reads CSV outputs produced by scripts/analyze_broyting_correlation.py
(e.g. weather_vs_broyting_<stem>_h6.csv) and summarizes:
- scenario distribution per window
- share of likely inspections (short duration + short distance)
- how often scenario changes when expanding the window

Usage:
  python scripts/reports/compare_broyting_windows.py \
    --stem historical_winter_all \
    --hours 6 12 18
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.config import settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ANALYZED = PROJECT_ROOT / "data" / "analyzed"


def _read_report(stem: str, hours: int) -> pd.DataFrame:
    p = DATA_ANALYZED / f"weather_vs_broyting_{stem}_h{hours}.csv"
    if not p.exists():
        raise FileNotFoundError(f"Missing report: {p}")
    return pd.read_csv(p)


def _median(df: pd.DataFrame, col: str, mask: pd.Series) -> float | None:
    if col not in df.columns:
        return None
    s = df.loc[mask, col].dropna()
    if len(s) == 0:
        return None
    return float(s.median())


def summarize_report(df: pd.DataFrame, hours: int) -> dict:
    ins = df.get("likely_inspection", pd.Series([False] * len(df))).fillna(False).astype(bool)
    short45 = df.get("short_run_45m", pd.Series([False] * len(df))).fillna(False).astype(bool)
    short45_no_trigger = df.get("short_45m_no_trigger", pd.Series([False] * len(df))).fillna(False).astype(bool)
    short45 = df.get("short_run_45m", pd.Series([False] * len(df))).fillna(False).astype(bool)
    short45_no_trigger = df.get("short_45m_no_trigger", pd.Series([False] * len(df))).fillna(False).astype(bool)
    out = {
        "window_hours": int(hours),
        "rows": int(len(df)),
        "inspection_n": int(ins.sum()),
        "inspection_pct": float(ins.mean() * 100) if len(df) else 0.0,
        "short45_n": int(short45.sum()),
        "short45_pct": float(short45.mean() * 100) if len(df) else 0.0,
        "short45_no_trigger_n": int(short45_no_trigger.sum()),
        "short45_no_trigger_pct": float(short45_no_trigger.mean() * 100) if len(df) else 0.0,
        "scenario_ANNET": int((df["scenario"] == "ANNET").sum()) if "scenario" in df.columns else 0,
        "scenario_SNØFOKK": int((df["scenario"] == "SNØFOKK").sum()) if "scenario" in df.columns else 0,
        "scenario_FRYSEFARE": int((df["scenario"] == "FRYSEFARE").sum()) if "scenario" in df.columns else 0,
        "scenario_NYSNØ": int((df["scenario"] == "NYSNØ").sum()) if "scenario" in df.columns else 0,
        "scenario_SLAPS": int((df["scenario"] == "SLAPS").sum()) if "scenario" in df.columns else 0,
        "inspect_duration_min_med": _median(df, "duration_minutes", ins),
        "inspect_distance_km_med": _median(df, "distance_km", ins),
        "inspect_gust_max_med": _median(df, "gust_max", ins),
        "inspect_precip_total_med": _median(df, "precip_total", ins),
        "noninspect_duration_min_med": _median(df, "duration_minutes", ~ins),
        "noninspect_distance_km_med": _median(df, "distance_km", ~ins),
        "noninspect_gust_max_med": _median(df, "gust_max", ~ins),
        "noninspect_precip_total_med": _median(df, "precip_total", ~ins),
    }
    return out


def scenario_change_rate(df_a: pd.DataFrame, df_b: pd.DataFrame) -> dict:
    idx_cols = ["start_utc", "rode", "enhet"]
    a = df_a.set_index(idx_cols)
    b = df_b.set_index(idx_cols)
    common = a.index.intersection(b.index)
    if len(common) == 0:
        return {"changed_n": 0, "changed_pct": 0.0}
    changed = (a.loc[common, "scenario"].astype(str) != b.loc[common, "scenario"].astype(str))
    n = int(changed.sum())
    return {"changed_n": n, "changed_pct": float(n / len(common) * 100)}


def start_hour_distribution(plowing_csv: Path) -> dict:
    df = pd.read_csv(plowing_csv, sep=";")
    df = df[df["Dato"] != "Totalt"].copy()

    import zoneinfo
    from datetime import UTC, datetime

    month_map = {
        "jan.": 1,
        "feb.": 2,
        "mars": 3,
        "apr.": 4,
        "mai": 5,
        "jun.": 6,
        "jul.": 7,
        "aug.": 8,
        "sep.": 9,
        "okt.": 10,
        "nov.": 11,
        "des.": 12,
    }
    oslo = zoneinfo.ZoneInfo("Europe/Oslo")

    def parse_dt(date_str: str, time_str: str):
        parts = str(date_str).split()
        day = int(parts[0].rstrip("."))
        month = month_map.get(parts[1], 1)
        year = int(parts[2])
        hh, mm, *rest = str(time_str).split(":")
        ss = int(rest[0]) if rest else 0
        local = datetime(year, month, day, int(hh), int(mm), ss, tzinfo=oslo)
        return local.astimezone(UTC)

    df["start_utc"] = df.apply(lambda r: parse_dt(r["Dato"], r["Starttid"]), axis=1)
    df = df.drop_duplicates(subset=["start_utc", "Rode", "Enhet"]).copy()
    df["start_hour_local"] = df["start_utc"].dt.tz_convert(oslo).dt.hour

    counts = df["start_hour_local"].value_counts().sort_index()
    morning_start = int(settings.scripts.compare_morning_start_hour)
    morning_end = int(settings.scripts.compare_morning_end_hour)
    morning = int(counts.loc[morning_start:morning_end].sum()) if len(counts) else 0
    total = int(counts.sum()) if len(counts) else 0

    return {
        "events": total,
        "morning_06_11_n": morning,
        "morning_06_11_pct": float(morning / total * 100) if total else 0.0,
        "morning_start": morning_start,
        "morning_end": morning_end,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stem", required=True, help="Weather report stem (e.g. historical_winter_all)")
    parser.add_argument("--hours", nargs="+", type=int, required=True, help="Hours windows to compare")
    parser.add_argument(
        "--plowing",
        type=Path,
        default=DATA_ANALYZED / "Rapport 2022-2025.csv",
        help="Plowing log CSV (semicolon-delimited)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output CSV path (default: data/analyzed/window_comparison_<stem>.csv)",
    )

    args = parser.parse_args()

    hours_list = list(dict.fromkeys(args.hours))
    frames = {h: _read_report(args.stem, h) for h in hours_list}

    rows = [summarize_report(frames[h], h) for h in hours_list]
    summary_df = pd.DataFrame(rows).sort_values("window_hours")

    # Scenario change rates vs the smallest window
    base_h = min(hours_list)
    base = frames[base_h]
    for h in hours_list:
        if h == base_h:
            summary_df.loc[summary_df.window_hours == h, "scenario_changed_vs_base_pct"] = 0.0
            continue
        ch = scenario_change_rate(base, frames[h])
        summary_df.loc[summary_df.window_hours == h, "scenario_changed_vs_base_pct"] = ch["changed_pct"]

    out_path = args.out or (DATA_ANALYZED / f"window_comparison_{args.stem}.csv")
    summary_df.to_csv(out_path, index=False)

    hours_str = ",".join(str(h) for h in hours_list)
    print(f"Wrote: {out_path} (hours={hours_str})")

    # Also print a tiny plowing start-time summary
    hstats = start_hour_distribution(args.plowing)
    print(
        f"Plowing start times: events={hstats['events']}, morning({hstats['morning_start']:02d}-{hstats['morning_end']:02d})={hstats['morning_06_11_n']} ({hstats['morning_06_11_pct']:.1f}%)"
    )


if __name__ == "__main__":
    main()
