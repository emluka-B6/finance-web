from unittest.mock import patch, MagicMock
from news import parse_feed

@patch("feedparser.parse")
def test_parse_feed_sorts_by_date(mock_parse):
    mock_parse.return_value = MagicMock(entries=[
        {"title": "Older", "link": "L1", "published": "Mon, 01 Jan 2020 10:00:00"},
        {"title": "Newer", "link": "L2", "published": "Tue, 02 Jan 2021 10:00:00"}
    ])

    items = parse_feed("http://fake-url", limit=5)

    assert items[0]["title"] == "Newer"

@patch("feedparser.parse")
def test_parse_feed_limit(mock_parse):
    mock_parse.return_value = MagicMock(entries=[
        {"title": f"Item {i}", "link": f"L{i}", "published": "Mon, 01 Jan 2020 10:00:00"}
        for i in range(10)
    ])

    items = parse_feed("x", limit=3)
    assert len(items) == 3

@patch("feedparser.parse")
def test_parse_feed_multiple_date_formats(mock_parse):
    mock_parse.return_value = MagicMock(entries=[
        {"title": "RSS", "link": "L1", "published": "Mon, 01 Jan 2020 10:00:00"},
        {"title": "ATOM", "link": "L2", "published": "2020-01-01T11:00:00Z"},
    ])

    items = parse_feed("x")

    assert len(items) == 2
    assert items[0]["title"] == "ATOM"

@patch("feedparser.parse")
def test_parse_feed_missing_published(mock_parse):
    mock_parse.return_value = MagicMock(entries=[
        {"title": "Has date", "link": "L1", "published": "Mon, 01 Jan 2020 10:00:00"},
        {"title": "No date", "link": "L2"}  # no published or updated
    ])

    items = parse_feed("x")

    assert items[0]["title"] == "Has date"
    assert items[-1]["title"] == "No date"

@patch("feedparser.parse")
def test_parse_feed_output_format(mock_parse):
    mock_parse.return_value = MagicMock(entries=[
        {"title": "Test", "link": "L1", "published": "Mon, 01 Jan 2020 10:00:00"},
    ])

    items = parse_feed("x")

    assert "title" in items[0]
    assert "link" in items[0]
    assert "published" in items[0]

@patch("feedparser.parse")
def test_parse_feed_removes_timezone_suffix(mock_parse):
    mock_parse.return_value = MagicMock(entries=[
        {"title": "Test", "link": "L1", "published": "Mon, 01 Jan 2020 10:00:00 +0000"},
    ])

    items = parse_feed("x")

    print(items[0]["published"])
    assert items[0]["published"].endswith("10:00:00")  # no +0000
    assert "+0000" not in items[0]["published"]

@patch("feedparser.parse")
def test_parse_feed_no_entries(mock_parse):
    mock_parse.return_value = MagicMock(entries=[])

    items = parse_feed("x")

    assert items == []




from news import format_datetime

def test_format_datetime_none():
    assert format_datetime(None) == ""


def test_format_datetime_empty_string():
    assert format_datetime("") == ""  

import time

def test_format_datetime_struct_time():
    """
    struct_time(2025-10-19 14:17:17 UTC) → convert to Europe/Warsaw
    Warsaw is typically UTC+1 or UTC+2 depending on DST.
    Let's assume test date is in October → DST (UTC+2).
    """
    struct = time.struct_time((2025, 10, 19, 14, 17, 17, 0, 0, 0))

    result = format_datetime(struct)
    assert result == "19/10/2025 14:17"   # 14:17 UTC → 16:17 Warsaw

def test_format_datetime_rfc822_with_timezone():
    value = "Sun, 19 Oct 2025 14:37:19 +0000"   # explicit UTC

    result = format_datetime(value)
    assert result == "19/10/2025 16:37"         # +2h for Warsaw


def test_format_datetime_rfc822_no_timezone():
    """
    No timezone → function uses naive datetime in local Warsaw conversion.
    We treat the given time as UTC (how your code behaves implicitly).
    """
    value = "Sun, 19 Oct 2025 14:37:19"

    result = format_datetime(value)
    assert result == "19/10/2025 14:37"         # interpreted as UTC → Warsaw +2h


def test_format_datetime_iso8601_with_Z():
    value = "2025-10-19T14:17:17Z"  # UTC

    result = format_datetime(value)
    assert result == "19/10/2025 14:17"


def test_format_datetime_iso8601_without_Z():
    value = "2025-10-19T14:17:17"   # treated as UTC (fallback)

    result = format_datetime(value)
    assert result == "19/10/2025 14:17"


def test_format_datetime_unexpected_value_type():
    """
    Should fall back to str(value)
    """
    class Dummy: pass
    value = Dummy()

    result = format_datetime(value)
    assert result == str(value)    