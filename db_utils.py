# Fil: db_utils.py
# Kategori: Database Functions

import sqlite3
import json
from datetime import datetime, timedelta
import pandas as pd
from dataclasses import dataclass
from contextlib import contextmanager
from typing import Optional, Dict, Tuple, List, Any
import numpy as np
from pandas import DataFrame
from functools import lru_cache
import logging

# Sett opp logging
logging.basicConfig(level=logging.INFO)

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
    conn = sqlite3.connect('snowdrift_settings.db')
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
            c.execute('''
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
            ''')
            
            # Periodestatistikk-tabell med forbedret skjema
            c.execute('''
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
            ''')
            
            # Værtabell med forbedret skjema
            c.execute('''
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
            ''')
            
            # Opprett indekser for bedre ytelse
            c.execute('CREATE INDEX IF NOT EXISTS idx_settings_timestamp ON settings(timestamp)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_period_stats_settings ON period_stats(settings_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_period_stats_time ON period_stats(start_time, end_time)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_weather_location_time ON weather_cache(location, timestamp)')
            
            conn.commit()
            
            # Kjør database migrering
            migration_success, migration_message = migrate_database_schema()
            if not migration_success:
                return False, f"Database initialisert, men migrering feilet: {migration_message}"
            
            return True, "Database initialisert og migrert vellykket"
            
    except Exception as e:
        error_msg = f"Feil ved initialisering av database: {str(e)}"
        print(error_msg)
        import traceback
        print(traceback.format_exc())
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
                'created_at': 'DATETIME',  # Fjernet DEFAULT CURRENT_TIMESTAMP
                'updated_at': 'DATETIME',  # Fjernet DEFAULT CURRENT_TIMESTAMP
                'critical_periods': 'INTEGER',
                'total_duration': 'INTEGER',
                'avg_risk_score': 'REAL'
            }
            
            # Legg til manglende kolonner i settings
            for col_name, col_def in required_columns.items():
                if col_name not in settings_columns:
                    try:
                        c.execute(f'ALTER TABLE settings ADD COLUMN {col_name} {col_def}')
                        # Sett timestamp direkte etter å ha lagt til kolonnen
                        if col_name in ['created_at', 'updated_at']:
                            c.execute(f'''
                                UPDATE settings 
                                SET {col_name} = datetime('now') 
                                WHERE {col_name} IS NULL
                            ''')
                        print(f"Lagt til kolonne: {col_name} i settings")
                    except Exception as e:
                        print(f"Feil ved tillegg av kolonne {col_name}: {str(e)}")
            
            # Sjekk period_stats-tabell
            c.execute("PRAGMA table_info(period_stats)")
            period_stats_columns = {col[1] for col in c.fetchall()}
            
            # Definer påkrevde kolonner for period_stats
            period_stats_required = {
                'created_at': 'DATETIME',
                'avg_wind': 'REAL',
                'wind_direction': 'REAL',
                'precipitation_sum': 'REAL'
            }
            
            # Legg til manglende kolonner i period_stats
            for col_name, col_def in period_stats_required.items():
                if col_name not in period_stats_columns:
                    try:
                        c.execute(f'ALTER TABLE period_stats ADD COLUMN {col_name} {col_def}')
                        print(f"Lagt til kolonne: {col_name} i period_stats")
                    except Exception as e:
                        print(f"Feil ved tillegg av kolonne {col_name}: {str(e)}")
            
            # Oppdater eksisterende rader med standardverdier
            c.execute('''
                UPDATE settings 
                SET created_at = CURRENT_TIMESTAMP 
                WHERE created_at IS NULL
            ''')
            
            c.execute('''
                UPDATE settings 
                SET updated_at = CURRENT_TIMESTAMP 
                WHERE updated_at IS NULL
            ''')
            
            conn.commit()
            return True, "Database migrering fullført"
            
    except Exception as e:
        return False, f"Feil under database migrering: {str(e)}"

