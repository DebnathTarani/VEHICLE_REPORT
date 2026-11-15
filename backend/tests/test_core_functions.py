from datetime import time

from app.services.dates import parse_date_loose, parse_time_loose
from app.services.vrn import display_vrn, is_valid_vrn, normalize_vrn


def test_normalize_vrn():
    assert normalize_vrn("AS-01-AB-1234") == "AS01AB1234"
    assert normalize_vrn("as01ab1234") == "AS01AB1234"
    assert normalize_vrn("NL1AJ 3099") == "NL01AJ3099"
    assert normalize_vrn("MZ01V 8993") == "MZ01V8993"
    assert normalize_vrn("AS01SC 3291") == "AS01SC3291"
    assert normalize_vrn("  ") == ""
    assert normalize_vrn(None) == ""


def test_display_vrn():
    assert display_vrn("AS01AB1234") == "AS-01-AB-1234"
    assert display_vrn("NL01AJ3099") == "NL-01-AJ-3099"
    assert display_vrn("weird") == "WEIRD"


def test_is_valid_vrn():
    assert is_valid_vrn("AS-01-AB-1234")
    assert is_valid_vrn("as01ab1234")
    assert not is_valid_vrn("1234")
    assert not is_valid_vrn("")
    assert not is_valid_vrn("ABCDEFGH")


def test_parse_date_loose_all_observed_formats():
    import datetime

    d = datetime.date(2025, 9, 9)
    for raw in ("2025-09-09", "09-09-2025", "09/09/2025", "9-9-2025", "9/9/2025", "09.09.2025"):
        assert parse_date_loose(raw) == d, raw
    # 2-digit years seen in the v1 DB
    assert parse_date_loose("23-05-26") == datetime.date(2026, 5, 23)
    assert parse_date_loose("26-9-2026") == datetime.date(2026, 9, 26)
    assert parse_date_loose("14/10/2026") == datetime.date(2026, 10, 14)
    assert parse_date_loose("") is None
    assert parse_date_loose(None) is None
    assert parse_date_loose("garbage-date") is None
    assert parse_date_loose("99-99-9999") is None
    assert parse_date_loose("01-01-1990") is None  # implausible year rejected


def test_parse_time_loose():
    assert parse_time_loose("10:30") == time(10, 30)
    assert parse_time_loose("1:05 PM") == time(13, 5)
    assert parse_time_loose("12:00 AM") == time(0, 0)
    assert parse_time_loose("12:30:00") == time(12, 30)
    assert parse_time_loose("25:00") is None
    assert parse_time_loose("nope") is None
    assert parse_time_loose(None) is None
