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
