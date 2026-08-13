from scripts.models import NoticeItem


def test_notice_item_stores_fields():
    item = NoticeItem(
        id="123",
        source="cba",
        title="테스트 공지",
        url="https://cba.snu.ac.kr/x",
        date="2026-08-14",
        meta="일반",
    )
    assert item.id == "123"
    assert item.source == "cba"
    assert item.title == "테스트 공지"
    assert item.url == "https://cba.snu.ac.kr/x"
    assert item.date == "2026-08-14"
    assert item.meta == "일반"


def test_notice_item_defaults():
    item = NoticeItem(id="1", source="extra", title="t", url="u")
    assert item.date == ""
    assert item.meta == ""
