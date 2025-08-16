#!/usr/bin/env python3
"""
Research-grade Snowdrift Analyzer for SN46220 (Gullingen)

Goal:
- Use hourly Frost data with robust derived features to detect physically plausible
  snowdrift (snøfokk) periods.
- Do not modify app criteria yet; produce explainable, research-quality outputs
  for review before integration.

Inputs (hourly):
- air_temperature (°C)
- wind_speed (m/s)
- wind_from_direction (°)
- surface_snow_thickness (cm)
- sum(precipitation_amount PT1H) (mm)
- relative_humidity (%)

Derived features:
- last_6h_precip (mm): rolling sum of precip last 6 hours
- delta_snow_6h (cm): snow depth change vs. 6h ago
- consecutive_wind_ge_{thr} (h): run-length of consecutive hours above threshold
- high_risk_sector (bool): NV–N–NØ (300°–60° wrap)
- loose_snow_gate (bool): (delta_snow_6h ≥ 1cm) OR ((snow_depth ≥ 3cm) AND (temp ≤ -1°C))
- humidity_penalty (bool): RH ≥ 95% AND |temp| < 1°C → increase wind threshold by +1 m/s

Risk logic (per-hour):
- High risk:
  wind ≥ 9 m/s (or ≥ 10 m/s if humidity_penalty) AND temp ≤ -1°C AND loose_snow_gate AND
  consecutive_wind_ge_7 ≥ 2. +1 qualitative weight if high_risk_sector.
- Medium risk:
  wind ≥ 7 m/s (or ≥ 8 m/s if humidity_penalty) AND temp ≤ -1°C AND loose_snow_gate
  OR wind ≥ 8 m/s near 0°C with recent new snow (delta_snow_6h ≥ 1cm).

Outputs:
- CSV/JSON of continuous risk periods (≥2h): start, end, duration, max/avg wind,
  min/avg temp, avg snow, delta snow period, predominant sector, reasons.
- Optional PNG plot path logged if used via PlottingService (not required here).

Usage:
    # Relative period
    python scripts/analysis/research_snowdrift_analyzer.py \
        --days 7 --station SN46220 --out data/analyzed

    # Fixed period
    python scripts/analysis/research_snowdrift_analyzer.py \
        --from 2023-10-01 --to 2024-04-30 --station SN46220 --out data/analyzed

"""
from __future__ import annotations

import argparse
import json

# Local imports
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure we can import from repo's src/ package
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_PATH = _REPO_ROOT / 'src'
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from snofokk.config import settings
from snofokk.services.weather import weather_service


@dataclass
class PeriodSummary:
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    duration_h: float
    risk_level: str  # 'high' or 'medium'
    max_wind: float
    avg_wind: float
    min_temp: float
    avg_temp: float
    avg_snow_depth: float
    delta_snow_period: float
    predominant_sector: str
    sector_counts: dict
    factors: list[str]


def _wind_sector(deg: float) -> str:
    if np.isnan(deg):
        return "NA"
    # 8-point compass
    sectors = [
        (22.5, "N"), (67.5, "NE"), (112.5, "E"), (157.5, "SE"),
        (202.5, "S"), (247.5, "SW"), (292.5, "W"), (337.5, "NW"), (360.0, "N")
    ]
    d = deg % 360
    for bound, label in sectors:
        if d < bound:
            return label
    return "N"


