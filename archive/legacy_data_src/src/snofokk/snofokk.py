# pylint: disable=line-too-long

"""
Modul for håndtering av snødata og væranalyse.
Inneholder funksjoner for å hente data fra Frost API og analysere snødrift-risiko.
"""

# Standard biblioteker
import logging
from datetime import datetime
from typing import Any, TypeVar  # ruff: noqa: F401

# Tredjeparts biblioteker
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from pandas import DataFrame
from plotly.subplots import make_subplots

# Lokale imports
from .config import DEFAULT_PARAMS, FROST_CLIENT_ID
from .snow_constants import SnowDepthConfig, enforce_snow_processing, get_risk_level

# Logging oppsett
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

T = TypeVar("T")

def enable_detailed_logging():
    """Konfigurerer detaljert logging for applikasjonen"""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Opprett en filhåndterer
    file_handler = logging.FileHandler('snofokk.log')
    file_handler.setLevel(logging.INFO)

    # Opprett en konsolhåndterer
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Definer formatet
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Legg til håndtererne til loggeren
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
# Initialiser logger
logger = enable_detailed_logging()


@st.cache_data(ttl=3600)  # Cache data for 1 time
def fetch_frost_data(start_date="2023-11-01", end_date="2024-04-30"):
    """
    Henter utvidet værdatasett fra Frost API
    """
    elements = [
        "air_temperature",
        "surface_snow_thickness",
        "wind_speed",
        "wind_from_direction",
        "relative_humidity",
        "max(wind_speed_of_gust PT1H)",
        "max(wind_speed PT1H)",
        "min(air_temperature PT1H)",
        "max(air_temperature PT1H)",
        "sum(duration_of_precipitation PT1H)",
        "sum(precipitation_amount PT1H)",
        "dew_point_temperature",
        "mean(relative_humidity PT1H)",
        "mean(surface_air_pressure PT1H)",
        "mean(cloud_area_fraction PT1H)",
        "sum(duration_of_sunshine PT1H)",
        "mean(global_radiation PT1H)",
        "surface_temperature",
        "sum(duration_of_precipitation_as_snow PT1H)"
    ]

    parameters = {
        "sources": "SN46220",
        "referencetime": f"{start_date}/{end_date}",
        "elements": ",".join(elements),
        "timeresolutions": "PT1H",
    }

    try:
        logger.info(
            f"Starting fetch_frost_data with FROST_CLIENT_ID: {FROST_CLIENT_ID}"
        )

        endpoint = "https://frost.met.no/observations/v0.jsonld"
        logger.info(f"API request parameters: {parameters}")

        # Legg til Accept-header
        headers = {"Accept": "application/json"}

        # Gjør API-kallet med headers
        logger.info("Making API request...")
        r = requests.get(
            endpoint, parameters, auth=(FROST_CLIENT_ID, ""), headers=headers
        )

        logger.info(f"API response status code: {r.status_code}")
        if r.status_code != 200:
            logger.error(f"API error response: {r.text}")

        if r.status_code == 200:
            data = r.json()

            # Debug: Skriv ut første observasjon med alle elementer
            if data["data"]:
                first_obs = data["data"][0]
                logger.info("Første observasjon inneholder følgende elementer:")
                for obs in first_obs["observations"]:
                    logger.info(f"{obs['elementId']}: {obs['value']}")

            # Sjekk om vi har data
            if not data.get("data"):
                logger.error("Ingen data mottatt fra API")
                return None

            # Legg til debugging av rådata
            if data.get("data"):
                sample_data = data["data"][0]
                logger.info("Eksempel på rådata fra API:")
                logger.info(f"Tidspunkt: {sample_data['referenceTime']}")
                logger.info("Tilgjengelige målinger:")
                for obs in sample_data["observations"]:
                    logger.info(f"Element: {obs['elementId']}, Verdi: {obs['value']}")

            # Konverter data til DataFrame
            df = pd.DataFrame(
                [
                    {
                        "timestamp": datetime.fromisoformat(
                            item["referenceTime"].rstrip("Z")
                        ),
                        "air_temperature": next(
                            (
                                obs["value"]
                                for obs in item["observations"]
                                if obs["elementId"] == "air_temperature"
                            ),
                            np.nan,
                        ),
                        "surface_snow_thickness": next(
                            (
                                obs["value"]
                                for obs in item["observations"]
                                if obs["elementId"] == "surface_snow_thickness"
                            ),
                            np.nan,
                        ),
                        "wind_speed": next(
                            (
                                obs["value"]
                                for obs in item["observations"]
                                if obs["elementId"] == "wind_speed"
                            ),
                            np.nan,
                        ),
                        "wind_from_direction": next(
                            (
                                obs["value"]
                                for obs in item["observations"]
                                if obs["elementId"] == "wind_from_direction"
                            ),
                            np.nan,
                        ),
                        "relative_humidity": next(
                            (
                                obs["value"]
                                for obs in item["observations"]
                                if obs["elementId"] == "relative_humidity"
                            ),
                            np.nan,
                        ),
                        "max(wind_speed_of_gust PT1H)": next(
                            (
                                obs["value"]
                                for obs in item["observations"]
                                if obs["elementId"] == "max(wind_speed_of_gust PT1H)"
                            ),
                            np.nan,
                        ),
                        "max(wind_speed PT1H)": next(
                            (
                                obs["value"]
                                for obs in item["observations"]
                                if obs["elementId"] == "max(wind_speed PT1H)"
                            ),
                            np.nan,
                        ),
                        "min(air_temperature PT1H)": next(
                            (
                                obs["value"]
                                for obs in item["observations"]
                                if obs["elementId"] == "min(air_temperature PT1H)"
                            ),
                            np.nan,
                        ),
                        "max(air_temperature PT1H)": next(
                            (
                                obs["value"]
                                for obs in item["observations"]
                                if obs["elementId"] == "max(air_temperature PT1H)"
                            ),
                            np.nan,
                        ),
                        "sum(duration_of_precipitation PT1H)": next(
                            (
                                obs["value"]
                                for obs in item["observations"]
                                if obs["elementId"]
                                == "sum(duration_of_precipitation PT1H)"
                            ),
                            np.nan,
                        ),
                        "sum(precipitation_amount PT1H)": next(
                            (
                                obs["value"]
                                for obs in item["observations"]
                                if obs["elementId"] == "sum(precipitation_amount PT1H)"
                            ),
                            np.nan,
                        ),
                        "dew_point_temperature": next(
                            (
                                obs["value"]
                                for obs in item["observations"]
                                if obs["elementId"] == "dew_point_temperature"
                            ),
                            np.nan,
                        ),
                    }
                    for item in data["data"]
                ]
            )

            # Sett timestamp som index
            df.set_index("timestamp", inplace=True)

            # Legg til debugging av snødybdedata
            logger.info("Snødybdedata analyse:")
            logger.info(
                f"Unike verdier i surface_snow_thickness: {df['surface_snow_thickness'].unique()}"
            )
            logger.info(
                f"Antall ikke-null verdier: {df['surface_snow_thickness'].count()}"
            )
            logger.info("Eksempel på første 5 snødybdeverdier:")
            logger.info(df["surface_snow_thickness"].head())

            # Konverter -1 verdier til NaN for snødybde
            df["surface_snow_thickness"] = df["surface_snow_thickness"].replace(
                -1, np.nan
            )

            return df

        else:
            logger.error("Error %s: %s", r.status_code, r.text)
            return None

    except Exception as e:
        logger.error("Feil i fetch_frost_data: %s", str(e))
        return None


