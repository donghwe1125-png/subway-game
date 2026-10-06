import os
import sys
import time
from datetime import datetime, timedelta, timezone

from scripts import state_store
from scripts.curator import select_and_explain
from scripts.message_formatter import build_digest_message, build_error_message
from scripts.models import NewsCandidate
from scripts.news_sources import SOURCES
from scripts.telegram_sender import send_message

KST = timezone(timedelta(hours=9))
DEFAULT_STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "state.json")

# 목표 발송 시각(KST). GitHub Actions의 예약 실행은 정시에 몰려 대기가 길어지므로
# 워크플로우는 이 시각보다 조금 이른 "애매한 분"에 깨우고, 여기까지 기다렸다 보낸다.
SEND_AT_HOUR = 7
SEND_AT_MINUTE = 0
# 깨어난 시각이 목표보다 너무 이르면(설정 실수, 수동 조작 등) 무한정 기다리지 않는다.
MAX_WAIT_SECONDS = 40 * 60


def _now() -> datetime:
    return datetime.now(KST)


def seconds_until_send_time(
    now: datetime, max_wait_seconds: int = MAX_WAIT_SECONDS
) -> int:
    """목표 발송 시각까지 남은 초. 이미 지났으면 0(=즉시 발송)."""
    target = now.replace(
        hour=SEND_AT_HOUR, minute=SEND_AT_MINUTE, second=0, microsecond=0
    )
    if now >= target:
        return 0
    return min(int((target - now).total_seconds()), max_wait_seconds)


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


def main(state_path: str = DEFAULT_STATE_PATH) -> None:
    gemini_key = os.environ["GEMINI_API_KEY"]
    telegram_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    telegram_chat_id = os.environ["TELEGRAM_CHAT_ID"]

    # 예약 실행일 때만 "목표 시각까지 대기"와 "오늘 이미 보냈으면 건너뛰기"가 적용된다.
    # 수동 실행(workflow_dispatch)은 사람이 지금 달라고 누른 것이므로 즉시 보낸다.
    scheduled_run = os.environ.get("SCHEDULED_RUN", "").lower() == "true"

    sent_urls = state_store.load_sent_urls(state_path)

    if scheduled_run:
        if state_store.already_sent_today(sent_urls, _now().date()):
            print("[main] 오늘 다이제스트는 이미 발송됨, 이번 트리거는 건너뜀")
            return

        wait_seconds = seconds_until_send_time(_now())
        if wait_seconds:
            print(f"[main] 목표 발송 시각까지 {wait_seconds}초 대기")
            time.sleep(wait_seconds)

    candidates, failed_sources = collect_candidates(SOURCES)
    if failed_sources:
        print(f"failed sources: {failed_sources}", file=sys.stderr)

    new_candidates = state_store.filter_unsent(candidates, sent_urls)

    items = select_and_explain(new_candidates, gemini_key) if new_candidates else []

    today = datetime.now(KST).date()

    # 전송 전에 먼저 저장한다. 전송이 도중에 실패해도 오늘 고른 뉴스가
    # 다음 실행에서 다시 뽑혀 중복 발송되는 일을 막는다.
    state_store.save_sent_urls(
        state_path, state_store.record_sent(sent_urls, items, today)
    )

    if items:
        messages = build_digest_message(items, today)
    else:
        messages = [
            build_error_message("오늘은 뉴스를 가져오지 못했어요. 내일 다시 시도할게요.")
        ]

    failures: list[tuple[int, Exception]] = []
    for index, message in enumerate(messages, start=1):
        try:
            send_message(telegram_bot_token, telegram_chat_id, message)
        except Exception as exc:
            print(f"[main] failed to send message {index}/{len(messages)}: {exc}", file=sys.stderr)
            failures.append((index, exc))

    if failures:
        failed_indexes = ", ".join(str(i) for i, _ in failures)
        raise RuntimeError(
            f"{len(failures)} of {len(messages)} message(s) failed to send "
            f"(indexes: {failed_indexes})"
        )


if __name__ == "__main__":
    main()
