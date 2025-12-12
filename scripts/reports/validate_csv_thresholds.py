#!/usr/bin/env python3
"""
Valider CSV-data mot konfigurerte terskler.

Kjører samme logikk som src/analyzers/* på historiske data for å:
1. Telle treff/ikke-treff per risikonivå
2. Sammenligne mot faktiske brøyteepisoder

Usage:
  venv/bin/python scripts/reports/validate_csv_thresholds.py \\
    --csv data/analyzed/enhanced_features_SN46220_2024-01-01_to_2024-03-31.csv \\
    --plowing data/analyzed/broyting_weather_correlation_2025.csv
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

# Allow running as a standalone script: ensure project root is importable.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analyzers.base import BaseAnalyzer, RiskLevel
from src.config import settings


@dataclass(frozen=True)
class Columns:
    """Normaliserte kolonnenavn."""
    time: str = "reference_time"
    air_temp: str = "air_temperature"
    surface_temp: str = "surface_temperature"
    wind: str = "wind_speed"
    gust: str = "max_wind_gust"
    wind_dir: str = "wind_from_direction"
    snow: str = "surface_snow_thickness"
    precip_1h: str = "precipitation_1h"
    dew_point: str = "dew_point_temperature"
    humidity: str = "relative_humidity"


COLS = Columns()


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliser kolonnenavn fra ulike CSV-kilder."""
    df = df.copy()
    df.columns = [str(c).strip().replace("\\n", "").replace("\\r", "") for c in df.columns]
    
    rename_map = {
        "referenceTime": COLS.time,
        "timestamp": COLS.time,
        "datetime": COLS.time,
        "start": COLS.time,
        "air_temp_avg": COLS.air_temp,
        "surface_temp_avg": COLS.surface_temp,
        "wind_avg": COLS.wind,
        "gust_max": COLS.gust,
        "surface_snow_thickness": COLS.snow,
        "snow_depth": COLS.snow,
        "sum(precipitation_amount PT1H)": COLS.precip_1h,
        "precip_mm_h": COLS.precip_1h,
        "precipitation_amount": COLS.precip_1h,
        "dew_point": COLS.dew_point,
        "dew_point_avg": COLS.dew_point,
        "humidity_avg": COLS.humidity,
    }
    
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    
    # Estimer nedbør hvis vi har total + varighet
    if COLS.precip_1h not in df.columns and {"precip_total", "precip_duration"}.issubset(df.columns):
        duration_h = pd.to_numeric(df["precip_duration"], errors="coerce") / 60.0
        total = pd.to_numeric(df["precip_total"], errors="coerce")
        rate = total / duration_h
        df[COLS.precip_1h] = rate.replace([float("inf"), float("-inf")], 0).fillna(0)
    
    # Parse tid
    if COLS.time in df.columns:
        df[COLS.time] = pd.to_datetime(df[COLS.time], errors="coerce", utc=True)
        df = df.dropna(subset=[COLS.time]).sort_values(COLS.time)
    
    return df


def safe_float(value: Any) -> float | None:
    """Konverter til float, håndter NaN/None."""
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        return float(value)
    except Exception:
        return None


def snow_at(df: pd.DataFrame, t: pd.Timestamp) -> float | None:
    """Hent snødybde ved tidspunkt t."""
    if COLS.snow not in df.columns or df.empty:
        return None
    tmp = pd.DataFrame({COLS.time: [t]})
    merged = pd.merge_asof(
        tmp, 
        df[[COLS.time, COLS.snow]].dropna().sort_values(COLS.time), 
        on=COLS.time, 
        direction="backward"
    )
    return safe_float(merged.iloc[0].get(COLS.snow))


def snow_change(df: pd.DataFrame, t: pd.Timestamp, hours: int) -> float | None:
    """Beregn snøendring siste N timer."""
    now = snow_at(df, t)
    past = snow_at(df, t - pd.Timedelta(hours=hours))
    if now is None or past is None:
        return None
    return now - past


