"""Migrate the v1 sqlite ``vehicle_reports`` table into the v2 schema.

Reads the old production DB strictly read-only and inserts ``VehicleEntry``
rows (idempotent via ``legacy_id``). Run from the backend dir:

    uv run python scripts/migrate_v1.py --old-db ../../vehicle_reports.db \
        [--new-db sqlite:///../data/app.db] [--dry-run] [--report exceptions.csv]

PostgreSQL targets: pass a plain *sync* SQLAlchemy URL and install the driver
first:  ``uv pip install psycopg2-binary``
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import Base  # noqa: E402
from app.models import Location, VehicleEntry  # noqa: E402
from app.services.dates import parse_date_loose, parse_time_loose  # noqa: E402
from app.services.vrn import normalize_vrn  # noqa: E402

SELECT_OLD = (
    "SELECT id, city, sr_no, vrn, model, entry_date, in_time, out_date, out_time, remarks "
    "FROM vehicle_reports ORDER BY id"
)

_STATUS_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("work_done", ("done", "complete", "exit", "out")),
    ("in_progress", ("progress", "wip")),
    ("pending", ("pending", "wait")),
    ("cancelled", ("cancel",)),
)

NOTE_UNMAPPED = "[migrated: status unmapped]"
NOTE_STATUS_FIXED = "[migrated: status corrected, out_date present]"


def map_status(raw: str | None) -> str | None:
    """Case/whitespace-tolerant substring mapping. None when unknown/empty."""
    text = (raw or "").strip().lower()
    if not text:
        return None
    for status, keys in _STATUS_RULES:
        if any(k in text for k in keys):
            return status
    return None


def _date_bucket(raw: str | None) -> str:
    text = (raw or "").strip()
    if not text:
        return "empty"
    return re.sub(r"\d", "N", text)


def _normalize_url(url: str) -> str:
    """Accept plain sqlite paths and upgrade async drivers to sync ones."""
    if "://" not in url:
        return "sqlite:///" + url
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def _make_engine(url: str) -> Engine:
    if url.startswith("sqlite:///"):
        path = url[len("sqlite:///") :]
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url)


def _sqlite_target_path(url: str) -> Path | None:
    if url.startswith("sqlite:///"):
        path = url[len("sqlite:///") :]
        if path and path != ":memory:":
            return Path(path)
    return None


def _append_note(remarks: str | None, note: str) -> str:
    base = (remarks or "").strip()
    return f"{base}; {note}".strip("; ") if base else note


def _existing_legacy_ids(engine: Engine) -> set[int]:
    with engine.connect() as conn:
        return {
            row[0]
            for row in conn.execute(
                select(VehicleEntry.legacy_id).where(VehicleEntry.legacy_id.is_not(None))
            )
        }


def _existing_location_ids(engine: Engine) -> dict[str, int]:
    with engine.connect() as conn:
        return {name: lid for lid, name in conn.execute(select(Location.id, Location.name))}


def migrate(old_db: str | Path, new_url: str, dry_run: bool = False) -> dict:
    """Run the migration. Returns a summary dict (safe for tests and CI gating)."""
    old_db = Path(old_db)
    if not old_db.exists():
        raise SystemExit(f"old database not found: {old_db}")
    url = _normalize_url(new_url)

    old_con = sqlite3.connect(f"file:{old_db}?mode=ro", uri=True)
    try:
        old_rows = old_con.execute(SELECT_OLD).fetchall()
    finally:
        old_con.close()

    # --- dry-run: do not touch the new db file at all if it does not exist yet ---
    engine: Engine | None = None
    target_file = _sqlite_target_path(url)
    if dry_run and target_file is not None and not target_file.exists():
        existing_ids: set[int] = set()
        known_locations: dict[str, int] = {}
    else:
        engine = _make_engine(url)
        if not dry_run:
            Base.metadata.create_all(engine)
        existing_ids = _existing_legacy_ids(engine)
        known_locations = _existing_location_ids(engine)

    summary: dict = {
        "total": len(old_rows),
        "inserted": 0,
        "skipped_existing": 0,
        "exceptions": [],
        "exceptions_by_reason": Counter(),
        "date_formats": {"entry_date": Counter(), "out_date": Counter()},
        "time_formats": {"in_time": Counter(), "out_time": Counter()},
        "status_counts": Counter(),
        "status_corrections": 0,
        "locations_created": 0,
        "locations_existing": len(known_locations),
        "dry_run": dry_run,
    }

    def add_exception(reason: str, row) -> None:
        summary["exceptions"].append(
            {
                "old_id": row[0],
                "city": row[1],
                "vrn": row[3],
                "raw_entry_date": row[5],
                "raw_out_date": row[7],
                "reason": reason,
            }
        )
        summary["exceptions_by_reason"][reason] += 1

    session: Session | None = None
    if engine is not None and not dry_run:
        session = Session(engine)

    pending_locations: dict[str, int] = {}

    def resolve_location(city: str | None) -> int:
        name = (city or "").strip() or "UNKNOWN"
        if name in known_locations:
            return known_locations[name]
        if name in pending_locations:
            return pending_locations[name]
        if dry_run or session is None:
            summary["locations_created"] += 1
            pending_locations[name] = 0
            return 0
        loc = Location(name=name, is_active=True)
        session.add(loc)
        session.flush()
        known_locations[name] = loc.id
        pending_locations[name] = loc.id
        summary["locations_created"] += 1
        return loc.id

    try:
        for row in old_rows:
            old_id, city, sr_no, vrn, model, raw_entry, raw_in, raw_out, raw_out_t, remarks = row

            summary["date_formats"]["entry_date"][_date_bucket(raw_entry)] += 1
            summary["date_formats"]["out_date"][_date_bucket(raw_out)] += 1
            summary["time_formats"]["in_time"][_date_bucket(raw_in)] += 1
            summary["time_formats"]["out_time"][_date_bucket(raw_out_t)] += 1

            entry_date = parse_date_loose(raw_entry)
            out_date = parse_date_loose(raw_out)
            in_time = parse_time_loose(raw_in)
            out_time = parse_time_loose(raw_out_t)

            raw_entry_text = (raw_entry or "").strip()
            if entry_date is None:
                add_exception(
                    "entry_date_missing" if not raw_entry_text else "entry_date_unparseable", row
                )
            raw_out_text = (raw_out or "").strip()
            if out_date is None and raw_out_text:
                add_exception("out_date_unparseable", row)

            status = map_status(remarks)
            new_remarks = (remarks or "").strip() or None
            if status is None:
                status = "in_progress"
                new_remarks = _append_note(new_remarks, NOTE_UNMAPPED)
                add_exception("status_unmapped", row)

            if out_date is not None and status == "in_progress":
                status = "work_done"
                new_remarks = _append_note(new_remarks, NOTE_STATUS_FIXED)
                summary["status_corrections"] += 1

            if entry_date is not None and out_date is not None and out_date < entry_date:
                add_exception("out_date_before_entry_date", row)

            summary["status_counts"][status] += 1

            if old_id in existing_ids:
                summary["skipped_existing"] += 1
                continue

            location_id = resolve_location(city)
            entry = VehicleEntry(
                location_id=location_id,
                sr_no=sr_no,
                vrn=(vrn or "").strip(),
                vrn_normalized=normalize_vrn(vrn),
                model=(model or "").strip() or None,
                entry_date=entry_date,
                in_time=in_time,
                out_date=out_date,
                out_time=out_time,
                status=status,
                remarks=new_remarks,
                source="manual",
                created_by=None,
                legacy_id=old_id,
            )
            if dry_run or session is None:
                summary["inserted"] += 1
                existing_ids.add(old_id)
                continue
            session.add(entry)
            existing_ids.add(old_id)
            summary["inserted"] += 1
            if summary["inserted"] % 500 == 0:
                session.commit()

        if session is not None:
            session.commit()
    finally:
        if session is not None:
            session.close()
        if engine is not None:
            engine.dispose()

    summary["exceptions_by_reason"] = dict(summary["exceptions_by_reason"])
    for group in ("date_formats", "time_formats"):
        summary[group] = {k: dict(v) for k, v in summary[group].items()}
    summary["status_counts"] = dict(summary["status_counts"])
    return summary


def write_report(exceptions: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "old_id",
                "city",
                "vrn",
                "raw_entry_date",
                "raw_out_date",
                "reason",
            ],
        )
        writer.writeheader()
        writer.writerows(exceptions)


def print_summary(summary: dict, report_path: str | Path | None = None) -> None:
    width = 46
    print("=" * width)
    print("v1 -> v2 migration summary" + ("  [DRY RUN]" if summary["dry_run"] else ""))
    print("=" * width)
    print(f"{'total old rows':<28}{summary['total']}")
    verb = "would insert" if summary["dry_run"] else "inserted"
    print(f"{verb:<28}{summary['inserted']}")
    print(f"{'skipped_existing':<28}{summary['skipped_existing']}")
    print(f"{'locations created':<28}{summary['locations_created']}")
    print(f"{'status auto-corrections':<28}{summary['status_corrections']}")
    print(f"{'exceptions':<28}{len(summary['exceptions'])}")
    for reason, count in sorted(
        summary["exceptions_by_reason"].items(), key=lambda kv: (-kv[1], kv[0])
    ):
        print(f"    {reason:<34}{count}")
    if summary.get("status_counts"):
        print("-" * width)
        print("final status distribution:")
        for status, count in sorted(
            summary["status_counts"].items(), key=lambda kv: (-kv[1], kv[0])
        ):
            print(f"    {status:<34}{count}")
    for field, hist in summary["date_formats"].items():
        print("-" * width)
        print(f"{field} source formats:")
        for bucket, count in sorted(hist.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"    {bucket:<34}{count}")
    if report_path:
        print("-" * width)
        print(f"exception report: {report_path}")
    print("=" * width)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog=(
            "PostgreSQL: use a sync SQLAlchemy URL (postgresql://...) and run "
            "'uv pip install psycopg2-binary' first. Exit code 1 if any exception rows."
        ),
    )
    parser.add_argument("--old-db", required=True, help="path to v1 sqlite file (read-only)")
    parser.add_argument(
        "--new-db",
        default="sqlite:///../data/app.db",
        help="sync SQLAlchemy URL or plain sqlite path "
        "(default: sqlite:///../data/app.db, relative to backend dir)",
    )
    parser.add_argument("--dry-run", action="store_true", help="print summary without writing")
    parser.add_argument("--report", default=None, help="write exception rows to this CSV")
    args = parser.parse_args(argv)

    summary = migrate(args.old_db, args.new_db, dry_run=args.dry_run)
    if args.report:
        write_report(summary["exceptions"], args.report)
    print_summary(summary, args.report)
    return 1 if summary["exceptions"] else 0


if __name__ == "__main__":
    sys.exit(main())
