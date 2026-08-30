from datetime import date

from scripts.message_formatter import MAX_CHARS, build_digest_message, build_error_message
from scripts.models import DigestItem


def _item(n: int, why_len: int = 50) -> DigestItem:
    return DigestItem(
        title_kr=f"제목{n}",
        what_happened=f"무슨 일 설명{n}",
        why_it_matters="왜중요" * why_len,
        source_name="BBC",
        url=f"https://example.com/{n}",
    )


def test_build_digest_message_fits_in_one_message_when_short():
    items = [_item(1), _item(2), _item(3)]
    messages = build_digest_message(items, date(2026, 8, 30))

    assert len(messages) == 1
    assert "8/30(일)" in messages[0]
    assert "제목1" in messages[0]
    assert "제목2" in messages[0]
    assert "제목3" in messages[0]
    assert "https://example.com/1" in messages[0]


def test_build_digest_message_splits_when_exceeding_max_chars():
    items = [_item(1, why_len=800), _item(2, why_len=800), _item(3, why_len=800)]
    messages = build_digest_message(items, date(2026, 8, 30))

    assert len(messages) == 3
    for message in messages:
        assert len(message) <= MAX_CHARS + 200


def test_build_digest_message_labels_each_part_when_split():
    items = [_item(1, why_len=800), _item(2, why_len=800), _item(3, why_len=800)]
    messages = build_digest_message(items, date(2026, 8, 30))

    assert len(messages) == 3
    total = len(messages)
    for index, message in enumerate(messages, start=1):
        assert f"({index}/{total})" in message


def test_build_digest_message_has_no_part_label_when_single_message():
    items = [_item(1), _item(2), _item(3)]
    messages = build_digest_message(items, date(2026, 8, 30))

    assert len(messages) == 1
    assert "(1/1)" not in messages[0]


def test_build_error_message_returns_warning_text():
    message = build_error_message("오늘은 뉴스를 가져오지 못했어요")

    assert message.startswith("⚠️")
    assert "오늘은 뉴스를 가져오지 못했어요" in message
