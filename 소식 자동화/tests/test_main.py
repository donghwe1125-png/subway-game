import json

import scripts.main as main_module
from scripts.models import NoticeItem


def test_collect_new_items_isolates_source_failures():
    def ok_source():
        return [NoticeItem(id="1", source="cba", title="A", url="u")]

    def bad_source():
        raise RuntimeError("boom")

    state = {}
    new_items, failed = main_module.collect_new_items(
        state, {"cba": ok_source, "gmail": bad_source}
    )

    assert [i.id for i in new_items] == ["1"]
    assert failed == ["gmail"]
    assert state["cba"] == ["1"]


def test_collect_new_items_skips_already_seen():
    def source():
        return [NoticeItem(id="1", source="cba", title="A", url="u")]

    state = {"cba": ["1"]}
    new_items, failed = main_module.collect_new_items(state, {"cba": source})

    assert new_items == []
    assert failed == []
    assert state["cba"] == ["1"]


def test_main_runs_pipeline_and_saves_state(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    state_path.write_text("{}", encoding="utf-8")

    def fake_source():
        return [
            NoticeItem(
                id="1", source="cba", title="새 공지", url="https://x", date="2026-08-14"
            )
        ]

    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("KAKAO_REST_API_KEY", "kakao-key")
    monkeypatch.setenv("KAKAO_REFRESH_TOKEN", "kakao-refresh")

    monkeypatch.setattr(main_module, "SOURCES", {"cba": fake_source})
    monkeypatch.setattr(
        main_module, "summarize_items", lambda items, api_key: items
    )
    monkeypatch.setattr(
        main_module, "refresh_access_token", lambda key, refresh: "access-token"
    )

    sent_messages = []
    monkeypatch.setattr(
        main_module, "send_message", lambda token, text: sent_messages.append(text)
    )

    main_module.main(state_path=str(state_path))

    assert len(sent_messages) == 1
    assert "새 공지" in sent_messages[0]

    saved_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved_state["cba"] == ["1"]
