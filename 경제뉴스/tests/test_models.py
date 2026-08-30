from scripts.models import DigestItem, NewsCandidate


def test_news_candidate_stores_fields():
    candidate = NewsCandidate(
        source="BBC",
        title="제목",
        summary="요약",
        url="https://a",
        published="2026-08-30",
    )
    assert candidate.source == "BBC"
    assert candidate.title == "제목"
    assert candidate.summary == "요약"
    assert candidate.url == "https://a"
    assert candidate.published == "2026-08-30"


def test_news_candidate_published_defaults_to_empty_string():
    candidate = NewsCandidate(source="BBC", title="제목", summary="요약", url="https://a")
    assert candidate.published == ""


def test_digest_item_stores_fields():
    item = DigestItem(
        title_kr="한글제목",
        what_happened="무슨일",
        why_it_matters="왜중요",
        source_name="BBC",
        url="https://a",
    )
    assert item.title_kr == "한글제목"
    assert item.what_happened == "무슨일"
    assert item.why_it_matters == "왜중요"
    assert item.source_name == "BBC"
    assert item.url == "https://a"
