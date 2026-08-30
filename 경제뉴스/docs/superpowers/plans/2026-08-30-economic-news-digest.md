# 세계 경제뉴스 텔레그램 다이제스트 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 매일 아침 07:00 KST에, 해외 경제 언론사 RSS에서 후보 기사를 모으고 Gemini로 가장 중요한 3개를 골라 초보자도 이해하기 쉬운 구어체로 설명한 뒤 텔레그램으로 자동 발송한다.

**Architecture:** `경제뉴스/scripts/` 아래 파이프라인을 4단계 모듈(뉴스 수집 → AI 선별/설명 → 메시지 포맷 → 텔레그램 전송)로 나누고, `main.py`가 이를 순서대로 호출하는 오케스트레이터 역할을 한다. GitHub Actions가 매일 정해진 시각에 `python -m scripts.main`을 실행한다. `소식 자동화` 프로젝트(같은 저장소)의 검증된 텔레그램 전송/메시지 분할 패턴을 재사용한다. 이 프로젝트는 매일 새로 3개를 고르는 방식이라 중복 방지용 상태 저장(state.json)이 필요 없다.

**Tech Stack:** Python 3.12, `requests`, `feedparser`, `google-generativeai` (Gemini), Telegram Bot API, GitHub Actions (cron), pytest

**Spec:** `경제뉴스/docs/superpowers/specs/2026-08-30-economic-news-digest-design.md`

## Global Constraints

- 전송 채널: 텔레그램 (기존 `소식 자동화` 프로젝트의 봇 토큰/채팅 ID를 그대로 재사용 — GitHub Secrets에 이미 등록되어 있다면 추가 작업 없음)
- 뉴스 소스: 해외 경제 언론사 RSS만 사용 (국내 언론 국제 섹션 아님)
- 소스 → 선별 방식: RSS로 헤드라인 후보를 먼저 모으고 AI가 그중에서 고름 (AI 자체 웹검색 방식 아님)
- 전송 시각: 매일 07:00~08:00 KST
- 뉴스 개수: 정확히 3개 (실패로 부족할 경우 있는 만큼만)
- 분량/톤: 뉴스당 "무슨 일" + "왜 중요한지"를 배경 설명 포함해 상세히, 친근한 구어체, 3개 합쳐 약 3분 분량 (약 200~300자 이상/항목)
- 상태 저장 없음: 매일 새로 3개를 고르므로 이전 발송 이력을 기억하지 않는다
- 소스 일부 실패 시 나머지로 계속 진행, 전체 실패 시 "오늘은 뉴스를 가져오지 못했어요" 알림을 텔레그램으로 전송

---

## Task 1: 프로젝트 스캐폴딩 + 데이터 모델

**Files:**
- Create: `경제뉴스/scripts/__init__.py`
- Create: `경제뉴스/scripts/models.py`
- Create: `경제뉴스/tests/__init__.py`
- Create: `경제뉴스/tests/test_models.py`
- Create: `경제뉴스/requirements.txt`
- Create: `경제뉴스/requirements-dev.txt`
- Create: `경제뉴스/.env.example`

**Interfaces:**
- Produces: `NewsCandidate(source: str, title: str, summary: str, url: str, published: str = "")` — dataclass
- Produces: `DigestItem(title_kr: str, what_happened: str, why_it_matters: str, source_name: str, url: str)` — dataclass

- [ ] **Step 1: 스캐폴딩 파일 만들기**

`경제뉴스/scripts/__init__.py` (빈 파일):

```python
```

`경제뉴스/tests/__init__.py` (빈 파일):

```python
```

`경제뉴스/requirements.txt`:

```
requests==2.34.2
feedparser==6.0.11
google-generativeai==0.8.6
```

`경제뉴스/requirements-dev.txt`:

```
-r requirements.txt
pytest==9.1.1
```

`경제뉴스/.env.example`:

```
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-telegram-chat-id
GEMINI_API_KEY=your-gemini-api-key
```

- [ ] **Step 2: 실패하는 테스트 작성**

`경제뉴스/tests/test_models.py`:

