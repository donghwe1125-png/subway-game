from datetime import date

from scripts.models import NoticeItem

SOURCE_ORDER = ["cba", "gmail", "extra"]
SOURCE_LABELS = {
    "cba": "학과 공지",
    "gmail": "이메일 공지",
    "extra": "비교과 프로그램",
}
WEEKDAYS_KR = ["월", "화", "수", "목", "금", "토", "일"]


def _date_label(today: date) -> str:
    return f"{today.month}/{today.day}({WEEKDAYS_KR[today.weekday()]})"


def _format_group(source: str, group_items: list[NoticeItem]) -> str:
    label = SOURCE_LABELS[source]
    lines = [f"[{label}] {len(group_items)}건"]
    for item in group_items:
        meta = f" ({item.meta})" if item.meta else ""
        lines.append(f"• {item.title}{meta}\n  {item.url}")
    return "\n".join(lines)


def build_digest_messages(items: list[NoticeItem], today: date) -> list[str]:
    total = len(items)
    if total == 0:
        return [f"📌 {_date_label(today)} 학교 소식 요약: 이번엔 새 소식 없음"]

    grouped = {source: [] for source in SOURCE_ORDER}
    for item in items:
        grouped[item.source].append(item)

    header = f"📌 {_date_label(today)} 학교 소식 요약 (신규 {total}건)"
    messages = []
    is_first_group = True
    for source in SOURCE_ORDER:
        group_items = grouped[source]
        if not group_items:
            continue
        block = _format_group(source, group_items)
        if is_first_group:
            messages.append(f"{header}\n\n{block}")
            is_first_group = False
        else:
            messages.append(block)
    return messages


def build_error_message(failed_sources: list[str]) -> str | None:
    if not failed_sources:
        return None
    labels = [SOURCE_LABELS[source] for source in failed_sources]
    return "⚠️ 확인 실패: " + ", ".join(labels)
