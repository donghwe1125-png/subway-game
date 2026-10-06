import json
from datetime import date, timedelta

from scripts.models import DigestItem, NewsCandidate

KEEP_DAYS = 3


def load_sent_urls(path: str) -> dict[str, str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_sent_urls(path: str, sent_urls: dict[str, str]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sent_urls, f, ensure_ascii=False, indent=2)


def filter_unsent(
    candidates: list[NewsCandidate], sent_urls: dict[str, str]
) -> list[NewsCandidate]:
    return [c for c in candidates if c.url not in sent_urls]


def already_sent_today(sent_urls: dict[str, str], today: date) -> bool:
    """오늘 날짜로 기록된 기사가 하나라도 있으면 오늘 다이제스트는 이미 나갔다.

    하루에 예약 트리거를 여러 번 걸어두고(발송 시각을 맞추기 위한 보험)
    그중 한 번만 실제로 보내기 위한 판단에 쓴다.
    """
    return today.isoformat() in sent_urls.values()


def record_sent(
    sent_urls: dict[str, str],
    items: list[DigestItem],
    today: date,
    keep_days: int = KEEP_DAYS,
) -> dict[str, str]:
    updated = dict(sent_urls)
    for item in items:
        updated[item.url] = today.isoformat()

    cutoff = today - timedelta(days=keep_days)
    return {
        url: sent_date
        for url, sent_date in updated.items()
        if date.fromisoformat(sent_date) >= cutoff
    }
