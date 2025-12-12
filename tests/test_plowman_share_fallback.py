from datetime import UTC, datetime

from src.plowman_client import _extract_latest_timestamp_from_share_html


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
