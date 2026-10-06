from datetime import date

from scripts.models import DigestItem, NewsCandidate
from scripts.state_store import (
    already_sent_today,
    filter_unsent,
    load_sent_urls,
    record_sent,
    save_sent_urls,
)


def test_load_sent_urls_returns_empty_dict_when_file_missing(tmp_path):
    missing_path = str(tmp_path / "state.json")

    assert load_sent_urls(missing_path) == {}


def test_save_then_load_round_trips(tmp_path):
    path = str(tmp_path / "state.json")

    save_sent_urls(path, {"https://a": "2026-08-29"})

    assert load_sent_urls(path) == {"https://a": "2026-08-29"}


def test_filter_unsent_excludes_already_sent_urls():
    candidates = [
        NewsCandidate(source="BBC", title="A", summary="s", url="https://a"),
        NewsCandidate(source="CNBC", title="B", summary="s", url="https://b"),
    ]
    sent_urls = {"https://a": "2026-08-29"}

    result = filter_unsent(candidates, sent_urls)

    assert [c.url for c in result] == ["https://b"]


def test_filter_unsent_keeps_all_when_nothing_sent():
    candidates = [
        NewsCandidate(source="BBC", title="A", summary="s", url="https://a"),
    ]

    result = filter_unsent(candidates, {})

    assert result == candidates


def test_record_sent_adds_items_with_todays_date():
    items = [
        DigestItem(
            title_kr="제목",
            what_happened="설명",
            why_it_matters="영향",
            source_name="BBC",
            url="https://a",
        )
    ]

    result = record_sent({}, items, today=date(2026, 8, 30))

    assert result == {"https://a": "2026-08-30"}


def test_already_sent_today_is_true_when_an_entry_carries_todays_date():
    sent_urls = {"https://a": "2026-10-05", "https://b": "2026-10-06"}

    assert already_sent_today(sent_urls, date(2026, 10, 6)) is True


def test_already_sent_today_is_false_when_only_older_entries_exist():
    sent_urls = {"https://a": "2026-10-04", "https://b": "2026-10-05"}

    assert already_sent_today(sent_urls, date(2026, 10, 6)) is False


def test_already_sent_today_is_false_for_empty_state():
    assert already_sent_today({}, date(2026, 10, 6)) is False


def test_record_sent_prunes_entries_older_than_keep_days():
    sent_urls = {
        "https://old": "2026-08-20",
        "https://recent": "2026-08-29",
    }

    result = record_sent(sent_urls, [], today=date(2026, 8, 30), keep_days=3)

    assert result == {"https://recent": "2026-08-29"}