```python
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
```

- [ ] **Step 3: 테스트 실행해서 실패 확인**

Run: `cd 경제뉴스 && python -m pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.models'`

- [ ] **Step 4: 최소 구현 작성**

`경제뉴스/scripts/models.py`:

```python
from dataclasses import dataclass


@dataclass
class NewsCandidate:
    source: str
    title: str
    summary: str
    url: str
    published: str = ""


@dataclass
class DigestItem:
    title_kr: str
    what_happened: str
    why_it_matters: str
    source_name: str
    url: str
```

- [ ] **Step 5: 테스트 실행해서 통과 확인**

Run: `cd 경제뉴스 && python -m pytest tests/test_models.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: 커밋**

```bash
cd "경제뉴스" && git add scripts/__init__.py scripts/models.py tests/__init__.py tests/test_models.py requirements.txt requirements-dev.txt .env.example
git commit -m "feat: scaffold economic-news-digest project and data models"
```

---

## Task 2: RSS 뉴스 수집 (news_sources.py)

**Files:**
- Create: `경제뉴스/scripts/news_sources.py`
- Test: `경제뉴스/tests/test_news_sources.py`

RSS 후보 4곳(BBC, CNBC, MarketWatch, Investing.com)은 실제로 살아있는지 curl로 확인했다. CNBC는 브라우저 User-Agent 헤더 없이는 403을 반환하므로, 모든 요청에 공통 User-Agent를 붙인다.

**Interfaces:**
- Consumes: `NewsCandidate` from `scripts.models` (Task 1)
- Produces: `fetch_feed_live(feed_key: str) -> list[NewsCandidate]`
- Produces: `FEEDS: dict[str, tuple[str, str]]` — `{feed_key: (source_label, url)}`
- Produces: `SOURCES: dict[str, Callable[[], list[NewsCandidate]]]` — `main.py`가 사용할 소스 이름 → 수집 함수 매핑

- [ ] **Step 1: 실패하는 테스트 작성**

`경제뉴스/tests/test_news_sources.py`:

```python
from unittest.mock import MagicMock, patch

from scripts.news_sources import FEEDS, SOURCES, fetch_feed_live

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


def test_fetch_feed_live_parses_entries_into_candidates():
    fake_response = MagicMock()
    fake_response.content = SAMPLE_RSS
    fake_response.raise_for_status.return_value = None

    with patch(
        "scripts.news_sources.requests.get", return_value=fake_response
    ) as mock_get:
        candidates = fetch_feed_live("bbc")

    called_url = mock_get.call_args.args[0]
    assert called_url == FEEDS["bbc"][1]
    assert len(candidates) == 2
    assert candidates[0].source == "BBC"
    assert candidates[0].title == "Fed holds interest rates steady"
    assert candidates[0].url == "https://example.com/fed-holds-rates"
    assert "Federal Reserve" in candidates[0].summary


def test_fetch_feed_live_sends_browser_user_agent():
    fake_response = MagicMock()
    fake_response.content = SAMPLE_RSS
    fake_response.raise_for_status.return_value = None

    with patch(
        "scripts.news_sources.requests.get", return_value=fake_response
    ) as mock_get:
        fetch_feed_live("cnbc")

    headers = mock_get.call_args.kwargs["headers"]
    assert "Mozilla" in headers["User-Agent"]


def test_fetch_feed_live_raises_on_http_error():
    fake_response = MagicMock()
    fake_response.raise_for_status.side_effect = RuntimeError("HTTP 403")

    with patch("scripts.news_sources.requests.get", return_value=fake_response):
        try:
            fetch_feed_live("cnbc")
        except RuntimeError:
            pass
        else:
            raise AssertionError("expected raise_for_status error to propagate")


def test_fetch_feed_live_raises_on_unparseable_feed():
    fake_response = MagicMock()
    fake_response.content = b"not xml at all"
    fake_response.raise_for_status.return_value = None

    with patch("scripts.news_sources.requests.get", return_value=fake_response):
        try:
            fetch_feed_live("bbc")
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError for unparseable feed")


