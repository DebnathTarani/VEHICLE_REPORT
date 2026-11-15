import io

from openpyxl import load_workbook


async def test_export_xlsx(admin, make_entry, location, location2):
    await make_entry(vrn="AS-01-AB-1111")
    await make_entry(vrn="NL-05-CD-2222", location_id=location2["id"], status="in_progress",
                     out_date=None, out_time=None)
    r = await admin.get("/api/exports/entries.xlsx")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    wb = load_workbook(io.BytesIO(r.content))
    ws = wb.active
    rows = list(ws.values)
    assert rows[0][0] == "Location"
    assert len(rows) == 3
    dates = {rows[1][4], rows[2][4]}
    assert "07-02-2026" in dates  # DD-MM-YYYY in exported file


async def test_vehicles_search_and_timeline(admin, make_entry, location):
    await make_entry(vrn="AS-01-AB-1234", entry_date="2026-01-10", in_time="09:00",
                     out_date="2026-01-10", out_time="13:30")
    await make_entry(vrn="as 01 ab 1234", entry_date="2026-02-05", in_time="10:00",
                     out_date=None, out_time=None, status="in_progress")
    await make_entry(vrn="NL-05-CD-2222", entry_date="2026-02-03", in_time="08:00",
                     out_date="2026-02-03", out_time="06:00")  # negative duration

    r = await admin.get("/api/vehicles?q=AS01AB1234")
    items = r.json()["items"]
    assert len(items) == 1
    v = items[0]
    assert v["vrn_normalized"] == "AS01AB1234"
    assert v["visits"] == 2
    assert v["open_entries"] == 1
    assert v["display_vrn"] == "AS-01-AB-1234"
    assert v["first_seen"] == "2026-01-10"
    assert v["last_seen"] == "2026-02-05"

    r = await admin.get("/api/vehicles/AS-01-AB-1234/timeline")
    body = r.json()
    assert body["display_vrn"] == "AS-01-AB-1234"
    assert len(body["entries"]) == 2
    newest, oldest = body["entries"]
    assert newest["entry_date"] == "2026-02-05"
    assert "open_record" in newest["flags"]
    assert oldest["duration_hours"] == 4.5

    r = await admin.get("/api/vehicles/NL05CD2222/timeline")
    e = r.json()["entries"][0]
    assert "negative_duration" in e["flags"]
    assert e["duration_hours"] < 0


async def test_dashboard(admin, make_entry, location, location2):
    from datetime import date

    today = date.today().isoformat()
    await make_entry(vrn="AS-01-AB-1234", entry_date=today, status="work_done", out_date=today)
    await make_entry(vrn="AS-02-CD-5678", entry_date=today, status="in_progress",
                     out_date=None, out_time=None, location_id=location2["id"])

    r = await admin.get("/api/dashboard/summary")
    body = r.json()
    assert body["date"] == today
    by_name = {p["name"]: p for p in body["per_location"]}
    assert by_name["Hailakandi"]["entries_today"] == 1
    assert by_name["Karimganj"]["open_wip"] == 1
    assert len(body["week_series"]) == 7
    wip = body["open_wip"]
    assert len(wip) == 1
    assert wip[0]["age_days"] == 0
    assert wip[0]["status"] == "in_progress"


async def test_email_report_no_entries(admin):
    r = await admin.post("/api/exports/email-report", {"date": "2000-01-01"})
    assert r.json()["ok"] is False
