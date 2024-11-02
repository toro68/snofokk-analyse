# Fil: db_utils.py
# Kategori: Database Functions

import json

# Logging oppsett
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

# Tredjeparts biblioteker
import pandas as pd
from pandas import DataFrame

logger = logging.getLogger(__name__)


@dataclass
class WeatherData:
    """Data class for værmålinger"""

    location: str
    timestamp: datetime
    temperature: float
    precipitation: float
    wind_speed: float
    wind_direction: str


@contextmanager
def get_db_connection():
    """Kontekstbehandler for databasetilkoblinger"""
    conn = sqlite3.connect("snowdrift_settings.db")
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> Tuple[bool, str]:
    """
    Initialiserer database og kjører nødvendige migreringer

    Returns:
        Tuple[bool, str]: (suksess, melding)
    """
    try:
        with get_db_connection() as conn:
            c = conn.cursor()

            # Settings-tabell med forbedret skjema
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    timestamp DATETIME NOT NULL,
                    parameters JSON NOT NULL,
                    changes JSON,
                    critical_periods INTEGER,
                    total_duration INTEGER,
                    avg_risk_score REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Periodestatistikk-tabell med forbedret skjema
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS period_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    settings_id INTEGER,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME NOT NULL,
                    duration INTEGER NOT NULL,
                    max_risk_score REAL NOT NULL,
                    avg_risk_score REAL,
                    max_wind REAL,
                    avg_wind REAL,
                    min_temp REAL,
                    max_snow_change REAL,
                    wind_direction REAL,
                    precipitation_sum REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (settings_id) REFERENCES settings (id)
                        ON DELETE CASCADE
                )
            """
            )

            # Værtabell med forbedret skjema
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS weather_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    temperature FLOAT,
                    precipitation FLOAT,
                    wind_speed FLOAT,
                    wind_direction FLOAT,
                    humidity FLOAT,
                    pressure FLOAT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(location, timestamp)
                )
            """
            )

            # Opprett indekser for bedre ytelse
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_settings_timestamp ON settings(timestamp)"
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_period_stats_settings ON period_stats(settings_id)"
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_period_stats_time ON period_stats(start_time, end_time)"
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_weather_location_time ON weather_cache(location, timestamp)"
            )

            conn.commit()

            # Kjør database migrering
            migration_success, migration_message = migrate_database_schema()
            if not migration_success:
                return (
                    False,
                    f"Database initialisert, men migrering feilet: {migration_message}",
                )

            return True, "Database initialisert og migrert vellykket"

    except Exception as e:
        error_msg = f"Feil ved initialisering av database: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def migrate_database_schema() -> Tuple[bool, str]:
    """
    Migrerer databaseskjema for å håndtere manglende kolonner og indekser

    Returns:
        Tuple[bool, str]: (suksess, melding)
    """
    try:
        with get_db_connection() as conn:
            c = conn.cursor()

            # Sjekk settings-tabell
            c.execute("PRAGMA table_info(settings)")
            settings_columns = {col[1] for col in c.fetchall()}

            # Endre definisjonene for å unngå CURRENT_TIMESTAMP
            required_columns = {
                "created_at": "DATETIME",  # Fjernet DEFAULT CURRENT_TIMESTAMP
                "updated_at": "DATETIME",  # Fjernet DEFAULT CURRENT_TIMESTAMP
                "critical_periods": "INTEGER",
                "total_duration": "INTEGER",
                "avg_risk_score": "REAL",
            }

            # Legg til manglende kolonner i settings
            for col_name, col_def in required_columns.items():
                if col_name not in settings_columns:
                    try:
                        c.execute(
                            f"ALTER TABLE settings ADD COLUMN {col_name} {col_def}"
                        )
                        # Sett timestamp direkte etter å ha lagt til kolonnen
                        if col_name in ["created_at", "updated_at"]:
                            c.execute(
                                f"""
                                UPDATE settings 
                                SET {col_name} = datetime('now') 
                                WHERE {col_name} IS NULL
                            """
                            )
                        logger.info(f"Lagt til kolonne: {col_name} i settings")
                    except Exception as e:
                        logger.error(
                            f"Feil ved tillegg av kolonne {col_name}: {str(e)}"
                        )

            # Sjekk period_stats-tabell
            c.execute("PRAGMA table_info(period_stats)")
            period_stats_columns = {col[1] for col in c.fetchall()}

            # Definer påkrevde kolonner for period_stats
            period_stats_required = {
                "created_at": "DATETIME",
                "avg_wind": "REAL",
                "wind_direction": "REAL",
                "precipitation_sum": "REAL",
            }

            # Legg til manglende kolonner i period_stats
            for col_name, col_def in period_stats_required.items():
                if col_name not in period_stats_columns:
                    try:
                        c.execute(
                            f"ALTER TABLE period_stats ADD COLUMN {col_name} {col_def}"
                        )
                        logger.info(f"Lagt til kolonne: {col_name} i period_stats")
                    except Exception as e:
                        logger.error(
                            f"Feil ved tillegg av kolonne {col_name}: {str(e)}"
                        )

            # Oppdater eksisterende rader med standardverdier
            c.execute(
                """
                UPDATE settings 
                SET created_at = CURRENT_TIMESTAMP 
                WHERE created_at IS NULL
            """
            )

            c.execute(
                """
                UPDATE settings 
                SET updated_at = CURRENT_TIMESTAMP 
                WHERE updated_at IS NULL
            """
            )

            conn.commit()
            return True, "Database migrering fullført"

    except Exception as e:
        return False, f"Feil under database migrering: {str(e)}"


