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


def test_refresh_access_token_warns_when_refresh_token_is_rotated(capsys):
    fake_response = MagicMock()
    fake_response.json.return_value = {
        "access_token": "new-token",
        "refresh_token": "rotated-refresh-token",
    }
    fake_response.raise_for_status.return_value = None

    with patch("scripts.kakao_sender.requests.post", return_value=fake_response):
        token = refresh_access_token("rest-key", "refresh-token")

    assert token == "new-token"
    stderr = capsys.readouterr().err
    assert "KAKAO_REFRESH_TOKEN" in stderr
    # 저장소가 public이므로 전체 토큰 값이 로그에 찍히면 안 된다. 마지막 6자리
    # 조각과 갱신 안내 문구만 남고, 재구성 가능한 전체 값은 없어야 한다.
    assert "rotated-refresh-token" not in stderr
    assert "-token" in stderr  # 새 refresh token의 마지막 6자리 (...-token)
    assert "갱신되었습니다" in stderr


def test_refresh_access_token_stays_quiet_when_token_is_not_rotated(capsys):
    fake_response = MagicMock()
    fake_response.json.return_value = {"access_token": "new-token"}
    fake_response.raise_for_status.return_value = None

    with patch("scripts.kakao_sender.requests.post", return_value=fake_response):
        refresh_access_token("rest-key", "refresh-token")

    captured = capsys.readouterr()
    assert "KAKAO_REFRESH_TOKEN" not in captured.err
    assert captured.err == ""


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


def test_send_message_does_not_truncate_long_text():
    long_text = "가" * 1500
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None

    with patch("scripts.kakao_sender.requests.post", return_value=fake_response) as mock_post:
        send_message("access-token", long_text)

    template = json.loads(mock_post.call_args.kwargs["data"]["template_object"])
    assert template["text"] == long_text
    assert len(template["text"]) == 1500
