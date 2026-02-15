from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.forecast_client import ForecastClient, ForecastClientError


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace('+00:00', 'Z')


@patch('src.forecast_client.requests.get')
def test_fetch_hourly_forecast_filters_past_and_limits_horizon(mock_get):
    now = datetime.now(UTC)

    payload = {
        "properties": {
            "timeseries": [
                {
                    "time": _iso(now - timedelta(hours=1)),
                    "data": {
                        "instant": {"details": {"air_temperature": -4.0, "wind_speed": 3.0}},
                        "next_1_hours": {"details": {"precipitation_amount": 0.5}},
                    },
                },
                {
                    "time": _iso(now + timedelta(hours=1)),
                    "data": {
                        "instant": {
                            "details": {
                                "air_temperature": -3.0,
                                "wind_speed": 4.0,
                                "wind_speed_of_gust": 8.0,
                            }
                        },
                        "next_1_hours": {"details": {"precipitation_amount": 0.2}},
                    },
                },
                {
                    "time": _iso(now + timedelta(hours=2)),
                    "data": {
                        "instant": {
                            "details": {
                                "air_temperature": -2.0,
                                "wind_speed": 5.0,
                                "wind_speed_of_gust": 9.0,
                            }
                        },
                        "next_1_hours": {"details": {"precipitation_amount": 0.0}},
                    },
                },
            ]
        }
    }

    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    mock_get.return_value = response

    points = ForecastClient().fetch_hourly_forecast(lat=59.4, lon=6.4, hours=1)

    assert len(points) == 1
    assert points[0].air_temperature == -3.0
    assert points[0].wind_speed == 4.0
    assert points[0].wind_gust == 8.0
    assert points[0].precipitation_1h == 0.2


@patch('src.forecast_client.requests.get')
def test_fetch_hourly_forecast_handles_missing_fields(mock_get):
    now = datetime.now(UTC)
    payload = {
        "properties": {
            "timeseries": [
                {
                    "time": _iso(now + timedelta(hours=1)),
                    "data": {
                        "instant": {"details": {}},
                    },
                }
            ]
        }
    }

    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    mock_get.return_value = response

    points = ForecastClient().fetch_hourly_forecast(lat=59.4, lon=6.4, hours=3)

    assert len(points) == 1
    assert points[0].air_temperature is None
    assert points[0].wind_speed is None
    assert points[0].wind_gust is None
    assert points[0].precipitation_1h is None


@patch('src.forecast_client.requests.get')
def test_fetch_hourly_forecast_raises_on_http_error(mock_get):
    mock_get.side_effect = requests.RequestException("network down")

    with pytest.raises(ForecastClientError):
        ForecastClient().fetch_hourly_forecast(lat=59.4, lon=6.4, hours=3)
