import re

import requests
from bs4 import BeautifulSoup

from scripts.models import NoticeItem

BASE_URL = "https://cba.snu.ac.kr"
LIST_URL = BASE_URL + "/newsroom/notice?sc=y"
BBSIDX_RE = re.compile(r"bbsidx=(\d+)")


def parse_cba_notices(html: str) -> list[NoticeItem]:
    soup = BeautifulSoup(html, "html.parser")
    # 게시판 틀 자체가 없으면 "새 소식 없음"이 아니라 사이트 변경/차단 페이지다.
    # 틀은 있는데 행이 0개인 경우는 정상 상태이므로 그대로 빈 목록을 돌려준다.
    if soup.select_one("div.board table tbody") is None:
        raise RuntimeError(
            "cba 공지 게시판 구조(div.board table tbody)를 찾을 수 없습니다 "
            "- 사이트 구조 변경이나 차단/대기 페이지일 수 있습니다"
        )

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