def save_settings(settings_data: Dict[str, Any], critical_periods_df: DataFrame) -> Tuple[bool, str]:
    """
    Lagrer innstillinger og periodestatistikk med forbedret feilhåndtering
    """
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Valider påkrevde felt
            required_fields = {'name', 'description', 'timestamp', 'parameters'}
            missing_fields = required_fields - settings_data.keys()
            if missing_fields:
                raise ValueError(f"Mangler påkrevde felt: {', '.join(missing_fields)}")
            
            # Beregn statistikk sikkert
            total_duration = int(critical_periods_df['duration'].sum()) if not critical_periods_df.empty else 0
            avg_risk_score = float(critical_periods_df['max_risk_score'].mean()) if not critical_periods_df.empty else 0.0
            num_periods = len(critical_periods_df)
            
            # Sett inn innstillinger
            c.execute('''
                INSERT INTO settings 
                (name, description, timestamp, parameters, changes, 
                 critical_periods, total_duration, avg_risk_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                settings_data['name'],
                settings_data['description'],
                settings_data['timestamp'],
                json.dumps(settings_data['parameters']),
                json.dumps(settings_data.get('changes', [])),
                num_periods,
                total_duration,
                avg_risk_score
            ))
            
            settings_id = c.lastrowid
            
            # Lagre statistikk for hver kritisk periode
            if not critical_periods_df.empty:
                for idx, period in critical_periods_df.iterrows():
                    try:
                        c.execute('''
                            INSERT INTO period_stats
                            (settings_id, start_time, end_time, duration, 
                             max_risk_score, max_wind, min_temp, max_snow_change)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            settings_id,
                            period['start_time'].isoformat(),
                            period['end_time'].isoformat(),
                            int(period['duration']),
                            float(period['max_risk_score']),
                            float(period.get('max_wind', 0)),
                            float(period.get('min_temp', 0)),
                            float(period.get('max_snow_change', 0))
                        ))
                    except Exception as e:
                        raise ValueError(f"Error saving period data: {str(e)}")
            
            conn.commit()
            return True, "Innstillingene ble lagret!"
            
    except Exception as e:
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
                'id', 'name', 'description', 'timestamp',
                'parameters', 'changes'
            }
            
            optional_columns = {
                'critical_periods', 'total_duration', 'avg_risk_score',
                'created_at', 'updated_at'
            }
            
            # Valider at alle påkrevde kolonner eksisterer
            missing_required = required_columns - available_columns
            if missing_required:
                raise ValueError(f"Mangler påkrevde kolonner i settings-tabell: {missing_required}")
            
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
                    for json_col in ['parameters', 'changes']:
                        settings_df[json_col] = settings_df[json_col].apply(
                            lambda x: json.loads(x) if pd.notnull(x) else {}
                        )
                    
                    # Konverter tidsstempler med feilhåndtering
                    datetime_columns = ['timestamp']
                    if 'created_at' in settings_df.columns:
                        datetime_columns.append('created_at')
                    if 'updated_at' in settings_df.columns:
                        datetime_columns.append('updated_at')
                    
                    for col in datetime_columns:
                        settings_df[col] = pd.to_datetime(
                            settings_df[col], 
                            errors='coerce'  # Håndterer ugyldige datoer
                        )
                    
                    # Konverter numeriske kolonner
                    numeric_columns = {
                        'critical_periods': 'Int64',  # Nullable integer
                        'total_duration': 'Int64',
                        'avg_risk_score': 'float64'
                    }
                    
                    for col, dtype in numeric_columns.items():
                        if col in settings_df.columns:
                            settings_df[col] = pd.to_numeric(
                                settings_df[col], 
                                errors='coerce'
                            ).astype(dtype)
                    
                except Exception as e:
                    print(f"Advarsel: Feil ved datakonvertering: {str(e)}")
                    # Fortsett med resten av dataene selv om noen konverteringer feiler
            
            return settings_df
            
    except Exception as e:
        print(f"Kritisk feil ved henting av innstillinger: {str(e)}")
        import traceback
        print(traceback.format_exc())
        # Returner tom DataFrame med forventede kolonner
        return pd.DataFrame(columns=list(required_columns))

def get_period_stats(settings_id: int) -> DataFrame:
    """
    Henter periodestatistikk med forbedret feilhåndtering og typing
    """
    try:
        with get_db_connection() as conn:
            stats_df = pd.read_sql_query('''
                SELECT *
                FROM period_stats
                WHERE settings_id = ?
                ORDER BY start_time
            ''', conn, params=[settings_id])
            
            if not stats_df.empty:
                # Konverter datetime-kolonner
                for col in ['start_time', 'end_time', 'created_at']:
                    stats_df[col] = pd.to_datetime(stats_df[col])
            
            return stats_df
            
    except Exception as e:
        print(f"Feil ved henting av periodestatistikk: {str(e)}")
        return pd.DataFrame()