def test_sources_maps_every_feed_key():
    assert set(SOURCES.keys()) == set(FEEDS.keys())
    assert callable(SOURCES["bbc"])
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `cd 경제뉴스 && python -m pytest tests/test_news_sources.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.news_sources'`

- [ ] **Step 3: 최소 구현 작성**

`경제뉴스/scripts/news_sources.py`:

```python
import functools
from typing import Callable

import feedparser
import requests

from scripts.models import NewsCandidate

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# 언론사가 RSS 주소를 바꾸면 여기만 고치면 된다.
FEEDS: dict[str, tuple[str, str]] = {
    "bbc": ("BBC", "http://feeds.bbci.co.uk/news/business/rss.xml"),
    "cnbc": ("CNBC", "https://www.cnbc.com/id/10001147/device/rss/rss.html"),
    "marketwatch": ("MarketWatch", "https://www.marketwatch.com/rss/topstories"),
    "investing": ("Investing.com", "https://www.investing.com/rss/news_25.rss"),
}


def fetch_feed_live(feed_key: str) -> list[NewsCandidate]:
    source_label, url = FEEDS[feed_key]
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
    response.raise_for_status()

    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"{feed_key} feed failed to parse: {parsed.bozo_exception}")

    return [
        NewsCandidate(
            source=source_label,
            title=entry.get("title", "").strip(),
            summary=entry.get("summary", "").strip(),
            url=entry.get("link", ""),
            published=entry.get("published", ""),
        )
        for entry in parsed.entries
    ]


SOURCES: dict[str, Callable[[], list[NewsCandidate]]] = {
    key: functools.partial(fetch_feed_live, key) for key in FEEDS
}
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `cd 경제뉴스 && python -m pytest tests/test_news_sources.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 커밋**

```bash
cd "경제뉴스" && git add scripts/news_sources.py tests/test_news_sources.py
git commit -m "feat: add RSS news source fetchers"
```

---

## Task 3: AI 선별 + 설명 (curator.py)

**Files:**
- Create: `경제뉴스/scripts/curator.py`
- Test: `경제뉴스/tests/test_curator.py`

**Interfaces:**
- Consumes: `NewsCandidate`, `DigestItem` from `scripts.models` (Task 1)
- Produces: `select_and_explain(candidates: list[NewsCandidate], api_key: str, model_name: str = DEFAULT_MODEL) -> list[DigestItem]`

- [ ] **Step 1: 실패하는 테스트 작성**

`경제뉴스/tests/test_curator.py`:

```python
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
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `cd 경제뉴스 && python -m pytest tests/test_curator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.curator'`

- [ ] **Step 3: 최소 구현 작성**

`경제뉴스/scripts/curator.py`:

```python
import json
import os

import google.generativeai as genai

from scripts.models import DigestItem, NewsCandidate

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

PROMPT_TEMPLATE = """\
너는 세계 경제뉴스를 한 번도 안 읽어본 한국인 독자를 위해 뉴스를 골라 설명해주는 어시스턴트야.

아래는 오늘 여러 해외 경제 언론사에서 올라온 기사 후보 목록이야 (JSON 배열).
이 중에서 오늘 가장 중요한 세계 경제뉴스 3개를 골라줘.

각 뉴스에 대해 아래 JSON 스키마로, 한국어로, 친근한 구어체로 답변해줘.
설명은 짧게 요약하지 말고, 배경 설명과 한국/개인 생활에 미치는 영향까지 포함해서
충분히 자세하게 써줘 (하나당 200~300자 이상).

[
  {{
    "title_kr": "짧은 한글 제목",
    "what_happened": "무슨 일이 있었는지, 배경 설명 포함해서 자세히",
    "why_it_matters": "왜 중요한지, 한국/개인 생활에 미치는 영향 포함해서 자세히",
    "source_name": "언론사 이름 (후보 목록의 source 값 그대로)",
    "url": "후보 목록의 url 값 그대로"
  }}
]

다른 설명 없이 JSON 배열만 출력해.

후보 목록:
{candidates_json}
"""


def _build_prompt(candidates: list[NewsCandidate]) -> str:
    trimmed = [
        {
            "source": c.source,
            "title": c.title,
            "summary": c.summary[:200],
            "url": c.url,
        }
        for c in candidates
    ]
    return PROMPT_TEMPLATE.format(
        candidates_json=json.dumps(trimmed, ensure_ascii=False)
    )


def _parse_response(text: str) -> list[DigestItem]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    data = json.loads(cleaned)
    return [
        DigestItem(
            title_kr=entry["title_kr"],
            what_happened=entry["what_happened"],
            why_it_matters=entry["why_it_matters"],
            source_name=entry["source_name"],
            url=entry["url"],
        )
        for entry in data
    ]


def select_and_explain(
    candidates: list[NewsCandidate], api_key: str, model_name: str = DEFAULT_MODEL
) -> list[DigestItem]:
    if not candidates:
        return []

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    prompt = _build_prompt(candidates)

    for attempt in range(2):
        try:
            response = model.generate_content(prompt)
            return _parse_response(response.text or "")
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            print(f"[curator] parse failed (attempt {attempt + 1}): {exc}")
        except Exception as exc:
            print(f"[curator] gemini call failed (attempt {attempt + 1}): {exc}")
    return []
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `cd 경제뉴스 && python -m pytest tests/test_curator.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
cd "경제뉴스" && git add scripts/curator.py tests/test_curator.py
git commit -m "feat: add Gemini curator to select and explain top news"
```

---

## Task 4: 메시지 포맷 (message_formatter.py)

**Files:**
- Create: `경제뉴스/scripts/message_formatter.py`
- Test: `경제뉴스/tests/test_message_formatter.py`

**Interfaces:**
- Consumes: `DigestItem` from `scripts.models` (Task 1)
- Produces: `build_digest_message(items: list[DigestItem], today: date) -> list[str]`
- Produces: `build_error_message(reason: str) -> str`
- Produces: `MAX_CHARS: int`

- [ ] **Step 1: 실패하는 테스트 작성**

`경제뉴스/tests/test_message_formatter.py`:

```python
from datetime import date

from scripts.message_formatter import MAX_CHARS, build_digest_message, build_error_message
from scripts.models import DigestItem


def _item(n: int, why_len: int = 50) -> DigestItem:
    return DigestItem(
        title_kr=f"제목{n}",
        what_happened=f"무슨 일 설명{n}",
        why_it_matters="왜중요" * why_len,
        source_name="BBC",
        url=f"https://example.com/{n}",
    )


def test_build_digest_message_fits_in_one_message_when_short():
    items = [_item(1), _item(2), _item(3)]
    messages = build_digest_message(items, date(2026, 8, 30))

    assert len(messages) == 1
    assert "8/30(일)" in messages[0]
    assert "제목1" in messages[0]
    assert "제목2" in messages[0]
    assert "제목3" in messages[0]
    assert "https://example.com/1" in messages[0]


def test_build_digest_message_splits_when_exceeding_max_chars():
    items = [_item(1, why_len=800), _item(2, why_len=800), _item(3, why_len=800)]
    messages = build_digest_message(items, date(2026, 8, 30))

    assert len(messages) == 3
    for message in messages:
        assert len(message) <= MAX_CHARS + 200


def test_build_error_message_returns_warning_text():
    message = build_error_message("오늘은 뉴스를 가져오지 못했어요")

    assert message.startswith("⚠️")
    assert "오늘은 뉴스를 가져오지 못했어요" in message
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `cd 경제뉴스 && python -m pytest tests/test_message_formatter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.message_formatter'`

- [ ] **Step 3: 최소 구현 작성**

`경제뉴스/scripts/message_formatter.py`:

