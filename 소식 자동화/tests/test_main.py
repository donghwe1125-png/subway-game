import json

import pytest

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


def _fake_source():
    return [
        NoticeItem(
            id="1", source="cba", title="새 공지", url="https://x", date="2026-08-14"
        )
    ]


def test_main_saves_state_even_when_sending_fails(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    state_path.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "telegram-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "telegram-chat-id")

    monkeypatch.setattr(main_module, "SOURCES", {"cba": _fake_source})
    monkeypatch.setattr(main_module, "summarize_items", lambda items, api_key: items)

    def exploding_send(bot_token, chat_id, text):
        raise RuntimeError("telegram down")

    monkeypatch.setattr(main_module, "send_message", exploding_send)

    with pytest.raises(RuntimeError, match="telegram down"):
        main_module.main(state_path=str(state_path))

    # 전송이 실패해도 수집 직후 저장된 seen 목록은 남아 있어야 한다
    saved_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved_state["cba"] == ["1"]


def test_main_runs_pipeline_and_saves_state(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    state_path.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "telegram-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "telegram-chat-id")

    monkeypatch.setattr(main_module, "SOURCES", {"cba": _fake_source})
    monkeypatch.setattr(
        main_module, "summarize_items", lambda items, api_key: items
    )

    sent_messages = []
    monkeypatch.setattr(
        main_module,
        "send_message",
        lambda bot_token, chat_id, text: sent_messages.append(text),
    )

    main_module.main(state_path=str(state_path))

    assert len(sent_messages) == 1
    assert "새 공지" in sent_messages[0]

    saved_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved_state["cba"] == ["1"]
