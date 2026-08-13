import json

from scripts.models import NoticeItem
from scripts.state_store import (
    filter_new_items,
    load_state,
    save_state,
    update_seen_ids,
)


def test_load_state_missing_file_returns_empty_dict(tmp_path):
    path = tmp_path / "state.json"
    assert load_state(str(path)) == {}


def test_save_and_load_state_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    save_state(str(path), {"cba": ["1", "2"]})
    assert load_state(str(path)) == {"cba": ["1", "2"]}
    with open(path, encoding="utf-8") as f:
        assert json.load(f) == {"cba": ["1", "2"]}


def test_filter_new_items_excludes_seen_ids():
    items = [
        NoticeItem(id="1", source="cba", title="a", url="u"),
        NoticeItem(id="2", source="cba", title="b", url="u"),
    ]
    result = filter_new_items(items, seen_ids=["1"])
    assert [i.id for i in result] == ["2"]


def test_filter_new_items_first_run_returns_all():
    items = [NoticeItem(id="1", source="cba", title="a", url="u")]
    result = filter_new_items(items, seen_ids=[])
    assert [i.id for i in result] == ["1"]


def test_update_seen_ids_dedupes_and_prepends_new():
    items = [
        NoticeItem(id="3", source="cba", title="a", url="u"),
        NoticeItem(id="1", source="cba", title="b", url="u"),
    ]
    result = update_seen_ids(seen_ids=["1", "2"], items=items)
    assert result == ["3", "1", "2"]


def test_update_seen_ids_trims_to_max_size():
    old_ids = [str(i) for i in range(10)]
    items = [NoticeItem(id="new", source="cba", title="a", url="u")]
    result = update_seen_ids(seen_ids=old_ids, items=items, max_size=5)
    assert len(result) == 5
    assert result[0] == "new"
