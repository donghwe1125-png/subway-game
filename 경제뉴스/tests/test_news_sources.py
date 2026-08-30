from unittest.mock import MagicMock, patch

from scripts.news_sources import FEEDS, SOURCES, fetch_feed_live

SAMPLE_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Sample Feed</title>
<item>
<title>Fed holds interest rates steady</title>
<link>https://example.com/fed-holds-rates</link>
<description>The Federal Reserve left rates unchanged.</description>
<pubDate>Sun, 30 Aug 2026 07:00:00 GMT</pubDate>
</item>
<item>
<title>Oil prices climb on Middle East tension</title>
<link>https://example.com/oil-prices</link>
<description>Crude oil rose to a three-week high.</description>
<pubDate>Sun, 30 Aug 2026 06:00:00 GMT</pubDate>
</item>
</channel>
</rss>
"""


def test_fetch_feed_live_parses_entries_into_candidates():
    fake_response = MagicMock()
    fake_response.content = SAMPLE_RSS
    fake_response.raise_for_status.return_value = None

    with patch(
        "scripts.news_sources.requests.get", return_value=fake_response
    ) as mock_get:
        candidates = fetch_feed_live("bbc")

    called_url = mock_get.call_args.args[0]
    assert called_url == FEEDS["bbc"][1]
    assert len(candidates) == 2
    assert candidates[0].source == "BBC"
    assert candidates[0].title == "Fed holds interest rates steady"
    assert candidates[0].url == "https://example.com/fed-holds-rates"
    assert "Federal Reserve" in candidates[0].summary


def test_fetch_feed_live_sends_browser_user_agent():
    fake_response = MagicMock()
    fake_response.content = SAMPLE_RSS
    fake_response.raise_for_status.return_value = None

    with patch(
        "scripts.news_sources.requests.get", return_value=fake_response
    ) as mock_get:
        fetch_feed_live("cnbc")

    headers = mock_get.call_args.kwargs["headers"]
    assert "Mozilla" in headers["User-Agent"]


def test_fetch_feed_live_raises_on_http_error():
    fake_response = MagicMock()
    fake_response.raise_for_status.side_effect = RuntimeError("HTTP 403")

    with patch("scripts.news_sources.requests.get", return_value=fake_response):
        try:
            fetch_feed_live("cnbc")
        except RuntimeError:
            pass
        else:
            raise AssertionError("expected raise_for_status error to propagate")


def test_fetch_feed_live_raises_on_unparseable_feed():
    fake_response = MagicMock()
    fake_response.content = b"not xml at all"
    fake_response.raise_for_status.return_value = None

    with patch("scripts.news_sources.requests.get", return_value=fake_response):
        try:
            fetch_feed_live("bbc")
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError for unparseable feed")


def test_sources_maps_every_feed_key():
    assert set(SOURCES.keys()) == set(FEEDS.keys())
    assert callable(SOURCES["bbc"])
