import re
from datetime import UTC, date, datetime, time


def utcnow_naive() -> datetime:
    """Naive-UTC now: portable across SQLite and Postgres TIMESTAMP WITHOUT TZ."""
    return datetime.now(UTC).replace(tzinfo=None)

_DATE_RES = [
    re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$"),          # ISO YYYY-MM-DD
    re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$"),  # DD-MM-YYYY / DD/MM/YYYY
    re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2})$"),  # DD-MM-YY
]


def parse_date_loose(raw: str | None) -> date | None:
    """Parse dates from any format observed in the v1 database.

    Handles ISO, DD-MM-YYYY, DD/MM/YYYY, DD-MM-YY, D-M-YYYY variants.
    Returns None when unparseable or out of the plausible 2000-2100 range.
    """
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    for pattern in _DATE_RES:
        m = pattern.match(text)
        if not m:
            continue
        a, b, c = (int(x) for x in m.groups())
        if pattern.pattern.startswith(r"^(\d{4})"):
            year, month, day = a, b, c
        else:
            day, month, year = a, b, c
            if year < 100:
                year += 2000
        try:
            d = date(year, month, day)
        except ValueError:
            continue
        if 2000 <= d.year <= 2100:
            return d
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


_TIME_RES = [
    re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$"),
    re.compile(r"^(\d{1,2}):(\d{2})\s*([APap]\.?[Mm]\.?)$"),
]


def parse_time_loose(raw: str | None) -> time | None:
    if not raw:
        return None
    text = raw.strip().upper().replace(".", "")
    m = _TIME_RES[1].match(text)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        suffix = m.group(3)
        if hour < 1 or hour > 12 or minute > 59:
            return None
        if suffix.startswith("P") and hour != 12:
            hour += 12
        if suffix.startswith("A") and hour == 12:
            hour = 0
        return time(hour, minute)
    m = _TIME_RES[0].match(text)
    if m:
        hour, minute, second = m.group(1), m.group(2), m.group(3) or "0"
        h, mi, s = int(hour), int(minute), int(second)
        if 0 <= h <= 23 and 0 <= mi <= 59 and 0 <= s <= 59:
            return time(h, mi, s)
    return None


def fmt_date(d: date | None) -> str | None:
    return d.isoformat() if d else None


def fmt_time(t: time | None) -> str | None:
    if t is None:
        return None
    return t.strftime("%H:%M") if t.second == 0 else t.strftime("%H:%M:%S")