def identify_risk_periods(df: pd.DataFrame, min_duration: int = 3) -> pd.DataFrame:
    """
    Identifiserer sammenhengende perioder med forhøyet risiko.

    Args:
        df: DataFrame med risikodata og værdata
        min_duration: Minimum varighet for en periode i timer

    Returns:
        DataFrame med identifiserte risikoperioder og deres egenskaper
    """
    try:
        if df.empty or "period_id" not in df.columns:
            logger.warning("Tomt datasett eller manglende period_id")
            return pd.DataFrame()

        periods = []
        unique_periods = df["period_id"].dropna().unique()

        for period_id in unique_periods:
            period_data = df[df["period_id"] == period_id].copy()

            if len(period_data) >= min_duration:
                period_info = {
                    "start_time": period_data.index[0],
                    "end_time": period_data.index[-1],
                    "duration": len(period_data),
                    "max_risk_score": period_data["risk_score"].max(),
                    "avg_risk_score": period_data["risk_score"].mean(),
                    "period_id": period_id
                }

                # Utvidet vindanalyse
                if "wind_speed" in period_data.columns:
                    wind_stats = {
                        "sustained_wind_max": period_data["wind_speed"].max(),
                        "sustained_wind_avg": period_data["wind_speed"].mean(),
                        "wind_stability": period_data["wind_speed"].std(),
                        "strong_wind_hours": len(period_data[period_data["wind_speed"] > 10.0]),
                    }

                    # Beregn vindstøt-faktor
                    if "max(wind_speed_of_gust PT1H)" in period_data.columns:
                        gust_factor = (
                            period_data["max(wind_speed_of_gust PT1H)"] /
                            period_data["wind_speed"]
                        ).mean()
                        wind_stats["gust_factor"] = gust_factor

                    # Vindretningsanalyse
                    if "wind_from_direction" in period_data.columns:
                        dirs = period_data["wind_from_direction"].dropna()
                        if not dirs.empty:
                            # Beregn vindretningsstabilitet
                            dir_changes = np.abs(dirs.diff()).fillna(0)
                            wind_stats.update({
                                "dir_change_max": dir_changes.max(),
                                "dir_change_avg": dir_changes.mean(),
                                "dir_stability": "stabil" if dir_changes.mean() < 30
                                              else "moderat" if dir_changes.mean() < 60
                                              else "ustabil"
                            })

                    period_info.update(wind_stats)

                # Temperaturanalyse
                if "air_temperature" in period_data.columns:
                    period_info.update({
                        "min_temp": period_data["air_temperature"].min(),
                        "avg_temp": period_data["air_temperature"].mean(),
                        "cold_hours": len(period_data[period_data["air_temperature"] < 0])
                    })

                # Snøanalyse
                if "snow_depth_change" in period_data.columns:
                    abs_change = period_data["snow_depth_change"].abs()
                    period_info.update({
                        "max_snow_change": abs_change.max(),
                        "total_snow_change": abs_change.sum(),
                        "significant_changes": len(period_data[abs_change > 0.5])
                    })

                # Nedbørsanalyse
                if "sum(precipitation_amount PT1H)" in period_data.columns:
                    period_info["total_precip"] = period_data["sum(precipitation_amount PT1H)"].sum()
                    period_info["precip_hours"] = len(period_data[period_data["sum(precipitation_amount PT1H)"] > 0])

                periods.append(period_info)

        return pd.DataFrame(periods)

    except Exception as e:
        logger.error(f"Feil i identify_risk_periods: {str(e)}", exc_info=True)
        return pd.DataFrame()