def save_settings(
    settings_data: Dict[str, Any], critical_periods_df: DataFrame
) -> Tuple[bool, str]:
    """
    Lagrer innstillinger og periodestatistikk med forbedret feilhåndtering
    """
    try:
        with get_db_connection() as conn:
            c = conn.cursor()

            # Valider påkrevde felt
            required_fields = {"name", "description", "timestamp", "parameters"}
            missing_fields = required_fields - settings_data.keys()
            if missing_fields:
                raise ValueError(f"Mangler påkrevde felt: {', '.join(missing_fields)}")

            # Beregn statistikk sikkert
            total_duration = (
                int(critical_periods_df["duration"].sum())
                if not critical_periods_df.empty
                else 0
            )
            avg_risk_score = (
                float(critical_periods_df["max_risk_score"].mean())
                if not critical_periods_df.empty
                else 0.0
            )
            num_periods = len(critical_periods_df)

            # Sett inn innstillinger
            c.execute(
                """
                INSERT INTO settings 
                (name, description, timestamp, parameters, changes, 
                 critical_periods, total_duration, avg_risk_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    settings_data["name"],
                    settings_data["description"],
                    settings_data["timestamp"],
                    json.dumps(settings_data["parameters"]),
                    json.dumps(settings_data.get("changes", [])),
                    num_periods,
                    total_duration,
                    avg_risk_score,
                ),
            )

            settings_id = c.lastrowid

            # Lagre statistikk for hver kritisk periode
            if not critical_periods_df.empty:
                for idx, period in critical_periods_df.iterrows():
                    try:
                        c.execute(
                            """
                            INSERT INTO period_stats
                            (settings_id, start_time, end_time, duration, 
                             max_risk_score, max_wind, min_temp, max_snow_change)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                settings_id,
                                period["start_time"].isoformat(),
                                period["end_time"].isoformat(),
                                int(period["duration"]),
                                float(period["max_risk_score"]),
                                float(period.get("max_wind", 0)),
                                float(period.get("min_temp", 0)),
                                float(period.get("max_snow_change", 0)),
                            ),
                        )
                    except Exception as e:
                        raise ValueError(f"Error saving period data: {str(e)}")

            conn.commit()
            return True, "Innstillingene ble lagret!"

    except Exception as e:
        logger.error(f"Feil ved lagring av innstillinger: {str(e)}")
        return False, f"Feil ved lagring av innstillinger: {str(e)}"


