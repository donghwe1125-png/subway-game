import re

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from scripts.models import NoticeItem

LIST_URL = "https://extra.snu.ac.kr/ptfol/pgm/index.do"
ID_RE = re.compile(r"global\.write\('([^']+)'")


def parse_extra_snu_programs(html: str) -> list[NoticeItem]:
    soup = BeautifulSoup(html, "html.parser")
    seen_ids: set[str] = set()
    items = []

    for title_el in soup.select("a.tit.ellipsis"):
        match = ID_RE.search(title_el.get("onclick", ""))
        if not match:
            continue
        program_id = match.group(1)
        if program_id in seen_ids:
            continue
        seen_ids.add(program_id)

        card = title_el.find_parent("div", class_="text_wrap")
        status, dday = "", ""
        if card is not None:
            status_el = card.select_one(".label_box a span")
            if status_el:
                status = status_el.get_text(strip=True)
            dday_el = card.select_one(".dday")
            if dday_el:
                dday = dday_el.get_text(strip=True)

        items.append(
            NoticeItem(
                id=program_id,
                source="extra",
                title=title_el.get_text(strip=True),
                url=LIST_URL,
                date="",
                meta=" ".join(part for part in (status, dday) if part),
            )
        )
    return items


def fetch_extra_snu_programs_live() -> list[NoticeItem]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(LIST_URL, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)
            html = page.content()
        finally:
            browser.close()
    return parse_extra_snu_programs(html)