@enforce_snow_processing
def calculate_snow_drift_risk(
    df: pd.DataFrame, params: dict
) -> tuple[pd.DataFrame, pd.DataFrame]:
    try:
        df = df.copy()

        # Innledende analyse
        snow_df = df["surface_snow_thickness"]
        logger.info("=== Snødybdeanalyse ===")
        logger.info(f"Målinger: {len(snow_df)} totalt, {snow_df.count()} gyldige")
        logger.info(
            f"Tidsperiode: {snow_df.index[0].strftime('%Y-%m-%d')} til {snow_df.index[-1].strftime('%Y-%m-%d')}"
        )
        logger.info(f"Første gyldige måling: {snow_df.dropna().iloc[0]:.1f} cm")
        logger.info(f"Siste gyldige måling: {snow_df.dropna().iloc[-1]:.1f} cm")

        # Prosesser snødybdedata
        df["surface_snow_thickness"] = SnowDepthConfig.process_snow_depth(snow_df)

        # Detaljert statistikk etter prosessering
        processed_snow = df["surface_snow_thickness"]
        logger.info("=== Etter prosessering ===")
        logger.info(
            f"Gyldige målinger: {processed_snow.count()} ({processed_snow.count()/len(processed_snow)*100:.1f}%)"
        )
        logger.info(
            f"Snødybdeområde: {processed_snow.min():.1f} - {processed_snow.max():.1f} cm"
        )
        logger.info("Statistikk:")
        logger.info(f"- Gjennomsnitt: {processed_snow.mean():.1f} cm")
        logger.info(f"- Median: {processed_snow.median():.1f} cm")
        logger.info(f"- Standardavvik: {processed_snow.std():.1f} cm")
        logger.info(f"- 25-percentil: {processed_snow.quantile(0.25):.1f} cm")
        logger.info(f"- 75-percentil: {processed_snow.quantile(0.75):.1f} cm")

        # Beregn snødybdeendringer med forbedret metode
        df["snow_depth_change"] = (
            df["surface_snow_thickness"]
            .diff()
            .rolling(
                window=SnowDepthConfig.WINDOW_SIZE,
                min_periods=SnowDepthConfig.MIN_PERIODS,
            )
            .mean()
            .clip(SnowDepthConfig.MIN_CHANGE, SnowDepthConfig.MAX_CHANGE)
        )

        # Forbedret vindanalyse
        df["sustained_wind"] = (
            df["wind_speed"]
            .rolling(window=3, min_periods=1)
            .mean()
            .ffill(limit=2)
        )

        # Beregn vindstabilitet
        df["wind_stability"] = (
            df["wind_speed"].rolling(window=6, min_periods=3).std().fillna(0)
        )

        # Forbedret vindretningsanalyse
        df["wind_dir_change"] = df["wind_from_direction"].diff().abs()
        df.loc[df["wind_dir_change"] > 180, "wind_dir_change"] = (
            360 - df.loc[df["wind_dir_change"] > 180, "wind_dir_change"]
        )

        # Beregn risikoscore med forbedret logikk
        def calculate_risk_score(row):
            score = 0

            # Vindrisiko med stabilitetsvurdering
            if row["wind_speed"] >= params["wind_strong"]:
                wind_factor = 40
                # Øk risiko ved ustabil vind
                if row["wind_stability"] > 3:
                    wind_factor *= 1.2
                score += wind_factor * params["wind_weight"]
            elif row["wind_speed"] >= params["wind_moderate"]:
                score += 20 * params["wind_weight"]

            # Vindkast-risiko
            if (
                "max(wind_speed_of_gust PT1H)" in row
                and row["max(wind_speed_of_gust PT1H)"] >= params["wind_gust"]
            ):
                score += 10 * params["wind_weight"]

            # Vindretningsrisiko med forbedret vurdering
            if row["wind_dir_change"] >= params["wind_dir_change"]:
                dir_factor = min(
                    20, row["wind_dir_change"] / 9
                )  # Maks 20 poeng ved 180° endring
                score += dir_factor * params["wind_weight"]

            # Temperaturrisiko med gradert vurdering
            if row["air_temperature"] <= params["temp_cold"]:
                score += 20 * params["temp_weight"]
            elif row["air_temperature"] <= params["temp_cool"]:
                temp_factor = (params["temp_cool"] - row["air_temperature"]) / (
                    params["temp_cool"] - params["temp_cold"]
                )
                score += 10 * temp_factor * params["temp_weight"]

            # Snrisiko med forbedret vurdering
            snow_change = abs(row["snow_depth_change"])
            if snow_change >= params["snow_high"]:
                score += 40 * params["snow_weight"]
            elif snow_change >= params["snow_moderate"]:
                snow_factor = (snow_change - params["snow_moderate"]) / (
                    params["snow_high"] - params["snow_moderate"]
                )
                score += (20 + 20 * snow_factor) * params["snow_weight"]
            elif snow_change >= params["snow_low"]:
                score += 10 * params["snow_weight"]

            return min(100, score) / 100  # Normaliser til 0-1

        # Beregn total risiko
        df["risk_score"] = df.apply(calculate_risk_score, axis=1)
        df["risk_level"] = pd.cut(
            df["risk_score"],
            bins=[-np.inf, 0.3, 0.5, 0.7, np.inf],
            labels=["Lav", "Moderat", "Høy", "Kritisk"],
        )

        # Identifiser perioder
        df["is_risk"] = df["risk_score"] > params.get("risk_threshold", 0.3)
        df["period_start"] = df["is_risk"].ne(df["is_risk"].shift()).cumsum()
        df["period_id"] = np.where(df["is_risk"], df["period_start"], np.nan)
        df = df.drop(["is_risk", "period_start"], axis=1)

        # Analyser perioder
        periods_df = identify_risk_periods(
            df, min_duration=params.get("min_duration", 3)
        )

        return df, periods_df

    except Exception as e:
        logger.error(f"Feil i calculate_snow_drift_risk: {str(e)}", exc_info=True)
        raise


def merge_nearby_periods(periods_df: pd.DataFrame, max_gap: int = 2) -> pd.DataFrame:
    """
    Slår sammen nærliggende kritiske perioder som er innenfor max_gap timer fra hverandre.

    Args:
        periods_df: DataFrame med kritiske perioder
        max_gap: Maksimal tidsavstand i timer mellom perioder som skal slås sammen

    Returns:
        DataFrame med sammenslåtte perioder
    """
    if periods_df.empty:
        return periods_df

    try:
        # Sorter periodene etter starttid
        sorted_periods = periods_df.sort_values("start_time").copy()
        merged_periods = []
        current_period = sorted_periods.iloc[0].to_dict()

        for _, period in sorted_periods.iloc[1:].iterrows():
            time_gap = (
                period["start_time"] - current_period["end_time"]
            ).total_seconds() / 3600

            if time_gap <= max_gap:
                # Slå sammen periodene
                current_period["end_time"] = period["end_time"]
                current_period["duration"] = (
                    current_period["end_time"] - current_period["start_time"]
                ).total_seconds() / 3600
                current_period["max_risk_score"] = max(
                    current_period["max_risk_score"],
                    period["max_risk_score"]
                )
                # Oppdater andre statistikker
                for key in ["max_wind", "min_temp", "max_snow_change"]:
                    if key in current_period and key in period:
                        current_period[key] = (
                            max(current_period[key], period[key])
                            if key != "min_temp"
                            else min(current_period[key], period[key])
                        )
            else:
                # Lagre nåværende periode og start en ny
                merged_periods.append(current_period)
                current_period = period.to_dict()

        # Legg til siste periode
        merged_periods.append(current_period)

        # Konverter tilbake til DataFrame og oppdater periode-IDer
        merged_df = pd.DataFrame(merged_periods)
        merged_df["period_id"] = range(len(merged_df))

        # Beregn nye statistikker for de sammenslåtte periodene
        if not merged_df.empty:
            # Beregn intensitet basert på risiko og varighet
            merged_df["intensity"] = merged_df["max_risk_score"] * np.log1p(
                merged_df["duration"]
            )

            # Beregn alvorlighetsgrad basert på flere faktorer
            merged_df["severity_score"] = (
                merged_df["intensity"] * 0.4  # Vekt for intensitet
                + (merged_df["max_wind"] / merged_df["max_wind"].max())
                * 0.3  # Vekt for vind
                + (np.abs(merged_df["min_temp"]) / np.abs(merged_df["min_temp"].min()))
                * 0.3  # Vekt for temperatur
            )

            # Kategoriser alvorlighetsgrad
            merged_df["severity"] = pd.qcut(
                merged_df["severity_score"],
                q=3,
                labels=["Moderat", "Alvorlig", "Ekstrem"],
            )

        logger.info(
            f"Sammenslåing fullført: {len(periods_df)} perioder redusert til {len(merged_df)}"
        )
        return merged_df

    except Exception as e:
        logger.error(f"Feil i merge_critical_periods: {str(e)}", exc_info=True)
        return periods_df


