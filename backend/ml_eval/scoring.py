"""Pure scoring functions for the ML extraction harness.

No network, no DB access — only the shared parsing/normalization helpers from
app.services so the harness scores exactly what the app itself produces.
"""

from __future__ import annotations

from app.services.dates import parse_date_loose, parse_time_loose
from app.services.vrn import normalize_vrn

DEFAULT_FIELDS: tuple[str, ...] = (
    "vrn",
    "model",
    "entry_date",
    "in_time",
    "out_date",
    "out_time",
    "status",
)

_DATE_FIELDS = frozenset({"entry_date", "out_date"})
_TIME_FIELDS = frozenset({"in_time", "out_time"})


def _s(value: object) -> str:
    return (str(value) if value is not None else "").strip()


def score_vrn(expected: str | None, actual: str | None) -> bool:
    e, a = _s(expected), _s(actual)
    if not e and not a:
        return True
    ne, na = normalize_vrn(e), normalize_vrn(a)
    if ne and na:
        return ne == na
    return e.casefold() == a.casefold()


def score_date(expected: str | None, actual: str | None) -> bool:
    e, a = _s(expected), _s(actual)
    if not e and not a:
        return True
    de, da = parse_date_loose(e), parse_date_loose(a)
    return de is not None and de == da


def score_time(expected: str | None, actual: str | None, tolerance_min: int = 0) -> bool:
    e, a = _s(expected), _s(actual)
    if not e and not a:
        return True
    te, ta = parse_time_loose(e), parse_time_loose(a)
    if te is None or ta is None:
        return False
    if tolerance_min <= 0:
        return te == ta
    me = te.hour * 60 + te.minute + (1 if te.second >= 30 else 0)
    ma = ta.hour * 60 + ta.minute + (1 if ta.second >= 30 else 0)
    return abs(me - ma) <= tolerance_min


def _score_field(field: str, expected: object, actual: object) -> bool:
    if field == "vrn":
        return score_vrn(_s(expected), _s(actual))
    if field in _DATE_FIELDS:
        return score_date(_s(expected), _s(actual))
    if field in _TIME_FIELDS:
        return score_time(_s(expected), _s(actual))
    return _s(expected).casefold() == _s(actual).casefold()


def score_row(
    expected_row: dict,
    actual_row: dict,
    fields: tuple[str, ...] = DEFAULT_FIELDS,
) -> dict:
    """Per-field bool correctness for one already-matched row pair."""
    exp = expected_row or {}
    act = actual_row or {}
    return {f: _score_field(f, exp.get(f), act.get(f)) for f in fields}


def match_rows(
    expected_rows: list[dict],
    actual_rows: list[dict],
) -> tuple[list[tuple[dict, dict]], int, int]:
    """Pair expected/actual rows by normalized VRN, falling back to order.

    Returns (pairs, missing_count, extra_count) where missing = expected rows
    with no partner at all and extra = unpaired actual rows.
    """
    actual = list(actual_rows or [])
    taken: set[int] = set()
    pairs: list[tuple[dict, dict]] = []
    unmatched_expected: list[dict] = []

    for exp in expected_rows or []:
        nexp = normalize_vrn(exp.get("vrn"))
        idx = None
        if nexp:
            for i, act in enumerate(actual):
                if i not in taken and normalize_vrn(act.get("vrn")) == nexp:
                    idx = i
                    break
        if idx is None:
            for i, act in enumerate(actual):
                if i not in taken and not normalize_vrn(act.get("vrn")):
                    idx = i
                    break
        if idx is None:
            unmatched_expected.append(exp)
        else:
            taken.add(idx)
            pairs.append((exp, actual[idx]))

    leftovers = [act for i, act in enumerate(actual) if i not in taken]
    while unmatched_expected and leftovers:
        pairs.append((unmatched_expected.pop(0), leftovers.pop(0)))
    return pairs, len(unmatched_expected), len(leftovers)


def score_case(
    expected_rows: list[dict],
    actual_rows: list[dict],
    fields: tuple[str, ...] = DEFAULT_FIELDS,
) -> dict:
    """Score one case (one image). Includes missing/extra row bookkeeping."""
    pairs, missing, extra = match_rows(expected_rows, actual_rows)
    return {
        "rows": [score_row(e, a, fields) for e, a in pairs],
        "missing": missing,
        "extra": extra,
    }


def aggregate(
    case_results: list[dict],
    fields: tuple[str, ...] = DEFAULT_FIELDS,
) -> dict:
    """Accuracy per field, fully correct rows/cases, and case total."""
    correct = {f: 0 for f in fields}
    total = {f: 0 for f in fields}
    rows_total = 0
    rows_fully_correct = 0
    cases_fully_correct = 0
    missing_rows = 0
    extra_rows = 0

    for case in case_results or []:
        missing_rows += case.get("missing", 0)
        extra_rows += case.get("extra", 0)
        case_ok = case.get("missing", 0) == 0 and case.get("extra", 0) == 0
        for row in case.get("rows", []):
            rows_total += 1
            row_ok = True
            for f in fields:
                if f not in row:
                    continue
                total[f] += 1
                if row[f]:
                    correct[f] += 1
                else:
                    row_ok = False
            rows_fully_correct += 1 if row_ok else 0
            case_ok = case_ok and row_ok
        cases_fully_correct += 1 if case_ok else 0

    per_field = {
        f: (round(correct[f] / total[f], 4) if total[f] else None) for f in fields
    }
    return {
        "cases_total": len(case_results or []),
        "cases_fully_correct": cases_fully_correct,
        "rows_total": rows_total,
        "rows_fully_correct": rows_fully_correct,
        "missing_rows": missing_rows,
        "extra_rows": extra_rows,
        "per_field_correct": correct,
        "per_field_total": total,
        "per_field_accuracy": per_field,
    }
