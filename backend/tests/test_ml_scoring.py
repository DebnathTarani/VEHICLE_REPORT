import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from ml_eval.scoring import (  # noqa: E402
    aggregate,
    match_rows,
    score_case,
    score_date,
    score_row,
    score_time,
    score_vrn,
)


def test_score_vrn():
    assert score_vrn("AS-01-AB-1234", "as01ab1234")
    assert score_vrn("AS01AB1234", "as-01-ab-1234")
    assert score_vrn("NL05C 4521", "NL05C4521")
    assert not score_vrn("AS01AB1234", "AS01AB1235")
    assert not score_vrn("AS01AB1234", "")
    assert score_vrn("", "")
    assert score_vrn(None, None)
    # fallback: non-VRN-shaped strings compare case-insensitively
    assert score_vrn("XYZ-9", "xyz 9")
    assert not score_vrn("XYZ-9", "abc")


def test_score_date():
    assert score_date("2025-09-09", "09-09-2025")
    assert score_date("2025-09-09", "09/09/2025")
    assert score_date("23-05-26", "2026-05-23")
    assert not score_date("2025-09-09", "2025-09-10")
    assert not score_date("garbage", "2025-09-09")
    assert not score_date("garbage", "")
    assert score_date("", "")
    assert score_date(None, "")


def test_score_time():
    assert score_time("10:30", "10:30")
    assert score_time("10:30", "10:31") is False
    assert score_time("10:30", "10:31", tolerance_min=2)
    assert score_time("10:30", "10:35", tolerance_min=2) is False
    assert score_time("10:30 AM", "10:30")
    assert not score_time("garbage", "10:30")
    assert score_time("", "")


def test_score_row_per_field():
    expected = {
        "vrn": "AS-01-AB-1234",
        "model": "Tata Ace",
        "entry_date": "07-02-2026",
        "in_time": "10:30",
        "out_date": "",
        "out_time": "",
        "status": "in_progress",
    }
    actual = {
        "vrn": "AS01AB1234",
        "model": "TATA ACE",
        "entry_date": "2026-02-07",
        "in_time": "10:31",
        "out_date": "",
        "out_time": "",
        "status": "in_progress",
    }
    result = score_row(expected, actual)
    assert result == {
        "vrn": True,
        "model": True,
        "entry_date": True,
        "in_time": False,
        "out_date": True,
        "out_time": True,
        "status": True,
    }
    # subset of fields works
    assert score_row(expected, actual, fields=("vrn",)) == {"vrn": True}


def test_match_rows_by_vrn_falls_back_to_order():
    expected = [
        {"vrn": "AS01AB1234"},
        {"vrn": "NL05C4521"},
    ]
    actual = [
        {"vrn": "nl05c 4521"},  # out of order
        {"vrn": "as-01-ab-1234"},
    ]
    pairs, missing, extra = match_rows(expected, actual)
    assert missing == 0 and extra == 0
    assert pairs[0][0]["vrn"] == "AS01AB1234" and pairs[0][1]["vrn"] == "as-01-ab-1234"
    assert pairs[1][0]["vrn"] == "NL05C4521" and pairs[1][1]["vrn"] == "nl05c 4521"

    # misread VRN -> positional fallback pairs them anyway
    pairs, missing, extra = match_rows(
        [{"vrn": "AS01AB1234"}], [{"vrn": "AS01AB1235"}]
    )
    assert (missing, extra) == (0, 0)
    assert pairs[0][0]["vrn"] == "AS01AB1234"

    # missing and extra bookkeeping
    pairs, missing, extra = match_rows(
        [{"vrn": "A"}, {"vrn": "B"}], [{"vrn": "A"}]
    )
    assert (missing, extra) == (1, 0)
    pairs, missing, extra = match_rows([{"vrn": "A"}], [{"vrn": "A"}, {"vrn": "B"}])
    assert (missing, extra) == (0, 1)


def test_score_case_and_aggregate():
    expected_rows = [
        {
            "vrn": "AS-01-AB-1234",
            "model": "BOLERO",
            "entry_date": "07-02-2026",
            "in_time": "10:30",
            "out_date": "",
            "out_time": "",
            "status": "in_progress",
        },
        {
            "vrn": "NL05C 4521",
            "model": "ACE",
            "entry_date": "07-02-2026",
            "in_time": "11:15",
            "out_date": "07-02-2026",
            "out_time": "14:45",
            "status": "work_done",
        },
    ]
    actual_ok = [dict(r) for r in expected_rows]
    actual_bad = [
        {**expected_rows[0], "in_time": "10:40"},
        {**expected_rows[1], "status": "in_progress"},
    ]
    case_ok = score_case(expected_rows, actual_ok)
    case_bad = score_case(expected_rows, actual_bad)
    case_missing = score_case(expected_rows, actual_ok[:1])

    agg = aggregate([case_ok, case_bad, case_missing])
    assert agg["cases_total"] == 3
    assert agg["rows_total"] == 5
    assert agg["rows_fully_correct"] == 3  # 2 in case_ok + the 1 matched row in case_missing
    assert agg["cases_fully_correct"] == 1
    assert agg["missing_rows"] == 1
    assert agg["extra_rows"] == 0
    assert agg["per_field_accuracy"]["vrn"] == 1.0
    assert agg["per_field_accuracy"]["in_time"] == round(4 / 5, 4)
    assert agg["per_field_accuracy"]["status"] == round(4 / 5, 4)

    assert aggregate([])["cases_total"] == 0