def create_rolling_stats(
    df: DataFrame, columns: list[str], windows: list[int], stats: list[str]
) -> DataFrame:
    """
    Beregner rullende statistikk for spesifiserte kolonner

    Args:
        df: Input DataFrame
        columns: Liste med kolonnenavn å beregne statistikk for
        windows: Liste med vindus-størrelser (i timer)
        stats: Liste med statistiske funksjoner ('mean', 'std', etc.)

    Returns:
        DataFrame med beregnede statistikker
    """
    result_df = df.copy()

    try:
        for col in columns:
            if col not in df.columns:
                continue

            for window in windows:
                rolling = df[col].rolling(window=window, min_periods=1)

                for stat in stats:
                    if hasattr(rolling, stat):
                        col_name = f"{col}_{window}h_{stat}"
                        result_df[col_name] = getattr(rolling, stat)()

        return result_df

    except Exception as e:
        logging.error(f"Feil ved beregning av rullende statistikk: {str(e)}")
        return df


def analyze_wind_directions(df: DataFrame) -> dict[str, Any]:
    try:
        logger.info("Starter vindretningsanalyse")
        logger.info(f"Input data shape: {df.shape}")

        if "wind_direction" not in df.columns:
            logger.warning("Vindretning mangler i datasettet")
            return None

        # Debug vindretningsdata
        logger.info("Vindretningsstatistikk:")
        logger.info(f"Null-verdier: {df['wind_direction'].isnull().sum()}")
        logger.info(f"Unike verdier: {df['wind_direction'].nunique()}")
        logger.info(
            f"Min/Maks: {df['wind_direction'].min():.1f}/{df['wind_direction'].max():.1f}"
        )

        # Lag en sikker kopi av DataFrame
        analysis_df = df.copy()

        # Definer hovedretninger (N, NØ, Ø, osv.)
        directions = {
            "N": (337.5, 22.5),
            "NØ": (22.5, 67.5),
            "Ø": (67.5, 112.5),
            "SØ": (112.5, 157.5),
            "S": (157.5, 202.5),
            "SV": (202.5, 247.5),
            "V": (247.5, 292.5),
            "NV": (292.5, 337.5),
        }

        # Kategoriser hver vindretning
        def categorize_direction(angle):
            angle = angle % 360
            for name, (start, end) in directions.items():
                if start <= angle < end or (
                    name == "N" and (angle >= 337.5 or angle < 22.5)
                ):
                    return name
            return "N"  # Fallback

        # Bruk loc for å unngå SettingWithCopyWarning
        analysis_df.loc[:, "direction_category"] = analysis_df["wind_direction"].apply(
            categorize_direction
        )

        # Analyser fordeling av vindretninger
        direction_counts = analysis_df["direction_category"].value_counts()
        total_periods = len(analysis_df)

        # Beregn gjennomsnittlig risikoscore for hver retning
        direction_risk = analysis_df.groupby("direction_category")[
            "max_risk_score"
        ].mean()

        # Beregn gjennomsnittlig vindstyrke for hver retning
        direction_wind = analysis_df.groupby("direction_category")["max_wind"].mean()

        # Finn dominerende retninger (over 15% av tilfellene eller høy risikoscore)
        significant_directions = []
        for direction in direction_counts.index:
            percentage = (direction_counts[direction] / total_periods) * 100
            avg_risk = direction_risk[direction]
            avg_wind = direction_wind[direction]

            if percentage > 15 or avg_risk > 70:
                significant_directions.append(
                    {
                        "direction": direction,
                        "percentage": percentage,
                        "avg_risk": avg_risk,
                        "avg_wind": avg_wind,
                    }
                )

        return {
            "counts": direction_counts.to_dict(),
            "risk_scores": direction_risk.to_dict(),
            "wind_speeds": direction_wind.to_dict(),
            "significant": significant_directions,
        }

    except Exception as e:
        logger.error(f"Feil i vindretningsanalyse: {str(e)}", exc_info=True)
        return None


def analyze_settings(
    df: pd.DataFrame, critical_periods: pd.DataFrame
) -> dict[str, Any]:
    """
    Analyserer effektiviteten av gjeldende parameterinnstillinger.

    Args:
        df: DataFrame med værdata og risikoberegninger
        critical_periods: DataFrame med kritiske perioder

    Returns:
        Dict med analyseresultater
    """
    try:
        analysis = {}

        # Grunnleggende statistikk
        analysis["total_hours"] = len(df)
        analysis["critical_periods"] = len(critical_periods)

        if not df.empty:
            # Værstatistikk
            for col, _name in {
                "wind_speed": "Vindstyrke",
                "air_temperature": "Temperatur",
                "surface_snow_thickness": "Snødybde",
            }.items():
                if col in df.columns:
                    analysis[f"{col}_stats"] = {
                        "min": df[col].min(),
                        "max": df[col].max(),
                        "mean": df[col].mean(),
                        "std": df[col].std(),
                    }

        if not critical_periods.empty:
            # Analyser kritiske perioder
            analysis["critical_stats"] = {
                "total_duration": critical_periods["duration"].sum(),
                "avg_duration": critical_periods["duration"].mean(),
                "max_risk": critical_periods["max_risk_score"].max(),
                "avg_risk": critical_periods["max_risk_score"].mean(),
            }

            # Legg til severity-statistikk hvis tilgjengelig
            if "severity" in critical_periods.columns:
                severity_counts = critical_periods["severity"].value_counts()
                analysis["severity_distribution"] = severity_counts.to_dict()

        # Parametereffektivitet
        current_params = st.session_state.get("params", DEFAULT_PARAMS.copy())
        analysis["parameter_usage"] = {}

        for param_name, param_value in current_params.items():
            if param_name in DEFAULT_PARAMS:
                default_value = DEFAULT_PARAMS[param_name]
                diff_from_default = abs(param_value - default_value)
                analysis["parameter_usage"][param_name] = {
                    "current": param_value,
                    "default": default_value,
                    "diff": diff_from_default,
                }

        return analysis

    except Exception as e:
        logger.error(f"Feil i analyse av innstillinger: {str(e)}", exc_info=True)
        return {}


def calculate_wind_direction_change(dir1: float, dir2: float) -> float:
    """
    Beregner minste vinkelendring mellom to vindretninger

    Args:
        dir1, dir2: Vindretninger i grader (0-360)
    Returns:
        Minste vinkelendring i grader (0-180)
    """
    diff = abs(dir1 - dir2)
    return min(diff, 360 - diff)


