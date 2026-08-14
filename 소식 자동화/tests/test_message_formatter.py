from datetime import date

from scripts.message_formatter import build_digest_messages, build_error_message
from scripts.models import NoticeItem


def test_build_digest_messages_no_new_items():
    messages = build_digest_messages([], today=date(2026, 8, 17))
    assert len(messages) == 1
    assert "새 소식 없음" in messages[0]
    assert "8/17" in messages[0]


def test_build_digest_messages_groups_by_source():
    items = [
        NoticeItem(id="1", source="cba", title="학과 공지 A", url="https://a", meta="일반"),
        NoticeItem(id="2", source="gmail", title="메일 공지 A", url="https://b", meta=""),
    ]
    messages = build_digest_messages(items, today=date(2026, 8, 17))
    assert len(messages) == 2
    assert "학교 소식 요약 (신규 2건)" in messages[0]
    assert "[학과 공지] 1건" in messages[0]
    assert "학과 공지 A" in messages[0]
    assert "(일반)" in messages[0]
    assert "[이메일 공지] 1건" in messages[1]
    assert "메일 공지 A" in messages[1]


def test_build_digest_messages_omits_empty_groups():
    items = [NoticeItem(id="1", source="extra", title="비교과 A", url="https://c")]
    messages = build_digest_messages(items, today=date(2026, 8, 17))
    assert len(messages) == 1
    assert "[비교과 프로그램] 1건" in messages[0]
    assert "학과 공지" not in messages[0]


def test_build_error_message_returns_none_when_no_failures():
    assert build_error_message([]) is None


def test_build_error_message_lists_failed_sources():
    message = build_error_message(["cba", "extra"])
    assert message == "⚠️ 확인 실패: 학과 공지, 비교과 프로그램"
