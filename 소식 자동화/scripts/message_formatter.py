from datetime import date

from scripts.models import NoticeItem

SOURCE_ORDER = ["cba", "gmail", "extra"]
SOURCE_LABELS = {
    "cba": "학과 공지",
    "gmail": "이메일 공지",
    "extra": "비교과 프로그램",
}
WEEKDAYS_KR = ["월", "화", "수", "목", "금", "토", "일"]

# 카카오 "나에게 보내기" 텍스트 템플릿의 안전 상한.
# 링크/버튼 오버헤드를 감안해 보수적으로 잡았다. 한 통이 이 길이를 넘으면
# 잘라내는 대신 여러 통으로 나눠 보낸다 (소식은 절대 유실되지 않는다).
MAX_CHARS = 900


def _date_label(today: date) -> str:
    return f"{today.month}/{today.day}({WEEKDAYS_KR[today.weekday()]})"


def _format_item(item: NoticeItem) -> str:
    meta = f" ({item.meta})" if item.meta else ""
    return f"• {item.title}{meta}\n  {item.url}"


def _group_header(prefix: str, source: str, total: int, index: int, parts: int) -> str:
    label = SOURCE_LABELS[source]
    suffix = "" if parts <= 1 else f" ({index}/{parts})"
    return f"{prefix}[{label}] {total}건{suffix}"


def _pack_blocks(
    blocks: list[str], prefix: str, source: str, total: int, assumed_parts: int
) -> list[list[str]]:
    """MAX_CHARS 예산에 맞춰 항목 블록들을 여러 덩어리로 나눈다."""
    chunks: list[list[str]] = []
    current: list[str] = []
    for block in blocks:
        candidate = current + [block]
        header = _group_header(
            prefix if not chunks else "", source, total, len(chunks) + 1, assumed_parts
        )
        size = len(header) + sum(len(b) + 1 for b in candidate)
        if current and size > MAX_CHARS:
            chunks.append(current)
            current = [block]
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _format_group(source: str, group_items: list[NoticeItem], prefix: str = "") -> list[str]:
    """한 출처의 소식을 MAX_CHARS 이하의 메시지 리스트로 만든다."""
    blocks = [_format_item(item) for item in group_items]
    total = len(group_items)

    # 분할 수가 머리말 길이(" (1/3)")에 영향을 주므로 안정될 때까지 반복한다.
    assumed_parts = 1
    chunks = _pack_blocks(blocks, prefix, source, total, assumed_parts)
    for _ in range(5):
        if len(chunks) == assumed_parts:
            break
        assumed_parts = len(chunks)
        chunks = _pack_blocks(blocks, prefix, source, total, assumed_parts)

    parts = len(chunks)
    return [
        "\n".join(
            [_group_header(prefix if index == 1 else "", source, total, index, parts)]
            + chunk
        )
        for index, chunk in enumerate(chunks, start=1)
    ]


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
        prefix = f"{header}\n\n" if is_first_group else ""
        messages.extend(_format_group(source, group_items, prefix))
        is_first_group = False
    return messages


def build_error_message(failed_sources: list[str]) -> str | None:
    if not failed_sources:
        return None
    labels = [SOURCE_LABELS[source] for source in failed_sources]
    return "⚠️ 확인 실패: " + ", ".join(labels)
