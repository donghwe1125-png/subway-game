import scripts.main as main_module
from scripts.models import DigestItem, NewsCandidate


def _fake_source():
    return [NewsCandidate(source="BBC", title="A", summary="s", url="https://a")]


def test_collect_candidates_isolates_source_failures():
    def ok_source():
        return [NewsCandidate(source="BBC", title="A", summary="s", url="https://a")]

    def bad_source():
        raise RuntimeError("boom")

    candidates, failed = main_module.collect_candidates(
        {"bbc": ok_source, "cnbc": bad_source}
    )

    assert len(candidates) == 1
    assert failed == ["cnbc"]


def test_main_sends_digest_when_items_found(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "telegram-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "telegram-chat-id")

    monkeypatch.setattr(main_module, "SOURCES", {"bbc": _fake_source})

    fake_item = DigestItem(
        title_kr="연준 금리 동결",
        what_happened="설명",
        why_it_matters="영향",
        source_name="BBC",
        url="https://a",
    )
    monkeypatch.setattr(
        main_module, "select_and_explain", lambda candidates, api_key: [fake_item]
    )

    sent_messages = []
    monkeypatch.setattr(
        main_module,
        "send_message",
        lambda bot_token, chat_id, text: sent_messages.append(text),
    )

    main_module.main()

    assert len(sent_messages) == 1
    assert "연준 금리 동결" in sent_messages[0]


def test_main_keeps_sending_remaining_messages_after_one_send_fails(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "telegram-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "telegram-chat-id")

    monkeypatch.setattr(main_module, "SOURCES", {"bbc": _fake_source})

    fake_item = DigestItem(
        title_kr="연준 금리 동결",
        what_happened="설명",
        why_it_matters="영향",
        source_name="BBC",
        url="https://a",
    )
    monkeypatch.setattr(
        main_module, "select_and_explain", lambda candidates, api_key: [fake_item]
    )
    monkeypatch.setattr(
        main_module,
        "build_digest_message",
        lambda items, today: ["msg1", "msg2", "msg3"],
    )

    sent_messages = []

    def flaky_send(bot_token, chat_id, text):
        if text == "msg2":
            raise RuntimeError("telegram down")
        sent_messages.append(text)

    monkeypatch.setattr(main_module, "send_message", flaky_send)

    raised = False
    try:
        main_module.main()
    except RuntimeError:
        raised = True

    assert raised, "main() should raise after all messages are attempted"
    # msg1 and msg3 must still have been sent despite msg2 failing.
    assert sent_messages == ["msg1", "msg3"]


def test_main_sends_error_message_when_no_candidates(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "telegram-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "telegram-chat-id")

    def bad_source():
        raise RuntimeError("boom")

    monkeypatch.setattr(main_module, "SOURCES", {"bbc": bad_source})

    sent_messages = []
    monkeypatch.setattr(
        main_module,
        "send_message",
        lambda bot_token, chat_id, text: sent_messages.append(text),
    )

    main_module.main()

    assert len(sent_messages) == 1
    assert sent_messages[0].startswith("⚠️")