def delete_settings(settings_id):
    """Sletter innstillinger og tilhørende periodestatistikk"""
    with get_db_connection() as conn:
        c = conn.cursor()
        
        try:
            # Slett periodestatistikk først (pga. foreign key constraint)
            c.execute('DELETE FROM period_stats WHERE settings_id = ?', (settings_id,))
            c.execute('DELETE FROM settings WHERE id = ?', (settings_id,))
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
            c.execute('SELECT parameters FROM settings WHERE id = ?', (settings_id,))
            result = c.fetchone()
            
            if result:
                return json.loads(result[0])
            return None
            
        except Exception as e:
            print(f"Feil ved lasting av parametre: {str(e)}")
            return None

def debug_database():
    """Debug-funksjon for å sjekke databaseinnhold direkte"""
    with get_db_connection() as conn:
        c = conn.cursor()
        
        try:
            # Sjekk settings-tabellen
            c.execute("SELECT COUNT(*) FROM settings")
            settings_count = c.fetchone()[0]
            
            if settings_count == 0:
                return  # Avslutt stille hvis ingen data finnes
                
            # Fortsett med debug-utskrift hvis det finnes data
            print("\n=== Settings Table ===")
            c.execute("SELECT * FROM settings")
            settings = c.fetchall()
            for row in settings:
                print(f"\nID: {row[0]}")
                print(f"Name: {row[1]}")
                print(f"Description: {row[2]}")
                print(f"Timestamp: {row[3]}")
                
            # Sjekk period_stats-tabellen
            c.execute("SELECT COUNT(*) FROM period_stats")
            stats_count = c.fetchone()[0]
            
            if stats_count > 0:
                print("\n=== Period Stats Table ===")
                c.execute("SELECT * FROM period_stats")
                stats = c.fetchall()
                for row in stats:
                    print(f"\nID: {row[0]}")
                    print(f"Settings ID: {row[1]}")
                    print(f"Start Time: {row[2]}")
                    print(f"End Time: {row[3]}")
                
        except Exception as e:
            print(f"Debug error: {str(e)}")

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
            'wind_dir_change': {
                'operation': 'calculate',
                'value': lambda x: x['wind_direction'].diff(),
                'fillna': 0.0
            },
            'max_dir_change': {
                'operation': 'rolling',
                'value': 'wind_dir_change',
                'args': {'window': 3, 'center': True, 'min_periods': 1},
                'aggregation': 'max',
                'fillna': 0.0
            },
            'wind_dir_stability': {
                'operation': 'rolling',
                'value': 'wind_dir_change',
                'args': {'window': 3, 'center': True, 'min_periods': 1},
                'aggregation': 'std',
                'fillna': 0.0
            },
            'significant_dir_change': {
                'operation': 'calculate',
                'value': lambda x: x['wind_dir_change'] > 45
            },
            'wind_pattern': {
                'operation': 'calculate',
                'value': lambda x: x.apply(
                    lambda row: 'ustabil' if row['wind_dir_stability'] > 30
                    else 'skiftende' if row['wind_dir_change'] > 45
                    else 'stabil' if row['wind_dir_stability'] < 10
                    else 'moderat', axis=1
                )
            }
        }
        
        # Utfør alle operasjoner sikkert
        result_df = safe_dataframe_operations(df, operations)
        
        # Legg til statistiske indikatorer hvis det er mer enn én rad
        if len(result_df) > 1:
            additional_ops = {
                'direction_trend': {
                    'operation': 'rolling',
                    'value': 'wind_direction',
                    'args': {'window': 3, 'min_periods': 1},
                    'aggregation': 'mean'
                },
                'significant_changes_pct': {
                    'operation': 'calculate',
                    'value': lambda x: (x['significant_dir_change'].sum() / len(x) * 100)
                }
            }
            result_df = safe_dataframe_operations(result_df, additional_ops)
        
        return result_df
        
    except Exception as e:
        logging.error(f"Feil i vindretningsanalyse: {str(e)}", exc_info=True)
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
        if 'wind_direction' not in df.columns:
            return None
            
        # Lag en sikker kopi av DataFrame
        analysis_df = df.copy()
        
        # Definer hovedretninger (N, NØ, Ø, osv.)
        directions = {
            'N': (337.5, 22.5),
            'NØ': (22.5, 67.5),
            'Ø': (67.5, 112.5),
            'SØ': (112.5, 157.5),
            'S': (157.5, 202.5),
            'SV': (202.5, 247.5),
            'V': (247.5, 292.5),
            'NV': (292.5, 337.5)
        }
        
        # Kategoriser hver vindretning
        def categorize_direction(angle):
            angle = angle % 360
            for name, (start, end) in directions.items():
                if start <= angle < end or (name == 'N' and (angle >= 337.5 or angle < 22.5)):
                    return name
            return 'N'  # Fallback
        
        # Bruk loc for å unngå SettingWithCopyWarning
        analysis_df.loc[:, 'direction_category'] = analysis_df['wind_direction'].apply(categorize_direction)
        
        # Analyser fordeling av vindretninger
        direction_counts = analysis_df['direction_category'].value_counts()
        total_periods = len(analysis_df)
        
        # Beregn gjennomsnittlig risikoscore for hver retning
        direction_risk = analysis_df.groupby('direction_category')['max_risk_score'].mean()
        
        # Beregn gjennomsnittlig vindstyrke for hver retning
        direction_wind = analysis_df.groupby('direction_category')['max_wind'].mean()
        
        # Finn dominerende retninger (over 15% av tilfellene eller høy risikoscore)
        significant_directions = []
        for direction in direction_counts.index:
            percentage = (direction_counts[direction] / total_periods) * 100
            avg_risk = direction_risk[direction]
            avg_wind = direction_wind[direction]
            
            if percentage > 15 or avg_risk > 70:
                significant_directions.append({
                    'direction': direction,
                    'percentage': percentage,
                    'avg_risk': avg_risk,
                    'avg_wind': avg_wind
                })
        
        return {
            'counts': direction_counts.to_dict(),
            'risk_scores': direction_risk.to_dict(),
            'wind_speeds': direction_wind.to_dict(),
            'significant': significant_directions
        }
        
    except Exception as e:
        logging.error(f"Feil i vindretningsanalyse: {str(e)}")
        return None