def get_saved_settings() -> DataFrame:
    """
    Henter alle lagrede innstillinger med forbedret feilhåndtering og dynamisk kolonnehåndtering

    Returns:
        DataFrame: Innstillinger med alle tilgjengelige kolonner
    """
    try:
        with get_db_connection() as conn:
            # Sjekk først hvilke kolonner som eksisterer
            c = conn.cursor()
            c.execute("PRAGMA table_info(settings)")
            available_columns = {col[1] for col in c.fetchall()}

            # Definer påkrevde og valgfrie kolonner
            required_columns = {
                "id",
                "name",
                "description",
                "timestamp",
                "parameters",
                "changes",
            }

            optional_columns = {
                "critical_periods",
                "total_duration",
                "avg_risk_score",
                "created_at",
                "updated_at",
            }

            # Valider at alle påkrevde kolonner eksisterer
            missing_required = required_columns - available_columns
            if missing_required:
                raise ValueError(
                    f"Mangler påkrevde kolonner i settings-tabell: {missing_required}"
                )

            # Bygg kolonneliste for spørring
            query_columns = list(required_columns)
            for col in optional_columns:
                if col in available_columns:
                    query_columns.append(col)

            # Bygg og utfør spørring
            query = f"""
                SELECT {', '.join(query_columns)}
                FROM settings
                ORDER BY timestamp DESC
            """

            settings_df = pd.read_sql_query(query, conn)

            if not settings_df.empty:
                try:
                    # Parse JSON-kolonner med feilhåndtering
                    for json_col in ["parameters", "changes"]:
                        settings_df[json_col] = settings_df[json_col].apply(
                            lambda x: json.loads(x) if pd.notnull(x) else {}
                        )

                    # Konverter tidsstempler med feilhåndtering
                    datetime_columns = ["timestamp"]
                    if "created_at" in settings_df.columns:
                        datetime_columns.append("created_at")
                    if "updated_at" in settings_df.columns:
                        datetime_columns.append("updated_at")

                    for col in datetime_columns:
                        settings_df[col] = pd.to_datetime(
                            settings_df[col],
                            errors="coerce",  # Håndterer ugyldige datoer
                        )

                    # Konverter numeriske kolonner
                    numeric_columns = {
                        "critical_periods": "Int64",  # Nullable integer
                        "total_duration": "Int64",
                        "avg_risk_score": "float64",
                    }

                    for col, dtype in numeric_columns.items():
                        if col in settings_df.columns:
                            settings_df[col] = pd.to_numeric(
                                settings_df[col], errors="coerce"
                            ).astype(dtype)

                except Exception as e:
                    logger.warning(f"Advarsel: Feil ved datakonvertering: {str(e)}")
                    # Fortsett med resten av dataene selv om noen konverteringer feiler

            return settings_df

    except Exception as e:
        logger.error(f"Kritisk feil ved henting av innstillinger: {e}", exc_info=True)
        return pd.DataFrame(columns=list(required_columns))


def get_period_stats(settings_id: int) -> DataFrame:
    """
    Henter periodestatistikk med forbedret feilhåndtering og typing
    """
    try:
        with get_db_connection() as conn:
            stats_df = pd.read_sql_query(
                """
                SELECT *
                FROM period_stats
                WHERE settings_id = ?
                ORDER BY start_time
            """,
                conn,
                params=[settings_id],
            )

            if not stats_df.empty:
                # Konverter datetime-kolonner
                for col in ["start_time", "end_time", "created_at"]:
                    stats_df[col] = pd.to_datetime(stats_df[col])

            return stats_df

    except Exception as e:
        logger.error(f"Feil ved henting av periodestatistikk: {str(e)}")
        return pd.DataFrame()


def delete_settings(settings_id):
    """Sletter innstillinger og tilhørende periodestatistikk"""
    with get_db_connection() as conn:
        c = conn.cursor()

        try:
            # Slett periodestatistikk først (pga. foreign key constraint)
            c.execute("DELETE FROM period_stats WHERE settings_id = ?", (settings_id,))
            c.execute("DELETE FROM settings WHERE id = ?", (settings_id,))
            conn.commit()
            return True, "Innstillingene ble slettet"

        except Exception as e:
            conn.rollback()
            return False, f"Feil ved sletting: {str(e)}"


def load_settings_parameters(settings_id):
    """Henter parametre for spesifikke innstillinger"""
    with get_db_connection() as conn:
        c = conn.cursor()

        try:
            c.execute("SELECT parameters FROM settings WHERE id = ?", (settings_id,))
            result = c.fetchone()

            if result:
                return json.loads(result[0])
            return None

        except Exception as e:
            logger.error(f"Feil ved lasting av parametre: {str(e)}")
            return None


def create_weather_table():
    """Opprett værtabell med forbedret skjema"""
    with get_db_connection() as conn:
        c = conn.cursor()

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS weather_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                temperature FLOAT,
                precipitation FLOAT,
                wind_speed FLOAT,
                wind_direction FLOAT,
                humidity FLOAT,
                pressure FLOAT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(location, timestamp)
            )
        """
        )

        # Opprett indekser for bedre ytelse
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_weather_location_time ON weather_cache(location, timestamp)"
        )

        conn.commit()


def save_weather_data(weather_data: WeatherData) -> bool:
    """
    Lagrer værdata med forbedret feilhåndtering

    Args:
        weather_data: WeatherData objekt med værinformasjon
    Returns:
        bool: True hvis vellykket, False hvis feil
    """
    try:
        with get_db_connection() as conn:
            c = conn.cursor()

            c.execute(
                """
                INSERT OR REPLACE INTO weather_cache (
                    location, 
                    timestamp, 
                    temperature, 
                    precipitation,
                    wind_speed,
                    wind_direction
                ) VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    weather_data.location,
                    weather_data.timestamp.isoformat(),
                    weather_data.temperature,
                    weather_data.precipitation,
                    weather_data.wind_speed,
                    weather_data.wind_direction,
                ),
            )

            conn.commit()
            return True

    except Exception as e:
        logger.error(f"Feil ved lagring av værdata: {str(e)}")
        return False


