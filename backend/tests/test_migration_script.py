import sqlite3
import sys
from datetime import date, time
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.models import Location, VehicleEntry  # noqa: E402
from scripts.migrate_v1 import migrate, write_report  # noqa: E402

# (id, city, sr_no, vrn, model, entry_date, in_time, out_date, out_time, remarks)
OLD_ROWS = [
    (1, "Karimganj", 1, "AS-01-AB-1234", "BOLERO", "2025-09-09", "10:30", "2025-09-09", "13:14", "Work Done"),
    (2, "Karimganj", 2, "NL05C 4521", "ACE", "09-09-2025", "09:00", "", "", "Work In Progress"),
    (3, "Jhapirbond", 3, "AS02C 9911", "SCORPIO", "09/09/2025", "08:00", "09/09/2025", "09:30", "done"),
    (4, "Jhapirbond", 4, "AS-02-C-9912", "SUMO", "9-9-2025", "08:30", "", "", "WIP"),
    (5, "Kalain", 5, "TR01J 0011", "TEMPO", "23-05-26", "07:00", "", "", "PENDING"),
    (6, "Kalain", 6, "ML04EF 5678", "SUMO", "garbage-date", "07:30", "", "", "Work In Progress"),
    (7, "Sildubi", 7, "AS-03-D-1111", "ACE", "2026-01-10", "10:00", "2026-01-08", "11:00", "Work Done"),
    (8, "Sildubi", 8, "AS-04-E-2222", "BIKE", "", "", "2026-01-10", "10:00", ""),
    (9, "Karimganj", 9, "AS-05-F-3333", "CAB", "09-09-2025", "09:00", "10-09-2025", "10:00", "in progress"),
    (10, "Karimganj", 10, "AS-06-G-4444", "TRACTOR", "09-09-2025", "09:00", "", "", "Cancelled"),
]


def make_old_db(path: Path) -> Path:
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE vehicle_reports ("
        "id INTEGER PRIMARY KEY, city TEXT, sr_no INTEGER, vrn TEXT, model TEXT, "
        "entry_date TEXT, in_time TEXT, out_date TEXT, out_time TEXT, remarks TEXT)"
    )
    con.executemany("INSERT INTO vehicle_reports VALUES (?,?,?,?,?,?,?,?,?,?)", OLD_ROWS)
    con.commit()
    con.close()
    return path


def fetch_entries(new_db_path: Path) -> dict[int, VehicleEntry]:
    engine = create_engine(f"sqlite:///{new_db_path}")
    with Session(engine) as session:
        entries = session.scalars(select(VehicleEntry)).all()
        session.expunge_all()
    engine.dispose()
    return {e.legacy_id: e for e in entries}


@pytest.fixture()
def old_db(tmp_path: Path) -> Path:
    return make_old_db(tmp_path / "old.db")


def new_url(tmp_path: Path, name: str = "new.db") -> str:
    return f"sqlite:///{tmp_path / name}"


