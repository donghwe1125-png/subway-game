import os

import pytest

from scripts.cba_notice import parse_cba_notices

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
FIXTURE_PATH = os.path.join(FIXTURE_DIR, "cba_notice_sample.html")


def _load_fixture(name: str = "cba_notice_sample.html") -> str:
    with open(os.path.join(FIXTURE_DIR, name), encoding="utf-8") as f:
        return f.read()


def test_parse_cba_notices_extracts_all_rows():
    items = parse_cba_notices(_load_fixture())
    assert len(items) == 2


def test_parse_cba_notices_extracts_fields_correctly():
    items = parse_cba_notices(_load_fixture())
    first = items[0]
    assert first.id == "26334"
    assert first.source == "cba"
    assert first.title == "2026학년도 2학기 졸업세미나 과목 등록 처리 완료 안내"
    assert first.url == "https://cba.snu.ac.kr/newsroom/notice?md=v&bbsidx=26334"
    assert first.date == "2026-08-13"
    assert first.meta == "일반"


def test_parse_cba_notices_second_row_category():
    items = parse_cba_notices(_load_fixture())
    assert items[1].id == "26328"
    assert items[1].meta == "장학"


def test_parse_cba_notices_raises_when_board_container_missing():
    with pytest.raises(RuntimeError, match="div.board table tbody"):
        parse_cba_notices(_load_fixture("cba_notice_blocked.html"))


def test_parse_cba_notices_returns_empty_when_board_exists_but_has_no_rows():
    # 게시판 틀이 있는데 행이 0건인 것은 정상 상태이므로 예외를 던지면 안 된다
    assert parse_cba_notices(_load_fixture("cba_notice_empty_board.html")) == []
