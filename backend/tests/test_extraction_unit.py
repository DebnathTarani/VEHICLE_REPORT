import pytest

from app.services.extraction import (
    _map_status,
    boost_confidence_with_ocr,
    normalize_row,
    parse_extraction_response,
)
from app.services.providers.base import ExtractionError, gemini_schema, image_mime


def test_parse_plain_object():
    out = parse_extraction_response('{"rows": [{"vrn": "AS-01-AB-1234"}]}')
    assert out == [{"vrn": "AS-01-AB-1234"}]


def test_parse_bare_array_and_fences():
    assert parse_extraction_response('```json\n[{"vrn": "A"}]\n```') == [{"vrn": "A"}]
    assert parse_extraction_response('Here you go:\n[{"vrn": "B"}]\nHope that helps') == [{"vrn": "B"}]


def test_parse_rejects_garbage():
    with pytest.raises(ExtractionError):
        parse_extraction_response("no json at all")
    with pytest.raises(ExtractionError):
        parse_extraction_response("")


def test_normalize_row_full():
    payload, conf = normalize_row(
        {
            "sr_no": "3",
            "vrn": "as01ab1234",
            "model": " Swift ",
            "entry_date": "07-02-2026",
            "in_time": "10:30",
            "out_date": "",
            "out_time": "",
            "status": "Work In Progress",
            "remarks": "  ",
            "confidence": {"vrn": 0.4},
        },
        location_id=7,
    )
    assert payload["location_id"] == 7
    assert payload["entry_date"] == "2026-02-07"  # normalized to ISO
    assert payload["in_time"] == "10:30"
    assert payload["status"] == "in_progress"
    assert payload["model"] == "Swift"
    assert payload["remarks"] is None
    assert conf["vrn"] == 0.4  # model-provided confidence respected
    assert conf["entry_date"] == 0.9  # heuristic fallback


def test_normalize_row_work_done_backfill():
    payload, _ = normalize_row(
        {"vrn": "AS-01-AB-1234", "entry_date": "07-02-2026", "in_time": "10:30",
         "out_date": "", "out_time": "16:00", "status": "work done"},
        location_id=1,
    )
    assert payload["status"] == "work_done"
    assert payload["out_date"] == "2026-02-07"  # backfilled from entry date


def test_map_status():
    assert _map_status("Work Done", False) == "work_done"
    assert _map_status("completed", False) == "work_done"
    assert _map_status("WIP", False) == "in_progress"
    assert _map_status("", False) == "in_progress"
    assert _map_status("", True) == "work_done"
    assert _map_status("cancelled", False) == "cancelled"


def test_boost_confidence_with_ocr():
    conf = {"vrn": 0.3}
    out = boost_confidence_with_ocr({"vrn": "AS-01-AB-1234"}, dict(conf), "some text AS01AB1234 here")
    assert out["vrn"] == 1.0
    out2 = boost_confidence_with_ocr({"vrn": "AS-01-AB-1234"}, dict(conf), "nothing relevant")
    assert out2["vrn"] == 0.3


def test_gemini_schema_conversion():
    schema = {
        "type": "object",
        "properties": {
            "rows": {"type": "array", "items": {"type": "object", "properties": {"a": {"type": "string"}}}},
            "n": {"type": "number"},
        },
        "required": ["rows"],
    }
    out = gemini_schema(schema)
    assert out["type"] == "OBJECT"
    assert out["properties"]["rows"]["type"] == "ARRAY"
    assert out["properties"]["rows"]["items"]["type"] == "OBJECT"
    assert out["required"] == ["rows"]


def test_image_mime():
    assert image_mime(b"\xff\xd8anything") == "image/jpeg"
    assert image_mime(b"\x89PNG\r\n\x1a\nxx") == "image/png"
    assert image_mime(b"unknown") == "image/jpeg"
