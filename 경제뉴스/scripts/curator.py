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

    items = []
    for i, entry in enumerate(data):
        try:
            item = DigestItem(
                title_kr=entry["title_kr"],
                what_happened=entry["what_happened"],
                why_it_matters=entry["why_it_matters"],
                source_name=entry["source_name"],
                url=entry["url"],
            )
            items.append(item)
        except (KeyError, TypeError) as exc:
            print(f"[curator] entry {i} skipped: {exc}")

    return items


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