def compute_derived(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Ensure sorted and hourly
    df = df.sort_values("referenceTime").reset_index(drop=True)

    # Clamp invalid snow depth
    if "surface_snow_thickness" in df.columns:
        df["surface_snow_thickness"] = df["surface_snow_thickness"].clip(lower=0)

    # last_6h_precip
    pcol = 'sum(precipitation_amount PT1H)'
    if pcol in df.columns:
        df['last_6h_precip'] = df[pcol].fillna(0).rolling(6, min_periods=1).sum()
    else:
        df['last_6h_precip'] = 0.0
    # precip intensity aliases
    df['precip_mm_h'] = df.get(pcol, pd.Series(0.0, index=df.index)).fillna(0.0)

    # delta_snow_6h
    if 'surface_snow_thickness' in df.columns:
        df['delta_snow_6h'] = df['surface_snow_thickness'] - df['surface_snow_thickness'].shift(6)
    else:
        df['delta_snow_6h'] = np.nan

    # Prefer hourly max wind if available
    if 'max(wind_speed PT1H)' in df.columns:
        base_wind = df['max(wind_speed PT1H)']
        df['wind_speed'] = base_wind.fillna(df.get('wind_speed'))
    # consecutive wind >= 7 m/s (for robustness)
    if 'wind_speed' in df.columns:
        thr = 7.0
        cond = (df['wind_speed'] >= thr).astype(int)
        # Run-length encode consecutive counts
        run = []
        c = 0
        for v in cond:
            if v == 1:
                c += 1
            else:
                c = 0
            run.append(c)
        df['consec_wind_ge7'] = run
    else:
        df['consec_wind_ge7'] = 0

    # high-risk sector (300–360 OR 0–60)
    if 'wind_from_direction' in df.columns:
        d = df['wind_from_direction'] % 360
        df['high_risk_sector'] = ((d >= 300) | (d <= 60)).astype(int)
        df['wind_sector'] = df['wind_from_direction'].apply(_wind_sector)
    else:
        df['high_risk_sector'] = 0
        df['wind_sector'] = 'NA'

    # loose snow gate
    temp = df.get('air_temperature')
    snow = df.get('surface_snow_thickness')
    delta6 = df.get('delta_snow_6h')
    loose = pd.Series(False, index=df.index)
    if temp is not None and snow is not None and delta6 is not None:
        loose = (
            (delta6.fillna(0) >= 1.0) |
            ((snow.fillna(0) >= 3.0) & (temp <= -1.0))
        )
    df['loose_snow_gate'] = loose.astype(int)

    # humidity penalty
    rh = df.get('relative_humidity', pd.Series(np.nan, index=df.index))
    tp = df.get('air_temperature', pd.Series(np.nan, index=df.index))
    df['humidity_penalty'] = ((rh >= 95) & (tp.abs() < 1.0)).astype(int)

    # keep surface and dew point temps if present (no-op)

    return df


def classify_risk_row(row: pd.Series) -> tuple[str, list[str]]:
    factors = []
    w = row.get('wind_speed', np.nan)
    t = row.get('air_temperature', np.nan)
    snow = row.get('surface_snow_thickness', np.nan)
    d6 = row.get('delta_snow_6h', np.nan)
    consec = row.get('consec_wind_ge7', 0)
    sector_boost = row.get('high_risk_sector', 0) == 1
    humidity_pen = row.get('humidity_penalty', 0) == 1

    if not np.isfinite(w) or not np.isfinite(t):
        return 'unknown', ["Mangler vind/temperatur"]

    # Adjust thresholds for humidity penalty near 0°C
    high_thr = 10.0 if humidity_pen else 9.0
    med_thr = 8.0 if humidity_pen else 7.0

    loose_gate = (pd.notna(d6) and d6 >= 1.0) or (pd.notna(snow) and snow >= 3.0 and t <= -1.0)

    if w >= high_thr and t <= -1.0 and loose_gate and consec >= 2:
        factors.append(f"Vind {w:.1f} m/s (≥{high_thr:.0f})")
        factors.append(f"Temp {t:.1f}°C ≤ -1")
        if pd.notna(snow):
            factors.append(f"Snødybde {snow:.0f} cm")
        if pd.notna(d6) and d6 >= 1.0:
            factors.append(f"Ny snø siste 6t {d6:.1f} cm")
        if sector_boost:
            factors.append("Høyrisiko vindsektor (NV–N–NØ)")
        return 'high', factors

    if w >= med_thr and t <= -1.0 and loose_gate:
        factors.append(f"Vind {w:.1f} m/s (≥{med_thr:.0f})")
        factors.append(f"Temp {t:.1f}°C ≤ -1")
        if pd.notna(d6) and d6 >= 1.0:
            factors.append(f"Ny snø siste 6t {d6:.1f} cm")
        if pd.notna(snow):
            factors.append(f"Snødybde {snow:.0f} cm")
        if humidity_pen:
            factors.append("Høy RH nær 0°C → strengere vindkrav brukt")
        return 'medium', factors

    # Edge: near-zero with strong wind and new snow
    if w >= 8.0 and -1.0 < t <= 1.0 and pd.notna(d6) and d6 >= 1.0:
        factors.append(f"Vind {w:.1f} m/s nær 0°C med nysnø {d6:.1f} cm/6t")
        return 'medium', factors

    return 'low', []


def detect_periods(df: pd.DataFrame, min_len: int = 2) -> list[PeriodSummary]:
    if df.empty:
        return []

    # Find contiguous regions for high and medium separately, prefer high
    df = df.copy()
    df['risk_level_num'] = df['risk_level'].map({'low':0,'medium':1,'high':2,'unknown':-1}).fillna(0)

    periods: list[PeriodSummary] = []
    for level, min_code in [('high',2), ('medium',1)]:
        mask = df['risk_level_num'] >= min_code
        if not mask.any():
            continue
        change = mask.astype(int).diff().fillna(0)
        starts = df.index[change == 1].tolist()
        ends = df.index[change == -1].tolist()
        if mask.iloc[0]:
            starts = [df.index[0]] + starts
        if mask.iloc[-1]:
            ends = ends + [df.index[-1]]
        for s, e in zip(starts, ends, strict=False):
            block = df.loc[s:e]
            if len(block) < min_len:
                continue
            factors_all = []
            for f in block['factors']:
                factors_all.extend(f)
            # Sector stats
            sector_counts = block['wind_sector'].value_counts(dropna=False).to_dict()
            predominant = max(sector_counts, key=sector_counts.get) if sector_counts else 'NA'
            periods.append(PeriodSummary(
                start_time=block['referenceTime'].iloc[0],
                end_time=block['referenceTime'].iloc[-1],
                duration_h=float(len(block)),
                risk_level=level,
                max_wind=float(block['wind_speed'].max()) if 'wind_speed' in block else np.nan,
                avg_wind=float(block['wind_speed'].mean()) if 'wind_speed' in block else np.nan,
                min_temp=float(block['air_temperature'].min()) if 'air_temperature' in block else np.nan,
                avg_temp=float(block['air_temperature'].mean()) if 'air_temperature' in block else np.nan,
                avg_snow_depth=float(block['surface_snow_thickness'].mean()) if 'surface_snow_thickness' in block else np.nan,
                delta_snow_period=float((block['surface_snow_thickness'].iloc[-1] - block['surface_snow_thickness'].iloc[0]) if 'surface_snow_thickness' in block else np.nan),
                predominant_sector=predominant,
                sector_counts=sector_counts,
                factors=sorted(list(set(factors_all)))[:10]
            ))
    return periods


# ---------------- Slippery-road analysis ----------------
def classify_slippery_row(row: pd.Series) -> tuple[str, list[str]]:
    """Classify slippery-road risk (regn-på-snø + isdannelse/rim).
    Returns (risk_level, factors).
    """
    factors: list[str] = []
    t_air = row.get('air_temperature', np.nan)
    t_surf = row.get('surface_temperature', np.nan)
    t_dew = row.get('dew_point_temperature', np.nan)
    rh = row.get('relative_humidity', np.nan)
    snow = row.get('surface_snow_thickness', np.nan)
    precip = row.get('precip_mm_h', 0.0)
    d6 = row.get('delta_snow_6h', np.nan)

    if not np.isfinite(t_air):
        return 'unknown', ["Mangler lufttemp"]

    existing_snow = (pd.notna(snow) and snow >= 1.0)
    rain_now = (precip is not None) and (precip >= 0.1) and (t_air > -1.0)

    # Heuristics thresholds
    rain_high = precip >= 1.0
    near_zero_air = (-1.0 <= t_air <= 2.0)
    dew_close_surface = (pd.notna(t_dew) and pd.notna(t_surf) and abs(t_dew - t_surf) <= 1.0)
    rh_high = (pd.notna(rh) and rh >= 95)

    # Protective rule: if snow depth increased ≥1 cm last 6h, prefer Low (nysnø = naturlig strøing)
    if pd.notna(d6) and d6 >= 1.0:
        return 'low', ["Økende snødybde (nysnø) → redusert glattrisiko"]

    # High risk: rain on snow OR black ice formation
    if (rain_high and near_zero_air and existing_snow):
        factors.append(f"Regn {precip:.1f} mm/h på snødybde {snow:.0f} cm")
        factors.append(f"Lufttemp {t_air:.1f}°C nær 0")
        return 'high', factors

    if (pd.notna(t_surf) and t_surf <= 0.0 and near_zero_air and (rain_now or (rh_high and dew_close_surface))):
        factors.append(f"Veitemp {t_surf:.1f}°C ≤ 0 med {('regn' if rain_now else 'høy RH')} og luft {t_air:.1f}°C")
        if dew_close_surface:
            factors.append("Duggpunkt ~ veitemp → isdannelse mulig")
        if existing_snow:
            factors.append("Snø til stede")
        return 'high', factors

    # Medium risk: light rain on snow, or marginal icing signals
    if ((precip >= 0.2 and near_zero_air and existing_snow) or
        (pd.notna(t_surf) and -0.5 <= t_surf <= 0.5 and (rh_high or dew_close_surface))):
        if precip >= 0.2 and existing_snow:
            factors.append(f"Lett regn {precip:.1f} mm/h på snø")
        if pd.notna(t_surf):
            factors.append(f"Veitemp {t_surf:.1f}°C rundt 0")
        if rh_high:
            factors.append("Høy relativ fuktighet")
        if dew_close_surface:
            factors.append("Duggpunkt nær veitemp")
        return 'medium', factors

    return 'low', []


def detect_periods_for(df: pd.DataFrame, label_col: str, min_len: int = 2) -> list[PeriodSummary]:
    if df.empty or label_col not in df.columns:
        return []
    df = df.copy()
    df['risk_level_num'] = df[label_col].map({'low':0,'medium':1,'high':2,'unknown':-1}).fillna(0)

    periods: list[PeriodSummary] = []
    for level, min_code in [('high',2), ('medium',1)]:
        mask = df['risk_level_num'] >= min_code
        if not mask.any():
            continue
        change = mask.astype(int).diff().fillna(0)
        starts = df.index[change == 1].tolist()
        ends = df.index[change == -1].tolist()
        if mask.iloc[0]:
            starts = [df.index[0]] + starts
        if mask.iloc[-1]:
            ends = ends + [df.index[-1]]
        for s, e in zip(starts, ends, strict=False):
            block = df.loc[s:e]
            if len(block) < min_len:
                continue
            factors_all: list[str] = []
            for f in block['factors_slippery'] if 'factors_slippery' in block else []:
                factors_all.extend(f)
            sector_counts = block.get('wind_sector', pd.Series(['NA']*len(block))).value_counts(dropna=False).to_dict()
            predominant = max(sector_counts, key=sector_counts.get) if sector_counts else 'NA'
            periods.append(PeriodSummary(
                start_time=block['referenceTime'].iloc[0],
                end_time=block['referenceTime'].iloc[-1],
                duration_h=float(len(block)),
                risk_level=level,
                max_wind=float(block['wind_speed'].max()) if 'wind_speed' in block else np.nan,
                avg_wind=float(block['wind_speed'].mean()) if 'wind_speed' in block else np.nan,
                min_temp=float(block['air_temperature'].min()) if 'air_temperature' in block else np.nan,
                avg_temp=float(block['air_temperature'].mean()) if 'air_temperature' in block else np.nan,
                avg_snow_depth=float(block['surface_snow_thickness'].mean()) if 'surface_snow_thickness' in block else np.nan,
                delta_snow_period=float((block['surface_snow_thickness'].iloc[-1] - block['surface_snow_thickness'].iloc[0]) if 'surface_snow_thickness' in block else np.nan),
                predominant_sector=predominant,
                sector_counts=sector_counts,
                factors=sorted(list(set(factors_all)))[:10]
            ))
    return periods


def _parse_range(days: int | None, from_date: str | None, to_date: str | None) -> tuple[pd.Timestamp, pd.Timestamp]:
    tz = settings.tz
    if from_date and to_date:
        start_local = pd.Timestamp(from_date).tz_localize(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = pd.Timestamp(to_date).tz_localize(tz).replace(hour=23, minute=0, second=0, microsecond=0)
        return start_local.tz_convert('UTC'), end_local.tz_convert('UTC')
    # fallback to days
    end_utc = pd.Timestamp.now(tz='UTC')
    start_utc = end_utc - pd.Timedelta(days=days or 7)
    return start_utc, end_utc


def _fetch_range_chunked(station: str, start_utc: pd.Timestamp, end_utc: pd.Timestamp, client_id: str, chunk_days: int = 31) -> pd.DataFrame:
    """Fetch large ranges in monthly-ish chunks to avoid API limits."""
    frames: list[pd.DataFrame] = []
    cur = start_utc
    while cur <= end_utc:
        chunk_end = min(cur + pd.Timedelta(days=chunk_days), end_utc)
        df_chunk = weather_service.fetch_weather_data(
            station=station,
            from_time=cur.strftime('%Y-%m-%dT%H:00:00Z'),
            to_time=chunk_end.strftime('%Y-%m-%dT%H:00:00Z'),
            client_id=client_id
        )
        if df_chunk is not None and not df_chunk.empty:
            frames.append(df_chunk)
        cur = chunk_end + pd.Timedelta(hours=1)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    # Drop potential duplicates
    df = df.drop_duplicates(subset=['referenceTime'])
    return df.sort_values('referenceTime').reset_index(drop=True)


def _write_report(outp: Path, station: str, ts: str,
                  snow_periods: list[PeriodSummary],
                  slip_periods: list[PeriodSummary],
                  df: pd.DataFrame,
                  title: str) -> Path:
    def _summ(periods: list[PeriodSummary]) -> dict[str, float]:
        if not periods:
            return {"count": 0, "median_dur_h": 0.0, "p95_wind": 0.0}
        durations = [p.duration_h for p in periods]
        winds = [p.max_wind for p in periods if np.isfinite(p.max_wind)]
        return {
            "count": len(periods),
            "median_dur_h": float(np.median(durations)),
            "p95_wind": float(np.percentile(winds, 95)) if winds else 0.0
        }

    snow_s = _summ(snow_periods)
    slip_s = _summ(slip_periods)
    start = df['referenceTime'].min()
    end = df['referenceTime'].max()
    md = []
    md.append(f"# {title}\n")
    md.append(f"Stasjon: {station}")
    md.append(f"Periode: {start} – {end}\n")
    md.append("## Snøfokk\n")
    md.append(f"- Antall perioder: {snow_s['count']}")
    md.append(f"- Median varighet: {snow_s['median_dur_h']:.1f} h")
    md.append(f"- 95-persentil maks vind: {snow_s['p95_wind']:.1f} m/s\n")
    md.append("## Glatt føre\n")
    md.append(f"- Antall perioder: {slip_s['count']}")
    md.append(f"- Median varighet: {slip_s['median_dur_h']:.1f} h\n")
    # Simple threshold sanity snapshots
    md.append("### Observasjoner (snapshot)\n")
    cnt_rain_snow = int(((df['precip_mm_h'] >= 0.2) & (df['air_temperature'] > -1) & (df.get('surface_snow_thickness', 0) >= 1)).sum())
    md.append(f"- Timer med regn på snø (≥0.2 mm/h): {cnt_rain_snow}")
    cnt_icing = int(((df.get('surface_temperature', np.nan) <= 0) & (df['air_temperature'] > -1)).sum())
    md.append(f"- Timer med mulig is-dannelse (veitemp ≤ 0, luft > -1°C): {cnt_icing}\n")

    report_path = outp / f"research_report_{station}_{ts}.md"
    report_path.write_text("\n".join(md), encoding='utf-8')
    return report_path


def run(days: int | None, station: str | None, out_dir: str, from_date: str | None = None, to_date: str | None = None) -> tuple[pd.DataFrame, list[PeriodSummary], list[PeriodSummary]]:
    station = station or settings.weather_station
    client_id = settings.frost_client_id

    start_utc, end_utc = _parse_range(days, from_date, to_date)

    # Chunked fetch for long ranges
    df = _fetch_range_chunked(station, start_utc, end_utc, client_id, chunk_days=31)
    if df is None or df.empty:
        raise SystemExit("No data fetched from Frost API")

    df = weather_service.normalize_snow_data(df)
    df = compute_derived(df)

    # Snowdrift per-hour classification
    risks = df.apply(classify_risk_row, axis=1)
    df['risk_level'] = risks.map(lambda x: x[0])
    df['factors'] = risks.map(lambda x: x[1])

    # Slippery per-hour classification
    slip = df.apply(classify_slippery_row, axis=1)
    df['risk_slippery'] = slip.map(lambda x: x[0])
    df['factors_slippery'] = slip.map(lambda x: x[1])

    # Detect periods
    periods_snow = detect_periods(df, min_len=2)
    periods_slip = detect_periods_for(df, 'risk_slippery', min_len=2)

    # Write outputs
    outp = Path(out_dir)
    outp.mkdir(parents=True, exist_ok=True)

    ts = pd.Timestamp.now(tz=settings.tz).strftime('%Y%m%d_%H%M')

    # Features
    df_out = df.copy()
    features_path = outp / f"research_features_{station}_{ts}.csv"
    df_out.to_csv(features_path, index=False)

    # Snowdrift periods
    snow_csv = outp / f"research_snowdrift_periods_{station}_{ts}.csv"
    snow_json = outp / f"research_snowdrift_periods_{station}_{ts}.json"
    snow_df = pd.DataFrame([{**asdict(p), 'start_time': p.start_time.isoformat(), 'end_time': p.end_time.isoformat()} for p in periods_snow])
    snow_df.to_csv(snow_csv, index=False)
    with open(snow_json, 'w', encoding='utf-8') as f:
        json.dump([asdict(p) for p in periods_snow], f, ensure_ascii=False, indent=2, default=str)

    # Slippery periods
    slip_csv = outp / f"research_slippery_periods_{station}_{ts}.csv"
    slip_json = outp / f"research_slippery_periods_{station}_{ts}.json"
    slip_df = pd.DataFrame([{**asdict(p), 'start_time': p.start_time.isoformat(), 'end_time': p.end_time.isoformat()} for p in periods_slip])
    slip_df.to_csv(slip_csv, index=False)
    with open(slip_json, 'w', encoding='utf-8') as f:
        json.dump([asdict(p) for p in periods_slip], f, ensure_ascii=False, indent=2, default=str)

    # Report
    report_path = _write_report(outp, station, ts, periods_snow, periods_slip, df_out, title="Sesonganalyse: snøfokk og glatt føre")

    print(f"Saved features to: {features_path}")
    print(f"Saved snowdrift periods CSV: {snow_csv}")
    print(f"Saved snowdrift periods JSON: {snow_json}")
    print(f"Saved slippery periods CSV: {slip_csv}")
    print(f"Saved slippery periods JSON: {slip_json}")
    print(f"Saved report: {report_path}")

    # Quick console summary
    high_cnt_snow = sum(1 for p in periods_snow if p.risk_level == 'high')
    med_cnt_snow = sum(1 for p in periods_snow if p.risk_level == 'medium')
    high_cnt_slip = sum(1 for p in periods_slip if p.risk_level == 'high')
    med_cnt_slip = sum(1 for p in periods_slip if p.risk_level == 'medium')
    print(f"Detected periods -> Snøfokk High: {high_cnt_snow}, Medium: {med_cnt_snow} | Glatt føre High: {high_cnt_slip}, Medium: {med_cnt_slip}")

    return df, periods_snow, periods_slip


def main():
    parser = argparse.ArgumentParser(description="Research-grade Snowdrift + Slippery Analyzer")
    parser.add_argument('--days', type=int, default=None, help='Number of days back from now')
    parser.add_argument('--from', dest='from_date', type=str, default=None, help='Start date (YYYY-MM-DD, local time)')
    parser.add_argument('--to', dest='to_date', type=str, default=None, help='End date (YYYY-MM-DD, local time)')
    parser.add_argument('--station', type=str, default=None, help='Frost station id (default from settings)')
    parser.add_argument('--out', type=str, default='data/analyzed', help='Output directory')
    args = parser.parse_args()

    if not args.days and not (args.from_date and args.to_date):
        # default to 7 days if nothing provided
        args.days = 7

    run(days=args.days, station=args.station, out_dir=args.out, from_date=args.from_date, to_date=args.to_date)


if __name__ == '__main__':
    main()
