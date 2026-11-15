async def test_create_and_get_entry(admin, location):
    payload = {
        "location_id": location["id"],
        "sr_no": 2,
        "vrn": "nl01a 5678",
        "model": "Bolero",
        "entry_date": "07-02-2026",  # DD-MM-YYYY accepted on input
        "in_time": "10:30",
        "out_date": None,
        "out_time": None,
        "status": "in_progress",
        "remarks": "tyre work",
    }
    r = await admin.post("/api/entries", payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["vrn_normalized"] == "NL01A5678"
    assert data["entry_date"] == "2026-02-07"  # stored/returned ISO
    assert data["in_time"] == "10:30"
    assert data["source"] == "manual"

    r = await admin.get(f"/api/entries?location_id={location['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["location_name"] == location["name"]


async def test_invalid_entry_rejected(admin, location):
    r = await admin.post(
        "/api/entries",
        {
            "location_id": location["id"],
            "vrn": "not-a-vehicle",
            "status": "in_progress",
        },
    )
    assert r.status_code == 422
    assert "vrn" in r.json()["detail"]["errors"]

    r = await admin.post(
        "/api/entries",
        {
            "location_id": location["id"],
            "vrn": "AS-01-AB-1234",
            "status": "work_done",
            "entry_date": "2026-02-07",
            "out_date": "2026-02-06",
        },
    )
    assert r.status_code == 422  # out_date before entry_date


async def test_bulk_atomic(admin, location):
    r = await admin.post(
        "/api/entries/bulk",
        {
            "items": [
                {"location_id": location["id"], "vrn": "AS-01-AB-0001", "status": "in_progress", "entry_date": "2026-02-07", "in_time": "09:00"},
                {"location_id": location["id"], "vrn": "garbage", "status": "in_progress"},
            ]
        },
    )
    assert r.status_code == 422
    assert "1.vrn" in r.json()["detail"]["errors"]
    r = await admin.get("/api/entries")
    assert r.json()["total"] == 0  # nothing inserted (atomic)

    r = await admin.post(
        "/api/entries/bulk",
        {
            "items": [
                {"location_id": location["id"], "vrn": "AS-01-AB-0001", "status": "in_progress", "entry_date": "2026-02-07", "in_time": "09:00"},
                {"location_id": location["id"], "sr_no": 2, "vrn": "AS02CD5678", "status": "work_done", "entry_date": "2026-02-07", "in_time": "10:00", "out_date": "2026-02-07", "out_time": "14:00"},
            ]
        },
    )
    assert r.status_code == 200
    assert len(r.json()["created"]) == 2


async def test_filters_and_search(admin, location, location2, make_entry):
    await make_entry(vrn="AS-01-AB-1111", entry_date="2026-01-15", model="Swift")
    await make_entry(vrn="NL-05-CD-2222", entry_date="2026-02-01", status="in_progress",
                     out_date=None, out_time=None, location_id=location2["id"], model=None)
    await make_entry(vrn="MZ-01-V-3333", entry_date="2026-02-05", remarks="engine", model=None)

    r = await admin.get(f"/api/entries?location_id={location2['id']}")
    assert r.json()["total"] == 1

    r = await admin.get("/api/entries?status=in_progress")
    assert r.json()["total"] == 1

    r = await admin.get("/api/entries?date_from=2026-02-01&date_to=2026-02-05")
    assert r.json()["total"] == 2

    r = await admin.get("/api/entries?q=as01ab1111")  # normalized match
    assert r.json()["total"] == 1
    r = await admin.get("/api/entries?q=engine")
    assert r.json()["total"] == 1
    r = await admin.get("/api/entries?q=Swift")
    assert r.json()["total"] == 1

    r = await admin.get("/api/entries?page=1&page_size=2")
    assert r.json()["total"] == 3 and len(r.json()["items"]) == 2


async def test_patch_and_delete(admin, make_entry, location, make_user):
    entry = await make_entry()
    r = await admin.patch(
        f"/api/entries/{entry['id']}",
        {"status": "work_done", "out_date": "2026-02-08", "out_time": "11:00"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "work_done"
    assert r.json()["out_time"] == "11:00"

    r = await admin.patch(f"/api/entries/{entry['id']}", {"status": "in_progress", "out_date": None, "out_time": None})
    assert r.json()["status"] == "in_progress"

    operator = await make_user("operator")
    entry2 = await make_entry(vrn="AS-03-EF-4444")
    r = await operator.delete(f"/api/entries/{entry2['id']}")
    assert r.status_code == 403  # delete admin-only
    r = await admin.delete(f"/api/entries/{entry2['id']}")
    assert r.status_code == 200


async def test_audit_records_maintained(admin, make_entry, clean_db):
    from sqlalchemy import select

    from app.db import async_session_maker
    from app.models import AuditLog

    await make_entry()
    async with async_session_maker() as db:
        rows = (await db.execute(select(AuditLog))).scalars().all()
    assert any(r.action == "create" and r.entity == "entry" for r in rows)
