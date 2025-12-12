#!/usr/bin/env python3
"""Sjekk vær-CSV mot brøyteloggen.

Første steg i en stegvis gjennomgang av appen:
- Les værdata fra en CSV (typisk `data/analyzed/enhanced_features_*.csv`).
- Les brøyteloggen `data/analyzed/Rapport 2022-2025.csv` (semikolon-separert).
- For hver unik brøytehendelse: hent vær i et vindu før start og beregn enkle
  statistikker + scenario.

Eksempel:
    python scripts/analyze_broyting_correlation.py \
      --weather data/analyzed/enhanced_features_SN46220_2024-01-01_to_2024-03-31.csv \
    --plowing "data/analyzed/Rapport 2022-2025.csv" \
      --hours 6
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

DEFAULT_WEATHER_FILE = DATA_DIR / "analyzed" / "enhanced_features_SN46220_2024-01-01_to_2024-03-31.csv"
DEFAULT_PLOWING_FILE = DATA_DIR / "analyzed" / "Rapport 2022-2025.csv"


def parse_duration_to_minutes(duration_str: str) -> float | None:
    s = str(duration_str).strip()
    if not s or s.lower() == "nan":
        return None
    try:
        parts = s.split(":")
        if len(parts) == 3:
            h, m, sec = (int(p) for p in parts)
            return h * 60 + m + sec / 60
        if len(parts) == 2:
            m, sec = (int(p) for p in parts)
            return m + sec / 60
        return None
    except Exception:
        return None


def parse_distance_km(distance_str: str) -> float | None:
    s = str(distance_str).strip()
    if not s or s.lower() == "nan":
        return None
    try:
        return float(s.replace(",", "."))
    except Exception:
        return None


def parse_norwegian_datetime_to_utc(date_str: str, time_str: str) -> datetime:
    """Parse norsk datoformat (lokal tid) og returner UTC."""
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

    parts = str(date_str).split()
    day = int(parts[0].rstrip("."))
    month = month_map.get(parts[1], 1)
    year = int(parts[2])

    time_parts = str(time_str).split(":")
    hour = int(time_parts[0])
    minute = int(time_parts[1])
    second = int(time_parts[2]) if len(time_parts) >= 3 else 0

    local_dt = datetime(year, month, day, hour, minute, second)

    try:
        import zoneinfo

        oslo_tz = zoneinfo.ZoneInfo("Europe/Oslo")
        return local_dt.replace(tzinfo=oslo_tz).astimezone(UTC)
    except Exception:
        # Fallback: antar UTC
        return local_dt.replace(tzinfo=UTC)


def load_plowing_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";")
    df = df[df["Dato"] != "Totalt"].copy()

    if "Varighet" in df.columns:
        df["duration_minutes"] = df["Varighet"].apply(parse_duration_to_minutes)
    else:
        df["duration_minutes"] = None

    if "Distanse (km)" in df.columns:
        df["distance_km"] = df["Distanse (km)"].apply(parse_distance_km)
    else:
        df["distance_km"] = None

    start_times: list[datetime | None] = []
    for _, row in df.iterrows():
        try:
            start_times.append(parse_norwegian_datetime_to_utc(row["Dato"], row["Starttid"]))
        except Exception:
            start_times.append(None)

    df["start_utc"] = start_times
    df = df.dropna(subset=["start_utc"]).copy()

    # Unike (samme starttid kan finnes flere ganger per rode/enhet)
    df = df.drop_duplicates(subset=["start_utc", "Rode", "Enhet"]).copy()
    df = df.sort_values("start_utc")
    return df


def _detect_time_column(df: pd.DataFrame) -> str:
    for candidate in [
        "reference_time",
        "referenceTime",
        "timestamp_utc",
        "timestamp",
        "time",
        "datetime",
    ]:
        if candidate in df.columns:
            return candidate
    raise ValueError("Fant ingen tid-kolonne i vær-CSV (prøv referenceTime/reference_time/timestamp)")


def load_weather_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    time_col = _detect_time_column(df)
    ts = pd.to_datetime(df[time_col], utc=True, errors="coerce")
    df = df.assign(timestamp_utc=ts).dropna(subset=["timestamp_utc"]).copy()
    df = df.sort_values("timestamp_utc")
    return df


def get_weather_before(weather_df: pd.DataFrame, dt_utc: datetime, hours: int) -> pd.DataFrame:
    start = dt_utc - timedelta(hours=hours)
    mask = (weather_df["timestamp_utc"] >= start) & (weather_df["timestamp_utc"] <= dt_utc)
    return weather_df.loc[mask]


def _col(df: pd.DataFrame, *names: str) -> str | None:
    for name in names:
        if name in df.columns:
            return name
    return None


def _safe_mean(df: pd.DataFrame, col: str | None) -> float | None:
    if not col:
        return None
    return float(df[col].mean())


def _safe_min(df: pd.DataFrame, col: str | None) -> float | None:
    if not col:
        return None
    return float(df[col].min())


def _safe_max(df: pd.DataFrame, col: str | None) -> float | None:
    if not col:
        return None
    return float(df[col].max())


def _safe_sum(df: pd.DataFrame, col: str | None) -> float | None:
    if not col:
        return None
    return float(df[col].sum())


def analyze_weather_vs_plowing(
    weather_path: Path,
    plowing_path: Path,
    hours: int,
    output_path: Path | None,
) -> pd.DataFrame:
    print("=" * 70)
    print("SJEKK: VÆR-CSV MOT BRØYTELOGG")
    print("=" * 70)

    print("\nLaster data...")
    plow_df = load_plowing_data(plowing_path)
    wx_df = load_weather_data(weather_path)

    print(f"  Brøytehendelser (unika): {len(plow_df)}")
    print(f"  Værobservasjoner: {len(wx_df)}")
    print(f"  Værperiode (UTC): {wx_df['timestamp_utc'].min()} til {wx_df['timestamp_utc'].max()}")

    results: list[dict] = []

    for _, row in plow_df.iterrows():
        start_utc: datetime = row["start_utc"]
        wx = get_weather_before(wx_df, start_utc, hours)

        air_col = _col(wx, "air_temperature")
        surface_col = _col(wx, "surface_temperature")
        wind_col = _col(wx, "wind_speed")
        gust_col = _col(wx, "max_wind_gust", "wind_speed_gust")
        precip_col = _col(wx, "precipitation_1h", "precip_mm_h", "sum(precipitation_amount PT1H)", "precipitation")
        snow_col = _col(wx, "surface_snow_thickness")
        humidity_col = _col(wx, "relative_humidity")
        dew_col = _col(wx, "dew_point_temperature")

        snow_start = float(wx[snow_col].iloc[0]) if (snow_col and len(wx) > 0) else None
        snow_end = float(wx[snow_col].iloc[-1]) if (snow_col and len(wx) > 0) else None
        snow_change = (snow_end - snow_start) if (snow_start is not None and snow_end is not None) else None

        out: dict = {
            "dato": row.get("Dato"),
            "rode": row.get("Rode"),
            "enhet": row.get("Enhet"),
            "start_utc": start_utc,
            "window_hours": hours,
            "duration_minutes": row.get("duration_minutes"),
            "distance_km": row.get("distance_km"),
            "wx_rows": int(len(wx)),
            "air_temp_avg": _safe_mean(wx, air_col),
            "air_temp_min": _safe_min(wx, air_col),
            "air_temp_max": _safe_max(wx, air_col),
            "surface_temp_avg": _safe_mean(wx, surface_col),
            "surface_temp_min": _safe_min(wx, surface_col),
            "wind_avg": _safe_mean(wx, wind_col),
            "wind_max": _safe_max(wx, wind_col),
            "gust_max": _safe_max(wx, gust_col),
            "precip_total": _safe_sum(wx, precip_col),
            "snow_depth_start": snow_start,
            "snow_depth_end": snow_end,
            "snow_change": snow_change,
            "humidity_avg": _safe_mean(wx, humidity_col),
            "dew_point_avg": _safe_mean(wx, dew_col),
        }

        duration_minutes = out.get("duration_minutes")
        distance_km = out.get("distance_km")

        out["short_run_45m"] = bool(duration_minutes is not None and duration_minutes <= 45)
        out["short_run_30m"] = bool(duration_minutes is not None and duration_minutes <= 30)

        # Legacy/stricter inspection proxy (short + short distance)
        out["likely_inspection"] = bool(
            duration_minutes is not None
            and distance_km is not None
            and duration_minutes <= 30
            and distance_km <= 6
        )

        # Enkel scenario-heuristikk for sanity check
        temp = out["air_temp_avg"]
        precip = out["precip_total"] or 0.0
        surface_temp = out["surface_temp_avg"]
        wind = out["wind_avg"]

        gust = out.get("gust_max")
        snow_delta = out.get("snow_change")

        # Simple trigger flags (for separating quick "check" runs from weather-driven need)
        out["trigger_fresh_snow"] = bool(snow_delta is not None and snow_delta >= 5.0)
        out["trigger_slaps"] = bool(temp is not None and temp > 0 and precip >= 5.0)
        out["trigger_freezing"] = bool(surface_temp is not None and surface_temp < 0 and temp is not None and temp > 0)
        out["trigger_snowdrift"] = bool(
            gust is not None
            and gust >= 15.0
            and temp is not None
            and temp < -1.0
            and wind is not None
            and wind >= 8.0
        )
        out["has_weather_trigger"] = bool(
            out["trigger_fresh_snow"]
            or out["trigger_slaps"]
            or out["trigger_freezing"]
            or out["trigger_snowdrift"]
        )
        out["short_45m_no_trigger"] = bool(out["short_run_45m"] and (not out["has_weather_trigger"]))

        if out["wx_rows"] == 0 or temp is None:
            out["scenario"] = "UKJENT"
        elif temp > 0 and precip > 5:
            out["scenario"] = "SLAPS"
        elif temp <= 0 and precip > 2:
            out["scenario"] = "NYSNØ"
        elif surface_temp is not None and surface_temp < 0 and temp > 0:
            out["scenario"] = "FRYSEFARE"
        elif wind is not None and wind > 6 and temp < -1:
            out["scenario"] = "SNØFOKK"
        else:
            out["scenario"] = "ANNET"

        results.append(out)

    out_df = pd.DataFrame(results)

    matched = int((out_df["wx_rows"] > 0).sum())
    print("\nOppsummering:")
    print(f"  Matchede brøytehendelser (har vær i vindu): {matched}/{len(out_df)}")
    if len(out_df) > 0:
        print(f"  Match-rate: {matched/len(out_df)*100:.1f}%")

    if "scenario" in out_df.columns and len(out_df) > 0:
        print("\nScenariofordeling:")
        for scenario, count in out_df["scenario"].value_counts().items():
            print(f"  {scenario}: {count}")

    if output_path is None:
        output_path = DATA_DIR / "analyzed" / f"weather_vs_broyting_{weather_path.stem}_h{hours}.csv"

    out_df.to_csv(output_path, index=False)
    print(f"\nSkrev rapport: {output_path}")

    return out_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Sjekk vær-CSV mot brøyteloggen")
    parser.add_argument("--weather", type=Path, default=DEFAULT_WEATHER_FILE, help="Værdata CSV")
    parser.add_argument("--plowing", type=Path, default=DEFAULT_PLOWING_FILE, help="Brøytelog CSV (Rapport 2022-2025)")
    parser.add_argument("--hours", type=int, default=6, help="Antall timer før brøyting som analyseres")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output CSV (default: data/analyzed/weather_vs_broyting_<stem>_h<hours>.csv)",
    )

    args = parser.parse_args()
    analyze_weather_vs_plowing(args.weather, args.plowing, args.hours, args.out)


if __name__ == "__main__":
    main()