def test_migrate_counts_status_and_dates(old_db: Path, tmp_path: Path):
    summary = migrate(old_db, new_url(tmp_path))
    assert summary["total"] == len(OLD_ROWS)
    assert summary["inserted"] == len(OLD_ROWS)
    assert summary["skipped_existing"] == 0
    assert summary["locations_created"] == 4  # Karimganj, Jhapirbond, Kalain, Sildubi

    reasons = summary["exceptions_by_reason"]
    assert reasons == {
        "entry_date_unparseable": 1,  # garbage-date (id 6)
        "entry_date_missing": 1,  # empty (id 8)
        "out_date_before_entry_date": 1,  # id 7
        "status_unmapped": 1,  # empty remarks (id 8)
    }
    assert len(summary["exceptions"]) == 4

    entries = fetch_entries(tmp_path / "new.db")
    assert entries[1].status == "work_done"
    assert entries[1].entry_date == date(2025, 9, 9)
    assert entries[1].out_time == time(13, 14)
    assert entries[2].status == "in_progress"
    assert entries[3].status == "work_done"  # "done"
    assert entries[4].status == "in_progress"  # "WIP"
    assert entries[5].status == "pending"
    assert entries[5].entry_date == date(2026, 5, 23)  # 2-digit year DD-MM-YY
    assert entries[6].status == "in_progress"
    assert entries[6].entry_date is None  # still migrated, unparseable -> None
    assert entries[7].status == "work_done"
    assert entries[8].status == "work_done"  # unmapped -> in_progress, then out_date fixes it
    assert "status unmapped" in (entries[8].remarks or "")
    assert "status corrected" in (entries[8].remarks or "")
    assert entries[1].vrn_normalized == "AS01AB1234"
    assert entries[2].vrn_normalized == "NL05C4521"
    assert entries[9].status == "work_done"  # in_progress + out_date present -> corrected
    assert "status corrected" in (entries[9].remarks or "")
    assert entries[10].status == "cancelled"

    # date format histogram includes the messy formats encountered
    fmts = summary["date_formats"]["entry_date"]
    for bucket in ("NNNN-NN-NN", "NN-NN-NNNN", "NN/NN/NNNN", "N-N-NNNN", "NN-NN-NN"):
        assert bucket in fmts, bucket


def test_migrate_is_idempotent(old_db: Path, tmp_path: Path):
    url = new_url(tmp_path)
    first = migrate(old_db, url)
    assert first["inserted"] == len(OLD_ROWS)
    second = migrate(old_db, url)
    assert second["inserted"] == 0
    assert second["skipped_existing"] == len(OLD_ROWS)
    assert second["locations_created"] == 0
    engine = create_engine(url)
    with Session(engine) as session:
        assert session.scalar(select(func.count(VehicleEntry.id))) == len(OLD_ROWS)
        assert session.scalar(select(func.count(Location.id))) == 4
    engine.dispose()


def test_migrate_dry_run_writes_nothing(old_db: Path, tmp_path: Path):
    target = tmp_path / "never.db"
    summary = migrate(old_db, f"sqlite:///{target}", dry_run=True)
    assert summary["dry_run"] is True
    assert summary["inserted"] == len(OLD_ROWS)  # "would insert"
    assert not target.exists()  # dry run never touches the filesystem
    # ... and the real run afterwards still inserts everything
    real = migrate(old_db, f"sqlite:///{target}")
    assert real["inserted"] == len(OLD_ROWS)


def test_migrate_plain_path_and_report_csv(old_db: Path, tmp_path: Path):
    url = new_url(tmp_path, "plain.db")
    summary = migrate(old_db, url)
    report = tmp_path / "sub" / "exceptions.csv"
    write_report(summary["exceptions"], report)
    lines = report.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "old_id,city,vrn,raw_entry_date,raw_out_date,reason"
    assert len(lines) == 1 + len(summary["exceptions"])
    assert any("garbage-date" in line for line in lines)
    assert any("2026-01-10" in line and "2026-01-08" in line for line in lines)


def test_migrate_main_exit_code_gates_on_exceptions(old_db: Path, tmp_path: Path, capsys):
    from scripts.migrate_v1 import main

    rc = main(["--old-db", str(old_db), "--new-db", new_url(tmp_path, "cli.db")])
    out = capsys.readouterr().out
    assert rc == 1  # exception rows exist
    assert "total old rows" in out
    assert "entry_date_unparseable" in out
    rc_ok = main(
        [
            "--old-db",
            str(old_db),
            "--new-db",
            new_url(tmp_path, "cli2.db"),
            "--dry-run",
        ]
    )
    assert rc_ok == 1  # exceptions are reported in dry-run too


def test_migrate_accepts_async_sqlite_url(old_db: Path, tmp_path: Path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'asyncfixed.db'}"
    summary = migrate(old_db, url)
    assert summary["inserted"] == len(OLD_ROWS)
    assert (tmp_path / "asyncfixed.db").exists()
