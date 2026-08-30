from datetime import date

from scripts.models import DigestItem

WEEKDAYS_KR = ["월", "화", "수", "목", "금", "토", "일"]
NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

# 텔레그램 메시지 한 통의 실제 상한은 4096자. 여유를 두고 보수적으로 잡았다.
# 한 통이 이 길이를 넘으면 잘라내는 대신 여러 통으로 나눠 보낸다.
MAX_CHARS = 3500

SEPARATOR = "\n\n──────────────\n\n"


def _date_label(today: date) -> str:
    return f"{today.month}/{today.day}({WEEKDAYS_KR[today.weekday()]})"


def _format_item(index: int, item: DigestItem) -> str:
    number = NUMBER_EMOJIS[index - 1] if index - 1 < len(NUMBER_EMOJIS) else f"{index}."
    return (
        f"{number} {item.title_kr}\n\n"
        f"{item.what_happened}\n\n"
        f"💡 왜 중요할까?\n{item.why_it_matters}\n\n"
        f"🔗 출처: {item.source_name} ({item.url})"
    )


def build_digest_message(items: list[DigestItem], today: date) -> list[str]:
    header = f"📰 {_date_label(today)} 아침, 오늘의 세계 경제뉴스 {len(items)}가지"
    blocks = [_format_item(i, item) for i, item in enumerate(items, start=1)]

    chunks: list[list[str]] = []
    current: list[str] = []
    current_len = 0
    for block in blocks:
        block_len = len(block) + len(SEPARATOR)
        if current and current_len + block_len > MAX_CHARS:
            chunks.append(current)
            current = [block]
            current_len = len(block)
        else:
            current.append(block)
            current_len += block_len
    if current:
        chunks.append(current)

    messages = []
    for index, chunk in enumerate(chunks):
        prefix = f"{header}\n\n" if index == 0 else ""
        messages.append(prefix + SEPARATOR.join(chunk))
    return messages


def build_error_message(reason: str) -> str:
    return f"⚠️ {reason}"
