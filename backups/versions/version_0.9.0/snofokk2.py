# Standard biblioteker
import logging
from datetime import datetime
from typing import Any, Dict, List, Tuple

# Tredjeparts biblioteker
import numpy as np
import pandas as pd
import requests
import streamlit as st
from pandas import DataFrame

# Logging oppsett
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Konstanter
from data.src.snofokk.config import (  # Legg til import fra config
    DEFAULT_PARAMS, FROST_CLIENT_ID)


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
            "elements": "air_temperature,surface_snow_thickness,wind_speed,wind_from_direction,relative_humidity,max(wind_speed_of_gust PT1H),max(wind_speed PT1H),min(air_temperature PT1H),max(air_temperature PT1H),sum(duration_of_precipitation PT1H),sum(precipitation_amount PT1H),dew_point_temperature",
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
            logger.error(f"Error {r.status_code}: {r.text}")
            return None

    except Exception as e:
        logger.exception(f"Feil i fetch_frost_data: {str(e)}")
        return None


def identify_risk_periods(df, min_duration=3):
    """
    Identifiserer sammenhengende perioder med forhøyet risiko
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


def calculate_snow_drift_risk(
    df: pd.DataFrame, params: Dict[str, float]
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Beregner snøfokk-risiko basert på værdata og parametre
    """
    min_duration = params.get("min_duration", 2)  # Bruker 2 som standardverdi

    df = df.copy()

    # Valider input data
    required_columns = {
        "surface_snow_thickness": -1.0,  # Endret standardverdi til -1.0
        "wind_speed": 0.0,
        "wind_from_direction": 0.0,
        "air_temperature": 0.0,
    }

    # Sjekk og legg til manglende kolonner
    missing_columns = []
    for col, default_value in required_columns.items():
        if col not in df.columns:
            logging.warning(
                f"Manglende kolonne '{col}' - bruker standardverdi {default_value}"
            )
            df[col] = default_value
            missing_columns.append(col)

    if missing_columns:
        st.warning(
            f"""
            Følgende data mangler fra værstasjonen: {', '.join(missing_columns)}.
            Analysen vil fortsette med standardverdier, men resultatet kan være mindre presist.
            For snødybde betyr -1 at det ikke er snø på bakken.
            """
        )

    # Sikre beregninger med fillna()
    df["snow_depth_change"] = df["surface_snow_thickness"].diff().fillna(0)
    df["sustained_wind"] = (
        df["wind_speed"].rolling(window=2, min_periods=1).mean().fillna(0)
    )
    df["wind_dir_change"] = df["wind_from_direction"].diff().abs().fillna(0)

    # Sikrere måte å håndtere snødybdeendringer
    df["prev_snow_depth"] = df["surface_snow_thickness"].shift()
    mask = (df["surface_snow_thickness"] == -1) | (df["prev_snow_depth"] == -1)
    df.loc[mask, "snow_depth_change"] = 0
    df.drop("prev_snow_depth", axis=1, inplace=True)  # Fjern hjelpkolonnen

    def calculate_risk_score(row):
        """Beregner risikoscore for en enkelt rad"""
        score = 0

        # Vindrisiko
        if row["wind_speed"] >= params["wind_strong"]:
            score += 40 * params["wind_weight"]
        elif row["wind_speed"] >= params["wind_moderate"]:
            score += 20 * params["wind_weight"]

        if (
            "max(wind_speed_of_gust PT1H)" in row
            and row["max(wind_speed_of_gust PT1H)"] >= params["wind_gust"]
        ):
            score += 10 * params["wind_weight"]

        if row["wind_dir_change"] >= params["wind_dir_change"]:
            score += 10 * params["wind_weight"]

        # Temperaturrisiko
        if row["air_temperature"] <= params["temp_cold"]:
            score += 20 * params["temp_weight"]
        elif row["air_temperature"] <= params["temp_cool"]:
            score += 10 * params["temp_weight"]

        # Snørisiko
        if abs(row["snow_depth_change"]) >= params["snow_high"]:
            score += 40 * params["snow_weight"]
        elif abs(row["snow_depth_change"]) >= params["snow_moderate"]:
            score += 20 * params["snow_weight"]
        elif abs(row["snow_depth_change"]) >= params["snow_low"]:
            score += 10 * params["snow_weight"]

        return min(100, score)

    # Beregn risikoscore
    df["risk_score"] = df.apply(calculate_risk_score, axis=1)
    df["risk_level"] = pd.cut(
        df["risk_score"],
        bins=[-np.inf, 30, 50, 70, np.inf],
        labels=["Lav", "Moderat", "Høy", "Kritisk"],
    )

    # Legg til periode-ID for sammenhengende risikoperioder
    # En ny periode starter når risk_score går fra 0 til over 0 eller omvendt
    risk_threshold = 30  # Juster denne verdien etter behov
    df["is_risk"] = df["risk_score"] > risk_threshold
    df["period_start"] = df["is_risk"].ne(df["is_risk"].shift()).cumsum()
    df["period_id"] = np.where(df["is_risk"], df["period_start"], np.nan)

    # Fjern midlertidige kolonner
    df = df.drop(["is_risk", "period_start"], axis=1)

    # Identifiser perioder med sikker min_duration
    periods_df = identify_risk_periods(df, min_duration=min_duration)

    return df, periods_df


def create_rolling_stats(
    df: DataFrame, columns: List[str], windows: List[int], stats: List[str]
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


def analyze_wind_directions(df: DataFrame) -> Dict[str, Any]:
    """
    Analyserer hvilke vindretninger som er mest assosiert med snøfokk

    Args:
        df: DataFrame med kritiske perioder
    Returns:
        Dict med vindretningsanalyse
    """
    try:
        if "wind_direction" not in df.columns:
            return None

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
        logging.error(f"Feil i vindretningsanalyse: {str(e)}")
        return None


def analyze_settings(
    params: Dict[str, float], critical_periods_df: DataFrame
) -> Dict[str, Any]:
    """
    Utfører avansert AI-analyse av parameterinnstillingene og deres effektivitet

    Args:
        params: Dict med gjeldende parameterinnstillinger
        critical_periods_df: DataFrame med kritiske perioder

    Returns:
        Dict med analyseinformasjon inkludert:
        - parameter_changes: Liste med betydelige parameterendringer
        - impact_analysis: Liste med effektanalyser
        - suggestions: Liste med forbedringsforslag
        - meteorological_context: Liste med meteorologisk kontekst
    """
    try:
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