def preprocess_critical_periods(df: DataFrame) -> DataFrame:
    """
    Forbehandler kritiske perioder med forbedret vindretningsanalyse
    """
    if not isinstance(df, pd.DataFrame):
        logging.error(f"Ugyldig input type i preprocess_critical_periods: {type(df)}")
        return pd.DataFrame()

    if df.empty:
        logging.warning("Tom DataFrame mottatt i preprocess_critical_periods")
        return df

    try:
        # Definer alle operasjoner som skal utføres
        operations = {
            "wind_dir_change": {
                "operation": "calculate",
                "value": lambda x: x["wind_direction"].diff(),
                "fillna": 0.0,
            },
            "max_dir_change": {
                "operation": "rolling",
                "value": "wind_dir_change",
                "args": {"window": 3, "center": True, "min_periods": 1},
                "aggregation": "max",
                "fillna": 0.0,
            },
            "wind_dir_stability": {
                "operation": "rolling",
                "value": "wind_dir_change",
                "args": {"window": 3, "center": True, "min_periods": 1},
                "aggregation": "std",
                "fillna": 0.0,
            },
            "significant_dir_change": {
                "operation": "calculate",
                "value": lambda x: x["wind_dir_change"] > 45,
            },
            "wind_pattern": {
                "operation": "calculate",
                "value": lambda x: x.apply(
                    lambda row: (
                        "ustabil"
                        if row["wind_dir_stability"] > 30
                        else (
                            "skiftende"
                            if row["wind_dir_change"] > 45
                            else (
                                "stabil"
                                if row["wind_dir_stability"] < 10
                                else "moderat"
                            )
                        )
                    ),
                    axis=1,
                ),
            },
        }

        # Utfør alle operasjoner sikkert
        result_df = safe_dataframe_operations(df, operations)

        # Legg til statistiske indikatorer hvis det er mer enn én rad
        if len(result_df) > 1:
            additional_ops = {
                "direction_trend": {
                    "operation": "rolling",
                    "value": "wind_direction",
                    "args": {"window": 3, "min_periods": 1},
                    "aggregation": "mean",
                },
                "significant_changes_pct": {
                    "operation": "calculate",
                    "value": lambda x: (
                        x["significant_dir_change"].sum() / len(x) * 100
                    ),
                },
            }
            result_df = safe_dataframe_operations(result_df, additional_ops)

        return result_df

    except Exception as e:
        logging.error(f"Feil i vindretningsanalyse: {str(e)}", exc_info=True)
        return df


def safe_dataframe_operations(df: pd.DataFrame, operations: dict) -> pd.DataFrame:
    """
    Utfører sikre operasjoner på DataFrame

    Args:
        df: Input DataFrame
        operations: Dictionary med operasjoner som skal utføres
    Returns:
        Prosessert DataFrame
    """
    result_df = df.copy()
    try:
        for op_name, op_config in operations.items():
            if op_config["operation"] == "calculate":
                result_df[op_name] = op_config["value"](result_df)
            elif op_config["operation"] == "rolling":
                series = result_df[op_config["value"]]
                rolling = series.rolling(**op_config["args"])
                result_df[op_name] = getattr(rolling, op_config["aggregation"])()

            if "fillna" in op_config:
                result_df[op_name] = result_df[op_name].fillna(op_config["fillna"])

        return result_df
    except Exception as e:
        logger.error("Feil i safe_dataframe_operations: %s", str(e))
        return df


def plot_risk_analysis(df: pd.DataFrame) -> go.Figure:
    """
    Lager interaktiv visualisering av risikoanalysen med forbedret layout og styling
    """
    fig = make_subplots(
        rows=5,
        cols=1,
        subplot_titles=(
            "Risikoscore og Nivå",
            "Vind og Vindkast",
            "Temperatur",
            "Snødybde og Endring",
            "Nedbør",
        ),
        vertical_spacing=0.08,
        row_heights=[0.25, 0.2, 0.2, 0.2, 0.15],  # Justerte høyder
    )

    # Risikoscore med forbedret styling
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["risk_score"],
            name="Risikoscore",
            line={"color": "red", "width": 2},
            fill="tozeroy",
            fillcolor="rgba(255,0,0,0.1)",
        ),
        row=1,
        col=1,
    )

    # Legg til risiko-nivåer som fargede områder
    risk_colors = {
        "Lav": "rgba(0,255,0,0.1)",
        "Moderat": "rgba(255,255,0,0.1)",
        "Høy": "rgba(255,165,0,0.1)",
        "Kritisk": "rgba(255,0,0,0.1)",
    }

    for level, color in risk_colors.items():
        mask = df["risk_level"] == level
        if mask.any():
            fig.add_trace(
                go.Scatter(
                    x=df[mask].index,
                    y=df[mask]["risk_score"],
                    name=f"{level} risiko",
                    fill="tozeroy",
                    fillcolor=color,
                    line={"width": 0},
                    showlegend=True,
                ),
                row=1,
                col=1,
            )

    # Vind med forbedret styling
    if "sustained_wind" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["sustained_wind"],
                name="Vedvarende vind",
                line={"color": "blue", "width": 2},
            ),
            row=2,
            col=1,
        )

    if "max(wind_speed_of_gust PT1H)" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["max(wind_speed_of_gust PT1H)"],
                name="Vindkast",
                line={"color": "lightblue", "width": 1, "dash": "dash"},
            ),
            row=2,
            col=1,
        )

    # Temperatur med gradient
    if "air_temperature" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["air_temperature"],
                name="Temperatur",
                line={"color": "green", "width": 2},
                fill="tozeroy",
                fillcolor="rgba(0,255,0,0.1)",
            ),
            row=3,
            col=1,
        )

    # Snødybde og endring med forbedret visning
    if "surface_snow_thickness" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["surface_snow_thickness"],
                name="Snødybde",
                line={"color": "purple", "width": 2},
                fill="tozeroy",
                fillcolor="rgba(128,0,128,0.1)",
            ),
            row=4,
            col=1,
        )

    if "snow_depth_change" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["snow_depth_change"],
                name="Endring i snødybde",
                line={"color": "magenta", "width": 1, "dash": "dot"},
            ),
            row=4,
            col=1,
        )

    # Nedbør som stolpediagram med gradient
    if "sum(duration_of_precipitation PT1H)" in df.columns:
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["sum(duration_of_precipitation PT1H)"],
                name="Nedbørsvarighet",
                marker_color="rgba(0,191,255,0.6)",
                marker_line_color="rgb(0,191,255)",
                marker_line_width=1,
            ),
            row=5,
            col=1,
        )

    # Oppdater layout med forbedret styling
    fig.update_layout(
        title={
            "text": "Snøfokk-risikoanalyse",
            "y": 0.95,
            "x": 0.5,
            "xanchor": "center",
            "yanchor": "top",
            "font": {"size": 24},
        },
        showlegend=True,
        height=1200,
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )

    # Legg til rutenett og forbedrede aksetitler
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.2)")
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.2)")

    # Spesifikke y-akse titler med forbedret styling
    fig.update_yaxes(title_text="Score", title_font={"size": 14}, row=1, col=1)
    fig.update_yaxes(title_text="m/s", title_font={"size": 14}, row=2, col=1)
    fig.update_yaxes(title_text="°C", title_font={"size": 14}, row=3, col=1)
    fig.update_yaxes(title_text="cm", title_font={"size": 14}, row=4, col=1)
    fig.update_yaxes(title_text="min", title_font={"size": 14}, row=5, col=1)

    return fig


