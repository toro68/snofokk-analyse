import pandas as pd
import pytest
from data.src.snofokk.db_utils import clean_dataframe, validate_dataframe, get_period_summary
from datetime import datetime, timedelta

def test_clean_dataframe():
    # Opprett test DataFrame
    test_data = {
        'wind_speed': ['10.5', '15.2', 'invalid', '12.3', '10.5'],  # Merk: duplisert verdi og ugyldig verdi
        'temperature': ['-2.1', '0.0', '1.5', 'error', '-2.1'],     # Merk: duplisert verdi og feil
        'snow_depth': ['50', '55', '60', '65', '50']                # Merk: duplisert verdi
    }
    test_df = pd.DataFrame(test_data)
    
    # Test funksjonen
    numeric_columns = ['wind_speed', 'temperature', 'snow_depth']
    cleaned_df = clean_dataframe(test_df, numeric_columns)
    
    # Sjekk resultater
    assert len(cleaned_df) < len(test_df), "Skulle ha fjernet duplikate rader"
    assert all(cleaned_df.dtypes == 'float64'), "Alle kolonner skulle vært konvertert til float64"
    assert cleaned_df['wind_speed'].isna().sum() == 1, "Skulle ha én NaN-verdi i wind_speed"
    assert cleaned_df['temperature'].isna().sum() == 1, "Skulle ha én NaN-verdi i temperature"

def test_validate_dataframe():
    # Test med gyldig DataFrame
    valid_df = pd.DataFrame({
        'col1': [1, 2, 3],
        'col2': ['a', 'b', 'c']
    })
    success, message = validate_dataframe(valid_df, ['col1', 'col2'])
    assert success, "Validering skulle lykkes med gyldig DataFrame"
    
    # Test med manglende kolonner
    success, message = validate_dataframe(valid_df, ['col1', 'col2', 'col3'])
    assert not success, "Validering skulle feile med manglende kolonne"
    assert "Mangler påkrevde kolonner" in message
    
    # Test med tomt DataFrame
    empty_df = pd.DataFrame()
    success, message = validate_dataframe(empty_df, ['col1'])
    assert not success, "Validering skulle feile med tomt DataFrame"
    assert "DataFrame er tomt" in message

    # Test med None input
    success, message = validate_dataframe(None, ['col1'])
    assert not success, "Validering skulle feile med None input"
    assert "Ugyldig DataFrame" in message

    # Test med DataFrame som har null-verdier
    null_df = pd.DataFrame({
        'col1': [1, None, 3],
        'col2': ['a', 'b', None]
    })
    success, message = validate_dataframe(null_df, ['col1', 'col2'])
    assert success, "Validering skulle lykkes med null-verdier"
    
    # Test med tom kolonneliste
    success, message = validate_dataframe(valid_df, [])
    assert not success, "Validering skulle feile med tom kolonneliste"
    assert "Ingen kolonner spesifisert" in message

def test_validate_dataframe_snow_depth():
    # Test DataFrame med negative snødybdeverdier
    snow_df = pd.DataFrame({
        'snow_depth': [10.0, -1.0, 0.0, 15.0, -1.0],  # -1.0 indikerer bar bakke
        'temperature': [-2.1, 0.0, 1.5, -1.0, 0.5],
        'wind_speed': [10.5, 15.2, 12.3, 11.1, 13.4]
    })
    
    # Test validering med snødybde
    success, message = validate_dataframe(snow_df, ['snow_depth', 'temperature', 'wind_speed'])
    assert success, "Validering skulle lykkes med negative snødybdeverdier"
    
    # Test at -1.0 verdier blir håndtert korrekt
    cleaned_df = clean_dataframe(snow_df, numeric_columns=['snow_depth'])
    assert all(cleaned_df['snow_depth'].replace(-1.0, 0.0) >= 0), "Negative snødybdeverdier (unntatt -1.0) skal ikke forekomme"
    
    # Test med ugyldige negative verdier
    invalid_snow_df = pd.DataFrame({
        'snow_depth': [10.0, -2.5, -5.0, 15.0, -1.0],  # Ugyldige negative verdier
        'temperature': [-2.1, 0.0, 1.5, -1.0, 0.5]
    })
    success, message = validate_dataframe(invalid_snow_df, ['snow_depth'])
    assert success, "Validering skal fortsatt lykkes, men logge advarsel"

def test_get_period_summary():
    # Opprett test DataFrame med tidsindeks
    dates = pd.date_range(start='2024-01-01', periods=5, freq='h')
    test_data = {
        'wind_speed': [10.5, 15.2, 12.3, 11.1, 13.4],
        'temperature': [-2.1, 0.0, 1.5, -1.0, 0.5],
        'snow_depth': [50.0, 55.0, 60.0, 65.0, 70.0]
    }
    test_df = pd.DataFrame(test_data, index=dates)
    
    # Test periodesammendrag
    start_time = datetime(2024, 1, 1, 0, 0)
    end_time = datetime(2024, 1, 1, 3, 0)
    
    summary = get_period_summary(test_df, start_time, end_time)
    
    # Sjekk at nøkkelstatistikk er tilstede
    assert "duration_hours" in summary
    assert "total_rows" in summary
    assert "wind_speed_stats" in summary
    
    # Sjekk verdier
    assert summary["total_rows"] == 4
    assert summary["duration_hours"] == 3.0
    assert summary["wind_speed_stats"]["min"] == 10.5
    assert summary["wind_speed_stats"]["max"] == 15.2

def test_get_period_summary_edge_cases():
    # Opprett test DataFrame med tidsindeks
    dates = pd.date_range(start='2024-01-01', periods=5, freq='h')
    test_data = {
        'wind_speed': [10.5, 15.2, 12.3, 11.1, 13.4],
        'temperature': [-2.1, 0.0, 1.5, -1.0, 0.5],
    }
    test_df = pd.DataFrame(test_data, index=dates)
    
    # Test 1: Tom periode
    start_time = datetime(2023, 1, 1)  # Før dataene starter
    end_time = datetime(2023, 1, 2)
    summary = get_period_summary(test_df, start_time, end_time)
    assert "error" in summary
    assert summary["error"] == "Ingen data funnet for perioden"
    
    # Test 2: Start tid etter slutt tid
    start_time = datetime(2024, 1, 1, 3)
    end_time = datetime(2024, 1, 1, 1)
    summary = get_period_summary(test_df, start_time, end_time)
    assert "error" in summary
    
    # Test 3: Delvis periode
    start_time = datetime(2024, 1, 1, 1)
    end_time = datetime(2024, 1, 1, 2)
    summary = get_period_summary(test_df, start_time, end_time)
    assert summary["total_rows"] == 2
    assert 15.2 in [summary["wind_speed_stats"]["min"], summary["wind_speed_stats"]["max"]]
