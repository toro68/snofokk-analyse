# pylint: disable=line-too-long

"""
Modul for håndtering av snødata og væranalyse.
Inneholder funksjoner for å hente data fra Frost API og analysere snødrift-risiko.
"""

# Standard biblioteker
import logging
from datetime import datetime
from typing import Any

# Tredjeparts biblioteker
import numpy as np
import pandas as pd
import requests
import streamlit as st
from pandas import DataFrame
# Lokale imports
from snow_constants import (SnowDepthConfig,  # Legg til denne importen
                            enforce_snow_processing)

from data.src.snofokk.config import DEFAULT_PARAMS, FROST_CLIENT_ID

# Logging oppsett
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@st.cache_data(ttl=3600)  # Cache data for 1 time
def fetch_frost_data(start_date="2023-11-01", end_date="2024-04-30"):
    """
    Henter utvidet værdatasett fra Frost API
    """
    try:
        endpoint = "https://frost.met.no/observations/v0.jsonld"
        parameters = {
            "sources": "SN46220",
            "referencetime": f"{start_date}/{end_date}",
            "elements": "air_temperature,surface_snow_thickness,wind_speed,wind_from_direction,relative_humidity,max(wind_speed_of_gust PT1H),max(wind_speed PT1H),min(air_temperature PT1H),max(air_temperature PT1H),sum(duration_of_precipitation PT1H),sum(precipitation_amount PT1H),dew_point_temperature",  # noqa: E501
            "timeresolutions": "PT1H",
        }

        # Legg til Accept-header
        headers = {"Accept": "application/json"}

        # Gjør API-kallet med headers
        r = requests.get(
            endpoint, parameters, auth=(FROST_CLIENT_ID, ""), headers=headers
        )

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


def identify_risk_periods(df, min_duration=3):
    """
    Identifiserer sammenhengende perioder med forhøyet risiko.

    Args:
        df: DataFrame med risikodata
        min_duration: Minimum varighet for en periode i timer

    Returns:
        DataFrame med identifiserte risikoperioder
    """
    periods = []

    for period_id in df["period_id"].dropna().unique():
        period_data = df[df["period_id"] == period_id].copy()

        if len(period_data) >= min_duration:
            # Definer standard kolonner med fallback-verdier
            period_info = {
                "start_time": period_data.index[0],
                "end_time": period_data.index[-1],
                "duration": len(period_data),
                "max_risk_score": period_data["risk_score"].max(),
                "avg_risk_score": period_data["risk_score"].mean(),
                "max_wind": period_data.get("sustained_wind", pd.Series()).max(),
                "max_gust": period_data.get(
                    "max(wind_speed_of_gust PT1H)", pd.Series()
                ).max(),
                "min_temp": period_data.get("air_temperature", pd.Series()).min(),
                "max_snow_change": period_data.get("snow_depth_change", pd.Series())
                .abs()
                .max(),
                "risk_level": period_data["risk_level"].mode()[0],
                "period_id": period_id,
            }

            # Legg til nedbørsinformasjon hvis kolonnene eksisterer
            if "sum(precipitation_amount PT1H)" in period_data.columns:
                period_info["total_precip"] = period_data[
                    "sum(precipitation_amount PT1H)"
                ].sum()
            else:
                period_info["total_precip"] = 0.0

            if "sum(duration_of_precipitation PT1H)" in period_data.columns:
                period_info["precip_duration"] = period_data[
                    "sum(duration_of_precipitation PT1H)"
                ].sum()
            else:
                period_info["precip_duration"] = 0.0

            # Beregn gjennomsnittlig vindretning hvis data finnes
            if "wind_from_direction" in period_data.columns:
                wind_dirs = period_data["wind_from_direction"].dropna()
                if not wind_dirs.empty:
                    rad = np.deg2rad(wind_dirs)
                    avg_sin = np.mean(np.sin(rad))
                    avg_cos = np.mean(np.cos(rad))
                    avg_dir = np.rad2deg(np.arctan2(avg_sin, avg_cos)) % 360
                    period_info["wind_direction"] = avg_dir

            periods.append(period_info)

    return pd.DataFrame(periods)


