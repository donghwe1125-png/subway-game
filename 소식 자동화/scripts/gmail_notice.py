import email
import imaplib
import os
import urllib.parse
from email.header import decode_header
from email.utils import parsedate_to_datetime

from scripts.models import NoticeItem

IMAP_HOST = "imap.gmail.com"
# Gmail의 from:은 도메인 부분 문자열로 매칭하므로 "*." 없이 써야
# user@snu.ac.kr과 user@sub.snu.ac.kr을 모두 잡는다.
SEARCH_QUERY = "from:snu.ac.kr newer_than:7d"


def _decode(value: str) -> str:
    parts = decode_header(value or "")
    decoded = ""
    for text, encoding in parts:
        if isinstance(text, bytes):
            decoded += text.decode(encoding or "utf-8", errors="replace")
        else:
            decoded += text
    return decoded


def parse_gmail_message(raw: bytes) -> NoticeItem:
    msg = email.message_from_bytes(raw)
    message_id = (msg.get("Message-ID") or "").strip()
    subject = _decode(msg.get("Subject", ""))
    sender = _decode(msg.get("From", ""))

    date_str = ""
    date_header = msg.get("Date")
    if date_header:
        try:
            date_str = parsedate_to_datetime(date_header).date().isoformat()
        except (TypeError, ValueError):
            date_str = ""

    bare_id = message_id.strip("<>")
    url = "https://mail.google.com/mail/u/0/#search/rfc822msgid:" + urllib.parse.quote(
        bare_id
    )

    return NoticeItem(
        id=message_id or subject,
        source="gmail",
        title=subject,
        url=url,
        date=date_str,
        meta=sender,
    )


def fetch_gmail_notices_live() -> list[NoticeItem]:
    address = os.environ["GMAIL_ADDRESS"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]

    conn = imaplib.IMAP4_SSL(IMAP_HOST)
    try:
        conn.login(address, app_password)
        conn.select("INBOX", readonly=True)
        status, data = conn.search(None, "X-GM-RAW", f'"{SEARCH_QUERY}"')
        if status != "OK" or not data or not data[0]:
            return []

        items = []
        for uid in data[0].split():
            status, msg_data = conn.fetch(uid, "(BODY.PEEK[HEADER])")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            items.append(parse_gmail_message(msg_data[0][1]))
        return items
    finally:
        conn.logout()
