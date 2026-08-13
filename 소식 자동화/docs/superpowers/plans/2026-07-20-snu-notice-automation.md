# SNU 소식 자동 요약 시스템 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 경영대학 학과 공지, Gmail로 전달되는 서울대 공지 메일, 비교과 프로그램 신규 항목을 매주 월/목 아침 8시(KST)에 자동으로 모아 Gemini로 한 줄 요약한 뒤 카카오톡 "나에게 보내기"로 발송하는 GitHub Actions 파이프라인을 만든다.

**Architecture:** 세 개의 독립적인 수집 모듈(`cba_notice`, `gmail_notice`, `extra_snu`)이 각각 `NoticeItem` 리스트를 반환하고, `state_store`가 이전 실행 이후의 신규 항목만 걸러낸다. 신규 항목은 `summarize`(Gemini)로 한 줄 요약되고, `message_formatter`가 소스별로 묶어 카카오톡 메시지 문자열 목록을 만들면, `kakao_sender`가 순서대로 발송한다. `main.py`가 이 전체를 조립하며, 한 소스가 실패해도 나머지는 계속 진행한다. GitHub Actions가 cron으로 이 스크립트를 실행하고 끝나면 `state.json`을 커밋한다.

**Tech Stack:** Python 3.12, `requests`, `beautifulsoup4`, `playwright`(sync API, Chromium headless), `google-generativeai`(Gemini), 표준 라이브러리 `imaplib`/`email`, GitHub Actions.

## Global Constraints

