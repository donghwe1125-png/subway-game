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
                "url": "https://a",
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
    assert result[0].url == "https://a"
    # No retry should be needed since JSON was valid
    assert fake_model.generate_content.call_count == 1


def test_select_and_explain_retries_when_top_level_is_not_a_list():
    # Gemini sometimes wraps the array in an object, or returns a single
    # object instead of an array. That's a shape mismatch, not a per-entry
    # problem, so it must trigger the same retry path as bad JSON.
    non_list_response = json.dumps(
        {
            "news": [
                {
                    "title_kr": "연준 금리 동결",
                    "what_happened": "설명",
                    "why_it_matters": "이유",
                    "source_name": "BBC",
                    "url": "https://a",
                }
            ]
        }
    )

    fake_response = MagicMock()
    fake_response.text = non_list_response
    fake_model = MagicMock()
    fake_model.generate_content.return_value = fake_response

    with patch("scripts.curator.genai.GenerativeModel", return_value=fake_model):
        result = select_and_explain(SAMPLE_CANDIDATES, api_key="fake-key")

    assert result == []
    assert fake_model.generate_content.call_count == 2


def test_select_and_explain_caps_result_to_three_items():
    candidates = [
        NewsCandidate(source="BBC", title=f"t{i}", summary="s", url=f"https://c{i}")
        for i in range(5)
    ]
    entries = [
        {
            "title_kr": f"제목{i}",
            "what_happened": f"설명{i}" * 10,
            "why_it_matters": f"이유{i}" * 10,
            "source_name": "BBC",
            "url": f"https://c{i}",
        }
        for i in range(5)
    ]
    fake_response = MagicMock()
    fake_response.text = json.dumps(entries)
    fake_model = MagicMock()
    fake_model.generate_content.return_value = fake_response

    with patch("scripts.curator.genai.GenerativeModel", return_value=fake_model):
        result = select_and_explain(candidates, api_key="fake-key")

    assert len(result) == 3


def test_select_and_explain_drops_item_with_unrecognized_url():
    response = json.dumps(
        [
            {
                "title_kr": "유효한 항목",
                "what_happened": "유효한 설명이 충분히 길게 이어진다.",
                "why_it_matters": "유효한 이유가 충분히 길게 이어진다.",
                "source_name": "BBC",
                "url": "https://a",
            },
            {
                "title_kr": "가짜 url 항목",
                "what_happened": "후보 목록에는 없는 url을 가진 이상한 항목이다.",
                "why_it_matters": "환각(hallucination)일 가능성이 높은 항목이다.",
                "source_name": "CNBC",
                "url": "https://not-a-real-candidate-url.example",
            },
        ]
    )

    fake_response = MagicMock()
    fake_response.text = response
    fake_model = MagicMock()
    fake_model.generate_content.return_value = fake_response

    with patch("scripts.curator.genai.GenerativeModel", return_value=fake_model):
        result = select_and_explain(SAMPLE_CANDIDATES, api_key="fake-key")

    assert len(result) == 1
    assert result[0].url == "https://a"


def test_select_and_explain_strips_uppercase_json_fence():
    fake_response = MagicMock()
    fake_response.text = f"```JSON\n{VALID_JSON_RESPONSE}\n```"
    fake_model = MagicMock()
    fake_model.generate_content.return_value = fake_response

    with patch("scripts.curator.genai.GenerativeModel", return_value=fake_model):
        result = select_and_explain(SAMPLE_CANDIDATES, api_key="fake-key")

    assert len(result) == 1
    assert result[0].title_kr == "연준 금리 동결"