```python
from datetime import date

from scripts.models import DigestItem

WEEKDAYS_KR = ["월", "화", "수", "목", "금", "토", "일"]
NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

# 텔레그램 메시지 한 통의 실제 상한은 4096자. 여유를 두고 보수적으로 잡았다.
# 한 통이 이 길이를 넘으면 잘라내는 대신 여러 통으로 나눠 보낸다.
MAX_CHARS = 3500

SEPARATOR = "\n\n──────────────\n\n"


def _date_label(today: date) -> str:
    return f"{today.month}/{today.day}({WEEKDAYS_KR[today.weekday()]})"


def _format_item(index: int, item: DigestItem) -> str:
    number = NUMBER_EMOJIS[index - 1] if index - 1 < len(NUMBER_EMOJIS) else f"{index}."
    return (
        f"{number} {item.title_kr}\n\n"
        f"{item.what_happened}\n\n"
        f"💡 왜 중요할까?\n{item.why_it_matters}\n\n"
        f"🔗 출처: {item.source_name} ({item.url})"
    )


def build_digest_message(items: list[DigestItem], today: date) -> list[str]:
    header = f"📰 {_date_label(today)} 아침, 오늘의 세계 경제뉴스 {len(items)}가지"
    blocks = [_format_item(i, item) for i, item in enumerate(items, start=1)]

    chunks: list[list[str]] = []
    current: list[str] = []
    current_len = 0
    for block in blocks:
        block_len = len(block) + len(SEPARATOR)
        if current and current_len + block_len > MAX_CHARS:
            chunks.append(current)
            current = [block]
            current_len = len(block)
        else:
            current.append(block)
            current_len += block_len
    if current:
        chunks.append(current)

    messages = []
    for index, chunk in enumerate(chunks):
        prefix = f"{header}\n\n" if index == 0 else ""
        messages.append(prefix + SEPARATOR.join(chunk))
    return messages


def build_error_message(reason: str) -> str:
    return f"⚠️ {reason}"
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `cd 경제뉴스 && python -m pytest tests/test_message_formatter.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
cd "경제뉴스" && git add scripts/message_formatter.py tests/test_message_formatter.py
git commit -m "feat: add telegram message formatter with length-based splitting"
```

---

## Task 5: 텔레그램 전송 (telegram_sender.py)

`소식 자동화/scripts/telegram_sender.py`와 동일한 구현을 그대로 가져온다 (이미 검증된 코드).

**Files:**
- Create: `경제뉴스/scripts/telegram_sender.py`
- Test: `경제뉴스/tests/test_telegram_sender.py`

**Interfaces:**
- Produces: `send_message(bot_token: str, chat_id: str, text: str) -> None`

- [ ] **Step 1: 실패하는 테스트 작성**

`경제뉴스/tests/test_telegram_sender.py`:

```python
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
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `cd 경제뉴스 && python -m pytest tests/test_telegram_sender.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.telegram_sender'`

- [ ] **Step 3: 최소 구현 작성**

`경제뉴스/scripts/telegram_sender.py`:

```python
import requests

API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_message(bot_token: str, chat_id: str, text: str) -> None:
    response = requests.post(
        API_URL.format(token=bot_token),
        json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=10,
    )
    response.raise_for_status()
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `cd 경제뉴스 && python -m pytest tests/test_telegram_sender.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
cd "경제뉴스" && git add scripts/telegram_sender.py tests/test_telegram_sender.py
git commit -m "feat: add telegram sender"
```

---

## Task 6: 오케스트레이터 (main.py)

**Files:**
- Create: `경제뉴스/scripts/main.py`
- Test: `경제뉴스/tests/test_main.py`

**Interfaces:**
- Consumes: `SOURCES` from `scripts.news_sources` (Task 2)
- Consumes: `select_and_explain(candidates, api_key, model_name=...)` from `scripts.curator` (Task 3)
- Consumes: `build_digest_message(items, today)`, `build_error_message(reason)` from `scripts.message_formatter` (Task 4)
- Consumes: `send_message(bot_token, chat_id, text)` from `scripts.telegram_sender` (Task 5)
- Produces: `collect_candidates(sources: dict) -> tuple[list[NewsCandidate], list[str]]`
- Produces: `main() -> None`

- [ ] **Step 1: 실패하는 테스트 작성**

`경제뉴스/tests/test_main.py`:

```python
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
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `cd 경제뉴스 && python -m pytest tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.main'`

