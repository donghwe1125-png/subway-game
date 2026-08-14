import json
from unittest.mock import MagicMock, patch

from scripts.kakao_sender import refresh_access_token, send_message


def test_refresh_access_token_posts_expected_params():
    fake_response = MagicMock()
    fake_response.json.return_value = {"access_token": "new-token"}
    fake_response.raise_for_status.return_value = None

    with patch("scripts.kakao_sender.requests.post", return_value=fake_response) as mock_post:
        token = refresh_access_token("rest-key", "refresh-token")

    assert token == "new-token"
    called_kwargs = mock_post.call_args.kwargs
    assert called_kwargs["data"]["grant_type"] == "refresh_token"
    assert called_kwargs["data"]["client_id"] == "rest-key"
    assert called_kwargs["data"]["refresh_token"] == "refresh-token"


def test_send_message_posts_text_template():
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None

    with patch("scripts.kakao_sender.requests.post", return_value=fake_response) as mock_post:
        send_message("access-token", "안녕하세요")

    called_kwargs = mock_post.call_args.kwargs
    assert called_kwargs["headers"]["Authorization"] == "Bearer access-token"
    template = json.loads(called_kwargs["data"]["template_object"])
    assert template["object_type"] == "text"
    assert template["text"] == "안녕하세요"
