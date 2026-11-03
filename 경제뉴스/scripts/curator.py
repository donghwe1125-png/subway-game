import json
import os
import re

import google.generativeai as genai

from scripts.models import DigestItem, NewsCandidate

# 앞에서부터 차례로 시도한다. 구글이 무료 키의 모델을 예고 없이 막거나 단종시키고,
# 붐빌 때는 첫 요청부터 429로 거절하는 일이 반복돼서 하나가 거절되면 다음 모델로 넘어간다.
# flash 모델들이 한꺼번에 거절되는 날에도 lite 모델들은 받아줬으므로 마지막 보루로 둔다.
FALLBACK_MODELS = (
    (os.environ["GEMINI_MODEL"],) if os.environ.get("GEMINI_MODEL") else ()
) + (
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-flash-latest",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
)

# SDK는 429를 받으면 알아서 수십 번 재요청하는데, 그 재요청이 모델당 하루 20회 무료
# 한도를 다 태워 뒤의 모델들까지 막아버린다. SDK 재시도는 끄고 우리 쪽에서만 재시도한다.
REQUEST_OPTIONS = {"retry": None, "timeout": 120}

# 프롬프트에 "가장 중요한 세계 경제뉴스 3개"를 요청하지만, 모델이 이를 넘겨서
# 반환하는 경우를 대비해 코드 레벨에서도 상한을 강제한다.
MAX_ITEMS = 3

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
    "id": 후보 목록의 id 숫자 그대로
  }}
]

다른 설명 없이 JSON 배열만 출력해.

후보 목록:
{candidates_json}
"""


def _build_prompt(candidates: list[NewsCandidate]) -> str:
    trimmed = [
        {
            "id": i,
            "source": c.source,
            "title": c.title,
            "summary": c.summary[:200],
            "published": c.published,
        }
        for i, c in enumerate(candidates)
    ]
    return PROMPT_TEMPLATE.format(
        candidates_json=json.dumps(trimmed, ensure_ascii=False)
    )


def _extract_json_payload(text: str) -> str:
    """마크다운 코드펜스(``` json / ```JSON 등)와 그 앞뒤의 잡담을 제거한다."""
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.S | re.I)
    if fence_match:
        return fence_match.group(1).strip()
    return text.strip()


def _resolve_candidate(
    entry: dict, candidates: list[NewsCandidate]
) -> NewsCandidate | None:
    """모델이 고른 기사를 원본 후보에서 찾는다. 모델은 url을 고쳐 쓰는 일이 있어서
    번호(id)를 먼저 믿고, 번호가 없을 때만 url이 정확히 일치하는 후보를 쓴다."""
    index = entry.get("id")
    if isinstance(index, str) and index.strip().isdigit():
        index = int(index)
    if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(candidates):
        return candidates[index]
    url = entry.get("url")
    return next((c for c in candidates if c.url == url), None)


def _parse_response(text: str, candidates: list[NewsCandidate]) -> list[DigestItem]:
    cleaned = _extract_json_payload(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # 코드펜스도 없고 텍스트 전체도 곧바로 JSON으로 파싱되지 않는 경우,
        # 응답 어딘가에 박혀 있는 첫 JSON 배열 구간만이라도 건져본다.
        array_match = re.search(r"\[.*\]", text, re.S)
        if not array_match:
            raise
        data = json.loads(array_match.group(0))

    if not isinstance(data, list):
        # 최상위가 배열이 아니면(예: {"news": [...]}) 개별 항목을 훑는 것 자체가
        # 무의미하다. 여기서 실패시켜 호출부의 재시도 로직을 타게 한다.
        raise TypeError(f"expected a JSON array at top level, got {type(data).__name__}")

    items = []
    for i, entry in enumerate(data):
        try:
            candidate = _resolve_candidate(entry, candidates)
            if candidate is not None and any(item.url == candidate.url for item in items):
                print(f"[curator] dropped entry {i}: same article picked twice")
                continue
            if candidate is None:
                print(
                    f"[curator] dropped entry {i} matching no candidate: "
                    f"id={entry.get('id')!r} url={entry.get('url')!r}"
                )
                continue
            item = DigestItem(
                title_kr=entry["title_kr"],
                what_happened=entry["what_happened"],
                why_it_matters=entry["why_it_matters"],
                source_name=candidate.source,
                url=candidate.url,
            )
            items.append(item)
        except (KeyError, TypeError, AttributeError) as exc:
            print(f"[curator] entry {i} skipped: {exc}")

    return items


def _describe_failure(exc: Exception) -> str:
    """오류 첫 줄에 어떤 한도(분당/하루)에 걸렸는지를 붙인다. 원문은 수십 줄이라 줄인다."""
    lines = str(exc).splitlines()
    quota = [
        line.strip()
        for line in lines
        if "quota_id" in line or "Please retry in" in line
    ]
    return " | ".join(lines[:1] + quota)


def select_and_explain(
    candidates: list[NewsCandidate],
    api_key: str,
    model_names: tuple[str, ...] = FALLBACK_MODELS,
) -> list[DigestItem]:
    if not candidates:
        return []

    genai.configure(api_key=api_key)
    prompt = _build_prompt(candidates)

    for model_name in model_names:
        model = genai.GenerativeModel(model_name)
        # 응답 형식이 틀린 경우만 같은 모델로 한 번 더 시도한다.
        # 호출 자체가 거절되면(429, 404 등) 즉시 재시도해도 같은 결과라 다음 모델로 간다.
        for attempt in range(2):
            try:
                response = model.generate_content(prompt, request_options=REQUEST_OPTIONS)
                items = _parse_response(response.text or "", candidates)
                return items[:MAX_ITEMS]
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                print(f"[curator] {model_name} parse failed (attempt {attempt + 1}): {exc}")
            except Exception as exc:
                print(f"[curator] {model_name} call failed: {_describe_failure(exc)}")
                break
    return []
