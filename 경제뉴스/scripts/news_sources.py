import functools
from typing import Callable

import feedparser
import requests

from scripts.models import NewsCandidate

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# 언론사가 RSS 주소를 바꾸면 여기만 고치면 된다.
FEEDS: dict[str, tuple[str, str]] = {
    "bbc": ("BBC", "http://feeds.bbci.co.uk/news/business/rss.xml"),
    "cnbc": ("CNBC", "https://www.cnbc.com/id/10001147/device/rss/rss.html"),
    "marketwatch": ("MarketWatch", "https://www.marketwatch.com/rss/topstories"),
    "investing": ("Investing.com", "https://www.investing.com/rss/news_25.rss"),
}


def fetch_feed_live(feed_key: str) -> list[NewsCandidate]:
    source_label, url = FEEDS[feed_key]
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
    response.raise_for_status()

    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"{feed_key} feed failed to parse: {parsed.bozo_exception}")

    return [
        NewsCandidate(
            source=source_label,
            title=entry.get("title", "").strip(),
            summary=entry.get("summary", "").strip(),
            url=entry.get("link", ""),
            published=entry.get("published", ""),
        )
        for entry in parsed.entries
    ]


SOURCES: dict[str, Callable[[], list[NewsCandidate]]] = {
    key: functools.partial(fetch_feed_live, key) for key in FEEDS
}