- [ ] **Step 3: 최소 구현 작성**

`경제뉴스/scripts/main.py`:

```python
import os
import sys
from datetime import datetime, timedelta, timezone

from scripts.curator import select_and_explain
from scripts.message_formatter import build_digest_message, build_error_message
from scripts.models import NewsCandidate
from scripts.news_sources import SOURCES
from scripts.telegram_sender import send_message

KST = timezone(timedelta(hours=9))


def collect_candidates(sources: dict) -> tuple[list[NewsCandidate], list[str]]:
    all_candidates: list[NewsCandidate] = []
    failed_sources: list[str] = []

    for name, fetch_fn in sources.items():
        try:
            all_candidates.extend(fetch_fn())
        except Exception as exc:
            print(f"[{name}] fetch failed: {exc}", file=sys.stderr)
            failed_sources.append(name)

    return all_candidates, failed_sources


def main() -> None:
    gemini_key = os.environ["GEMINI_API_KEY"]
    telegram_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    telegram_chat_id = os.environ["TELEGRAM_CHAT_ID"]

    candidates, failed_sources = collect_candidates(SOURCES)
    if failed_sources:
        print(f"failed sources: {failed_sources}", file=sys.stderr)

    items = select_and_explain(candidates, gemini_key) if candidates else []

    today = datetime.now(KST).date()
    if items:
        messages = build_digest_message(items, today)
    else:
        messages = [
            build_error_message("오늘은 뉴스를 가져오지 못했어요. 내일 다시 시도할게요.")
        ]

    for message in messages:
        send_message(telegram_bot_token, telegram_chat_id, message)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `cd 경제뉴스 && python -m pytest tests/test_main.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 전체 테스트 스위트 실행**

Run: `cd 경제뉴스 && python -m pytest -v`
Expected: 모든 테스트 PASS (Task 1~6 합계 17개)

- [ ] **Step 6: 커밋**

```bash
cd "경제뉴스" && git add scripts/main.py tests/test_main.py
git commit -m "feat: wire economic news digest pipeline together"
```

---

## Task 7: GitHub Actions 스케줄링

**Files:**
- Create: `.github/workflows/economic-news-digest.yml`

**Interfaces:**
- Consumes: `scripts.main` (Task 6) via `python -m scripts.main`
- Consumes: repo secrets `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY` (기존 `소식 자동화`용으로 이미 등록되어 있으면 재사용)

- [ ] **Step 1: 워크플로우 파일 작성**

`.github/workflows/economic-news-digest.yml`:

```yaml
name: Economic News Digest

on:
  schedule:
    - cron: '0 22 * * *'
  workflow_dispatch: {}

jobs:
  digest:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: 경제뉴스

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run digest
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: python -m scripts.main
```

cron `'0 22 * * *'`은 UTC 22:00 = KST 07:00(다음날) 이다.

- [ ] **Step 2: YAML 문법 확인**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/economic-news-digest.yml'))" && echo OK`
Expected: `OK` 출력 (파이썬에 `pyyaml`이 없으면 `pip install pyyaml` 먼저 실행)

- [ ] **Step 3: 커밋**

```bash
git add .github/workflows/economic-news-digest.yml
git commit -m "ci: add scheduled GitHub Actions workflow for economic news digest"
```

- [ ] **Step 4: (사용자 확인 필요) GitHub Secrets 확인**

저장소 Settings → Secrets and variables → Actions에서 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY`가 이미 등록되어 있는지 확인한다 (`소식 자동화` 워크플로우가 쓰던 값 그대로 재사용). 없다면 새로 등록한다.

- [ ] **Step 5: (사용자 확인 필요) 수동 실행으로 종단 테스트**

GitHub 저장소 → Actions 탭 → "Economic News Digest" 워크플로우 → "Run workflow" 버튼으로 수동 실행한 뒤, 텔레그램으로 실제 다이제스트 메시지가 오는지 확인한다. 실패하면 Actions 로그에서 어느 단계(수집/AI 선별/전송)에서 실패했는지 확인한다.
