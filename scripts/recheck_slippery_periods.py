#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

# Make repo-root importable so `import src...` works regardless of cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analyzers.slippery_road import SlipperyRoadAnalyzer


def _load_weather_csv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    # Normalize timestamp
    if 'timestamp' in df.columns:
        df['reference_time'] = pd.to_datetime(df['timestamp'], utc=True)
        df = df.drop(columns=['timestamp'])
    elif 'reference_time' in df.columns:
        df['reference_time'] = pd.to_datetime(df['reference_time'], utc=True)
    else:
        raise ValueError(f"Missing timestamp/reference_time in {csv_path}")

    # Normalize precip column name
    if 'precipitation' in df.columns and 'precipitation_1h' not in df.columns:
        df = df.rename(columns={'precipitation': 'precipitation_1h'})

    # Ensure numeric
    numeric_cols = [
        'air_temperature',
        'surface_temperature',
        'surface_snow_thickness',
        'wind_speed',
        'wind_from_direction',
        'relative_humidity',
        'dew_point_temperature',
        'precipitation_1h',
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Remove obviously invalid snow depth
    if 'surface_snow_thickness' in df.columns:
        df.loc[df['surface_snow_thickness'] < 0, 'surface_snow_thickness'] = pd.NA

    df = df.sort_values('reference_time').reset_index(drop=True)
    return df


def _format_val(val) -> str:
    if val is None or pd.isna(val):
        return 'None'
    try:
        return f"{float(val):.2f}"
    except Exception:
        return str(val)


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-check SlipperyRoadAnalyzer against detected rain-on-snow periods")
    parser.add_argument('--top', type=int, default=10, help='How many top periods to print')
    parser.add_argument('--context-hours', type=int, default=48, help='How many hours of context to include before evaluation time')
    parser.add_argument(
        '--eval',
        choices=['end', 'peak'],
        default='peak',
        help='Evaluate only at period end, or compute peak (max) risk within the period',
    )
    parser.add_argument(
        '--only-rain',
        action='store_true',
        help='Filter out periods that do not show rain (precip >= rain_threshold) and/or peak as Snøfall',
    )
    parser.add_argument(
        '--require-dewpoint',
        action='store_true',
        help='When dew point is available, require dew_point_temperature > 0 at least once in the period (proxy for rain)',
    )
    args = parser.parse_args()

    csv_path = Path('data/raw/winter_seasons/winter_2023-2024.csv')
    periods_path = Path('data/analyzed/rain_on_snow_slippery_periods.json')

    if not csv_path.exists():
        raise SystemExit(f"Missing {csv_path}")
    if not periods_path.exists():
        raise SystemExit(f"Missing {periods_path}")

    df = _load_weather_csv(csv_path)
    periods = json.loads(periods_path.read_text())

    analyzer = SlipperyRoadAnalyzer()
    rain_threshold = float(getattr(getattr(__import__('src.config', fromlist=['settings']).settings, 'slippery'), 'rain_threshold_mm'))

    print(f"Loaded rows: {len(df)}")
    print(f"Loaded periods: {len(periods)}")

    risk_order = {'UNKNOWN': 0, 'LOW': 1, 'MEDIUM': 2, 'HIGH': 3}

    def _is_higher(a: str, b: str) -> bool:
        return risk_order.get(a, 0) > risk_order.get(b, 0)

    results = []

    stats = {
        "periods_total": 0,
        "periods_evaluated": 0,
        "skipped_no_overlap_rows": 0,
        "skipped_no_peak_result": 0,
        "filtered_no_rain": 0,
        "filtered_peak_snofall": 0,
        "filtered_dewpoint_not_above_zero": 0,
    }
    for p in periods:
        stats["periods_total"] += 1
        start = pd.to_datetime(p['start_time'])
        end = pd.to_datetime(p['end_time'])

        # Times to evaluate: either just period end, or every available hour inside the period.
        if args.eval == 'end':
            eval_times = [end]
        else:
            eval_times = df.loc[(df['reference_time'] >= start) & (df['reference_time'] <= end), 'reference_time']
            eval_times = list(pd.to_datetime(eval_times).tolist())
            if not eval_times:
                eval_times = [end]

        peak = None
        peak_time = None
        peak_last_row = None
        saw_rain = False
        saw_dewpoint = False
        saw_dewpoint_above_zero = False

        for t_eval in eval_times:
            sample = df[df['reference_time'] <= t_eval].copy()
            sample = sample[sample['reference_time'] >= (pd.to_datetime(t_eval) - pd.Timedelta(hours=args.context_hours))]
            if sample.empty:
                continue

            stats["periods_evaluated"] += 1

            # Track whether we ever saw rain in the evaluated window inside the period
            if args.only_rain:
                last_p = sample.iloc[-1].get('precipitation_1h')
                if last_p is not None and not pd.isna(last_p) and float(last_p) >= rain_threshold:
                    saw_rain = True

            if args.require_dewpoint:
                last_dp = sample.iloc[-1].get('dew_point_temperature')
                if last_dp is not None and not pd.isna(last_dp):
                    saw_dewpoint = True
                    if float(last_dp) > 0.0:
                        saw_dewpoint_above_zero = True

            res = analyzer.analyze(sample)
            if peak is None or _is_higher(res.risk_level.name, peak.risk_level.name):
                peak = res
                peak_time = pd.to_datetime(t_eval)
                peak_last_row = sample.iloc[-1]

            # Fast exit: cannot beat HIGH
            if res.risk_level.name == 'HIGH':
                break

        if peak is None or peak_last_row is None:
            # No data rows could be used to evaluate this period
            stats["skipped_no_peak_result"] += 1
            # Distinguish between "no overlap" and other issues (best-effort)
            if df.loc[(df['reference_time'] >= start) & (df['reference_time'] <= end)].empty:
                stats["skipped_no_overlap_rows"] += 1
            continue

        if args.only_rain:
            # Filter out "Snøfall" peak results (nysnø/naturlig strøing) and windows with no clear rain.
            if not saw_rain:
                stats["filtered_no_rain"] += 1
                continue
            if str(getattr(peak, 'scenario', '')).strip().lower() == 'snøfall':
                stats["filtered_peak_snofall"] += 1
                continue

        if args.require_dewpoint:
            # Only enforce when dew point exists at least once (avoid excluding periods with missing dew point).
            if saw_dewpoint and not saw_dewpoint_above_zero:
                stats["filtered_dewpoint_not_above_zero"] += 1
                continue

        results.append({
            "start": start,
            "end": end,
            "peak_time": peak_time,
            "scenario_type": p.get('scenario_type'),
            "duration_hours": p.get('duration_hours'),
            "danger_score": p.get('danger_score'),
            "total_precipitation": p.get('total_precipitation'),
            "avg_temperature": p.get('avg_temperature'),
            "peak_air": None if pd.isna(peak_last_row.get('air_temperature')) else float(peak_last_row.get('air_temperature')),
            "peak_surface": None if pd.isna(peak_last_row.get('surface_temperature')) else float(peak_last_row.get('surface_temperature')),
            "peak_snow": None if pd.isna(peak_last_row.get('surface_snow_thickness')) else float(peak_last_row.get('surface_snow_thickness')),
            "peak_precip_1h": None if pd.isna(peak_last_row.get('precipitation_1h')) else float(peak_last_row.get('precipitation_1h')),
            "risk_level": peak.risk_level.name,
            "scenario": peak.scenario,
            "message": peak.message,
            "factors": peak.factors or [],
        })

    if not results:
        raise SystemExit('No periods could be evaluated (no overlapping weather rows).')

    print("\nFilter/evaluation summary:")
    print(f"  periods_total: {stats['periods_total']}")
    print(f"  periods_evaluated (sample windows evaluated): {stats['periods_evaluated']}")
    print(f"  skipped_no_peak_result: {stats['skipped_no_peak_result']}")
    print(f"  skipped_no_overlap_rows: {stats['skipped_no_overlap_rows']}")
    if args.only_rain:
        print(f"  filtered_no_rain (precip never >= {rain_threshold} mm/h): {stats['filtered_no_rain']}")
        print(f"  filtered_peak_snofall: {stats['filtered_peak_snofall']}")
    if args.require_dewpoint:
        print(f"  filtered_dewpoint_not_above_zero: {stats['filtered_dewpoint_not_above_zero']}")

    # Summary counts
    counts = {}
    for r in results:
        counts[r['risk_level']] = counts.get(r['risk_level'], 0) + 1

    print("\nRisk level counts:")
    for level in sorted(counts.keys()):
        print(f"  {level}: {counts[level]}")

    # Print top-N by the period scoring (danger_score, total_precipitation, duration)
    def sort_key(r):
        return (
            -int(r['danger_score'] or 0),
            -float(r['total_precipitation'] or 0.0),
            -float(r['duration_hours'] or 0.0),
        )

    top_n = sorted(results, key=sort_key)[: max(1, int(args.top))]
    print(f"\nTop {len(top_n)} periods (by danger_score/precip/duration):")
    for r in top_n:
        print("\n---")
        print('scenario_type:', r['scenario_type'])
        print('period:', r['start'], '->', r['end'], f"({r['duration_hours']}h)")
        if r.get('peak_time') is not None:
            print('peak_time:', r['peak_time'])
        print('danger_score/total_precip/avg_temp:', r['danger_score'], r['total_precipitation'], r['avg_temperature'])
        print('peak air/surface/snow/precip_1h:',
              _format_val(r['peak_air']), _format_val(r['peak_surface']), _format_val(r['peak_snow']), _format_val(r['peak_precip_1h']))
        print('result:', r['risk_level'], '-', r['scenario'])
        print('message:', r['message'])
        if r['factors']:
            print('factors:', '; '.join(r['factors']))

    low = [r for r in results if r['risk_level'] == 'LOW']
    if low:
        print(f"\nLOW results (first {min(10, len(low))} of {len(low)}):")
        low_sorted = sorted(low, key=sort_key)[:10]
        for r in low_sorted:
            print(f"- {r['start']} -> {r['end']} | peak={r.get('peak_time')} | air={_format_val(r['peak_air'])} surface={_format_val(r['peak_surface'])} precip_1h={_format_val(r['peak_precip_1h'])} | {r['scenario']}")


if __name__ == '__main__':
    main()
