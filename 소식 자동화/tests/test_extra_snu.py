import os

from scripts.extra_snu import LIST_URL, parse_extra_snu_programs

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "extra_snu_sample.html"
)


def _load_fixture() -> str:
    with open(FIXTURE_PATH, encoding="utf-8") as f:
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
