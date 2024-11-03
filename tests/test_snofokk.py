import pandas as pd
from snofokk import calculate_snow_drift_risk
from snofokk.config import DEFAULT_PARAMS


def test_calculate_snow_drift_risk_empty():
    """Test at funksjonen håndterer tom DataFrame"""
    df = pd.DataFrame()
    params = DEFAULT_PARAMS.copy()

    df_risk, periods = calculate_snow_drift_risk(df, params)
    assert df_risk.empty
    assert periods.empty


def test_calculate_snow_drift_risk_basic():
    """Test med enkle testdata"""
    # Opprett test DataFrame med minimale data
    data = {
        "air_temperature": [-5.0, -4.0, -3.0],
        "wind_speed": [10.0, 12.0, 15.0],
        "snow_depth": [100, 102, 105],
    }
    df = pd.DataFrame(data)
    params = DEFAULT_PARAMS.copy()

    df_risk, periods = calculate_snow_drift_risk(df, params)

    # Grunnleggende sjekker
    assert not df_risk.empty
    assert "risk_score" in df_risk.columns