def plot_critical_periods(df: pd.DataFrame, periods_df: pd.DataFrame) -> go.Figure:
    """
    Lager en detaljert visualisering av kritiske snøfokkperioder

    Args:
        df: DataFrame med værdata og risikoberegninger
        periods_df: DataFrame med identifiserte perioder
    """
    try:
        # Finn kritiske perioder
        critical_periods = periods_df[periods_df["risk_level"] == "Kritisk"].copy()

        if critical_periods.empty:
            logger.warning("Ingen kritiske perioder funnet")
            return None

        logger.debug(f"Fant {len(critical_periods)} kritiske perioder")

        # Opprett subplots med spesifikke høyder
        fig = make_subplots(
            rows=4,
            cols=1,
            subplot_titles=(
                "Vindforhold under kritiske perioder",
                "Temperatur under kritiske perioder",
                "Snødybde og endring under kritiske perioder",
                "Oversikt over kritiske perioder",
            ),
            vertical_spacing=0.1,
            row_heights=[0.25, 0.25, 0.25, 0.25],
        )

        # Legg til vertikale markeringer FØRST
        for _, period in critical_periods.iterrows():
            logger.debug(
                f"Legger til vertikal markering for periode {period['period_id']}: "
                f"{period['start_time']} til {period['end_time']}"
            )

            for row in range(1, 5):
                fig.add_vrect(
                    x0=period["start_time"],
                    x1=period["end_time"],
                    fillcolor="rgba(255, 0, 0, 0.1)",
                    layer="below",  # Sikrer at markeringen er under dataene
                    line_width=0,
                    row=row,
                    col=1,
                    annotation_text=f"Periode {int(period['period_id'])}",
                    annotation_position="top left",
                )

        # Vindforhold
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["wind_speed"],
                name="Vindstyrke",
                line={"color": "blue", "width": 2},
            ),
            row=1,
            col=1,
        )

        if "max(wind_speed_of_gust PT1H)" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["max(wind_speed_of_gust PT1H)"],
                    name="Vindkast",
                    line={"color": "lightblue", "width": 1, "dash": "dash"},
                ),
                row=1,
                col=1,
            )

        # Temperatur med frysepunkt-linje
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["air_temperature"],
                name="Temperatur",
                line={"color": "green", "width": 2},
            ),
            row=2,
            col=1,
        )

        fig.add_hline(
            y=0,
            line_dash="dash",
            line_color="gray",
            annotation_text="Frysepunkt",
            row=2,
            col=1,
        )

        # Snødybde og endring
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["surface_snow_thickness"],
                name="Snødybde",
                line={"color": "purple", "width": 2},
            ),
            row=3,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["snow_depth_change"],
                name="Endring i snødybde",
                line={"color": "magenta", "width": 1, "dash": "dot"},
            ),
            row=3,
            col=1,
        )

        # Kritiske perioder som scatter plot med ulike farger
        colors = px.colors.qualitative.Set3
        for i, period in critical_periods.iterrows():
            period_data = df[period["start_time"] : period["end_time"]]
            fig.add_trace(
                go.Scatter(
                    x=period_data.index,
                    y=period_data["risk_score"],
                    name=f'Periode {int(period["period_id"])}',
                    mode="lines+markers",
                    line={"color": colors[i % len(colors)], "width": 3},
                    marker={"size": 8},
                ),
                row=4,
                col=1,
            )

        # Oppdater layout
        fig.update_layout(
            height=1000,
            showlegend=True,
            plot_bgcolor="white",
            paper_bgcolor="white",
            title={
                "text": "Detaljert analyse av kritiske perioder",
                "y": 0.95,
                "x": 0.5,
                "xanchor": "center",
                "yanchor": "top",
                "font": {"size": 20},
            },
            legend={
                "orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1
            },
        )

        # Legg til rutenett og forbedrede aksetitler
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.2)")
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.2)")

        # Y-akse titler
        fig.update_yaxes(title_text="m/s", title_font={"size": 12}, row=1, col=1)
        fig.update_yaxes(title_text="°C", title_font={"size": 12}, row=2, col=1)
        fig.update_yaxes(title_text="cm", title_font={"size": 12}, row=3, col=1)
        fig.update_yaxes(title_text="Score", title_font={"size": 12}, row=4, col=1)

        logger.debug("Ferdig med å legge til alle spor og markeringer")
        logger.debug(f"Antall spor i figuren: {len(fig.data)}")

        return fig

    except Exception as e:
        logger.error(f"Feil i plot_critical_periods: {str(e)}", exc_info=True)
        raise


def merge_critical_periods(periods_df: pd.DataFrame, max_gap: int = 2) -> pd.DataFrame:
    """
    Slår sammen nærliggende kritiske perioder til mer meningsfylte varsler.

    Args:
        periods_df: DataFrame med kritiske perioder
        max_gap: Maksimalt antall timer mellom perioder som skal slås sammen

    Returns:
        DataFrame med sammenslåtte perioder
    """
    if periods_df.empty:
        return periods_df

    try:
        # Sorter perioder etter starttid
        sorted_periods = periods_df.sort_values("start_time").copy()
        merged_periods = []
        current_period = sorted_periods.iloc[0].to_dict()

        for _, next_period in sorted_periods.iloc[1:].iterrows():
            # Beregn tidsforskjell mellom periodene
            time_diff = (
                next_period["start_time"] - current_period["end_time"]
            ).total_seconds() / 3600

            # Hvis periodene er nær nok, slå dem sammen
            if time_diff <= max_gap:
                # Oppdater slutttid og varighet
                current_period["end_time"] = max(
                    current_period["end_time"], next_period["end_time"]
                )
                current_period["duration"] = (
                    current_period["end_time"] - current_period["start_time"]
                ).total_seconds() / 3600

                # Oppdater maksimumsverdier
                current_period["max_risk_score"] = max(
                    current_period["max_risk_score"], next_period["max_risk_score"]
                )

                # Oppdater gjennomsnittsverdier med vekting basert på varighet
                for field in ["avg_risk_score", "avg_wind", "avg_temp"]:
                    if field in current_period and field in next_period:
                        dur1 = current_period["duration"]
                        dur2 = next_period["duration"]
                        total_dur = dur1 + dur2
                        current_period[field] = (
                            current_period[field] * dur1 + next_period[field] * dur2
                        ) / total_dur

                # Oppdater ekstremer
                for field, func in {
                    "max_wind": max,
                    "max_gust": max,
                    "min_temp": min,
                    "max_snow_change": max,
                    "wind_direction": lambda x, y: x,  # Behold original retning
                }.items():
                    if field in current_period and field in next_period:
                        current_period[field] = func(
                            current_period[field], next_period[field]
                        )

                # Oppdater akkumulerte verdier
                for field in [
                    "total_precip",
                    "significant_changes",
                    "wind_hours_above_threshold",
                    "cold_hours",
                ]:
                    if field in current_period and field in next_period:
                        current_period[field] = (
                            current_period[field] + next_period[field]
                        )

            else:
                # Legg til gjeldende periode og start en ny
                merged_periods.append(current_period)
                current_period = next_period.to_dict()

        # Legg til siste periode
        merged_periods.append(current_period)

        # Konverter tilbake til DataFrame og oppdater periode-IDer
        merged_df = pd.DataFrame(merged_periods)
        merged_df["period_id"] = range(len(merged_df))

        # Beregn nye statistikker for de sammenslåtte periodene
        if not merged_df.empty:
            # Beregn intensitet basert på risiko og varighet
            merged_df["intensity"] = merged_df["max_risk_score"] * np.log1p(
                merged_df["duration"]
            )

            # Beregn alvorlighetsgrad basert på flere faktorer
            merged_df["severity_score"] = (
                merged_df["intensity"] * 0.4  # Vekt for intensitet
                + (merged_df["max_wind"] / merged_df["max_wind"].max())
                * 0.3  # Vekt for vind
                + (np.abs(merged_df["min_temp"]) / np.abs(merged_df["min_temp"].min()))
                * 0.3  # Vekt for temperatur
            )

            # Kategoriser alvorlighetsgrad
            merged_df["severity"] = pd.qcut(
                merged_df["severity_score"],
                q=3,
                labels=["Moderat", "Alvorlig", "Ekstrem"],
            )

        logger.info(
            f"Sammenslåing fullført: {len(periods_df)} perioder redusert til {len(merged_df)}"
        )
        return merged_df

    except Exception as e:
        logger.error(f"Feil i merge_critical_periods: {str(e)}", exc_info=True)
        return periods_df


