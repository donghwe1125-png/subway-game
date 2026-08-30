from unittest.mock import MagicMock, patch

from scripts.telegram_sender import send_message


def test_send_message_posts_to_bot_url_with_expected_payload():
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None

    with patch(
        "scripts.telegram_sender.requests.post", return_value=fake_response
    ) as mock_post:
        send_message("bot-token-123", "chat-id-456", "안녕하세요")

    called_args, called_kwargs = mock_post.call_args
    assert called_args[0] == "https://api.telegram.org/botbot-token-123/sendMessage"
    assert called_kwargs["json"]["chat_id"] == "chat-id-456"
    assert called_kwargs["json"]["text"] == "안녕하세요"
    assert called_kwargs["json"]["disable_web_page_preview"] is True


def test_send_message_raises_on_http_error():
    fake_response = MagicMock()
    fake_response.raise_for_status.side_effect = RuntimeError("bad request")

    with patch("scripts.telegram_sender.requests.post", return_value=fake_response):
        try:
            send_message("bot-token", "chat-id", "text")
        except RuntimeError:
            pass
        else:
            raise AssertionError("expected raise_for_status error to propagate")