@lru_cache(maxsize=128)
def get_cached_weather(location: str, timestamp: datetime) -> Optional[WeatherData]:
    """
    Henter cachet værdata med forbedret ytelse

    Args:
        location: Stedsnavn
        timestamp: Tidspunkt for værdataene
    Returns:
        WeatherData objekt eller None hvis ikke funnet
    """
    try:
        with get_db_connection() as conn:
            c = conn.cursor()

            # Søk med tidsbuffer (±15 minutter)
            time_buffer = timedelta(minutes=15)
            start_time = (timestamp - time_buffer).isoformat()
            end_time = (timestamp + time_buffer).isoformat()

            c.execute(
                """
                SELECT * FROM weather_cache 
                WHERE location = ? 
                AND timestamp BETWEEN ? AND ?
                ORDER BY ABS(STRFTIME('%s', timestamp) - STRFTIME('%s', ?))
                LIMIT 1
            """,
                (location, start_time, end_time, timestamp.isoformat()),
            )

            row = c.fetchone()

            if row:
                return WeatherData(
                    location=row[1],
                    timestamp=datetime.fromisoformat(row[2]),
                    temperature=row[3],
                    precipitation=row[4],
                    wind_speed=row[5],
                    wind_direction=row[6],
                )
            return None

    except Exception as e:
        logger.error(f"Feil ved henting av cachet værdata: {str(e)}")
        return None


def cleanup_old_weather_data(days: int = 7) -> None:
    """
    Rydder opp i gamle værdata

    Args:
        days: Antall dager å beholde data for
    """
    try:
        with get_db_connection() as conn:
            c = conn.cursor()

            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

            c.execute("DELETE FROM weather_cache WHERE timestamp < ?", (cutoff_date,))
            conn.commit()

    except Exception as e:
        logger.error(f"Feil ved opprydding av værdata: {str(e)}")


def safe_dataframe_operations(
    df: DataFrame, operations: Dict[str, Dict[str, Any]] = None
) -> DataFrame:
    """
    Utfører sikre DataFrame-operasjoner med feilhåndtering
    """
    if not isinstance(df, pd.DataFrame):
        logger.error(f"Ugyldig input type: {type(df)}. Forventer DataFrame.")
        return pd.DataFrame()  # Returner tom DataFrame ved ugyldig input

    try:
        # Lag en dyp kopi for å unngå SettingWithCopyWarning
        result_df = df.copy(deep=True)

        if result_df.empty:
            return result_df

        # Fjern duplikate rader
        result_df = result_df.drop_duplicates()

        # Standard kolonner som skal håndteres
        default_fillna = {
            "risk_score": 0,
            "wind_speed": 0,
            "air_temperature": 0,
            "surface_snow_thickness": 0,
        }

        # Håndter manglende verdier for standardkolonner
        for col, value in default_fillna.items():
            if col in result_df.columns:
                result_df.loc[:, col] = result_df[col].fillna(value)

        # Hvis operations er gitt, utfør tilpassede operasjoner
        if operations:
            for col_name, op_info in operations.items():
                try:
                    operation_type = op_info["operation"]

                    if operation_type == "calculate":
                        result_df.loc[:, col_name] = op_info["value"](result_df)

                    elif operation_type == "rolling":
                        base_col = op_info["value"]
                        window_args = op_info.get("args", {"window": 3})
                        agg_func = op_info.get("aggregation", "mean")

                        rolling = result_df[base_col].rolling(**window_args)
                        if hasattr(rolling, agg_func):
                            result_df.loc[:, col_name] = getattr(rolling, agg_func)()
                        else:
                            result_df.loc[:, col_name] = rolling.agg(agg_func)

                    # Håndter NaN-verdier hvis spesifisert
                    if "fillna" in op_info:
                        result_df.loc[:, col_name] = result_df[col_name].fillna(
                            op_info["fillna"]
                        )

                except Exception as e:
                    logger.warning(
                        f"Feil ved prosessering av kolonne {col_name}: {str(e)}"
                    )
                    continue

        return result_df

    except Exception as e:
        error_msg = f"Kritisk feil i safe_dataframe_operations: {str(e)}"
        logger.error(error_msg)
        return pd.DataFrame()
