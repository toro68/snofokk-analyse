# Fil: db_utils.py
# Kategori: Database Functions

import sqlite3
import json
from datetime import datetime
import pandas as pd

def init_db():
    """Initialiserer databasen med nødvendige tabeller"""
    conn = sqlite3.connect('snowdrift_settings.db')
    c = conn.cursor()
    
    # Hovedtabell for innstillinger
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            timestamp TEXT NOT NULL,
            parameters JSON NOT NULL,
            changes JSON,
            critical_periods INTEGER,
            total_duration INTEGER,
            avg_risk_score REAL
        )
    ''')
    
    # Tabell for å lagre statistikk for hver periode
    c.execute('''
        CREATE TABLE IF NOT EXISTS period_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            settings_id INTEGER,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            duration INTEGER NOT NULL,
            max_risk_score REAL NOT NULL,
            max_wind REAL,
            min_temp REAL,
            max_snow_change REAL,
            FOREIGN KEY (settings_id) REFERENCES settings (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def save_settings(settings_data, critical_periods_df):
    """
    Lagrer innstillinger og periodestatistikk i databasen
    
    Args:
        settings_data: Dict med innstillingsinformasjon
        critical_periods_df: DataFrame med kritiske perioder
    """
    conn = sqlite3.connect('snowdrift_settings.db')
    c = conn.cursor()
    
    try:
        # Debug: Skriv ut innkommende data
        print("\nDebug - Innkommende data:")
        print(f"Settings data: {settings_data}")
        print(f"Critical periods shape: {critical_periods_df.shape}")

        # Sjekk at nødvendige felter eksisterer
        required_fields = ['name', 'description', 'timestamp', 'parameters']
        missing_fields = [field for field in required_fields if field not in settings_data]
        if missing_fields:
            raise ValueError(f"Manglende felt: {', '.join(missing_fields)}")

        # Konverter parameters og changes til JSON-strenger
        parameters_json = json.dumps(settings_data['parameters'])
        changes_json = json.dumps(settings_data.get('changes', []))

        # Debug: Skriv ut SQL-verdier før innsetting
        print("\nDebug - Verdier som skal settes inn:")
        print(f"Name: {settings_data['name']}")
        print(f"Description: {settings_data['description']}")
        print(f"Timestamp: {settings_data['timestamp']}")
        print(f"Parameters: {parameters_json[:100]}...")  # Vis bare starten av JSON

        # Beregn statistikk
        total_duration = int(critical_periods_df['duration'].sum()) if not critical_periods_df.empty else 0
        avg_risk_score = float(critical_periods_df['max_risk_score'].mean()) if not critical_periods_df.empty else 0.0
        num_periods = len(critical_periods_df)

        # Lagre hovedinnstillingene
        c.execute('''
            INSERT INTO settings 
            (name, description, timestamp, parameters, changes, 
             critical_periods, total_duration, avg_risk_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            settings_data['name'],
            settings_data['description'],
            settings_data['timestamp'],
            parameters_json,
            changes_json,
            num_periods,
            total_duration,
            avg_risk_score
        ))
        
        # Hent ID for de nylig lagrede innstillingene
        settings_id = c.lastrowid
        print(f"\nDebug - Ny settings_id: {settings_id}")

        # Legg til debug-utskrift for critical_periods_df
        print("\nDebug - Critical Periods Data:")
        if not critical_periods_df.empty:
            print(critical_periods_df.head())
            print("\nKolonner i DataFrame:")
            print(critical_periods_df.columns.tolist())
            print("\nDatatyper:")
            print(critical_periods_df.dtypes)

        # Lagre statistikk for hver kritisk periode
        if not critical_periods_df.empty:
            for idx, period in critical_periods_df.iterrows():
                try:
                    # Debug: Skriv ut verdiene som skal settes inn
                    print(f"\nInserting period {idx}:")
                    print(f"settings_id: {settings_id}")
                    print(f"start_time: {period['start_time']}")
                    print(f"end_time: {period['end_time']}")
                    print(f"duration: {period['duration']}")
                    print(f"max_risk_score: {period['max_risk_score']}")
                    print(f"max_wind: {period.get('max_wind', 0)}")
                    print(f"min_temp: {period.get('min_temp', 0)}")
                    print(f"max_snow_change: {period.get('max_snow_change', 0)}")

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
                    print(f"Detaljert feil ved lagring av periode {idx}: {str(e)}")
                    print(f"Period data: {period.to_dict()}")
                    raise

        # Commit endringene
        conn.commit()
        print("\nDebug - Vellykket lagring, utfører commit")
        
        # Verifiser at dataene ble lagret
        c.execute("SELECT COUNT(*) FROM settings WHERE id = ?", (settings_id,))
        count = c.fetchone()[0]
        if count == 0:
            raise Exception("Verifisering feilet: Fant ikke lagrede innstillinger")

        return True, "Innstillingene ble lagret!"
        
    except Exception as e:
        conn.rollback()
        print(f"\nDebug - Feil ved lagring: {str(e)}")
        return False, f"Feil ved lagring: {str(e)}"
        
    finally:
        conn.close()

def get_saved_settings():
    """Henter alle lagrede innstillinger"""
    conn = sqlite3.connect('snowdrift_settings.db')
    
    try:
        # Sjekk først om det finnes data i tabellen
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM settings")
        count = c.fetchone()[0]
        
        # Hvis ingen innstillinger finnes, returner tom DataFrame uten debugmeldinger
        if count == 0:
            return pd.DataFrame()
        
        # Hent hovedinnstillingene hvis de finnes
        settings_df = pd.read_sql_query('''
            SELECT 
                id,
                name,
                description,
                timestamp,
                parameters,
                changes,
                critical_periods,
                total_duration,
                avg_risk_score
            FROM settings
            ORDER BY timestamp DESC
        ''', conn)
        
        # Konverter JSON-strenger tilbake til Python objekter
        settings_df['parameters'] = settings_df['parameters'].apply(json.loads)
        settings_df['changes'] = settings_df['changes'].apply(json.loads)
        
        return settings_df
        
    except Exception as e:
        # Logg feilen mer diskret
        print(f"Database error: {str(e)}")
        return pd.DataFrame()
    finally:
        conn.close()

def get_period_stats(settings_id):
    """Henter statistikk for alle perioder tilknyttet gitte innstillinger"""
    conn = sqlite3.connect('snowdrift_settings.db')
    
    try:
        stats_df = pd.read_sql_query('''
            SELECT *
            FROM period_stats
            WHERE settings_id = ?
            ORDER BY start_time
        ''', conn, params=[settings_id])
        
        # Konverter tidspunkt-strenger til datetime
        stats_df['start_time'] = pd.to_datetime(stats_df['start_time'])
        stats_df['end_time'] = pd.to_datetime(stats_df['end_time'])
        
        return stats_df
        
    except Exception as e:
        print(f"Feil ved henting av periodestatistikk: {str(e)}")
        return pd.DataFrame()
        
    finally:
        conn.close()

def delete_settings(settings_id):
    """Sletter innstillinger og tilhørende periodestatistikk"""
    conn = sqlite3.connect('snowdrift_settings.db')
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
        
    finally:
        conn.close()

def load_settings_parameters(settings_id):
    """Henter parametre for spesifikke innstillinger"""
    conn = sqlite3.connect('snowdrift_settings.db')
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
        
    finally:
        conn.close()

def debug_database():
    """Debug-funksjon for å sjekke databaseinnhold direkte"""
    conn = sqlite3.connect('snowdrift_settings.db')
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
    finally:
        conn.close()

def calculate_wind_direction_change(dir1, dir2):
    """
    Beregner den minste vinkelendringen mellom to vindretninger
    
    Args:
        dir1, dir2: Vindretninger i grader (0-360)
    Returns:
        Minste vinkelendring i grader (0-180)
    """
    diff = abs(dir1 - dir2)
    return min(diff, 360 - diff)

def preprocess_critical_periods(df):
    """
    Forbehandler kritiske perioder med beregning av vindretningsendringer
    """
    if df.empty:
        return df
        
    try:
        # Lag en eksplisitt kopi av DataFrame
        df = df.copy(deep=True)
        
        # Sjekk om nødvendige kolonner eksisterer
        required_cols = ['wind_direction', 'start_time']
        if not all(col in df.columns for col in required_cols):
            print("Mangler nødvendige kolonner for vindretningsanalyse")
            return df

        # Sorter etter starttidspunkt og reset index
        df = df.sort_values('start_time').reset_index(drop=True)
        
        # Initialiser nye kolonner med .loc
        df.loc[:, 'wind_dir_change'] = 0.0
        df.loc[:, 'max_dir_change'] = 0.0
        df.loc[:, 'significant_dir_change'] = False
        
        # Beregn endring fra forrige periode
        for i in range(1, len(df)):
            prev_dir = df.loc[i-1, 'wind_direction']
            curr_dir = df.loc[i, 'wind_direction']
            df.loc[i, 'wind_dir_change'] = calculate_wind_direction_change(prev_dir, curr_dir)
        
        # Beregn rullende statistikk
        df.loc[:, 'max_dir_change'] = df['wind_dir_change'].rolling(
            window=3, center=True, min_periods=1).max()
        
        # Sett significant_dir_change med .loc
        df.loc[:, 'significant_dir_change'] = df['wind_dir_change'] > 45
        
        # Statistikk utskrift
        print("\nVindretningsstatistikk:")
        print(f"Gjennomsnittlig endring: {df['wind_dir_change'].mean():.1f}°")
        print(f"Maksimal endring: {df['wind_dir_change'].max():.1f}°")
        print(f"Andel betydelige endringer: {(df['significant_dir_change'].mean() * 100):.1f}%")
        
        return df
        
    except Exception as e:
        print(f"Feil i vindretningsberegning: {str(e)}")
        return df

def analyze_wind_directions(df):
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
        
        df['direction_category'] = df['wind_direction'].apply(categorize_direction)
        
        # Analyser fordeling av vindretninger
        direction_counts = df['direction_category'].value_counts()
        total_periods = len(df)
        
        # Beregn gjennomsnittlig risikoscore for hver retning
        direction_risk = df.groupby('direction_category')['max_risk_score'].mean()
        
        # Beregn gjennomsnittlig vindstyrke for hver retning
        direction_wind = df.groupby('direction_category')['max_wind'].mean()
        
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
        print(f"Feil i vindretningsanalyse: {str(e)}")
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
        
        # Analyser vindretninger
        wind_dir_analysis = analyze_wind_directions(critical_periods_df)
        if wind_dir_analysis and wind_dir_analysis['significant']:
            # Legg til vindretningsanalyse i impact_analysis
            direction_desc = []
            for dir_info in wind_dir_analysis['significant']:
                direction_desc.append({
                    'importance': 'høy' if dir_info['avg_risk'] > 70 else 'moderat',
                    'description': (
                        f"Vind fra {dir_info['direction']} forekommer i {dir_info['percentage']:.1f}% "
                        f"av tilfellene med gjennomsnittlig risikoscore på {dir_info['avg_risk']:.1f} "
                        f"og vindstyrke på {dir_info['avg_wind']:.1f} m/s"
                    )
                })
            analysis['impact_analysis'].extend(direction_desc)
            
            # Legg til i meteorologisk kontekst
            dominant_dirs = [d['direction'] for d in wind_dir_analysis['significant']]
            analysis['meteorological_context'].append(
                f"Snøfokk forekommer hyppigst med vind fra {', '.join(dominant_dirs)}. "
                "Dette kan indikere spesielt utsatte områder i denne retningen eller "
                "topografiske forhold som forsterker effekten av vind fra disse retningene."
            )
            
            # Legg til eventuelle forslag
            if len(dominant_dirs) <= 2:
                analysis['suggestions'].append(
                    "Snøfokk ser ut til å være sterkt retningsavhengig. "
                    "Vurder å tilpasse varsling spesielt for disse vindretningene."
                )
        
        # ... resten av eksisterende analyse ...
        
        return analysis
        
    except Exception as e:
        print(f"Feil i analyse av innstillinger: {str(e)}")
        return None