import matplotlib

matplotlib.use("Agg")

import numpy as np
import pandas as pd

from src.visualizations import WeatherPlots


def _df_base(n: int = 24) -> pd.DataFrame:
    # tz-aware UTC timestamps are a common source of matplotlib issues
    times = pd.date_range("2025-12-10T00:00:00Z", periods=n, freq="h")
    return pd.DataFrame(
        {
            "reference_time": times,
            "air_temperature": np.linspace(-8, 2, n),
            "surface_temperature": np.linspace(-10, 0, n),
            "wind_speed": np.linspace(0, 12, n),
            "max_wind_gust": np.linspace(2, 20, n),
            "wind_from_direction": np.linspace(100, 260, n),
            "surface_snow_thickness": np.full(n, 12.0),
            "precipitation_1h": np.concatenate([np.zeros(n - 2), [0.2, 1.2]]),
            "dew_point_temperature": np.linspace(-10, 0, n),
        }
    )


def _assert_renders(fig):
    assert fig is not None
    # Force render to catch backend errors
    fig.canvas.draw()


def test_weather_grafer_tabs_render_smoke():
    df = _df_base()

    _assert_renders(WeatherPlots.create_snow_depth_plot(df))
    _assert_renders(WeatherPlots.create_precip_plot(df))
    _assert_renders(WeatherPlots.create_temperature_plot(df))
    _assert_renders(WeatherPlots.create_wind_plot(df))
    _assert_renders(WeatherPlots.create_wind_direction_plot(df))


def test_weather_grafer_tolerate_nans_and_strings():
    df = _df_base()
    df.loc[0, "air_temperature"] = np.nan
    df.loc[1, "wind_speed"] = np.nan
    df = df.astype(
        {
            "precipitation_1h": "object",
            "surface_snow_thickness": "object",
            "wind_from_direction": "object",
        }
    )
    df.loc[2, "precipitation_1h"] = "0.1"  # stringy input sometimes sneaks in
    df.loc[3, "surface_snow_thickness"] = "15"  # string
    df.loc[4, "wind_from_direction"] = "180"  # string

    _assert_renders(WeatherPlots.create_snow_depth_plot(df))
    _assert_renders(WeatherPlots.create_precip_plot(df))
    _assert_renders(WeatherPlots.create_temperature_plot(df))
    _assert_renders(WeatherPlots.create_wind_plot(df))
    _assert_renders(WeatherPlots.create_wind_direction_plot(df))


def test_wind_chill_plot_smoke():
    df = _df_base(12)
    df.loc[0, "air_temperature"] = np.nan
    _assert_renders(WeatherPlots.create_wind_chill_plot(df))
