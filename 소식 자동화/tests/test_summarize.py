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


def test_summarize_items_sleeps_between_gemini_calls_but_not_after_the_last():
    items = [
        NoticeItem(id=str(n), source="cba", title=f"제목 {n}", url="u") for n in range(3)
    ]
    fake_response = MagicMock()
    fake_response.text = "요약본"
    fake_model = MagicMock()
    fake_model.generate_content.return_value = fake_response

    with patch("scripts.summarize.genai.GenerativeModel", return_value=fake_model):
        with patch("scripts.summarize.time.sleep") as fake_sleep:
            result = summarize_items(items, api_key="fake-key")

    assert len(result) == 3
    # 3개 항목 -> 사이에만 2번 쉰다 (마지막 항목 뒤에는 쉬지 않는다)
    assert fake_sleep.call_count == 2
    assert all(call.args[0] == 4.0 for call in fake_sleep.call_args_list)


def test_summarize_items_does_not_sleep_for_a_single_item():
    items = [NoticeItem(id="1", source="cba", title="제목", url="u")]
    fake_response = MagicMock()
    fake_response.text = "요약본"
    fake_model = MagicMock()
    fake_model.generate_content.return_value = fake_response

    with patch("scripts.summarize.genai.GenerativeModel", return_value=fake_model):
        with patch("scripts.summarize.time.sleep") as fake_sleep:
            summarize_items(items, api_key="fake-key")

    fake_sleep.assert_not_called()


def test_summarize_items_sleep_can_be_disabled():
    items = [
        NoticeItem(id=str(n), source="cba", title=f"제목 {n}", url="u") for n in range(3)
    ]
    fake_response = MagicMock()
    fake_response.text = "요약본"
    fake_model = MagicMock()
    fake_model.generate_content.return_value = fake_response

    with patch("scripts.summarize.genai.GenerativeModel", return_value=fake_model):
        with patch("scripts.summarize.time.sleep") as fake_sleep:
            summarize_items(items, api_key="fake-key", sleep_seconds=0)

    fake_sleep.assert_not_called()


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
