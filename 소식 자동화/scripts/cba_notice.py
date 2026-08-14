import re

import requests
from bs4 import BeautifulSoup

from scripts.models import NoticeItem

BASE_URL = "https://cba.snu.ac.kr"
LIST_URL = BASE_URL + "/newsroom/notice?sc=y"
BBSIDX_RE = re.compile(r"bbsidx=(\d+)")


def parse_cba_notices(html: str) -> list[NoticeItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for row in soup.select("div.board table tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        category = cells[1].get_text(strip=True)
        link = cells[2].find("a")
        if not link or not link.get("href"):
            continue
        match = BBSIDX_RE.search(link["href"])
        if not match:
            continue
        items.append(
            NoticeItem(
                id=match.group(1),
                source="cba",
                title=link.get_text(strip=True),
                url=BASE_URL + link["href"],
                date=cells[3].get_text(strip=True),
                meta=category,
            )
        )
    return items


def fetch_cba_notices_live() -> list[NoticeItem]:
    response = requests.get(
        LIST_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"}
    )
    response.raise_for_status()
    return parse_cba_notices(response.text)
