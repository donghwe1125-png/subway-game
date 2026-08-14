import os
import time

import google.generativeai as genai

from scripts.models import NoticeItem

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
# Gemini 무료 등급은 분당 약 15회 호출까지만 허용한다.
SLEEP_SECONDS = 4.0


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


def summarize_items(
    items: list[NoticeItem], api_key: str, sleep_seconds: float = SLEEP_SECONDS
) -> list[NoticeItem]:
    summarized = []
    last_index = len(items) - 1
    for index, item in enumerate(items):
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
        # 무료 등급은 분당 약 15회다. 첫 실행처럼 항목이 몰릴 때 429로
        # 전부 원문 제목으로 떨어지지 않도록 호출 사이에 간격을 둔다.
        if sleep_seconds > 0 and index < last_index:
            time.sleep(sleep_seconds)
    return summarized
