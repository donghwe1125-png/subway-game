import os
import time

import google.generativeai as genai

from scripts.models import NoticeItem

# 앞에서부터 차례로 쓰다가, 한 모델이 거절하면(하루 한도 초과, 단종 등) 다음 모델로 넘어간다.
# 무료 등급은 모델당 하루 약 20회라 한 번에 20~30개씩 몰리는 공지를 한 모델로는 못 버틴다.
# 짧은 제목 요약이라 가벼운 lite 모델을 먼저 쓰고, gemini-3.8-flash는 경제뉴스 몫으로 남겨둔다.
FALLBACK_MODELS = (
    (os.environ["GEMINI_MODEL"],) if os.environ.get("GEMINI_MODEL") else ()
) + (
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.7-flash",
    "gemini-flash-latest",
)
# Gemini 무료 등급은 모델당 분당 5회 호출까지만 허용한다.
SLEEP_SECONDS = 13.0


def summarize_title(
    title: str, meta: str, api_key: str, model_name: str = FALLBACK_MODELS[0]
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
    # 이번 실행에서 아직 거절당하지 않은 모델들. 한도에 걸린 모델은 다시 부르지 않는다.
    available_models = list(FALLBACK_MODELS)
    last_index = len(items) - 1
    for index, item in enumerate(items):
        summary = item.title
        while available_models:
            try:
                summary = summarize_title(item.title, item.meta, api_key, available_models[0])
                break
            except Exception as exc:  # 할당량 초과 등 어떤 이유로든 실패하면 다음 모델로
                print(f"[gemini] {available_models[0]} failed for {item.id}: {str(exc).splitlines()[0]}")
                available_models.pop(0)
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
        # 첫 실행처럼 항목이 몰릴 때 분당 한도(429)에 걸려 모델을 잃지 않도록
        # 호출 사이에 간격을 둔다.
        if sleep_seconds > 0 and index < last_index:
            time.sleep(sleep_seconds)
    return summarized
