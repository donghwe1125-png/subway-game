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
