from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from src.netatmo_client import NetatmoClient


def test_parse_public_data_accepts_body_devices_dict() -> None:
    client = NetatmoClient(client_id="id", client_secret="secret")
    data = {
        "body": {
            "devices": [
                {
                    "_id": "station-1",
                    "place": {
                        "city": "Fjellberg",
                        "location": [6.42, 59.39],  # [lon, lat]
                        "altitude": 610,
                    },
                    "measures": {
                        "mod-1": {
                            "type": ["temperature", "humidity"],
                            "res": {
                                "1700000000": [1.5, 88],
                            },
                        }
                    },
                }
            ]
        }
    }

    stations = client._parse_public_data(data)  # noqa: SLF001
    assert len(stations) == 1
    s = stations[0]
    assert s.station_id == "station-1"
    assert s.lon == 6.42
    assert s.lat == 59.39
    assert s.temperature == 1.5
    assert s.humidity == 88
    assert s.timestamp is not None


def test_get_public_data_retries_after_401() -> None:
    client = NetatmoClient(client_id="id", client_secret="secret")

    # Pretend auth already valid on first call.
    client.access_token = "old-token"
    client.access_token_expires_at = datetime.now(tz=UTC) + timedelta(hours=1)

    first = MagicMock()
    first.status_code = 401
    first.raise_for_status.side_effect = None

    second = MagicMock()
    second.status_code = 200
    second.raise_for_status.return_value = None
    second.json.return_value = {"body": []}

    client._session.get = MagicMock(side_effect=[first, second])  # noqa: SLF001
    client.authenticate = MagicMock(side_effect=[True, True])  # type: ignore[method-assign]

    out = client.get_public_data(59.4, 6.5, 59.3, 6.3)
    assert out == []
    assert client._session.get.call_count == 2  # noqa: SLF001

