from email.message import EmailMessage
from unittest.mock import MagicMock, patch

from scripts.gmail_notice import fetch_gmail_notices_live, parse_gmail_message


def _build_raw_email(message_id, subject, sender, date):
    msg = EmailMessage()
    msg["Message-ID"] = message_id
    msg["Subject"] = subject
    msg["From"] = sender
    msg["Date"] = date
    msg.set_content("본문 내용")
    return msg.as_bytes()


def test_parse_gmail_message_extracts_fields():
    raw = _build_raw_email(
        "<abc123@mail.snu.ac.kr>",
        "[경력개발센터] AI진로캠프 모집",
        "snucareer@snu.ac.kr",
        "Wed, 12 Aug 2026 06:42:00 +0000",
    )
    item = parse_gmail_message(raw)
    assert item.id == "<abc123@mail.snu.ac.kr>"
    assert item.source == "gmail"
    assert item.title == "[경력개발센터] AI진로캠프 모집"
    assert item.date == "2026-08-12"
    assert item.meta == "snucareer@snu.ac.kr"
    assert "rfc822msgid" in item.url


def test_fetch_gmail_notices_live_uses_imap_search(monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "me@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-pass")

    raw = _build_raw_email(
        "<xyz@snu.ac.kr>", "테스트 공지", "office@snu.ac.kr", "Thu, 13 Aug 2026 01:00:00 +0000"
    )

    fake_conn = MagicMock()
    fake_conn.search.return_value = ("OK", [b"1"])
    fake_conn.fetch.return_value = ("OK", [(b"1 (BODY[HEADER])", raw)])

    with patch("scripts.gmail_notice.imaplib.IMAP4_SSL", return_value=fake_conn):
        items = fetch_gmail_notices_live()

    fake_conn.login.assert_called_once_with("me@gmail.com", "app-pass")
    assert fake_conn.search.call_args[0][1] == "X-GM-RAW"
    assert len(items) == 1
    assert items[0].id == "<xyz@snu.ac.kr>"