def plot_critical_periods_overview(df: pd.DataFrame, periods_df: pd.DataFrame):
    """
    Lager en oversiktsgraf som viser score-spennet for kun de mest kritiske periodene
    """
    try:
        if periods_df.empty:
            return None

        # Filtrer ut bare de mest kritiske periodene
        critical_threshold = 0.85  # Høy terskel for å få ca. 14 perioder
        min_duration = 3  # Timer

        # Filtrer og sorter periodene
        critical_periods = (
            periods_df[
                (periods_df["max_risk_score"] > critical_threshold)
                & (periods_df["duration"] >= min_duration)
            ]
            .sort_values("max_risk_score", ascending=False)
            .head(14)
        )

        if critical_periods.empty:
            return None

        # Opprett figur
        fig = go.Figure()

        # Legg til hver kritisk periode som en vertikal linje
        for _, period in critical_periods.iterrows():
            period_data = df[
                (df.index >= period["start_time"]) & (df.index <= period["end_time"])
            ]

            if not period_data.empty:
                # Beregn statistikk
                min_score = period_data["risk_score"].min() * 100
                max_score = period["max_risk_score"] * 100
                avg_wind = period_data["wind_speed"].mean()
                max_wind = period_data["wind_speed"].max()
                min_temp = period_data["air_temperature"].min()

                # Legg til vertikal linje
                fig.add_trace(
                    go.Scatter(
                        x=[period["start_time"], period["start_time"]],
                        y=[min_score, max_score],
                        mode="lines",
                        line={"color": "red", "width": 3},
                        name=f"Kritisk periode {int(period['period_id'])}",
                        hovertemplate=(
                            "<b>Kritisk periode</b><br>"
                            + f"Start: {period['start_time'].strftime('%d-%m-%Y %H:%M')}<br>"
                            + f"Varighet: {period['duration']:.1f} timer<br>"
                            + f"Risiko: {max_score:.1f}%<br>"
                            + f"Vind: {avg_wind:.1f} m/s (maks {max_wind:.1f})<br>"
                            + f"Min temp: {min_temp:.1f}°C"
                        ),
                    )
                )

        # Oppdater layout
        fig.update_layout(
            title="Oversikt over mest kritiske perioder",
            height=300,
            showlegend=False,
            yaxis_title="Risikoscore (%)",
            xaxis_title="",
            hovermode="x unified",
            margin={"t": 30, "b": 20, "l": 50, "r": 20},
            plot_bgcolor="white",
            yaxis={"gridcolor": "lightgray", "range": [0, 100], "tickformat": ",d"},
            xaxis={"gridcolor": "lightgray", "tickformat": "%d-%m-%Y\n%H:%M"},
        )

        return fig

    except Exception as e:
        logger.error(f"Feil i plot_critical_periods_overview: {str(e)}")
        return None


def analyze_wind_direction_impact(
    wind_dir: float, wind_speed: float, params: dict
) -> float:
    """
    Beregner vindretningens påvirkning på snøfokk-risiko med forbedret logikk

    Args:
        wind_dir: Vindretning i grader (0-360)
        wind_speed: Vindstyrke i m/s
        params: Parameterinnstillinger

    Returns:
        float: Risikoscore (0-1) basert på vindretning og styrke
    """
    try:
        # Hent parametre med sikre standardverdier
        primary_dir = params.get("wind_dir_primary", 270)  # Vestlig vind som standard
        tolerance = max(
            15, min(90, params.get("wind_dir_tolerance", 45))
        )  # Begrenset til 15-90 grader

        # Normaliser vindretninger til 0-360
        wind_dir = wind_dir % 360
        primary_dir = primary_dir % 360

        # Beregn minste vinkelforskjell med forbedret metode
        angle_diff = min(
            abs((wind_dir - primary_dir) % 360), abs((primary_dir - wind_dir) % 360)
        )

        # Beregn retningspåvirkning med myk overgang
        if angle_diff <= tolerance:
            direction_impact = np.cos(np.radians(angle_diff * 90 / tolerance))
        else:
            direction_impact = 0

        # Beregn vindstyrkefaktor med terskelverdi
        min_speed = params.get("wind_moderate", 5)
        max_speed = params.get("wind_strong", 10)
        speed_factor = np.clip((wind_speed - min_speed) / (max_speed - min_speed), 0, 1)

        # Kombiner påvirkningene med vekting
        total_impact = direction_impact * speed_factor

        return float(np.clip(total_impact, 0, 1))

    except Exception as e:
        logger.error(f"Feil i analyze_wind_direction_impact: {str(e)}")
        return 0.0