def precip_total(df: pd.DataFrame, t: pd.Timestamp, hours: int) -> float:
    """Akkumuler nedbør siste N timer (mm) basert på precipitation_1h."""
    if COLS.precip_1h not in df.columns or df.empty:
        return 0.0
    window = df[(df[COLS.time] >= (t - pd.Timedelta(hours=hours))) & (df[COLS.time] <= t)]
    vals = pd.to_numeric(window[COLS.precip_1h], errors="coerce").fillna(0.0)
    return float(vals.sum())


def loose_snow_available(df: pd.DataFrame, t: pd.Timestamp) -> bool | None:
    """Sjekk om løssnø er tilgjengelig (kontinuerlig frost)."""
    if COLS.air_temp not in df.columns or df.empty:
        return None
    window = df[(df[COLS.time] >= (t - pd.Timedelta(hours=24))) & (df[COLS.time] <= t)]
    temps = pd.to_numeric(window[COLS.air_temp], errors="coerce").dropna()
    if temps.empty:
        return None
    
    mild_hours = int((temps > 0).sum())
    continuous_frost = bool((temps <= -1).all())
    
    if continuous_frost:
        return True
    if mild_hours >= 6:
        return False
    return True


def recent_snow_relief(df: pd.DataFrame, t: pd.Timestamp) -> bool | None:
    """Sjekk om fersk snø gir naturlig strøing."""
    change = snow_change(df, t, hours=settings.slippery.recent_snow_relief_hours)
    if change is None:
        return None
    return change >= settings.slippery.recent_snow_relief_cm


def evaluate_snowdrift(df: pd.DataFrame, row: pd.Series) -> RiskLevel:
    """Evaluer snøfokk-risiko for én rad."""
    th = settings.snowdrift
    t = row[COLS.time]
    
    if t.month not in settings.WINTER_MONTHS:
        return RiskLevel.LOW
    
    temp = safe_float(row.get(COLS.air_temp))
    wind = safe_float(row.get(COLS.wind))
    snow = safe_float(row.get(COLS.snow)) or 0.0
    gust = safe_float(row.get(COLS.gust))
    wind_dir = safe_float(row.get(COLS.wind_dir))
    
    if temp is None or wind is None:
        return RiskLevel.UNKNOWN
    
    loose = loose_snow_available(df, t)
    if loose is False:
        return RiskLevel.LOW
    
    if snow < th.snow_depth_min_cm:
        return RiskLevel.LOW
    
    wind_chill = BaseAnalyzer.calculate_wind_chill(temp, wind)
    critical_dir = wind_dir is not None and th.critical_wind_dir_min <= wind_dir <= th.critical_wind_dir_max
    
    # Vindkast-trigger (høyeste prioritet)
    if gust is not None and temp <= th.temperature_max:
        if gust >= th.wind_gust_critical and wind >= th.wind_speed_warning:
            return RiskLevel.HIGH
        if gust >= th.wind_gust_warning and wind >= th.wind_speed_median:
            return RiskLevel.MEDIUM
    
    # ML vindkjøling-kriterier
    if wind_chill <= th.wind_chill_critical and wind >= th.wind_speed_critical:
        return RiskLevel.HIGH
    if wind_chill <= th.wind_chill_warning and wind >= th.wind_speed_warning:
        return RiskLevel.MEDIUM
    
    # Tradisjonelle kriterier
    if wind >= th.wind_speed_warning and temp <= th.temperature_max:
        if wind >= th.wind_speed_critical or critical_dir:
            return RiskLevel.HIGH
        return RiskLevel.MEDIUM
    
    return RiskLevel.LOW


