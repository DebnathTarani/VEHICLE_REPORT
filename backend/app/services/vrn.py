import re

VRN_FULL_RE = re.compile(r"^([A-Z]{1,2})(\d{1,2})([A-Z]{1,3})(\d{1,4})$")


def normalize_vrn(raw: str | None) -> str:
    """Return compact normalized form, e.g. 'AS01AB1234'. Falls back to alnum-strip."""
    if not raw:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
    m = VRN_FULL_RE.match(cleaned)
    if not m:
        return cleaned
    state, district, series, number = m.groups()
    return f"{state}{district.zfill(2)}{series}{number.zfill(4)}"


def display_vrn(vrn_normalized: str | None) -> str:
    """Render normalized VRN as AS-01-AB-1234 when parseable."""
    if not vrn_normalized:
        return ""
    cleaned = re.sub(r"[^A-Z0-9]", "", vrn_normalized.upper())
    m = VRN_FULL_RE.match(cleaned)
    if not m:
        return cleaned
    state, district, series, number = m.groups()
    return f"{state}-{district.zfill(2)}-{series}-{number.zfill(4)}"


def is_valid_vrn(raw: str | None) -> bool:
    return bool(VRN_FULL_RE.match(re.sub(r"[^A-Za-z0-9]", "", raw or "").upper()))