def analyze_temperature_impact(temp: float, params: dict) -> tuple[float, str]:
    """
    Analyserer temperaturens påvirkning på snøfokk-risiko

    Args:
        temp: Temperatur i Celsius
        params: Parameterinnstillinger

    Returns:
        tuple[float, str]: (risikoscore 0-1, beskrivelse)
    """
    try:
        # Legg til validering av input
        if not isinstance(temp, int | float):
            raise TypeError("Temperatur må være et tall")

        cold_temp = params.get("temp_cold", -2.22)
        cool_temp = params.get("temp_cool", 0.0)

        # Sikre at cold_temp er lavere enn cool_temp
        if cold_temp >= cool_temp:
            raise ValueError("temp_cold må være lavere enn temp_cool")

        # Beregn risikoscore og beskrivelse
        if temp <= cold_temp:
            score = 1.0
            desc = "Veldig kaldt - optimal for snøfokk"
        elif temp <= cool_temp:
            # Forbedret interpolering med smoothing
            norm_temp = (cool_temp - temp) / (cool_temp - cold_temp)
            score = np.clip(
                norm_temp * 1.2, 0, 1
            )  # 20% buffer for å fange opp grensetilfeller
            desc = "Kjølige forhold - betydelig risiko"
        elif temp <= (cool_temp + 2):
            # Gradvis overgang rundt frysepunktet
            score = max(0, 0.7 - (temp - cool_temp) / 4)
            desc = "Nær frysepunktet - moderat risiko"
        else:
            # Eksponentiell reduksjon over 2°C
            score = max(0, 0.5 * np.exp(-(temp - cool_temp) / 5))
            desc = "For mildt for betydelig snøfokk"

        # Avrund score til 3 desimaler for konsistens
        score = round(score, 3)

        return score, desc

    except Exception as e:
        logger.error(f"Feil i analyze_temperature_impact: {str(e)}")
        return 0.0, "Feil i temperaturanalyse"


def analyze_snow_conditions(
    snow_depth: float, snow_change: float, params: dict
) -> dict[str, Any]:
    # ... existing docstring ...

    results = {
        "risk_score": 0.0,
        "risk_factors": [],
        "recommendations": [],
        "severity": "lav",  # Ny felt for risiko-nivå
    }

    # ... existing snow depth analysis ...

    # Forbedret endringsanalyse
    abs_change = abs(snow_change)
    if abs_change >= params["snow_high"]:
        results["risk_factors"].append("Betydelig endring i snødybde")
        results["risk_score"] = min(1.0, results["risk_score"] + 0.8)
        results["recommendations"].append("Høy risiko for snøfokk")
        results["severity"] = "høy"
    elif abs_change >= params["snow_moderate"]:
        results["risk_factors"].append("Moderat endring i snødybde")
        results["risk_score"] = min(1.0, results["risk_score"] + 0.5)
        results["severity"] = "moderat"

    # Legg til generelle anbefalinger basert på severity
    if results["severity"] == "høy":
        results["recommendations"].extend(
            ["Unngå eksponerte områder", "Følg med på værmeldinger"]
        )

    return results


def calculate_combined_risk(
    wind_data: dict, temp_data: tuple[float, str], snow_data: dict, params: dict
) -> dict[str, Any]:
    """
    Beregner samlet snøfokk-risiko basert på alle faktorer

    Args:
        wind_data: Resultater fra vindanalyse
        temp_data: Resultater fra temperaturanalyse
        snow_data: Resultater fra snøanalyse
        params: Parameterinnstillinger

    Returns:
        dict med samlet risikovurdering
    """
    try:
        # Valider input
        if not all(isinstance(x, dict) for x in [wind_data, snow_data, params]):
            raise ValueError("Ugyldig input-format")

        # Hent vekter med sikre standardverdier
        weights = {
            "wind": params.get("wind_weight", 1.68),
            "temp": params.get("temp_weight", 1.22),
            "snow": params.get("snow_weight", 1.08),
        }

        # Beregn normaliserte risikoscorer
        scores = {
            "wind": wind_data.get("risk_score", 0) * weights["wind"],
            "temp": temp_data[0] * weights["temp"],
            "snow": snow_data.get("risk_score", 0) * weights["snow"],
        }

        # Beregn total risiko med normalisering
        total_weight = sum(weights.values())
        total_risk = sum(scores.values()) / total_weight

        # Legg til konfidensgrad basert på datakvalitet
        confidence = calculate_confidence(wind_data, temp_data, snow_data)

        return {
            "total_risk_score": round(total_risk, 3),
            "risk_level": get_risk_level(total_risk),
            "confidence_level": confidence,
            "contributing_factors": {
                "wind": wind_data.get("risk_factors", []),
                "temperature": temp_data[1],
                "snow": snow_data.get("risk_factors", []),
            },
            "factor_scores": {k: round(v / weights[k], 3) for k, v in scores.items()},
            "recommendations": generate_recommendations(total_risk, scores, snow_data),
        }

    except Exception as e:
        logger.error(f"Feil i calculate_combined_risk: {str(e)}")
        return {"total_risk_score": 0, "risk_level": "ukjent", "error": str(e)}


def calculate_confidence(wind_data: dict, temp_data: tuple, snow_data: dict) -> str:
    """Beregner konfidensgrad basert på datakvalitet"""
    confidence_score = 0
    total_factors = 0

    # Sjekk vinddata
    if wind_data.get("risk_score") is not None:
        confidence_score += 1
        total_factors += 1

    # Sjekk temperaturdata
    if temp_data[0] is not None:
        confidence_score += 1
        total_factors += 1

    # Sjekk snødata
    if snow_data.get("risk_score") is not None:
        confidence_score += 1
        total_factors += 1

    ratio = confidence_score / total_factors if total_factors > 0 else 0

    if ratio >= 0.8:
        return "høy"
    elif ratio >= 0.5:
        return "moderat"
    else:
        return "lav"


def generate_recommendations(
    total_risk: float, factor_scores: dict, snow_data: dict
) -> list[str]:
    """Genererer anbefalinger basert på risikofaktorer"""
    recommendations = snow_data.get("recommendations", [])

    if total_risk > 0.7:
        recommendations.extend(
            ["Unngå eksponerte områder", "Følg nøye med på værmeldinger"]
        )
    elif total_risk > 0.4:
        recommendations.append("Vær oppmerksom på værforholdene")

    return list(set(recommendations))  # Fjern duplikater


if __name__ == "__main__":
    # Legg til prosjektets rotmappe i Python path
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent.parent
    sys.path.append(str(project_root))

    try:
        logger.info("Starter test av API-kall...")
        test_data = fetch_frost_data("2024-01-01", "2024-01-02")
        if test_data is not None:
            logger.info("API-kall vellykket!")
            logger.info(f"Antall rader: {len(test_data)}")
            logger.info("Første rad med data:")
            logger.info(test_data.iloc[0])
        else:
            logger.error("API-kall feilet - ingen data mottatt")
    except Exception as e:
        logger.error(f"Feil under testing: {str(e)}")
