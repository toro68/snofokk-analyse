from datetime import UTC, datetime

from src.plowman_client import _extract_latest_timestamp_from_share_html, _sanitize_base_url


def test_fallback_used_when_maintenance_api_returns_no_payload(monkeypatch):
  from src.plowman_client import MaintenanceApiClient

  class FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
      self.status_code = status_code
      self.text = text
      self.ok = 200 <= status_code < 300

    def raise_for_status(self):
      import requests

      if not self.ok:
        raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
      raise ValueError("no json")

  share_html = '... $D2025-11-27T11:20:34.000Z ...'

  # First call: maintenance API -> 401 (client treats as no payload)
  # Second call: share page -> 200 with timestamps
  calls = {"n": 0}

  def fake_get(url, headers=None, timeout=None):
    calls["n"] += 1
    if calls["n"] == 1:
      return FakeResponse(401, '{"error":"Unauthorized"}')
    return FakeResponse(200, share_html)

  client = MaintenanceApiClient(base_url="https://example.web.app", token="token")
  monkeypatch.setattr(client.session, "get", fake_get)

  event = client.get_last_maintenance_time()
  assert event is not None
  assert event.timestamp == datetime(2025, 11, 27, 11, 20, 34, tzinfo=UTC)


def test_extract_latest_timestamp_from_share_html_picks_latest():
    html = """
    <html>
      <head></head>
      <body>
        <script>
          // some next payload
          var x = "lastUpdated:\"$D2025-11-27T10:00:00.000Z\"";
          var y = "lastUpdated:\"$D2025-11-27T12:30:00.000Z\"";
        </script>
      </body>
    </html>
    """

    ts = _extract_latest_timestamp_from_share_html(html)
    assert ts is not None
    assert ts == datetime(2025, 11, 27, 12, 30, 0, tzinfo=UTC)


def test_extract_latest_timestamp_from_share_html_returns_none_when_missing():
    html = "<html><body><script>no timestamps here</script></body></html>"
    ts = _extract_latest_timestamp_from_share_html(html)
    assert ts is None


def test_sanitize_base_url_rejects_placeholders_and_non_urls():
  assert _sanitize_base_url(None) == ""
  assert _sanitize_base_url("") == ""
  assert _sanitize_base_url("<din-host>") == ""
  assert _sanitize_base_url(" https://<din-host> ") == ""
  assert _sanitize_base_url("din-host") == ""
  assert _sanitize_base_url("example.web.app") == ""  # missing scheme


def test_sanitize_base_url_strips_quotes_and_trailing_slash():
  assert _sanitize_base_url('"https://fjellbs-app-ny.web.app/"') == "https://fjellbs-app-ny.web.app"
