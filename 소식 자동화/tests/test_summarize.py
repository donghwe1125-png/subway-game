from unittest.mock import MagicMock, patch

from scripts.models import NoticeItem
from scripts.summarize import summarize_items, summarize_title


def test_summarize_title_returns_model_text():
    fake_response = MagicMock()
    fake_response.text = "요약된 한 줄"
    fake_model = MagicMock()
    fake_model.generate_content.return_value = fake_response

    with patch("scripts.summarize.genai.GenerativeModel", return_value=fake_model):
        result = summarize_title("긴 원본 제목", "장학", api_key="fake-key")

    assert result == "요약된 한 줄"


def test_summarize_title_falls_back_to_title_on_empty_response():
    fake_response = MagicMock()
    fake_response.text = ""
    fake_model = MagicMock()
    fake_model.generate_content.return_value = fake_response

    with patch("scripts.summarize.genai.GenerativeModel", return_value=fake_model):
        result = summarize_title("원본 제목", "", api_key="fake-key")

    assert result == "원본 제목"


def test_summarize_items_falls_back_to_title_on_error():
    items = [NoticeItem(id="1", source="cba", title="원본 제목", url="u", meta="일반")]

    with patch("scripts.summarize.genai.GenerativeModel", side_effect=RuntimeError("quota")):
        result = summarize_items(items, api_key="fake-key")

    assert len(result) == 1
    assert result[0].title == "원본 제목"
    assert result[0].id == "1"


def test_summarize_items_replaces_title_with_summary():
    items = [NoticeItem(id="1", source="cba", title="원본 제목", url="u", meta="일반")]
    fake_response = MagicMock()
    fake_response.text = "요약본"
    fake_model = MagicMock()
    fake_model.generate_content.return_value = fake_response

    with patch("scripts.summarize.genai.GenerativeModel", return_value=fake_model):
        result = summarize_items(items, api_key="fake-key")

    assert result[0].title == "요약본"
    assert result[0].url == "u"
