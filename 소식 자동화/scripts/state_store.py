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
