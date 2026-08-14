from datetime import date

from scripts.message_formatter import (
    MAX_CHARS,
    build_digest_messages,
    build_error_message,
)
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


def _many_items(count: int, source: str = "cba") -> list[NoticeItem]:
    return [
        NoticeItem(
            id=str(n),
            source=source,
            title=f"공지 제목 {n}번 - 학사일정 및 장학금 신청 관련 상세 안내",
            url=f"https://cba.snu.ac.kr/newsroom/notice?md=v&bbsidx=2630{n}",
            date="2026-08-13",
            meta="일반",
        )
        for n in range(1, count + 1)
    ]


def test_build_digest_messages_splits_long_group_into_multiple_messages():
    items = _many_items(15)
    messages = build_digest_messages(items, today=date(2026, 8, 17))

    assert len(messages) >= 2
    assert all(len(message) <= MAX_CHARS for message in messages)
    assert f"[학과 공지] 15건 (1/{len(messages)})" in messages[0]
    assert f"[학과 공지] 15건 ({len(messages)}/{len(messages)})" in messages[-1]


def test_build_digest_messages_never_drops_an_item():
    items = _many_items(15)
    combined = "\n".join(build_digest_messages(items, today=date(2026, 8, 17)))

    for item in items:
        assert item.title in combined
        assert item.url in combined


def test_build_digest_messages_keeps_header_only_on_first_message():
    messages = build_digest_messages(_many_items(15), today=date(2026, 8, 17))

    assert "학교 소식 요약 (신규 15건)" in messages[0]
    assert all("학교 소식 요약" not in message for message in messages[1:])


def test_build_digest_messages_single_message_group_has_no_part_suffix():
    messages = build_digest_messages(_many_items(2), today=date(2026, 8, 17))

    assert len(messages) == 1
    assert "[학과 공지] 2건" in messages[0]
    assert "(1/1)" not in messages[0]


def test_build_digest_messages_chunks_each_source_independently():
    items = _many_items(15) + _many_items(15, source="extra")
    messages = build_digest_messages(items, today=date(2026, 8, 17))

    assert all(len(message) <= MAX_CHARS for message in messages)
    assert sum("[학과 공지]" in m for m in messages) >= 2
    assert sum("[비교과 프로그램]" in m for m in messages) >= 2
    # 두 그룹의 머리말이 한 통에 섞이지 않는다
    assert not any("[학과 공지]" in m and "[비교과 프로그램]" in m for m in messages)


def test_build_error_message_returns_none_when_no_failures():
    assert build_error_message([]) is None


def test_build_error_message_lists_failed_sources():
    message = build_error_message(["cba", "extra"])
    assert message == "⚠️ 확인 실패: 학과 공지, 비교과 프로그램"