def evaluate_fresh_snow(df: pd.DataFrame, row: pd.Series) -> RiskLevel:
    """Evaluer nysnø-risiko for én rad."""
    th = settings.fresh_snow
    t = row[COLS.time]
    
    if t.month not in settings.WINTER_MONTHS:
        return RiskLevel.LOW
    
    snow_now = safe_float(row.get(COLS.snow))
    if snow_now is None:
        return RiskLevel.UNKNOWN
    
    temp = safe_float(row.get(COLS.air_temp))
    dew = safe_float(row.get(COLS.dew_point))
    precip = safe_float(row.get(COLS.precip_1h)) or 0.0
    
    change_6h = snow_change(df, t, hours=6)
    if change_6h is None:
        change_6h = safe_float(row.get("snow_change_6h"))
    
    is_snow = False
    if precip > 0:
        if dew is not None:
            is_snow = dew < th.dew_point_max
        elif temp is not None:
            is_snow = temp < th.air_temp_max
    
    active_snowfall = precip > th.precipitation_min and is_snow
    
    if change_6h is not None:
        if change_6h >= th.snow_increase_critical:
            return RiskLevel.HIGH
        if change_6h >= th.snow_increase_warning:
            return RiskLevel.MEDIUM
    
    if active_snowfall:
        return RiskLevel.MEDIUM
    
    return RiskLevel.LOW


def evaluate_slaps(df: pd.DataFrame, row: pd.Series) -> RiskLevel:
    """Evaluer slaps-risiko for én rad."""
    th = settings.slaps
    t = row[COLS.time]
    
    if t.month not in settings.WINTER_MONTHS:
        return RiskLevel.LOW
    
    temp = safe_float(row.get(COLS.air_temp))
    if temp is None:
        return RiskLevel.UNKNOWN
    
    snow = safe_float(row.get(COLS.snow)) or 0.0
    precip = safe_float(row.get(COLS.precip_1h)) or 0.0
    precip_12h = precip_total(df, t, hours=12)
    dew = safe_float(row.get(COLS.dew_point))
    
    if snow < th.snow_depth_min:
        return RiskLevel.LOW
    
    in_range = th.temp_min <= temp <= th.temp_max
    if not in_range:
        if temp < th.temp_min:
            return RiskLevel.LOW
        # Temp over maks gir ikke slaps-varsel alene – krever tegn på aktiv smelting.
        change_6h = snow_change(df, t, hours=6)
        if change_6h is not None and change_6h < -2:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
    
    change_6h = snow_change(df, t, hours=6)
    rain = (dew is not None and dew >= 0.0) or (dew is None and temp >= 1.0)
    
    rain_on_snow = rain and precip_12h >= th.precipitation_12h_min
    melting = change_6h is not None and change_6h < -2
    
    if rain_on_snow and melting:
        return RiskLevel.HIGH
    if rain_on_snow:
        return RiskLevel.HIGH if precip_12h >= th.precipitation_12h_heavy else RiskLevel.MEDIUM
    if melting:
        return RiskLevel.MEDIUM
    
    return RiskLevel.LOW


