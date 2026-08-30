import json
from unittest.mock import MagicMock, patch

from scripts.curator import select_and_explain
from scripts.models import NewsCandidate

SAMPLE_CANDIDATES = [
    NewsCandidate(source="BBC", title="Fed holds rates", summary="s1", url="https://a"),
    NewsCandidate(source="CNBC", title="Oil climbs", summary="s2", url="https://b"),
]

VALID_JSON_RESPONSE = json.dumps(
    [
        {
            "title_kr": "연준 금리 동결",
            "what_happened": "연준이 금리를 동결했다는 자세한 설명이 이어진다.",
            "why_it_matters": "환율에 영향을 줄 수 있다는 자세한 설명이 이어진다.",
            "source_name": "BBC",
            "url": "https://a",
        }
    ]
)


def test_select_and_explain_parses_valid_json_response():
    fake_response = MagicMock()
    fake_response.text = VALID_JSON_RESPONSE
    fake_model = MagicMock()
    fake_model.generate_content.return_value = fake_response

    with patch("scripts.curator.genai.GenerativeModel", return_value=fake_model):
        result = select_and_explain(SAMPLE_CANDIDATES, api_key="fake-key")

    assert len(result) == 1
    assert result[0].title_kr == "연준 금리 동결"
    assert result[0].source_name == "BBC"
    assert result[0].url == "https://a"


def test_select_and_explain_strips_markdown_code_fence():
    fake_response = MagicMock()
    fake_response.text = f"```json\n{VALID_JSON_RESPONSE}\n```"
    fake_model = MagicMock()
    fake_model.generate_content.return_value = fake_response

    with patch("scripts.curator.genai.GenerativeModel", return_value=fake_model):
        result = select_and_explain(SAMPLE_CANDIDATES, api_key="fake-key")

    assert len(result) == 1
    assert result[0].title_kr == "연준 금리 동결"


def test_select_and_explain_retries_once_then_gives_up_on_bad_json():
    fake_response = MagicMock()
    fake_response.text = "not json"
    fake_model = MagicMock()
    fake_model.generate_content.return_value = fake_response

    with patch("scripts.curator.genai.GenerativeModel", return_value=fake_model):
        result = select_and_explain(SAMPLE_CANDIDATES, api_key="fake-key")

    assert result == []
    assert fake_model.generate_content.call_count == 2


def test_select_and_explain_returns_empty_list_without_calling_gemini_when_no_candidates():
    with patch("scripts.curator.genai.GenerativeModel") as mock_cls:
        result = select_and_explain([], api_key="fake-key")

    assert result == []
    mock_cls.assert_not_called()


def test_select_and_explain_skips_malformed_entry_but_keeps_valid_ones():
    partial_response = json.dumps(
        [
            {
                "title_kr": "유효한 항목",
                "what_happened": "유효한 설명",
                "why_it_matters": "유효한 이유",
                "source_name": "BBC",
                "url": "https://valid",
            },
            {
                "title_kr": "손상된 항목",
                "what_happened": "손상된 설명",
                "why_it_matters": "손상된 이유",
                # Missing "url" field
                "source_name": "CNBC",
            },
        ]
    )

    fake_response = MagicMock()
    fake_response.text = partial_response
    fake_model = MagicMock()
    fake_model.generate_content.return_value = fake_response

    with patch("scripts.curator.genai.GenerativeModel", return_value=fake_model):
        result = select_and_explain(SAMPLE_CANDIDATES, api_key="fake-key")

    assert len(result) == 1
    assert result[0].title_kr == "유효한 항목"
    assert result[0].url == "https://valid"
    # No retry should be needed since JSON was valid
    assert fake_model.generate_content.call_count == 1