- Python 3.12를 사용한다 (GitHub Actions `actions/setup-python@v5`와 로컬 개발 환경 동일 버전).
- 유료 API를 쓰지 않는다: Gemini는 무료 할당량 범위 내에서만 호출하고, 카카오는 "나에게 보내기"(`/v2/api/talk/memo/default/send`)만 사용한다. 친구톡/알림톡 등 유료 API는 사용하지 않는다.
- 새로 추가하는 의존성은 반드시 `소식 자동화/requirements.txt`(런타임) 또는 `소식 자동화/requirements-dev.txt`(테스트 전용)에 기록한다.
- 실행 주기는 매주 월요일·목요일 08:00 KST 이며, cron 표현식은 UTC 기준 `0 23 * * 0,3` (일요일 23:00 UTC = 월요일 08:00 KST, 수요일 23:00 UTC = 목요일 08:00 KST) 이다.
- 어떤 비밀번호/API 키도 코드나 `state.json`에 하드코딩하지 않는다. 모두 환경변수(`GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `KAKAO_REST_API_KEY`, `KAKAO_REFRESH_TOKEN`, `GEMINI_API_KEY`)로만 전달하고, GitHub Actions에서는 Secrets로 주입한다.
- 상태 파일은 프로젝트 루트의 `소식 자동화/state.json`이며, 매 실행 성공 후 git에 커밋된다.
- 모든 신규 파일은 `소식 자동화/` 아래 두되, GitHub Actions 워크플로 파일만 저장소 규칙상 리포지토리 루트의 `.github/workflows/`에 둔다 (리포지토리 루트는 `/Users/donghwikim/바이브코딩`).

---

## Task 1: 프로젝트 뼈대 & 공용 데이터 모델

**Files:**
- Create: `소식 자동화/requirements.txt`
- Create: `소식 자동화/requirements-dev.txt`
- Create: `소식 자동화/scripts/__init__.py`
- Create: `소식 자동화/scripts/models.py`
- Create: `소식 자동화/tests/__init__.py`
- Test: `소식 자동화/tests/test_models.py`

**Interfaces:**
- Produces: `NoticeItem` dataclass with fields `id: str, source: str, title: str, url: str, date: str = "", meta: str = ""` — 이후 모든 모듈이 이 타입을 사용한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`소식 자동화/tests/test_models.py`:
```python
from scripts.models import NoticeItem


def test_notice_item_stores_fields():
    item = NoticeItem(
        id="123",
        source="cba",
        title="테스트 공지",
        url="https://cba.snu.ac.kr/x",
        date="2026-08-14",
        meta="일반",
    )
    assert item.id == "123"
    assert item.source == "cba"
    assert item.title == "테스트 공지"
    assert item.url == "https://cba.snu.ac.kr/x"
    assert item.date == "2026-08-14"
    assert item.meta == "일반"


def test_notice_item_defaults():
    item = NoticeItem(id="1", source="extra", title="t", url="u")
    assert item.date == ""
    assert item.meta == ""
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run (반드시 `소식 자동화/` 디렉터리에서 실행):
```bash
cd "소식 자동화" && python3 -m pytest tests/test_models.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts'` 또는 `models`

- [ ] **Step 3: 파일 생성**

`소식 자동화/requirements.txt`:
```
requests
beautifulsoup4
playwright
google-generativeai
```

`소식 자동화/requirements-dev.txt`:
```
-r requirements.txt
pytest
```

`소식 자동화/scripts/__init__.py`: (빈 파일)

`소식 자동화/tests/__init__.py`: (빈 파일)

`소식 자동화/scripts/models.py`:
```python
from dataclasses import dataclass


@dataclass
class NoticeItem:
    id: str
    source: str
    title: str
    url: str
    date: str = ""
    meta: str = ""
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run:
```bash
cd "소식 자동화" && python3 -m pip install -r requirements-dev.txt && python3 -m pytest tests/test_models.py -v
```
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add "소식 자동화/requirements.txt" "소식 자동화/requirements-dev.txt" "소식 자동화/scripts/__init__.py" "소식 자동화/scripts/models.py" "소식 자동화/tests/__init__.py" "소식 자동화/tests/test_models.py"
git commit -m "feat: add project scaffolding and NoticeItem model"
```

---

## Task 2: 상태 저장소 (중복 방지 ledger)

**Files:**
- Create: `소식 자동화/scripts/state_store.py`
- Test: `소식 자동화/tests/test_state_store.py`

**Interfaces:**
- Consumes: `NoticeItem` (from Task 1, `scripts.models`)
- Produces:
  - `load_state(path: str) -> dict` — 파일 없으면 `{}` 반환
  - `save_state(path: str, state: dict) -> None`
  - `filter_new_items(items: list[NoticeItem], seen_ids: list[str]) -> list[NoticeItem]`
  - `update_seen_ids(seen_ids: list[str], items: list[NoticeItem], max_size: int = 500) -> list[str]`
- `state`는 `{"cba": ["id1", "id2", ...], "gmail": [...], "extra": [...]}` 형태의 dict. 각 소스 키에는 "이미 본 항목 id 목록"(최근 것이 앞쪽)이 저장된다.

- [ ] **Step 1: 실패하는 테스트 작성**

`소식 자동화/tests/test_state_store.py`:
```python
import json

from scripts.models import NoticeItem
from scripts.state_store import (
    filter_new_items,
    load_state,
    save_state,
    update_seen_ids,
)


def test_load_state_missing_file_returns_empty_dict(tmp_path):
    path = tmp_path / "state.json"
    assert load_state(str(path)) == {}


def test_save_and_load_state_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    save_state(str(path), {"cba": ["1", "2"]})
    assert load_state(str(path)) == {"cba": ["1", "2"]}
    with open(path, encoding="utf-8") as f:
        assert json.load(f) == {"cba": ["1", "2"]}


def test_filter_new_items_excludes_seen_ids():
    items = [
        NoticeItem(id="1", source="cba", title="a", url="u"),
        NoticeItem(id="2", source="cba", title="b", url="u"),
    ]
    result = filter_new_items(items, seen_ids=["1"])
    assert [i.id for i in result] == ["2"]


def test_filter_new_items_first_run_returns_all():
    items = [NoticeItem(id="1", source="cba", title="a", url="u")]
    result = filter_new_items(items, seen_ids=[])
    assert [i.id for i in result] == ["1"]


def test_update_seen_ids_dedupes_and_prepends_new():
    items = [
        NoticeItem(id="3", source="cba", title="a", url="u"),
        NoticeItem(id="1", source="cba", title="b", url="u"),
    ]
    result = update_seen_ids(seen_ids=["1", "2"], items=items)
    assert result == ["3", "1", "2"]


def test_update_seen_ids_trims_to_max_size():
    old_ids = [str(i) for i in range(10)]
    items = [NoticeItem(id="new", source="cba", title="a", url="u")]
    result = update_seen_ids(seen_ids=old_ids, items=items, max_size=5)
    assert len(result) == 5
    assert result[0] == "new"
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run:
```bash
cd "소식 자동화" && python3 -m pytest tests/test_state_store.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.state_store'`

- [ ] **Step 3: 구현**

`소식 자동화/scripts/state_store.py`:
```python
import json
import os

from scripts.models import NoticeItem


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_state(path: str, state: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)


def filter_new_items(items: list[NoticeItem], seen_ids: list[str]) -> list[NoticeItem]:
    seen = set(seen_ids)
    return [item for item in items if item.id not in seen]


def update_seen_ids(
    seen_ids: list[str], items: list[NoticeItem], max_size: int = 500
) -> list[str]:
    combined = [item.id for item in items] + list(seen_ids)
    deduped: list[str] = []
    seen: set[str] = set()
    for item_id in combined:
        if item_id not in seen:
            seen.add(item_id)
            deduped.append(item_id)
    return deduped[:max_size]
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run:
```bash
cd "소식 자동화" && python3 -m pytest tests/test_state_store.py -v
```
Expected: PASS (6 passed)

- [ ] **Step 5: 커밋**

```bash
git add "소식 자동화/scripts/state_store.py" "소식 자동화/tests/test_state_store.py"
git commit -m "feat: add state store for duplicate-notice tracking"
```

---

## Task 3: 학과 홈페이지 공지 수집 (cba.snu.ac.kr)

실제 페이지(`https://cba.snu.ac.kr/newsroom/notice?sc=y`)를 확인한 결과, 로그인 없이 접근 가능한 정적 HTML이며 구조는 다음과 같다:

```html
<div class="board">
  <table class="fixwidth table table-rows thcenter noborder va-m">
    <tbody>
      <tr class="noti">
        <td class="text-center noti-ico">공지</td>
        <td class="text-center hidden-sm-down">일반</td>
        <td class="title noti-tit">
          <a href="/newsroom/notice?md=v&bbsidx=26334"><span class="">제목텍스트</span></a>
        </td>
        <td class="text-center hidden-xs-down FS12">2026-08-13</td>
        <td class="text-center hidden-sm-down">60</td>
      </tr>
      ...
```

`bbsidx` 쿼리 파라미터가 게시글의 고유하고 안정적인 ID다.

**Files:**
- Create: `소식 자동화/scripts/cba_notice.py`
- Create: `소식 자동화/tests/fixtures/cba_notice_sample.html`
- Test: `소식 자동화/tests/test_cba_notice.py`

**Interfaces:**
- Consumes: `NoticeItem` (Task 1)
- Produces:
  - `parse_cba_notices(html: str) -> list[NoticeItem]`
  - `fetch_cba_notices_live() -> list[NoticeItem]` (네트워크 호출, `main.py`가 사용)

- [ ] **Step 1: 실패하는 테스트와 fixture 작성**

`소식 자동화/tests/fixtures/cba_notice_sample.html` (실제 사이트에서 그대로 가져온 구조):
```html
<div class="board">
  <table class="fixwidth table table-rows thcenter noborder va-m">
    <thead>
      <tr>
        <th scope="col">No.</th>
        <th scope="col" class="hidden-sm-down">분류</th>
        <th scope="col">제목</th>
        <th scope="col" class="hidden-xs-down">날짜</th>
        <th scope="col" class="hidden-sm-down">조회수</th>
      </tr>
    </thead>
    <tbody>
      <tr class="noti">
        <td class="text-center noti-ico">공지</td>
        <td class="text-center hidden-sm-down">일반</td>
        <td class="title noti-tit">
          <a href="/newsroom/notice?md=v&bbsidx=26334"><span class="">2026학년도 2학기 졸업세미나 과목 등록 처리 완료 안내</span></a>
        </td>
        <td class="text-center hidden-xs-down FS12">2026-08-13</td>
        <td class="text-center hidden-sm-down">60</td>
      </tr>
      <tr class="noti">
        <td class="text-center noti-ico">공지</td>
        <td class="text-center hidden-sm-down">장학</td>
        <td class="title noti-tit">
          <a href="/newsroom/notice?md=v&bbsidx=26328"><span class="">[대학원] 2026학년도 2학기 대학원생 생활지원장학금 선발 안내(~9/7 18:00)</span></a>
        </td>
        <td class="text-center hidden-xs-down FS12">2026-08-12</td>
        <td class="text-center hidden-sm-down">114</td>
      </tr>
    </tbody>
  </table>
</div>
```

`소식 자동화/tests/test_cba_notice.py`:
```python
import os

from scripts.cba_notice import parse_cba_notices

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "cba_notice_sample.html"
)


def _load_fixture() -> str:
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return f.read()


def test_parse_cba_notices_extracts_all_rows():
    items = parse_cba_notices(_load_fixture())
    assert len(items) == 2


def test_parse_cba_notices_extracts_fields_correctly():
    items = parse_cba_notices(_load_fixture())
    first = items[0]
    assert first.id == "26334"
    assert first.source == "cba"
    assert first.title == "2026학년도 2학기 졸업세미나 과목 등록 처리 완료 안내"
    assert first.url == "https://cba.snu.ac.kr/newsroom/notice?md=v&bbsidx=26334"
    assert first.date == "2026-08-13"
    assert first.meta == "일반"


def test_parse_cba_notices_second_row_category():
    items = parse_cba_notices(_load_fixture())
    assert items[1].id == "26328"
    assert items[1].meta == "장학"
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run:
```bash
cd "소식 자동화" && python3 -m pytest tests/test_cba_notice.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.cba_notice'`

- [ ] **Step 3: 구현**

`소식 자동화/scripts/cba_notice.py`:
```python
import re

import requests
from bs4 import BeautifulSoup

from scripts.models import NoticeItem

BASE_URL = "https://cba.snu.ac.kr"
LIST_URL = BASE_URL + "/newsroom/notice?sc=y"
BBSIDX_RE = re.compile(r"bbsidx=(\d+)")


def parse_cba_notices(html: str) -> list[NoticeItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for row in soup.select("div.board table tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        category = cells[1].get_text(strip=True)
        link = cells[2].find("a")
        if not link or not link.get("href"):
            continue
        match = BBSIDX_RE.search(link["href"])
        if not match:
            continue
        items.append(
            NoticeItem(
                id=match.group(1),
                source="cba",
                title=link.get_text(strip=True),
                url=BASE_URL + link["href"],
                date=cells[3].get_text(strip=True),
                meta=category,
            )
        )
    return items


def fetch_cba_notices_live() -> list[NoticeItem]:
    response = requests.get(
        LIST_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"}
    )
    response.raise_for_status()
    return parse_cba_notices(response.text)
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run:
```bash
cd "소식 자동화" && python3 -m pytest tests/test_cba_notice.py -v
```
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add "소식 자동화/scripts/cba_notice.py" "소식 자동화/tests/test_cba_notice.py" "소식 자동화/tests/fixtures/cba_notice_sample.html"
git commit -m "feat: add cba.snu.ac.kr notice scraper"
```

---

## Task 4: Gmail 공지 메일 수집

Gmail 앱 비밀번호 + IMAP(`imap.gmail.com`)로 접속하고, Gmail 전용 확장 검색 문법 `X-GM-RAW`로 `from:*.snu.ac.kr newer_than:7d`를 검색한다. 메일을 읽음 처리하지 않도록 `BODY.PEEK[HEADER]`로 헤더만 가져온다. 중복 방지는 `Message-ID` 헤더를 id로 사용해 Task 2의 seen-ledger가 처리하므로, 검색 기간(7일)은 스케줄 주기(주 2회)보다 여유 있게 잡아 실행이 한 번 밀려도 놓치는 메일이 없게 한다.

**Files:**
- Create: `소식 자동화/scripts/gmail_notice.py`
- Test: `소식 자동화/tests/test_gmail_notice.py`

**Interfaces:**
- Consumes: `NoticeItem` (Task 1)
- Produces:
  - `parse_gmail_message(raw: bytes) -> NoticeItem`
  - `fetch_gmail_notices_live() -> list[NoticeItem]` (환경변수 `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` 필요)

- [ ] **Step 1: 실패하는 테스트 작성**

`소식 자동화/tests/test_gmail_notice.py`:
```python
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

from scripts.gmail_notice import fetch_gmail_notices_live, parse_gmail_message


def _build_raw_email(message_id, subject, sender, date):
    msg = EmailMessage()
    msg["Message-ID"] = message_id
    msg["Subject"] = subject
    msg["From"] = sender
    msg["Date"] = date
    msg.set_content("본문 내용")
    return msg.as_bytes()


def test_parse_gmail_message_extracts_fields():
    raw = _build_raw_email(
        "<abc123@mail.snu.ac.kr>",
        "[경력개발센터] AI진로캠프 모집",
        "snucareer@snu.ac.kr",
        "Wed, 12 Aug 2026 06:42:00 +0000",
    )
    item = parse_gmail_message(raw)
    assert item.id == "<abc123@mail.snu.ac.kr>"
    assert item.source == "gmail"
    assert item.title == "[경력개발센터] AI진로캠프 모집"
    assert item.date == "2026-08-12"
    assert item.meta == "snucareer@snu.ac.kr"
    assert "rfc822msgid" in item.url


def test_fetch_gmail_notices_live_uses_imap_search(monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "me@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-pass")

    raw = _build_raw_email(
        "<xyz@snu.ac.kr>", "테스트 공지", "office@snu.ac.kr", "Thu, 13 Aug 2026 01:00:00 +0000"
    )

    fake_conn = MagicMock()
    fake_conn.search.return_value = ("OK", [b"1"])
    fake_conn.fetch.return_value = ("OK", [(b"1 (BODY[HEADER])", raw)])

    with patch("scripts.gmail_notice.imaplib.IMAP4_SSL", return_value=fake_conn):
        items = fetch_gmail_notices_live()

    fake_conn.login.assert_called_once_with("me@gmail.com", "app-pass")
    assert fake_conn.search.call_args[0][1] == "X-GM-RAW"
    assert len(items) == 1
    assert items[0].id == "<xyz@snu.ac.kr>"
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run:
```bash
cd "소식 자동화" && python3 -m pytest tests/test_gmail_notice.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.gmail_notice'`

- [ ] **Step 3: 구현**

`소식 자동화/scripts/gmail_notice.py`:
```python
import email
import imaplib
import os
import urllib.parse
from email.header import decode_header
from email.utils import parsedate_to_datetime

from scripts.models import NoticeItem

IMAP_HOST = "imap.gmail.com"
SEARCH_QUERY = "from:*.snu.ac.kr newer_than:7d"


def _decode(value: str) -> str:
    parts = decode_header(value or "")
    decoded = ""
    for text, encoding in parts:
        if isinstance(text, bytes):
            decoded += text.decode(encoding or "utf-8", errors="replace")
        else:
            decoded += text
    return decoded


def parse_gmail_message(raw: bytes) -> NoticeItem:
    msg = email.message_from_bytes(raw)
    message_id = (msg.get("Message-ID") or "").strip()
    subject = _decode(msg.get("Subject", ""))
    sender = _decode(msg.get("From", ""))

    date_str = ""
    date_header = msg.get("Date")
    if date_header:
        try:
            date_str = parsedate_to_datetime(date_header).date().isoformat()
        except (TypeError, ValueError):
            date_str = ""

    bare_id = message_id.strip("<>")
    url = "https://mail.google.com/mail/u/0/#search/rfc822msgid:" + urllib.parse.quote(
        bare_id
    )

    return NoticeItem(
        id=message_id or subject,
        source="gmail",
        title=subject,
        url=url,
        date=date_str,
        meta=sender,
    )


def fetch_gmail_notices_live() -> list[NoticeItem]:
    address = os.environ["GMAIL_ADDRESS"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]

    conn = imaplib.IMAP4_SSL(IMAP_HOST)
    try:
        conn.login(address, app_password)
        conn.select("INBOX", readonly=True)
        status, data = conn.search(None, "X-GM-RAW", f'"{SEARCH_QUERY}"')
        if status != "OK" or not data or not data[0]:
            return []

        items = []
        for uid in data[0].split():
            status, msg_data = conn.fetch(uid, "(BODY.PEEK[HEADER])")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            items.append(parse_gmail_message(msg_data[0][1]))
        return items
    finally:
        conn.logout()
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run:
```bash
cd "소식 자동화" && python3 -m pytest tests/test_gmail_notice.py -v
```
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add "소식 자동화/scripts/gmail_notice.py" "소식 자동화/tests/test_gmail_notice.py"
git commit -m "feat: add Gmail IMAP notice fetcher"
```

---

## Task 5: 비교과 프로그램 수집 (extra.snu.ac.kr)

Playwright로 실제 접속해서 확인한 결과: `https://extra.snu.ac.kr`은 NetFunnel 대기 화면을 거쳐 `/index.do`로 자동 리다이렉트되고, 프로그램 전체 목록은 로그인 없이 `https://extra.snu.ac.kr/ptfol/pgm/index.do`에서 서버 렌더링된 HTML로 바로 제공된다(별도 JSON API 호출 없음). 각 프로그램 카드는 다음 구조다:

```html
<div class="lica_gp">
  <div class="cont_box">
    <div class="desc_wrap">
      <div class="text_wrap">
        <div class="label_box">
          <a onclick="global.write('PGM012002012', '/ptfol/pgm/view.do');"><span>모집중</span></a>
          <span class="dday">D-34</span>
        </div>
        <ul class="major_type"><li class="first">첨단융합학부</li><li class="last">교육(특강/세미나)</li></ul>
        <a class="tit ellipsis" onclick="global.write('PGM012002012', '/ptfol/pgm/view.do');">프로그램 제목</a>
      </div>
    </div>
  </div>
</div>
```

`global.write('PGM...', ...)`의 첫 번째 인자가 프로그램의 고유 ID다. 상세 페이지는 서버가 암호화된 파라미터로 리다이렉트하는 방식이라 ID만으로 직접 링크를 만들 수 없으므로, 링크는 전체 목록 페이지 URL로 대체한다(실제로 Playwright로 클릭까지 재현하면 실행 시간이 크게 늘고 깨지기 쉬워, 목록 URL로 대체하는 쪽이 안정적이라고 판단).

**Files:**
- Create: `소식 자동화/scripts/extra_snu.py`
- Create: `소식 자동화/tests/fixtures/extra_snu_sample.html`
- Test: `소식 자동화/tests/test_extra_snu.py`

**Interfaces:**
- Consumes: `NoticeItem` (Task 1)
- Produces:
  - `parse_extra_snu_programs(html: str) -> list[NoticeItem]`
  - `fetch_extra_snu_programs_live() -> list[NoticeItem]` (Playwright 사용, `main.py`가 사용)

- [ ] **Step 1: 실패하는 테스트와 fixture 작성**

`소식 자동화/tests/fixtures/extra_snu_sample.html` (실제 사이트 렌더링 결과에서 발췌):
```html
<div class="lica_wrap"><ul>
<li class="first">
  <div class="lica_gp">
    <div class="cont_box">
      <div class="img_wrap"><a href="#" onclick="global.write('PGM012002012', '/ptfol/pgm/view.do');"><img src="x.jpg" id="repnImg" alt=".."></a></div>
      <div class="desc_wrap">
        <div class="text_wrap">
          <div class="label_box">
            <a href="#" class="btn01 col08" onclick="global.write('PGM012002012', '/ptfol/pgm/view.do');"><span>모집중</span></a>
            <span class="dday">D-34</span>
          </div>
          <ul class="major_type"><li class="first">첨단융합학부</li><li class="last">교육(특강/세미나)</li></ul>
          <a href="#;" class="tit ellipsis" onclick="global.write('PGM012002012', '/ptfol/pgm/view.do');">[첨단융합학부 - 2026 SNUTI Into Future #4]건강한 자신과 소통하기 그리고 타인과 소통하기(김창옥 대표)</a>
          <p class="desc ellipsis">초학제적 융합소양에 기반한 새로운 분야 개척가들과의 만남</p>
        </div>
      </div>
    </div>
  </div>
</li>
<li>
  <div class="lica_gp">
    <div class="cont_box">
      <div class="img_wrap"><a href="#" onclick="global.write('PGM012002011', '/ptfol/pgm/view.do');"><img src="y.jpg" id="repnImg" alt=".."></a></div>
      <div class="desc_wrap">
        <div class="text_wrap">
          <div class="label_box">
            <a href="#" class="btn01 col06" onclick="global.write('PGM012002011', '/ptfol/pgm/view.do');"><span>모집대기</span></a>
            <span class="dday">D-13</span>
          </div>
          <ul class="major_type"><li class="first">학생지원과</li><li class="last">레크리에이션</li></ul>
          <a href="#;" class="tit ellipsis" onclick="global.write('PGM012002011', '/ptfol/pgm/view.do');">2026 예술주간 공연 참가자 모집</a>
          <p class="desc ellipsis">'예술주간; ArtSpace@SNU'에서 공연을 진행할 학생 개인 및 동아리(단체)를 모집합니다.</p>
        </div>
      </div>
    </div>
  </div>
</li>
</ul></div>
```

`소식 자동화/tests/test_extra_snu.py`:
```python
import os

from scripts.extra_snu import LIST_URL, parse_extra_snu_programs

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "extra_snu_sample.html"
)


def _load_fixture() -> str:
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return f.read()


def test_parse_extra_snu_programs_extracts_all_cards():
    items = parse_extra_snu_programs(_load_fixture())
    assert len(items) == 2


def test_parse_extra_snu_programs_extracts_fields():
    items = parse_extra_snu_programs(_load_fixture())
    first = items[0]
    assert first.id == "PGM012002012"
    assert first.source == "extra"
    assert "SNUTI Into Future" in first.title
    assert first.url == LIST_URL
    assert first.meta == "모집중 D-34"


def test_parse_extra_snu_programs_second_card():
    items = parse_extra_snu_programs(_load_fixture())
    assert items[1].id == "PGM012002011"
    assert items[1].title == "2026 예술주간 공연 참가자 모집"
    assert items[1].meta == "모집대기 D-13"
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run:
```bash
cd "소식 자동화" && python3 -m pytest tests/test_extra_snu.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.extra_snu'`

- [ ] **Step 3: 구현**

`소식 자동화/scripts/extra_snu.py`:
```python
import re

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from scripts.models import NoticeItem

LIST_URL = "https://extra.snu.ac.kr/ptfol/pgm/index.do"
ID_RE = re.compile(r"global\.write\('([^']+)'")


def parse_extra_snu_programs(html: str) -> list[NoticeItem]:
    soup = BeautifulSoup(html, "html.parser")
    seen_ids: set[str] = set()
    items = []

    for title_el in soup.select("a.tit.ellipsis"):
        match = ID_RE.search(title_el.get("onclick", ""))
        if not match:
            continue
        program_id = match.group(1)
        if program_id in seen_ids:
            continue
        seen_ids.add(program_id)

        card = title_el.find_parent("div", class_="text_wrap")
        status, dday = "", ""
        if card is not None:
            status_el = card.select_one(".label_box a span")
            if status_el:
                status = status_el.get_text(strip=True)
            dday_el = card.select_one(".dday")
            if dday_el:
                dday = dday_el.get_text(strip=True)

        items.append(
            NoticeItem(
                id=program_id,
                source="extra",
                title=title_el.get_text(strip=True),
                url=LIST_URL,
                date="",
                meta=" ".join(part for part in (status, dday) if part),
            )
        )
    return items


def fetch_extra_snu_programs_live() -> list[NoticeItem]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(LIST_URL, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)
            html = page.content()
        finally:
            browser.close()
    return parse_extra_snu_programs(html)
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run:
```bash
cd "소식 자동화" && python3 -m pytest tests/test_extra_snu.py -v
```
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add "소식 자동화/scripts/extra_snu.py" "소식 자동화/tests/test_extra_snu.py" "소식 자동화/tests/fixtures/extra_snu_sample.html"
git commit -m "feat: add extra.snu.ac.kr program scraper"
```

---

## Task 6: Gemini 한 줄 요약

**Files:**
- Create: `소식 자동화/scripts/summarize.py`
- Test: `소식 자동화/tests/test_summarize.py`

**Interfaces:**
- Consumes: `NoticeItem` (Task 1)
- Produces:
  - `summarize_title(title: str, meta: str, api_key: str, model_name: str = DEFAULT_MODEL) -> str`
  - `summarize_items(items: list[NoticeItem], api_key: str) -> list[NoticeItem]` — 실패한 항목은 원래 제목을 그대로 사용 (요약 없이도 소식은 반드시 전달됨)

- [ ] **Step 1: 실패하는 테스트 작성**

`소식 자동화/tests/test_summarize.py`:
```python
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
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run:
```bash
cd "소식 자동화" && python3 -m pytest tests/test_summarize.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.summarize'`

- [ ] **Step 3: 구현**

`소식 자동화/scripts/summarize.py`:
```python
import os

import google.generativeai as genai

from scripts.models import NoticeItem

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")


def summarize_title(
    title: str, meta: str, api_key: str, model_name: str = DEFAULT_MODEL
) -> str:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    prompt = (
        "다음은 대학 공지 제목이야. 핵심만 담아 20자 내외의 한국어 한 줄로 요약해줘. "
        "요약 문장 하나만 출력하고 다른 말은 하지 마.\n\n"
        f"제목: {title}\n"
        f"부가정보: {meta}"
    )
    response = model.generate_content(prompt)
    text = (response.text or "").strip()
    return text or title


def summarize_items(items: list[NoticeItem], api_key: str) -> list[NoticeItem]:
    summarized = []
    for item in items:
        try:
            summary = summarize_title(item.title, item.meta, api_key)
        except Exception as exc:  # Gemini 무료 할당량 초과 등 어떤 이유로든 실패해도 진행
            print(f"[gemini] summarize failed for {item.id}: {exc}")
            summary = item.title
        summarized.append(
            NoticeItem(
                id=item.id,
                source=item.source,
                title=summary,
                url=item.url,
                date=item.date,
                meta=item.meta,
            )
        )
    return summarized
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run:
```bash
cd "소식 자동화" && python3 -m pytest tests/test_summarize.py -v
```
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
git add "소식 자동화/scripts/summarize.py" "소식 자동화/tests/test_summarize.py"
git commit -m "feat: add Gemini one-line summarizer with fallback"
```

---

## Task 7: 카카오톡 메시지 포맷터

카카오 "나에게 보내기" 기본 텍스트 템플릿은 한 메시지에 담을 수 있는 글자 수가 넉넉하지 않으므로, 항목이 많을 때를 대비해 소스(그룹)별로 메시지를 나눠 여러 통으로 보낸다. 첫 메시지에는 헤더(날짜 + 총 건수)를 포함한다.

**Files:**
- Create: `소식 자동화/scripts/message_formatter.py`
- Test: `소식 자동화/tests/test_message_formatter.py`

**Interfaces:**
- Consumes: `NoticeItem` (Task 1)
- Produces:
  - `SOURCE_LABELS: dict[str, str]` = `{"cba": "학과 공지", "gmail": "이메일 공지", "extra": "비교과 프로그램"}`
  - `build_digest_messages(items: list[NoticeItem], today: date) -> list[str]`
  - `build_error_message(failed_sources: list[str]) -> str | None`

- [ ] **Step 1: 실패하는 테스트 작성**

`소식 자동화/tests/test_message_formatter.py`:
```python
from datetime import date

from scripts.message_formatter import build_digest_messages, build_error_message
from scripts.models import NoticeItem


def test_build_digest_messages_no_new_items():
    messages = build_digest_messages([], today=date(2026, 8, 17))
    assert len(messages) == 1
    assert "새 소식 없음" in messages[0]
    assert "8/17" in messages[0]


def test_build_digest_messages_groups_by_source():
    items = [
        NoticeItem(id="1", source="cba", title="학과 공지 A", url="https://a", meta="일반"),
        NoticeItem(id="2", source="gmail", title="메일 공지 A", url="https://b", meta=""),
    ]
    messages = build_digest_messages(items, today=date(2026, 8, 17))
    assert len(messages) == 2
    assert "학교 소식 요약 (신규 2건)" in messages[0]
    assert "[학과 공지] 1건" in messages[0]
    assert "학과 공지 A" in messages[0]
    assert "(일반)" in messages[0]
    assert "[이메일 공지] 1건" in messages[1]
    assert "메일 공지 A" in messages[1]


def test_build_digest_messages_omits_empty_groups():
    items = [NoticeItem(id="1", source="extra", title="비교과 A", url="https://c")]
    messages = build_digest_messages(items, today=date(2026, 8, 17))
    assert len(messages) == 1
    assert "[비교과 프로그램] 1건" in messages[0]
    assert "학과 공지" not in messages[0]


def test_build_error_message_returns_none_when_no_failures():
    assert build_error_message([]) is None


def test_build_error_message_lists_failed_sources():
    message = build_error_message(["cba", "extra"])
    assert message == "⚠️ 확인 실패: 학과 공지, 비교과 프로그램"
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run:
```bash
cd "소식 자동화" && python3 -m pytest tests/test_message_formatter.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.message_formatter'`

- [ ] **Step 3: 구현**

`소식 자동화/scripts/message_formatter.py`:
```python
from datetime import date

from scripts.models import NoticeItem

SOURCE_ORDER = ["cba", "gmail", "extra"]
SOURCE_LABELS = {
    "cba": "학과 공지",
    "gmail": "이메일 공지",
    "extra": "비교과 프로그램",
}
WEEKDAYS_KR = ["월", "화", "수", "목", "금", "토", "일"]


def _date_label(today: date) -> str:
    return f"{today.month}/{today.day}({WEEKDAYS_KR[today.weekday()]})"


def _format_group(source: str, group_items: list[NoticeItem]) -> str:
    label = SOURCE_LABELS[source]
    lines = [f"[{label}] {len(group_items)}건"]
    for item in group_items:
        meta = f" ({item.meta})" if item.meta else ""
        lines.append(f"• {item.title}{meta}\n  {item.url}")
    return "\n".join(lines)


def build_digest_messages(items: list[NoticeItem], today: date) -> list[str]:
    total = len(items)
    if total == 0:
        return [f"📌 {_date_label(today)} 학교 소식 요약: 이번엔 새 소식 없음"]

    grouped = {source: [] for source in SOURCE_ORDER}
    for item in items:
        grouped[item.source].append(item)

    header = f"📌 {_date_label(today)} 학교 소식 요약 (신규 {total}건)"
    messages = []
    is_first_group = True
    for source in SOURCE_ORDER:
        group_items = grouped[source]
        if not group_items:
            continue
        block = _format_group(source, group_items)
        if is_first_group:
            messages.append(f"{header}\n\n{block}")
            is_first_group = False
        else:
            messages.append(block)
    return messages


def build_error_message(failed_sources: list[str]) -> str | None:
    if not failed_sources:
        return None
    labels = [SOURCE_LABELS[source] for source in failed_sources]
    return "⚠️ 확인 실패: " + ", ".join(labels)
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run:
```bash
cd "소식 자동화" && python3 -m pytest tests/test_message_formatter.py -v
```
Expected: PASS (5 passed)

- [ ] **Step 5: 커밋**

```bash
git add "소식 자동화/scripts/message_formatter.py" "소식 자동화/tests/test_message_formatter.py"
git commit -m "feat: add Kakao digest message formatter"
```

---

## Task 8: 카카오톡 발송

**Files:**
- Create: `소식 자동화/scripts/kakao_sender.py`
- Test: `소식 자동화/tests/test_kakao_sender.py`

**Interfaces:**
- Produces:
  - `refresh_access_token(rest_api_key: str, refresh_token: str) -> str`
  - `send_message(access_token: str, text: str) -> None`

- [ ] **Step 1: 실패하는 테스트 작성**

`소식 자동화/tests/test_kakao_sender.py`:
```python
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
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run:
```bash
cd "소식 자동화" && python3 -m pytest tests/test_kakao_sender.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.kakao_sender'`

- [ ] **Step 3: 구현**

`소식 자동화/scripts/kakao_sender.py`:
```python
import json

import requests

TOKEN_URL = "https://kauth.kakao.com/oauth/token"
SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def refresh_access_token(rest_api_key: str, refresh_token: str) -> str:
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": rest_api_key,
            "refresh_token": refresh_token,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def send_message(access_token: str, text: str) -> None:
    template = {
        "object_type": "text",
        "text": text[:1000],
        "link": {"web_url": "https://cba.snu.ac.kr/newsroom/notice?sc=y"},
        "button_title": "바로가기",
    }
    response = requests.post(
        SEND_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        data={"template_object": json.dumps(template, ensure_ascii=False)},
        timeout=10,
    )
    response.raise_for_status()
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run:
```bash
cd "소식 자동화" && python3 -m pytest tests/test_kakao_sender.py -v
```
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add "소식 자동화/scripts/kakao_sender.py" "소식 자동화/tests/test_kakao_sender.py"
git commit -m "feat: add Kakao 'send to me' client"
```

---

## Task 9: 메인 오케스트레이터

세 소스를 각각 독립적으로 수집해서 한 소스가 실패해도 나머지는 계속 진행하고, 신규 항목을 요약·포맷해서 카카오톡으로 보낸 뒤 상태를 저장한다.

**Files:**
- Create: `소식 자동화/scripts/main.py`
- Test: `소식 자동화/tests/test_main.py`

**Interfaces:**
- Consumes: 모든 이전 Task의 함수들
- Produces:
  - `collect_new_items(state: dict, sources: dict[str, Callable[[], list[NoticeItem]]]) -> tuple[list[NoticeItem], list[str]]`
  - `main(state_path: str = DEFAULT_STATE_PATH) -> None`

- [ ] **Step 1: 실패하는 테스트 작성**

`소식 자동화/tests/test_main.py`:
```python
import json

import scripts.main as main_module
from scripts.models import NoticeItem


def test_collect_new_items_isolates_source_failures():
    def ok_source():
        return [NoticeItem(id="1", source="cba", title="A", url="u")]

    def bad_source():
        raise RuntimeError("boom")

    state = {}
    new_items, failed = main_module.collect_new_items(
        state, {"cba": ok_source, "gmail": bad_source}
    )

    assert [i.id for i in new_items] == ["1"]
    assert failed == ["gmail"]
    assert state["cba"] == ["1"]


def test_collect_new_items_skips_already_seen():
    def source():
        return [NoticeItem(id="1", source="cba", title="A", url="u")]

    state = {"cba": ["1"]}
    new_items, failed = main_module.collect_new_items(state, {"cba": source})

    assert new_items == []
    assert failed == []
    assert state["cba"] == ["1"]


def test_main_runs_pipeline_and_saves_state(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    state_path.write_text("{}", encoding="utf-8")

    def fake_source():
        return [
            NoticeItem(
                id="1", source="cba", title="새 공지", url="https://x", date="2026-08-14"
            )
        ]

    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("KAKAO_REST_API_KEY", "kakao-key")
    monkeypatch.setenv("KAKAO_REFRESH_TOKEN", "kakao-refresh")

    monkeypatch.setattr(main_module, "SOURCES", {"cba": fake_source})
    monkeypatch.setattr(
        main_module, "summarize_items", lambda items, api_key: items
    )
    monkeypatch.setattr(
        main_module, "refresh_access_token", lambda key, refresh: "access-token"
    )

    sent_messages = []
    monkeypatch.setattr(
        main_module, "send_message", lambda token, text: sent_messages.append(text)
    )

    main_module.main(state_path=str(state_path))

    assert len(sent_messages) == 1
    assert "새 공지" in sent_messages[0]

    saved_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved_state["cba"] == ["1"]
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run:
```bash
cd "소식 자동화" && python3 -m pytest tests/test_main.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.main'`

- [ ] **Step 3: 구현**

`소식 자동화/scripts/main.py`:
```python
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Callable

from scripts import state_store
from scripts.cba_notice import fetch_cba_notices_live
from scripts.extra_snu import fetch_extra_snu_programs_live
from scripts.gmail_notice import fetch_gmail_notices_live
from scripts.kakao_sender import refresh_access_token, send_message
from scripts.message_formatter import build_digest_messages, build_error_message
from scripts.models import NoticeItem
from scripts.summarize import summarize_items

KST = timezone(timedelta(hours=9))
DEFAULT_STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "state.json")

SOURCES: dict[str, Callable[[], list[NoticeItem]]] = {
    "cba": fetch_cba_notices_live,
    "gmail": fetch_gmail_notices_live,
    "extra": fetch_extra_snu_programs_live,
}


def collect_new_items(
    state: dict, sources: dict[str, Callable[[], list[NoticeItem]]]
) -> tuple[list[NoticeItem], list[str]]:
    all_new_items: list[NoticeItem] = []
    failed_sources: list[str] = []

    for source, fetch_fn in sources.items():
        try:
            items = fetch_fn()
        except Exception as exc:
            print(f"[{source}] fetch failed: {exc}", file=sys.stderr)
            failed_sources.append(source)
            continue

        seen_ids = state.get(source, [])
        new_items = state_store.filter_new_items(items, seen_ids)
        state[source] = state_store.update_seen_ids(seen_ids, items)
        all_new_items.extend(new_items)

    return all_new_items, failed_sources


def main(state_path: str = DEFAULT_STATE_PATH) -> None:
    gemini_key = os.environ["GEMINI_API_KEY"]
    kakao_key = os.environ["KAKAO_REST_API_KEY"]
    kakao_refresh = os.environ["KAKAO_REFRESH_TOKEN"]

    state = state_store.load_state(state_path)
    new_items, failed_sources = collect_new_items(state, SOURCES)
    new_items = summarize_items(new_items, gemini_key)

    today = datetime.now(KST).date()
    messages = build_digest_messages(new_items, today)

    error_message = build_error_message(failed_sources)
    if error_message:
        messages.append(error_message)

    access_token = refresh_access_token(kakao_key, kakao_refresh)
    for message in messages:
        send_message(access_token, message)

    state_store.save_state(state_path, state)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run:
```bash
cd "소식 자동화" && python3 -m pytest tests/test_main.py -v
```
Expected: PASS (3 passed)

- [ ] **Step 5: 전체 테스트 스위트 실행**

Run:
```bash
cd "소식 자동화" && python3 -m pytest -v
```
Expected: PASS (모든 테스트, 총 25개 통과)

- [ ] **Step 6: 커밋**

```bash
git add "소식 자동화/scripts/main.py" "소식 자동화/tests/test_main.py"
git commit -m "feat: wire pipeline together in main orchestrator"
```

---

## Task 10: GitHub Actions 워크플로 & 실행 설정

리포지토리 루트(`/Users/donghwikim/바이브코딩`)는 이미 GitHub 원격 저장소(`origin`)에 연결되어 있으므로, 워크플로 파일만 추가하면 된다.

**Files:**
- Create: `.github/workflows/notice-digest.yml` (리포지토리 루트 기준)
- Create: `소식 자동화/.env.example`

**Interfaces:**
- Consumes: `소식 자동화/scripts/main.py` (Task 9), 리포지토리 루트의 git 원격 설정
- Produces: 없음 (배포 설정)

- [ ] **Step 1: 워크플로 파일 작성**

`.github/workflows/notice-digest.yml` (리포지토리 루트 `/Users/donghwikim/바이브코딩/.github/workflows/notice-digest.yml`):
```yaml
name: SNU Notice Digest

on:
  schedule:
    - cron: '0 23 * * 0,3'
  workflow_dispatch: {}

permissions:
  contents: write

jobs:
  digest:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: 소식 자동화
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          playwright install --with-deps chromium

      - name: Run digest
        env:
          GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          KAKAO_REST_API_KEY: ${{ secrets.KAKAO_REST_API_KEY }}
          KAKAO_REFRESH_TOKEN: ${{ secrets.KAKAO_REFRESH_TOKEN }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: python -m scripts.main

      - name: Commit updated state
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add state.json
          if ! git diff --cached --quiet; then
            git commit -m "chore: update notice state [skip ci]"
            git push
          fi
```

- [ ] **Step 2: 로컬 실행용 환경변수 예시 파일 작성**

`소식 자동화/.env.example`:
```
GMAIL_ADDRESS=your-account@gmail.com
GMAIL_APP_PASSWORD=xxxxxxxxxxxxxxxx
KAKAO_REST_API_KEY=your-kakao-rest-api-key
KAKAO_REFRESH_TOKEN=your-kakao-refresh-token
GEMINI_API_KEY=your-gemini-api-key
```

- [ ] **Step 3: state.json 초기 파일 생성**

`소식 자동화/state.json`:
```json
{}
```

- [ ] **Step 4: YAML 문법 검증**

Run:
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/notice-digest.yml'))" && echo "valid yaml"
```
Expected: `valid yaml` 출력 (PyYAML이 없으면 `pip install pyyaml` 먼저 실행)

- [ ] **Step 5: 커밋**

```bash
git add .github/workflows/notice-digest.yml "소식 자동화/.env.example" "소식 자동화/state.json"
git commit -m "ci: add scheduled GitHub Actions workflow for notice digest"
```

---

## Task 11: 초기 자격증명 발급 & 라이브 검증 (수동)

이 태스크는 자동화 코드가 아니라 사용자 본인만 할 수 있는 계정 연동 작업이므로 수동으로 진행한다. 자동 테스트 대상이 아니다.

- [ ] **Step 1: Gmail 앱 비밀번호 발급**
  - Google 계정 → 보안 → 2단계 인증 활성화
  - 보안 → 앱 비밀번호 → 새 앱 비밀번호 생성 → `GMAIL_APP_PASSWORD`로 사용

- [ ] **Step 2: 카카오 디벨로퍼스 앱 등록 및 refresh token 발급**
  - https://developers.kakao.com 에서 애플리케이션 생성
  - 카카오 로그인 활성화, 동의항목에서 "카카오톡 메시지 전송" 권한 활성화
  - REST API 키를 `KAKAO_REST_API_KEY`로 사용
  - 본인 계정으로 인가 코드 로그인 → 토큰 발급 API로 `refresh_token` 획득 → `KAKAO_REFRESH_TOKEN`으로 사용

- [ ] **Step 3: Gemini API 키 발급**
  - https://aistudio.google.com 에서 API 키 생성 (무료)
  - `GEMINI_API_KEY`로 사용

- [ ] **Step 4: GitHub Secrets 등록**
  - 저장소 Settings → Secrets and variables → Actions
  - `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `KAKAO_REST_API_KEY`, `KAKAO_REFRESH_TOKEN`, `GEMINI_API_KEY` 등록

- [ ] **Step 5: 로컬에서 한 소스씩 라이브로 확인**

```bash
cd "소식 자동화"
export $(cat .env | xargs)   # .env 파일에 실제 값 채워넣고 실행 (커밋 금지)
python3 -c "from scripts.cba_notice import fetch_cba_notices_live as f; print(f())"
python3 -c "from scripts.gmail_notice import fetch_gmail_notices_live as f; print(f())"
python3 -c "from scripts.extra_snu import fetch_extra_snu_programs_live as f; print(f())"
```
각 명령이 예외 없이 `NoticeItem` 리스트를 출력하는지 확인한다.

- [ ] **Step 6: GitHub Actions 수동 실행으로 전체 파이프라인 확인**
  - GitHub 저장소 → Actions → "SNU Notice Digest" → "Run workflow"
  - 카카오톡에 실제로 메시지가 도착하는지 확인

- [ ] **Step 7: "신규 소식 없음" 케이스 확인**
  - 위 실행으로 `state.json`이 최신 상태로 커밋된 뒤, 워크플로를 한 번 더 수동 실행
  - "이번엔 새 소식 없음" 메시지가 오는지 확인

- [ ] **Step 8: 실패 격리 확인**
  - `scripts/cba_notice.py`의 `LIST_URL`을 일부러 잘못된 값으로 바꿔 로컬에서 `python3 -m scripts.main` 실행
  - 나머지 두 소스는 정상 처리되고, 카카오톡 메시지에 `⚠️ 확인 실패: 학과 공지`가 포함되는지 확인
  - 확인 후 `LIST_URL`을 원래 값으로 되돌리고 변경사항이 커밋되지 않았는지 확인

---

## Self-Review 메모

- **Spec coverage:** 설계 문서의 3개 소스 수집(Task 3~5), 중복 방지(Task 2), Gemini 요약(Task 6), 카카오 발송(Task 7~8), 에러 처리(Task 9 `collect_new_items` + `build_error_message`), GitHub Actions 8시 스케줄(Task 10), 초기 설정 및 테스트 계획(Task 11)까지 모두 태스크로 매핑됨.
- **상태 스키마 변경:** 설계 문서의 `state.json` 예시(`{"cba_notice": {"last_seen_id": ...}}`)는 소스별 단일 커서 방식이었으나, 소스마다 ID 형식이 달라(cba는 정렬 가능한 숫자, gmail/extra는 정렬 불가능한 문자열) 이 계획에서는 소스별 "본 적 있는 ID 목록"(seen-ledger, 최대 500개 유지) 방식으로 구현한다. 동작(신규 항목만 발송)은 설계 의도와 동일하다.
- **타입 일관성:** `NoticeItem(id, source, title, url, date, meta)` 필드명이 Task 1부터 Task 9까지 모든 모듈에서 동일하게 사용됨을 확인함. `SOURCES` dict의 키(`cba`/`gmail`/`extra`)가 `state.json` 키, `SOURCE_LABELS` 키와 일치함을 확인함.
