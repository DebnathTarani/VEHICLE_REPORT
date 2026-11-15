import base64

import pytest

import app.api.imports as imports_api
import app.services.jobs as jobs_mod
from app.services.extraction import ExtractionResult

PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _result(rows, confs=None):
    res = ExtractionResult(provider="openai", model="test-model", ocr_available=False)
    res.rows = rows
    res.confidences = confs or [None] * len(rows)
    return res


async def _seed_provider(admin) -> int:
    r = await admin.post(
        "/api/settings/providers",
        {
            "name": "local-vllm",
            "kind": "openai",
            "base_url": "http://localhost:9",
            "default_model": "test-vision",
            "api_key": "sk-secret-9999",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.fixture()
def fake_extract(monkeypatch):
    captured = {}
    monkeypatch.setattr(imports_api, "enqueue_job", lambda jid, image_ids=None: None)

    def _set(rows):
        async def fake(spec, image_bytes, location_id=None):
            captured["location_id"] = location_id
            for row in rows:
                row.setdefault("location_id", location_id)
            return _result(rows)

        monkeypatch.setattr(jobs_mod, "extract_rows", fake)
        return captured

    return _set


async def test_import_requires_provider_and_location(admin, location, location2, fake_extract):
    # no provider configured
    r = await admin.post(
        "/api/imports", files=[("files", ("a.png", PNG_1x1, "image/png"))], data={"location_id": str(location["id"])}
    )
    assert r.status_code == 422
    assert r.json()["detail"]["provider_id"] == "no_enabled_provider"

    await _seed_provider(admin)
    # location missing while two active locations exist
    r = await admin.post("/api/imports", files=[("files", ("a.png", PNG_1x1, "image/png"))])
    assert r.status_code == 422
    assert r.json()["detail"]["location_id"] == "location_required"


async def test_import_rejects_bad_files(admin, location, fake_extract):
    await _seed_provider(admin)
    r = await admin.post(
        "/api/imports", files=[("files", ("evil.txt", b"not an image at all", "text/plain"))],
        data={"location_id": str(location["id"])},
    )
    assert r.status_code == 422
    assert "files" in r.json()["detail"]


async def test_review_and_commit_flow(admin, location, location2, fake_extract):
    provider_id = await _seed_provider(admin)
    rows = [
        # row 1: clean, will be accepted then committed
        {"sr_no": "1", "vrn": "AS-01-AB-1234", "model": "Swift", "entry_date": "2026-02-07",
         "in_time": "10:30", "out_date": "2026-02-07", "out_time": "16:00", "status": "work_done", "remarks": None},
        # row 2: broken VRN — must block acceptance until edited
        {"sr_no": "2", "vrn": "??", "model": "City", "entry_date": "2026-02-07",
         "in_time": "11:00", "out_date": "", "out_time": "", "status": "in_progress", "remarks": None},
        # row 3: work_done without out_date — validation error
        {"sr_no": "3", "vrn": "NL-05-CD-2222", "model": "", "entry_date": "2026-02-07",
         "in_time": "12:00", "out_date": "", "out_time": "", "status": "work_done", "remarks": None},
    ]
    captured = fake_extract(rows)

    r = await admin.post(
        "/api/imports",
        files=[("files", ("register.png", PNG_1x1, "image/png"))],
        data={"location_id": str(location["id"]), "provider_id": str(provider_id)},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    await jobs_mod.process_job(job_id)

    detail = (await admin.get(f"/api/imports/{job_id}")).json()
    assert detail["status"] == "done"
    assert len(detail["images"]) == 1 and len(detail["images"][0]["rows"]) == 3
    assert captured["location_id"] == location["id"]
    rows_out = detail["images"][0]["rows"]
    assert rows_out[0]["validation"]["valid"] is True
    assert rows_out[1]["validation"]["valid"] is False
    assert rows_out[2]["validation"]["valid"] is False

    # cannot accept an invalid row
    r = await admin.patch(f"/api/imports/rows/{rows_out[1]['id']}", {"status": "accepted"})
    assert r.status_code == 422
    assert "vrn" in r.json()["detail"]["errors"]

    # cannot save an invalid payload edit
    r = await admin.patch(
        f"/api/imports/rows/{rows_out[1]['id']}",
        {"payload": {**rows_out[1]["payload"], "vrn": "still-bad"}},
    )
    assert r.status_code == 422

    # fix the VRN → accept
    fixed = {**rows_out[1]["payload"], "vrn": "AS-02-CD-5678"}
    r = await admin.patch(f"/api/imports/rows/{rows_out[1]['id']}", {"payload": fixed})
    assert r.status_code == 200
    assert r.json()["edited_fields"] == ["vrn"]
    r = await admin.patch(f"/api/imports/rows/{rows_out[1]['id']}", {"status": "accepted"})
    assert r.status_code == 200

    # accept the good row
    r = await admin.patch(f"/api/imports/rows/{rows_out[0]['id']}", {"status": "accepted"})
    assert r.status_code == 200

    # rejecting row 3
    r = await admin.post(f"/api/imports/rows/{rows_out[2]['id']}/reject")
    assert r.json()["status"] == "rejected"

    # commit all accepted
    r = await admin.post(f"/api/imports/{job_id}/commit", {})
    assert r.status_code == 200, r.text
    assert r.json()["committed"] == 2

    # entries exist with ai_import source and link back
    entries = (await admin.get("/api/entries")).json()["items"]
    assert len(entries) == 2
    assert all(e["source"] == "ai_import" for e in entries)
    assert {e["vrn_normalized"] for e in entries} == {"AS01AB1234", "AS02CD5678"}

    # committed rows are locked
    r = await admin.patch(f"/api/imports/rows/{rows_out[0]['id']}", {"status": "pending_review"})
    assert r.status_code == 409

    # second commit is a no-op
    r = await admin.post(f"/api/imports/{job_id}/commit", {})
    assert r.json()["committed"] == 0


async def test_commit_with_explicit_unaccepted_id_fails(admin, location, fake_extract):
    provider_id = await _seed_provider(admin)
    fake_extract([
        {"sr_no": "1", "vrn": "AS-01-AB-1234", "model": "X", "entry_date": "2026-02-07",
         "in_time": "10:00", "out_date": "2026-02-07", "out_time": "12:00", "status": "work_done", "remarks": None}
    ])
    r = await admin.post(
        "/api/imports", files=[("files", ("a.png", PNG_1x1, "image/png"))],
        data={"location_id": str(location["id"]), "provider_id": str(provider_id)},
    )
    job_id = r.json()["job_id"]
    await jobs_mod.process_job(job_id)
    detail = (await admin.get(f"/api/imports/{job_id}")).json()
    row_id = detail["images"][0]["rows"][0]["id"]
    r = await admin.post(f"/api/imports/{job_id}/commit", {"row_ids": [row_id]})
    assert r.status_code == 400


async def test_image_extraction_failure_marks_image(admin, location, monkeypatch):
    await _seed_provider(admin)

    from app.services.providers.base import ExtractionError

    async def boom(spec, image_bytes, location_id=None):
        raise ExtractionError("provider down")

    monkeypatch.setattr(jobs_mod, "extract_rows", boom)
    r = await admin.post(
        "/api/imports", files=[("files", ("a.png", PNG_1x1, "image/png"))],
        data={"location_id": str(location["id"])},
    )
    job_id = r.json()["job_id"]
    await jobs_mod.process_job(job_id)
    detail = (await admin.get(f"/api/imports/{job_id}")).json()
    assert detail["status"] == "failed"
    assert detail["images"][0]["status"] == "failed"
    assert "provider down" in detail["images"][0]["error"]

    # retry endpoint re-enqueues; stub enqueue to avoid background task
    called = {}
    monkeypatch.setattr(imports_api, "enqueue_job", lambda jid, image_ids=None: called.setdefault("n", (jid, image_ids)))
    image_id = detail["images"][0]["id"]
    r = await admin.post(f"/api/imports/{job_id}/images/{image_id}/retry")
    assert r.status_code == 200
    assert called["n"][1] == [image_id]


async def test_operator_can_review(admin, make_user, location, fake_extract):
    await _seed_provider(admin)
    fake_extract([
        {"sr_no": "1", "vrn": "AS-01-AB-7777", "model": "X", "entry_date": "2026-02-07",
         "in_time": "10:00", "out_date": "", "out_time": "", "status": "in_progress", "remarks": None}
    ])
    operator = await make_user("operator")
    r = await operator.post(
        "/api/imports", files=[("files", ("a.png", PNG_1x1, "image/png"))],
        data={"location_id": str(location["id"])},
    )
    assert r.status_code == 200
    await jobs_mod.process_job(r.json()["job_id"])
    detail = (await operator.get(f"/api/imports/{r.json()['job_id']}")).json()
    row_id = detail["images"][0]["rows"][0]["id"]
    assert (await operator.patch(f"/api/imports/rows/{row_id}", {"status": "accepted"})).status_code == 200
    assert (await operator.post(f"/api/imports/{r.json()['job_id']}/commit", {})).json()["committed"] == 1
