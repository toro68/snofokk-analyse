from __future__ import annotations

from pathlib import Path
import sys
import re

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]

# Ensure `import src.*` works regardless of current working directory.
sys.path.insert(0, str(REPO_ROOT))

from src.config import settings  # noqa: E402

CORRELATION_CSV = REPO_ROOT / "data" / "analyzed" / "broyting_weather_correlation_2025.csv"
PLOWING_CSV = REPO_ROOT / "data" / "analyzed" / "Rapport 2022-2025.csv"


def _load_correlation_df() -> pd.DataFrame:
    df = pd.read_csv(CORRELATION_CSV, parse_dates=["datetime"])
    return df


def _apply_event_relevance_filter(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Bruk event_relevant_for_thresholds hvis tilgjengelig.

    Fallback: behold alle rader (bakoverkompatibelt med eldre CSV-er).
    """
    stats = {
        "raw_rows": int(len(df)),
        "excluded_not_relevant": 0,
        "kept_rows": int(len(df)),
    }

    if "event_relevant_for_thresholds" not in df.columns:
        return df, stats

    flag = (
        df["event_relevant_for_thresholds"]
        .astype(str)
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False})
    )
    # Manglende/ukjent tolkes konservativt som relevant
    relevant = flag.fillna(True)
    filtered = df.loc[relevant].copy()

    stats["excluded_not_relevant"] = int((~relevant).sum())
    stats["kept_rows"] = int(len(filtered))
    return filtered, stats


def _load_plow_events() -> pd.DataFrame:
    plow = pd.read_csv(PLOWING_CSV, sep=";", encoding="utf-8")
    event_key = ["Dato", "Starttid", "Sluttid", "Rode"]
    plow_events = plow.drop_duplicates(subset=event_key).copy()

    plow_events["duration"] = pd.to_timedelta(plow_events["Varighet"], errors="coerce")
    plow_events["duration_minutes"] = (
        plow_events["duration"].dt.total_seconds().div(60).astype("Float64")
    )
    plow_events["distance_km"] = pd.to_numeric(
        plow_events["Distanse (km)"], errors="coerce"
    ).astype("Float64")

    return plow_events


def _print_header(title: str) -> None:
    print("\n" + title)
    print("-" * len(title))


def _parse_norwegian_dato_series(dato: pd.Series) -> pd.Series:
    """Parse dates like '21. des. 2022' from Rapport 2022-2025.csv."""
    month_map = {
        "jan": "01",
        "feb": "02",
        "mar": "03",
        "apr": "04",
        "mai": "05",
        "jun": "06",
        "jul": "07",
        "aug": "08",
        "sep": "09",
        "okt": "10",
        "nov": "11",
        "des": "12",
    }

    s = dato.astype(str).str.strip()

    # First try numeric dd.mm.yyyy (some exports may use this).
    parsed = pd.to_datetime(s, format="%d.%m.%Y", errors="coerce")
    if parsed.notna().any() and parsed.isna().sum() == 0:
        return parsed

    # Then try Norwegian month names: '21. des. 2022'
    pattern = re.compile(r"^(\d{1,2})\.\s*([A-Za-zÆØÅæøå]+)\.?\s*(\d{4})$")

    def _convert_one(value: str) -> str | None:
        match = pattern.match(value)
        if not match:
            return None
        day, month_name, year = match.groups()
        month_key = month_name.lower()[:3]
        month_num = month_map.get(month_key)
        if not month_num:
            return None
        return f"{year}-{month_num}-{int(day):02d}"

    iso = s.map(_convert_one)
    return pd.to_datetime(iso, errors="coerce")


def main() -> None:
    if not CORRELATION_CSV.exists():
        raise SystemExit(f"Missing file: {CORRELATION_CSV}")
    if not PLOWING_CSV.exists():
        raise SystemExit(f"Missing file: {PLOWING_CSV}")

    df_raw = _load_correlation_df()
    df_filtered, relevance_stats = _apply_event_relevance_filter(df_raw)
    dup = df_raw.duplicated(subset=["datetime", "scenario"], keep=False)
    dup_filtered = df_filtered.duplicated(subset=["datetime", "scenario"], keep=False)
    df = df_filtered.drop_duplicates(subset=["datetime", "scenario"]).copy()

    _print_header("Correlation dataset")
    print("rows (raw):", len(df_raw))
    if "event_relevant_for_thresholds" in df_raw.columns:
        print(
            "event_relevance filter:",
            f"excluded={relevance_stats['excluded_not_relevant']}",
            f"kept={relevance_stats['kept_rows']}",
        )
    print("dup rows on (datetime, scenario):", int(dup.sum()))
    if "event_relevant_for_thresholds" in df_raw.columns:
        print("dup rows on (datetime, scenario) after relevance filter:", int(dup_filtered.sum()))
    print("rows (deduped):", len(df))
    print("scenario counts:", df["scenario"].value_counts().to_dict())

    if len(df) and "datetime" in df.columns:
        print("period:", df["datetime"].min(), "→", df["datetime"].max())

    cols = [
        "gust_max",
        "wind_avg",
        "wind_max",
        "precip_total",
        "snow_depth",
        "snow_change",
        "air_temp_avg",
        "surface_temp_avg",
        "dew_point_avg",
    ]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing expected columns in correlation CSV: {missing}")

    q = df.groupby("scenario")[cols].quantile([0.5, 0.9]).unstack(level=1)

    sd = settings.snowdrift
    fs = settings.fresh_snow
    sl = settings.slaps

    _print_header("Config validation")

    snowdrift_gust_p50 = float(q.loc["SNØFOKK", ("gust_max", 0.5)])
    snowdrift_gust_p90 = float(q.loc["SNØFOKK", ("gust_max", 0.9)])
    print(
        "SNØFOKK gust p50/p90:",
        round(snowdrift_gust_p50, 2),
        "/",
        round(snowdrift_gust_p90, 2),
        "| wind_gust_critical:",
        sd.wind_gust_critical,
    )

    for sc in ["ANNET", "FRYSEFARE", "NYSNØ", "SLAPS"]:
        p90 = float(q.loc[sc, ("gust_max", 0.9)])
        print(
            f"{sc} gust p90:",
            round(p90, 2),
            "| wind_gust_critical:",
            sd.wind_gust_critical,
        )

    dp_p90 = float(q.loc["NYSNØ", ("dew_point_avg", 0.9)])
    print(
        "NYSNØ dew_point_avg p90:",
        round(dp_p90, 2),
        "| dew_point_max:",
        fs.dew_point_max,
    )

    st_p50 = float(q.loc["SLAPS", ("surface_temp_avg", 0.5)])
    dp_slaps_p50 = float(q.loc["SLAPS", ("dew_point_avg", 0.5)])
    print(
        "SLAPS surface_temp_avg p50:",
        round(st_p50, 2),
        "| slaps temp range:",
        (sl.temp_min, sl.temp_max),
    )
    print("SLAPS dew_point_avg p50:", round(dp_slaps_p50, 2))

    _print_header("Snowdrift threshold check (gust_max)")
    if "scenario" in df.columns and "gust_max" in df.columns:
        is_snowdrift = df["scenario"] == "SNØFOKK"

        def _rates(triggered: pd.Series) -> tuple[float, float, int, int]:
            tp = int((triggered & is_snowdrift).sum())
            fn = int((~triggered & is_snowdrift).sum())
            fp = int((triggered & ~is_snowdrift).sum())
            tn = int((~triggered & ~is_snowdrift).sum())

            tpr = tp / (tp + fn) if (tp + fn) else 0.0
            fpr = fp / (fp + tn) if (fp + tn) else 0.0
            return tpr, fpr, tp, fp

        # 1) Gust-only (shows why gust alone is too permissive)
        for label, thr in [
            ("warning", sd.wind_gust_warning),
            ("critical", sd.wind_gust_critical),
        ]:
            triggered = df["gust_max"] >= float(thr)
            tpr, fpr, tp, fp = _rates(triggered)
            print(
                f"{label} (gust-only): gust_max >= {thr}",
                f"| TPR {tpr:.2f} ({tp}/{int(is_snowdrift.sum())})",
                f"| FPR {fpr:.2f} ({fp}/{int((~is_snowdrift).sum())})",
            )

        # 2) Analyzer-like gust trigger with gates
        # NOTE: Loose-snow availability requires a 24h time series; the correlation CSV is event-level.
        required_cols = {"air_temp_avg", "snow_depth", "wind_avg"}
        if required_cols.issubset(df.columns):
            temp_gate = df["air_temp_avg"] <= float(sd.temperature_max)
            snow_gate = df["snow_depth"] >= float(sd.snow_depth_min_cm)

            # Per SnowdriftAnalyzer:
            # - warning gust uses wind_speed_gust_warning_gate
            # - critical gust uses wind_speed_warning gate
            wind_gate_warning = df["wind_avg"] >= float(sd.wind_speed_gust_warning_gate)
            wind_gate_critical = df["wind_avg"] >= float(sd.wind_speed_warning)

            # Optional proxy for "dry/loose" snow on event level.
            # This is NOT the same as the 24h loose-snow heuristic, but helps reduce wet-snow false positives.
            dew_point_gate = (
                (df["dew_point_avg"] <= float(settings.fresh_snow.dew_point_max))
                if "dew_point_avg" in df.columns
                else None
            )

            rules: list[tuple[str, pd.Series]] = []

            warning_rule = (
                (df["gust_max"] >= float(sd.wind_gust_warning))
                & wind_gate_warning
                & temp_gate
                & snow_gate
            )
            rules.append((
                f"warning (gated): gust>= {sd.wind_gust_warning}, wind_avg>= {sd.wind_speed_gust_warning_gate}, temp<= {sd.temperature_max}, snow>= {sd.snow_depth_min_cm}",
                warning_rule,
            ))

            warning_rule_no_wind_gate = (
                (df["gust_max"] >= float(sd.wind_gust_warning))
                & temp_gate
                & snow_gate
            )
            rules.append((
                f"warning (no wind gate): gust>= {sd.wind_gust_warning}, temp<= {sd.temperature_max}, snow>= {sd.snow_depth_min_cm}",
                warning_rule_no_wind_gate,
            ))

            critical_rule = (
                (df["gust_max"] >= float(sd.wind_gust_critical))
                & wind_gate_critical
                & temp_gate
                & snow_gate
            )
            rules.append((
                f"critical (gated): gust>= {sd.wind_gust_critical}, wind_avg>= {sd.wind_speed_warning}, temp<= {sd.temperature_max}, snow>= {sd.snow_depth_min_cm}",
                critical_rule,
            ))

            if dew_point_gate is not None:
                rules.append((
                    "warning (gated + dew_point proxy <= 0C)",
                    warning_rule & dew_point_gate,
                ))
                rules.append((
                    "warning (no wind gate + dew_point proxy <= 0C)",
                    warning_rule_no_wind_gate & dew_point_gate,
                ))
                rules.append((
                    "critical (gated + dew_point proxy <= 0C)",
                    critical_rule & dew_point_gate,
                ))

            for name, triggered in rules:
                tpr, fpr, tp, fp = _rates(triggered)
                print(
                    name,
                    f"| TPR {tpr:.2f} ({tp}/{int(is_snowdrift.sum())})",
                    f"| FPR {fpr:.2f} ({fp}/{int((~is_snowdrift).sum())})",
                )
    else:
        print("Missing required columns for snowdrift check")

    _print_header("Inspection-candidate heuristic")
    plow_events = _load_plow_events()

    # Parse date for weekday analysis (Norwegian month-name format is common here).
    plow_events["date"] = _parse_norwegian_dato_series(plow_events["Dato"])
    plow_events["weekday"] = plow_events["date"].dt.day_name()

    n_bad_dates = int(plow_events["date"].isna().sum())
    if n_bad_dates:
        raw = plow_events.loc[plow_events["date"].isna(), "Dato"].astype(str).str.strip()
        sample = raw.dropna().unique()[:5]
        print(f"NOTE: {n_bad_dates} rows had unparseable 'Dato' values. Sample:", list(sample))

    # Quantile-based thresholds so the heuristic stays stable as the dataset grows.
    q_dist = float(plow_events["distance_km"].quantile(0.10))
    q_dur = float(plow_events["duration_minutes"].quantile(0.10))
    plow_events["inspection_candidate"] = (
        (plow_events["distance_km"] <= q_dist) & (plow_events["duration_minutes"] <= q_dur)
    )

    n = len(plow_events)
    n_ins = int(plow_events["inspection_candidate"].sum())
    pct = (n_ins / n * 100.0) if n else 0.0

    print(
        "q10 thresholds:",
        "distance_km <=",
        round(q_dist, 2),
        "AND duration_minutes <=",
        round(q_dur, 1),
    )
    print("inspection candidates:", n_ins, f"({pct:.1f}%)")

    # Weekday signal: helps evaluate hypotheses like "tunbrøyting Fridays".
    weekday_stats = (
        plow_events.dropna(subset=["weekday"])
        .groupby("weekday")
        .agg(
            n=("weekday", "size"),
            distance_km_median=("distance_km", "median"),
            duration_min_median=("duration_minutes", "median"),
            inspection_candidates=("inspection_candidate", "sum"),
        )
        .sort_values("n", ascending=False)
    )

    _print_header("Weekday patterns (plowing report)")
    if len(weekday_stats):
        print(weekday_stats.round(2).to_string())
    else:
        print("No weekday data (date parse failed)")


if __name__ == "__main__":
    main()
