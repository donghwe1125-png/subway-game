from dataclasses import dataclass


@dataclass
class NewsCandidate:
    source: str
    title: str
    summary: str
    url: str
    published: str = ""


@dataclass
class DigestItem:
    title_kr: str
    what_happened: str
    why_it_matters: str
    source_name: str
    url: str