def evaluate_slippery(df: pd.DataFrame, row: pd.Series) -> RiskLevel:
    """Evaluer glattføre-risiko for én rad."""
    th = settings.slippery
    t = row[COLS.time]
    
    if t.month not in settings.WINTER_MONTHS:
        return RiskLevel.LOW
    
    temp = safe_float(row.get(COLS.air_temp))
    if temp is None:
        return RiskLevel.UNKNOWN
    
    snow = safe_float(row.get(COLS.snow)) or 0.0
    precip = safe_float(row.get(COLS.precip_1h)) or 0.0
    surface_temp = safe_float(row.get(COLS.surface_temp))
    dew_point = safe_float(row.get(COLS.dew_point))
    humidity = safe_float(row.get(COLS.humidity))
    wind = safe_float(row.get(COLS.wind))
    
    mild = th.mild_temp_min <= temp <= th.mild_temp_max
    existing_snow = snow >= th.snow_depth_min_cm
    rain_now = precip >= th.rain_threshold_mm
    freezing_precip_warning = precip >= th.freezing_precip_warning_mm
    freezing_precip_critical = precip >= th.freezing_precip_critical_mm
    near_freezing = th.near_freezing_temp_min <= temp <= th.near_freezing_temp_max

    precip_12h = precip_total(df, t, hours=12)

    hidden_freeze = (
        surface_temp is not None
        and th.hidden_freeze_air_min <= temp <= th.hidden_freeze_air_max
        and surface_temp <= th.hidden_freeze_surface_max
    )
    ice_risk = surface_temp is not None and surface_temp <= th.surface_temp_freeze
    
    if hidden_freeze:
        melt = snow_change(df, t, hours=6)
        melt_indicator = melt is not None and melt <= th.melt_snow_change_6h_cm
        moisture_likely = (
            (precip_12h >= th.hidden_freeze_precip_12h_min)
            or melt_indicator
            or (humidity is not None and humidity >= th.rimfrost_humidity_min)
        )
        return RiskLevel.HIGH if moisture_likely else RiskLevel.MEDIUM
    
    if mild and existing_snow and rain_now:
        relief = recent_snow_relief(df, t)
        if relief is True:
            return RiskLevel.MEDIUM
        return RiskLevel.HIGH
    
    # Underkjølt regn / frysing på kald bakke: nær frysepunktet + målbar nedbør
    if ice_risk and freezing_precip_critical and near_freezing:
        return RiskLevel.HIGH

    if ice_risk and freezing_precip_warning and near_freezing:
        return RiskLevel.MEDIUM

    # Kald bakke under snø: normalt vinterføre. Varsle kun ved rimfrost/refrysing-indikatorer.
    if ice_risk and existing_snow:
        frost_risk = False
        if dew_point is not None:
            frost_risk = (
                abs(temp - dew_point) < 2
                and (humidity is None or humidity >= th.rimfrost_humidity_min)
                and (wind is None or wind <= th.rimfrost_wind_max)
            )

        melt = snow_change(df, t, hours=6)
        melt_indicator = melt is not None and melt <= th.melt_snow_change_6h_cm

        if frost_risk or melt_indicator:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
    
    return RiskLevel.LOW


def load_plowing_data(path: Path) -> pd.DataFrame:
    """Last brøytedata."""
    df = pd.read_csv(path)
    df = normalize_columns(df)
    return df


