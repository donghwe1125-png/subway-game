import os

import pytest

from scripts.extra_snu import LIST_URL, parse_extra_snu_programs

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
FIXTURE_PATH = os.path.join(FIXTURE_DIR, "extra_snu_sample.html")


def _load_fixture(name: str = "extra_snu_sample.html") -> str:
    with open(os.path.join(FIXTURE_DIR, name), encoding="utf-8") as f:
        return f.read()


def test_parse_extra_snu_programs_extracts_all_cards():
    items = parse_extra_snu_programs(_load_fixture())
    assert len(items) == 2


def test_parse_extra_snu_programs_extracts_fields():
    items = parse_extra_snu_programs(_load_fixture())
    first = items[0]
    assert first.id == "PGM012002012"
    assert first.source == "extra"
    assert "SNUTI Into Future" in first.title
    assert first.url == LIST_URL
    assert first.meta == "모집중 D-34"


def test_parse_extra_snu_programs_second_card():
    items = parse_extra_snu_programs(_load_fixture())
    assert items[1].id == "PGM012002011"
    assert items[1].title == "2026 예술주간 공연 참가자 모집"
    assert items[1].meta == "모집대기 D-13"


def test_parse_extra_snu_programs_raises_on_netfunnel_queue_page():
    with pytest.raises(RuntimeError, match="lica_wrap"):
        parse_extra_snu_programs(_load_fixture("extra_snu_netfunnel.html"))


def test_parse_extra_snu_programs_returns_empty_when_list_container_is_empty():
    # 목록 틀은 있는데 모집 중인 프로그램이 0건인 것은 정상 상태다
    assert parse_extra_snu_programs('<div class="lica_wrap"><ul></ul></div>') == []