def analyze_settings(params, critical_periods_df, DEFAULT_PARAMS):
    """
    Utfører avansert AI-analyse av parameterinnstillingene og deres effektivitet
    """
    try:
        analysis = {
            'parameter_changes': [],
            'impact_analysis': [],
            'suggestions': [],
            'meteorological_context': []
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
                percent_change = ((current_value - default_value) / abs(default_value)) * 100
            
            if abs(percent_change) >= 10:  # Bare rapporter betydelige endringer
                change_type = "økning" if percent_change > 0 else "reduksjon"
                
                # Forbedret parametertype-beskrivelse
                param_description = {
                    'wind_strong': 'Sterk vind',
                    'wind_moderate': 'Moderat vind',
                    'wind_gust': 'Vindkast terskel',
                    'wind_dir_change': 'Vindretningsendring',
                    'wind_weight': 'Vindvekt',
                    'temp_cold': 'Kald temperatur',
                    'temp_cool': 'Kjølig temperatur',
                    'temp_weight': 'Temperaturvekt',
                    'snow_high': 'Høy snøendring',
                    'snow_moderate': 'Moderat snøendring',
                    'snow_low': 'Lav snøendring',
                    'snow_weight': 'Snøvekt',
                    'min_duration': 'Minimum varighet'
                }.get(param_name, param_name)
                
                analysis['parameter_changes'].append({
                    'description': f"{param_description}: {abs(percent_change):.1f}% {change_type} "
                                 f"fra standard ({default_value} → {current_value})",
                    'importance': 'høy' if abs(percent_change) > 25 else 'moderat'
                })

        # 2. Analyser kritiske perioder
        if not critical_periods_df.empty:
            # Beregn nøkkelstatistikk
            avg_duration = critical_periods_df['duration'].mean()
            avg_risk = critical_periods_df['max_risk_score'].mean()
            max_wind = critical_periods_df['max_wind'].max() if 'max_wind' in critical_periods_df.columns else 0
            min_temp = critical_periods_df['min_temp'].min() if 'min_temp' in critical_periods_df.columns else 0
            
            # Legg til viktige observasjoner
            if avg_duration > 4:
                analysis['impact_analysis'].append({
                    'description': f"Lange kritiske perioder (snitt {avg_duration:.1f} timer) "
                                 f"indikerer vedvarende risikotilstander",
                    'importance': 'høy'
                })
            
            if avg_risk > 80:
                analysis['impact_analysis'].append({
                    'description': f"Høy gjennomsnittlig risikoscore ({avg_risk:.1f}) "
                                 f"tyder på alvorlige forhold under kritiske perioder",
                    'importance': 'høy'
                })

            # 3. Analyser vindretninger
            if 'wind_direction' in critical_periods_df.columns:
                wind_dir_analysis = analyze_wind_directions(critical_periods_df)
                if wind_dir_analysis and wind_dir_analysis.get('significant'):
                    for dir_info in wind_dir_analysis['significant']:
                        analysis['impact_analysis'].append({
                            'description': (
                                f"Vind fra {dir_info['direction']} er betydelig: "
                                f"Forekommer i {dir_info['percentage']:.1f}% av tilfellene "
                                f"med snittrisiko {dir_info['avg_risk']:.1f} "
                                f"og vindstyrke {dir_info['avg_wind']:.1f} m/s"
                            ),
                            'importance': 'høy' if dir_info['avg_risk'] > 70 else 'moderat'
                        })
        # 4. Generer forslag basert på analysen
        if 'max_wind' in critical_periods_df.columns and params['wind_weight'] < 1.0 and max_wind > params['wind_strong']:
            analysis['suggestions'].append(
                "Vurder å øke vindvekten da det observeres sterke vindforhold"
            )
            
        if 'min_temp' in critical_periods_df.columns and params['temp_weight'] < 1.0 and min_temp < params['temp_cold']:
            analysis['suggestions'].append(
                "Vurder å øke temperaturvekten da det observeres svært kalde forhold"
            )
            
        if avg_duration < 2:
            analysis['suggestions'].append(
                "Vurder å redusere minimum varighet for å fange opp kortere hendelser"
            )

        # 5. Legg til meteorologisk kontekst
        if not critical_periods_df.empty:
            analysis['meteorological_context'].append(
                f"Analysen er basert på {len(critical_periods_df)} kritiske perioder "
                f"med gjennomsnittlig varighet på {avg_duration:.1f} timer og "
                f"gjennomsnittlig risikoscore på {avg_risk:.1f}"
            )
            
            if 'wind_direction' in critical_periods_df.columns:
                wind_dir_analysis = analyze_wind_directions(critical_periods_df)
                if wind_dir_analysis and wind_dir_analysis.get('significant'):
                    dominant_dirs = [d['direction'] for d in wind_dir_analysis['significant']]
                    analysis['meteorological_context'].append(
                        f"Dominerende vindretninger under kritiske perioder: {', '.join(dominant_dirs)}. "
                        "Dette kan indikere spesielt utsatte områder i disse retningene."
                    )

        return analysis

    except Exception as e:
        print(f"Feil i analyse av innstillinger: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None

def create_weather_table():
    """Opprett værtabell med forbedret skjema"""
    with get_db_connection() as conn:
        c = conn.cursor()
        
        c.execute('''
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
        ''')
        
        # Opprett indekser for bedre ytelse
        c.execute('CREATE INDEX IF NOT EXISTS idx_weather_location_time ON weather_cache(location, timestamp)')
        
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
            
            c.execute('''
                INSERT OR REPLACE INTO weather_cache (
                    location, 
                    timestamp, 
                    temperature, 
                    precipitation,
                    wind_speed,
                    wind_direction
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                weather_data.location,
                weather_data.timestamp.isoformat(),
                weather_data.temperature,
                weather_data.precipitation,
                weather_data.wind_speed,
                weather_data.wind_direction
            ))
            
            conn.commit()
            return True
            
    except Exception as e:
        print(f"Feil ved lagring av værdata: {str(e)}")
        return False

def analyze_weather_patterns(df: DataFrame) -> Dict[str, Any]:
    """
    Analyserer værmønstre i kritiske perioder
    
    Args:
        df: DataFrame med værdata
    Returns:
        Dict med analyseresultater
    """
    try:
        if df.empty:
            return {'temperature': {}, 'wind': {}, 'precipitation': {}, 'patterns': []}
            
        # Beregn rullende statistikk for relevante kolonner
        stats_df = create_rolling_stats(
            df,
            columns=['temperature', 'wind_speed', 'precipitation'],
            windows=[3, 6, 12],  # 3, 6, og 12 timers vinduer
            stats=['mean', 'std']
        )
        
        analysis = {
            'temperature': {},
            'wind': {},
            'precipitation': {},
            'patterns': []
        }
        
        # Temperaturanalyse
        analysis['temperature'] = {
            'mean': df['temperature'].mean(),
            'min': df['temperature'].min(),
            'max': df['temperature'].max(),
            'std': df['temperature'].std()
        }
        
        # Vindanalyse
        analysis['wind'] = {
            'mean_speed': df['wind_speed'].mean(),
            'max_speed': df['wind_speed'].max(),
            'dominant_direction': df['wind_direction'].mode().iloc[0] if 'wind_direction' in df else None
        }
        
        # Nedbørsanalyse
        if 'precipitation' in df:
            analysis['precipitation'] = {
                'total': df['precipitation'].sum(),
                'max_intensity': df['precipitation'].max()
            }
        
        # Identifiser mønstre
        if len(df) > 24:  # Minst 24 timer med data
            # Døgnvariasjoner
            df['hour'] = df['timestamp'].dt.hour
            hourly_temps = df.groupby('hour')['temperature'].mean()
            
            # Finn kaldeste og varmeste tidspunkt
            coldest_hour = hourly_temps.idxmin()
            warmest_hour = hourly_temps.idxmax()
            
            analysis['patterns'].append({
                'type': 'daily_cycle',
                'coldest_hour': coldest_hour,
                'warmest_hour': warmest_hour,
                'temperature_range': hourly_temps.max() - hourly_temps.min()
            })
        
        return analysis
        
    except Exception as e:
        logging.error(f"Feil i væranalyse: {str(e)}")
        return {}

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
            
            c.execute('''
                SELECT * FROM weather_cache 
                WHERE location = ? 
                AND timestamp BETWEEN ? AND ?
                ORDER BY ABS(STRFTIME('%s', timestamp) - STRFTIME('%s', ?))
                LIMIT 1
            ''', (location, start_time, end_time, timestamp.isoformat()))
            
            row = c.fetchone()
            
            if row:
                return WeatherData(
                    location=row[1],
                    timestamp=datetime.fromisoformat(row[2]),
                    temperature=row[3],
                    precipitation=row[4],
                    wind_speed=row[5],
                    wind_direction=row[6]
                )
            return None
            
    except Exception as e:
        print(f"Feil ved henting av cachet værdata: {str(e)}")
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
            
            c.execute('DELETE FROM weather_cache WHERE timestamp < ?', (cutoff_date,))
            conn.commit()
            
    except Exception as e:
        print(f"Feil ved opprydding av værdata: {str(e)}")

from typing import Dict, Any, Tuple, Union
import pandas as pd
import logging
from pandas import DataFrame

def safe_dataframe_operations(
    df: DataFrame,
    operations: Dict[str, Dict[str, Any]] = None
) -> DataFrame:
    """
    Utfører sikre DataFrame-operasjoner med feilhåndtering
    """
    if not isinstance(df, pd.DataFrame):
        logging.error(f"Ugyldig input type: {type(df)}. Forventer DataFrame.")
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
            'risk_score': 0,
            'wind_speed': 0,
            'air_temperature': 0,
            'surface_snow_thickness': 0
        }
        
        # Håndter manglende verdier for standardkolonner
        for col, value in default_fillna.items():
            if col in result_df.columns:
                result_df.loc[:, col] = result_df[col].fillna(value)
        
        # Hvis operations er gitt, utfør tilpassede operasjoner
        if operations:
            for col_name, op_info in operations.items():
                try:
                    operation_type = op_info['operation']
                    
                    if operation_type == 'calculate':
                        result_df.loc[:, col_name] = op_info['value'](result_df)
                        
                    elif operation_type == 'rolling':
                        base_col = op_info['value']
                        window_args = op_info.get('args', {'window': 3})
                        agg_func = op_info.get('aggregation', 'mean')
                        
                        rolling = result_df[base_col].rolling(**window_args)
                        if hasattr(rolling, agg_func):
                            result_df.loc[:, col_name] = getattr(rolling, agg_func)()
                        else:
                            result_df.loc[:, col_name] = rolling.agg(agg_func)
                    
                    # Håndter NaN-verdier hvis spesifisert
                    if 'fillna' in op_info:
                        result_df.loc[:, col_name] = result_df[col_name].fillna(op_info['fillna'])
                        
                except Exception as e:
                    logging.warning(f"Feil ved prosessering av kolonne {col_name}: {str(e)}")
                    continue
        
        return result_df
        
    except Exception as e:
        error_msg = f"Kritisk feil i safe_dataframe_operations: {str(e)}"
        logging.error(error_msg)
        return pd.DataFrame()

def create_rolling_stats(df: DataFrame, 
                        columns: List[str], 
                        windows: List[int], 
                        stats: List[str]) -> DataFrame:
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