def match_plowing_events(weather_df: pd.DataFrame, plowing_df: pd.DataFrame, hours_before: int = 6) -> dict:
    """
    Sjekk hvor mange brøyteepisoder som hadde medium/høy risiko i timene før.
    
    Returns:
        Dict med statistikk per scenario.
    """
    results = {
        "snowdrift": {"total_events": 0, "had_warning": 0, "had_critical": 0},
        "slippery": {"total_events": 0, "had_warning": 0, "had_critical": 0},
        "fresh_snow": {"total_events": 0, "had_warning": 0, "had_critical": 0},
        "slaps": {"total_events": 0, "had_warning": 0, "had_critical": 0},
    }
    
    for _, plow_row in plowing_df.iterrows():
        plow_time = plow_row[COLS.time]
        scenario = plow_row.get("scenario", "ANNET")
        
        # Hent værdata 6 timer før brøyting
        window = weather_df[
            (weather_df[COLS.time] >= plow_time - pd.Timedelta(hours=hours_before)) &
            (weather_df[COLS.time] <= plow_time)
        ]
        
        if window.empty:
            continue
        
        # Evaluer risiko i vinduet
        for key, eval_func in [
            ("snowdrift", evaluate_snowdrift),
            ("slippery", evaluate_slippery),
            ("fresh_snow", evaluate_fresh_snow),
            ("slaps", evaluate_slaps),
        ]:
            risks = [eval_func(weather_df, row) for _, row in window.iterrows()]
            
            has_high = any(r == RiskLevel.HIGH for r in risks)
            has_medium = any(r == RiskLevel.MEDIUM for r in risks)
            
            # Tell kun relevante scenarier
            relevant = False
            if key == "snowdrift" and scenario in ["SNØFOKK", "ANNET"]:
                relevant = True
            elif key == "fresh_snow" and scenario in ["NYSNØ", "ANNET"]:
                relevant = True
            elif key == "slaps" and scenario in ["SLAPS", "ANNET"]:
                relevant = True
            elif key == "slippery" and scenario in ["FRYSEFARE", "ANNET"]:
                relevant = True
            
            if relevant:
                results[key]["total_events"] += 1
                if has_high:
                    results[key]["had_critical"] += 1
                elif has_medium:
                    results[key]["had_warning"] += 1
    
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Valider CSV mot terskler")
    parser.add_argument("--csv", required=True, help="Værdata CSV")
    parser.add_argument("--plowing", help="Brøytedata CSV (valgfritt)")
    parser.add_argument("--out", help="Output CSV sti")
    args = parser.parse_args()
    
    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV ikke funnet: {csv_path}")
    
    # Last værdata
    df = pd.read_csv(csv_path)
    df = normalize_columns(df)
    
    if COLS.time not in df.columns:
        raise SystemExit(f"Fant ikke tidsstempel-kolonne. Kolonner: {list(df.columns)}")
    
    print("=" * 70)
    print(f"Validerer: {csv_path}")
    print(f"Rader: {len(df)}")
    print(f"Periode: {df[COLS.time].min()} til {df[COLS.time].max()}")
    
    # Evaluer risikonivåer
    df_out = df.copy()
    df_out["snowdrift_risk"] = df_out.apply(lambda r: evaluate_snowdrift(df_out, r).value, axis=1)
    df_out["slippery_risk"] = df_out.apply(lambda r: evaluate_slippery(df_out, r).value, axis=1)
    df_out["fresh_snow_risk"] = df_out.apply(lambda r: evaluate_fresh_snow(df_out, r).value, axis=1)
    df_out["slaps_risk"] = df_out.apply(lambda r: evaluate_slaps(df_out, r).value, axis=1)
    
    # Oppsummering
    def count_levels(col):
        counts = df_out[col].value_counts().to_dict()
        return {
            "unknown": counts.get("unknown", 0),
            "low": counts.get("low", 0),
            "medium": counts.get("medium", 0),
            "high": counts.get("high", 0),
        }
    
    print("\nRISIKOFORDELING:")
    print(f"  Snøfokk:   {count_levels('snowdrift_risk')}")
    print(f"  Glattføre: {count_levels('slippery_risk')}")
    print(f"  Nysnø:     {count_levels('fresh_snow_risk')}")
    print(f"  Slaps:     {count_levels('slaps_risk')}")
    
    # Brøytevalidering
    if args.plowing:
        plow_path = Path(args.plowing)
        if plow_path.exists():
            print(f"\nBRØYTEVALIDERING: {plow_path}")
            plow_df = load_plowing_data(plow_path)
            print(f"Brøyteepisoder: {len(plow_df)}")
            
            matches = match_plowing_events(df_out, plow_df, hours_before=6)
            
            print("\nTREFFRATE (hadde varsling 6t før brøyting):")
            for key, stats in matches.items():
                total = stats["total_events"]
                if total == 0:
                    continue
                warn = stats["had_warning"]
                crit = stats["had_critical"]
                pct = ((warn + crit) / total * 100) if total > 0 else 0
                print(f"  {key:12} {total:3} episoder → {warn} medium, {crit} høy ({pct:.1f}% treff)")
    
    # Lagre
    if args.out:
        out_path = Path(args.out)
    else:
        out_path = Path("data/analyzed") / f"threshold_validation_{csv_path.stem}.csv"
    
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(out_path, index=False)
    print(f"\nLagret: {out_path}")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