@enforce_snow_processing
def calculate_snow_drift_risk(
    df: pd.DataFrame, params: dict[str, float]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    try:
        # Legg til debugging av input
        logger.info(f"Starter calculate_snow_drift_risk med {len(df)} rader")
        logger.info(f"Parametre mottatt: {params}")

        df = df.copy()

        # Snødybdehåndtering med debugging
        if "surface_snow_thickness" in df.columns:
            logger.info("Snødybdedata før prosessering:")
            logger.info(f"Null-verdier: {df['surface_snow_thickness'].isnull().sum()}")
            logger.info(f"Unike verdier: {df['surface_snow_thickness'].unique()}")

            df["surface_snow_thickness"] = SnowDepthConfig.process_snow_depth(
                df["surface_snow_thickness"]
            )

            logger.info("Snødybdedata etter prosessering:")
            logger.info(f"Null-verdier: {df['surface_snow_thickness'].isnull().sum()}")
            logger.info(f"Unike verdier: {df['surface_snow_thickness'].unique()}")

            # Beregn endringer med debugging
            df["snow_depth_change"] = (
                df["surface_snow_thickness"]
                .diff()
                .rolling(
                    window=SnowDepthConfig.WINDOW_SIZE,
                    min_periods=SnowDepthConfig.MIN_PERIODS,
                )
                .mean()
            )

            logger.info("Snødybdeendringer statistikk:")
            logger.info(f"Min: {df['snow_depth_change'].min():.2f}")
            logger.info(f"Maks: {df['snow_depth_change'].max():.2f}")
            logger.info(f"Gjennomsnitt: {df['snow_depth_change'].mean():.2f}")

        # Debug risikokomponenter
        for risk_component in ["wind_risk", "temp_risk", "snow_risk"]:
            if risk_component in df.columns:
                logger.info(f"{risk_component} statistikk:")
                logger.info(f"Min: {df[risk_component].min():.2f}")
                logger.info(f"Maks: {df[risk_component].max():.2f}")
                logger.info(f"Gjennomsnitt: {df[risk_component].mean():.2f}")
                logger.info(f"Null-verdier: {df[risk_component].isnull().sum()}")

        # Beregn risikokomponenter
        df["wind_risk"] = (
            (df["wind_speed"] > params["wind_strong"]).astype(float) * 1.0
            + (
                (df["wind_speed"] > params["wind_moderate"])
                & (df["wind_speed"] <= params["wind_strong"])
            ).astype(float)
            * 0.6
        ) * params["wind_weight"]

        df["temp_risk"] = (
            (df["air_temperature"] < params["temp_cold"]).astype(float) * 1.0
            + (
                (df["air_temperature"] < params["temp_cool"])
                & (df["air_temperature"] >= params["temp_cold"])
            ).astype(float)
            * 0.6
        ) * params["temp_weight"]

        df["snow_risk"] = (
            (abs(df["snow_depth_change"]) > params["snow_high"]).astype(float) * 1.0
            + (
                (abs(df["snow_depth_change"]) > params["snow_moderate"])
                & (abs(df["snow_depth_change"]) <= params["snow_high"])
            ).astype(float)
            * 0.6
            + (
                (abs(df["snow_depth_change"]) > params["snow_low"])
                & (abs(df["snow_depth_change"]) <= params["snow_moderate"])
            ).astype(float)
            * 0.3
        ) * params["snow_weight"]

        # Total risikoberegning
        df["risk_score"] = df["wind_risk"] + df["temp_risk"] + df["snow_risk"]

        # Identifiser kritiske perioder
        critical_mask = df["risk_score"] > 0.5
        df["is_critical"] = critical_mask

        # Lag periods_df
        periods_df = pd.DataFrame(
            columns=[
                "start_time",
                "end_time",
                "duration",
                "max_risk_score",
                "avg_wind_speed",
                "min_temp",
                "snow_depth_change",
                "risk_level",
            ]
        )

        if critical_mask.any():
            # Finn start og slutt for hver periode
            critical_periods = []
            start_idx = None

            for idx, is_critical in critical_mask.items():
                if is_critical and start_idx is None:
                    start_idx = idx
                elif not is_critical and start_idx is not None:
                    max_risk = df.loc[start_idx:idx, "risk_score"].max()
                    period_data = {
                        "start_time": start_idx,
                        "end_time": idx,
                        "duration": (idx - start_idx).total_seconds() / 3600,
                        "max_risk_score": max_risk,
                        "avg_wind_speed": df.loc[start_idx:idx, "wind_speed"].mean(),
                        "min_temp": df.loc[start_idx:idx, "air_temperature"].min(),
                        "snow_depth_change": df.loc[start_idx:idx, "snow_depth_change"]
                        .abs()
                        .max(),
                        "risk_level": (
                            "Høy"
                            if max_risk > 0.8
                            else "Moderat"
                            if max_risk > 0.65
                            else "Lav"
                        ),
                    }
                    critical_periods.append(period_data)
                    start_idx = None

            # Håndter siste periode hvis den er aktiv
            if start_idx is not None:
                max_risk = df.loc[start_idx:, "risk_score"].max()
                period_data = {
                    "start_time": start_idx,
                    "end_time": df.index[-1],
                    "duration": (df.index[-1] - start_idx).total_seconds() / 3600,
                    "max_risk_score": max_risk,
                    "avg_wind_speed": df.loc[start_idx:, "wind_speed"].mean(),
                    "min_temp": df.loc[start_idx:, "air_temperature"].min(),
                    "snow_depth_change": df.loc[start_idx:, "snow_depth_change"]
                    .abs()
                    .max(),
                    "risk_level": (
                        "Høy"
                        if max_risk > 0.8
                        else "Moderat"
                        if max_risk > 0.65
                        else "Lav"
                    ),
                }
                critical_periods.append(period_data)

            # Konverter til DataFrame og filtrer
            if critical_periods:
                periods_df = pd.DataFrame(critical_periods)
                periods_df = periods_df[
                    periods_df["duration"] >= params["min_duration"]
                ]

        # Debug kritiske perioder
        logger.info(f"Antall kritiske perioder funnet: {len(periods_df)}")
        if not periods_df.empty:
            logger.info("Kritiske perioder statistikk:")
            logger.info(
                f"Gjennomsnittlig varighet: {periods_df['duration'].mean():.2f} timer"
            )
            logger.info(f"Maks risikoscore: {periods_df['max_risk_score'].max():.2f}")

        return df, periods_df

    except Exception as e:
        logger.error(f"Feil i calculate_snow_drift_risk: {str(e)}", exc_info=True)
        raise


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
    params: dict[str, float], critical_periods_df: DataFrame
) -> dict[str, Any]:
    """
    Utfører avansert AI-analyse av parameterinnstillingene og deres effektivitet
    """
    try:
        from snow_constants import SnowDepthConfig

        snow_config = SnowDepthConfig.get_processing_config()

        analysis = {
            "parameter_changes": [],
            "impact_analysis": [],
            "suggestions": [],
            "meteorological_context": [],
        }

        # Initialiser statistiske variabler med standardverdier
        avg_duration = 0
        avg_risk = 0
        max_wind = 0
        min_temp = 0

        # 1. Analyser parameterendringer med sikker prosentberegning
        for param_name, current_value in params.items():
            default_value = DEFAULT_PARAMS[param_name]

            # Sikker beregning av prosentendring
            if default_value == 0:
                if current_value == 0:
                    percent_change = 0
                else:
                    percent_change = 100  # Indikerer en endring fra 0
            else:
                percent_change = (
                    (current_value - default_value) / abs(default_value)
                ) * 100

            if abs(percent_change) >= 10:  # Bare rapporter betydelige endringer
                change_type = "økning" if percent_change > 0 else "reduksjon"

                # Forbedret parametertype-beskrivelse
                param_description = {
                    "wind_strong": "Sterk vind",
                    "wind_moderate": "Moderat vind",
                    "wind_gust": "Vindkast terskel",
                    "wind_dir_change": "Vindretningsendring",
                    "wind_weight": "Vindvekt",
                    "temp_cold": "Kald temperatur",
                    "temp_cool": "Kjølig temperatur",
                    "temp_weight": "Temperaturvekt",
                    "snow_high": "Høy snøendring",
                    "snow_moderate": "Moderat snøendring",
                    "snow_low": "Lav snøendring",
                    "snow_weight": "Snøvekt",
                    "min_duration": "Minimum varighet",
                }.get(param_name, param_name)

                analysis["parameter_changes"].append(
                    {
                        "description": f"{param_description}: {abs(percent_change):.1f}% {change_type} "
                        f"fra standard ({default_value} → {current_value})",
                        "importance": "høy" if abs(percent_change) > 25 else "moderat",
                    }
                )

        # 2. Analyser kritiske perioder
        if not critical_periods_df.empty:
            # Beregn nøkkelstatistikk
            avg_duration = critical_periods_df["duration"].mean()
            avg_risk = critical_periods_df["max_risk_score"].mean()
            max_wind = (
                critical_periods_df["max_wind"].max()
                if "max_wind" in critical_periods_df.columns
                else 0
            )
            min_temp = (
                critical_periods_df["min_temp"].min()
                if "min_temp" in critical_periods_df.columns
                else 0
            )

            # Legg til snødybdeanalyse
            if "max_snow_change" in critical_periods_df.columns:
                max_snow_change = critical_periods_df["max_snow_change"].abs().max()
                if max_snow_change > snow_config["max_change"]:
                    analysis["impact_analysis"].append(
                        {
                            "description": (
                                f"Observert høy snøendringsrate ({max_snow_change:.1f} cm/t) - "
                                "justert innenfor konfigurerte grenser"
                            )
                        }
                    )

            # Legg til viktige observasjoner
            if avg_duration > 4:
                analysis["impact_analysis"].append(
                    {
                        "description": f"Lange kritiske perioder (snitt {avg_duration:.1f} timer) "
                        f"indikerer vedvarende risikotilstander",
                        "importance": "høy",
                    }
                )

            if avg_risk > 80:
                analysis["impact_analysis"].append(
                    {
                        "description": f"Høy gjennomsnittlig risikoscore ({avg_risk:.1f}) "
                        f"tyder på alvorlige forhold under kritiske perioder",
                        "importance": "høy",
                    }
                )

            # 3. Analyser vindretninger
            if "wind_direction" in critical_periods_df.columns:
                wind_dir_analysis = analyze_wind_directions(critical_periods_df)
                if wind_dir_analysis and wind_dir_analysis.get("significant"):
                    for dir_info in wind_dir_analysis["significant"]:
                        analysis["impact_analysis"].append(
                            {
                                "description": (
                                    f"Vind fra {dir_info['direction']} er betydelig: "
                                    f"Forekommer i {dir_info['percentage']:.1f}% av tilfellene "
                                    f"med snittrisiko {dir_info['avg_risk']:.1f} "
                                    f"og vindstyrke {dir_info['avg_wind']:.1f} m/s"
                                ),
                                "importance": (
                                    "høy" if dir_info["avg_risk"] > 70 else "moderat"
                                ),
                            }
                        )
        # 4. Generer forslag basert på analysen
        if (
            "max_wind" in critical_periods_df.columns
            and params["wind_weight"] < 1.0
            and max_wind > params["wind_strong"]
        ):
            analysis["suggestions"].append(
                "Vurder å øke vindvekten da det observeres sterke vindforhold"
            )

        if (
            "min_temp" in critical_periods_df.columns
            and params["temp_weight"] < 1.0
            and min_temp < params["temp_cold"]
        ):
            analysis["suggestions"].append(
                "Vurder å øke temperaturvekten da det observeres svært kalde forhold"
            )

        if avg_duration < 2:
            analysis["suggestions"].append(
                "Vurder å redusere minimum varighet for å fange opp kortere hendelser"
            )

        # 5. Legg til meteorologisk kontekst
        if not critical_periods_df.empty:
            analysis["meteorological_context"].append(
                f"Analysen er basert på {len(critical_periods_df)} kritiske perioder "
                f"med gjennomsnittlig varighet på {avg_duration:.1f} timer og "
                f"gjennomsnittlig risikoscore på {avg_risk:.1f}"
            )

            if "wind_direction" in critical_periods_df.columns:
                wind_dir_analysis = analyze_wind_directions(critical_periods_df)
                if wind_dir_analysis and wind_dir_analysis.get("significant"):
                    dominant_dirs = [
                        d["direction"] for d in wind_dir_analysis["significant"]
                    ]
                    analysis["meteorological_context"].append(
                        f"Dominerende vindretninger under kritiske perioder: {', '.join(dominant_dirs)}. "
                        "Dette kan indikere spesielt utsatte områder i disse retningene."
                    )

        # Forbedret analyse av varighetsinnstillinger
        if not critical_periods_df.empty:
            duration_stats = critical_periods_df["duration"].describe()
            min_duration = params.get("min_duration", 3)

            # Analyser varighetsfordeling
            if duration_stats["25%"] > min_duration + 2:
                analysis["suggestions"].append(
                    f"Vurder å øke minimum varighet fra {min_duration} til {int(duration_stats['25%'])} timer "
                    "da de fleste kritiske perioder varer lengre"
                )
            elif duration_stats["75%"] < min_duration:
                analysis["suggestions"].append(
                    f"Vurder å redusere minimum varighet fra {min_duration} "
                    f"til {max(2, int(duration_stats['75%']))} timer "
                    "for å fange opp flere potensielle hendelser"
                )

            # Legg til varighetsstatistikk i meteorologisk kontekst
            analysis["meteorological_context"].append(
                f"Varighetsfordeling for kritiske perioder: "
                f"Minimum: {duration_stats['min']:.1f}, "
                f"25-persentil: {duration_stats['25%']:.1f}, "
                f"Median: {duration_stats['50%']:.1f}, "
                f"75-persentil: {duration_stats['75%']:.1f}, "
                f"Maksimum: {duration_stats['max']:.1f} timer"
            )

        return analysis

    except Exception as e:
        logger.error(f"Feil i analyse av innstillinger: {str(e)}", exc_info=True)
        return {
            "parameter_changes": [],
            "impact_analysis": [],
            "suggestions": ["Kunne ikke fullføre analysen p grunn av en feil"],
            "meteorological_context": [],
        }


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
