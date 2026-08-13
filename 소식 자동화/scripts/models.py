from dataclasses import dataclass


@dataclass
class NoticeItem:
    id: str
    source: str
    title: str
    url: str
    date: str = ""
    meta: str = ""
