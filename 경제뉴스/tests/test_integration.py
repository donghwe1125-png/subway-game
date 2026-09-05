"""Cross-module integration test.

Every other test in this project mocks its neighboring module's function by
hand (e.g. test_main.py monkeypatches ``select_and_explain`` with a
hand-written lambda). That's fine for unit-level isolation, but it means a
signature drift between ``news_sources.py`` -> ``curator.py`` ->
``message_formatter.py`` -> ``telegram_sender.py`` -> ``main.py`` would not
be caught by any existing test.

This test calls the REAL ``scripts.main.main()`` and only stubs the true
process boundaries: outbound HTTP (``requests.get`` / ``requests.post``) and
the Gemini SDK (``google.generativeai.GenerativeModel``). Everything in
between runs for real.
"""

import json
from unittest.mock import MagicMock, patch

import scripts.main as main_module

SAMPLE_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Sample Feed</title>
<item>
<title>Fed holds interest rates steady</title>
<link>https://example.com/fed-holds-rates</link>
<description>The Federal Reserve left rates unchanged.</description>
<pubDate>Sun, 30 Aug 2026 07:00:00 GMT</pubDate>
</item>
<item>
<title>Oil prices climb on Middle East tension</title>
<link>https://example.com/oil-prices</link>
<description>Crude oil rose to a three-week high.</description>
<pubDate>Sun, 30 Aug 2026 06:00:00 GMT</pubDate>
</item>
</channel>
</rss>
"""

FAKE_GEMINI_JSON = json.dumps(
    [
        {
            "title_kr": "연준, 기준금리 동결 결정",
            "what_happened": (
                "연준이 이번 회의에서 기준금리를 동결했다는 자세한 설명이 이어진다. "
                "시장은 어느 정도 예상했던 결과라 큰 동요는 없었다."
            ),
            "why_it_matters": (
                "금리가 유지되면서 원달러 환율과 대출 이자에 미치는 영향이 있다는 "
                "자세한 설명이 이어진다."
            ),
            "source_name": "BBC",
            "url": "https://example.com/fed-holds-rates",
        }
    ]
)


def test_main_end_to_end_through_real_module_chain(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "telegram-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "telegram-chat-id")

    fake_get_response = MagicMock()
    fake_get_response.content = SAMPLE_RSS
    fake_get_response.raise_for_status.return_value = None

    fake_gemini_response = MagicMock()
    fake_gemini_response.text = FAKE_GEMINI_JSON
    fake_model = MagicMock()
    fake_model.generate_content.return_value = fake_gemini_response

    fake_post_response = MagicMock()
    fake_post_response.raise_for_status.return_value = None

    with patch("requests.get", return_value=fake_get_response), patch(
        "requests.post", return_value=fake_post_response
    ) as mock_post, patch(
        "google.generativeai.GenerativeModel", return_value=fake_model
    ):
        main_module.main(state_path=str(tmp_path / "state.json"))

    assert mock_post.called
    sent_texts = [call.kwargs["json"]["text"] for call in mock_post.call_args_list]
    assert any("연준, 기준금리 동결 결정" in text for text in sent_texts)
