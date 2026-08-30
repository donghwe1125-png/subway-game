import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Callable

from scripts import state_store
from scripts.cba_notice import fetch_cba_notices_live
from scripts.extra_snu import fetch_extra_snu_programs_live
from scripts.gmail_notice import fetch_gmail_notices_live
from scripts.message_formatter import build_digest_messages, build_error_message
from scripts.models import NoticeItem
from scripts.summarize import summarize_items
from scripts.telegram_sender import send_message

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
    telegram_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    telegram_chat_id = os.environ["TELEGRAM_CHAT_ID"]

    state = state_store.load_state(state_path)
    new_items, failed_sources = collect_new_items(state, SOURCES)
    # 발송 전에 먼저 저장한다. 전송이 도중에 실패해도 이미 보낸 소식이
    # 다음 실행에서 다시 쌓여 중복 발송되는 일을 막는다.
    state_store.save_state(state_path, state)

    new_items = summarize_items(new_items, gemini_key)

    today = datetime.now(KST).date()
    messages = build_digest_messages(new_items, today)

    error_message = build_error_message(failed_sources)
    if error_message:
        messages.append(error_message)

    for message in messages:
        send_message(telegram_bot_token, telegram_chat_id, message)


if __name__ == "__main__":
    main()
