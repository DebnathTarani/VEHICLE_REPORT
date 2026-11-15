from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models import User, VehicleEntry
from app.schemas import serialize_entry
from app.services.dates import fmt_date
from app.services.vrn import display_vrn, normalize_vrn

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("")
async def search_vehicles(
    q: str = Query("", max_length=32),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    norm = normalize_vrn(q)
    stmt = (
        select(
            VehicleEntry.vrn_normalized,
            func.count().label("visits"),
            func.min(VehicleEntry.entry_date).label("first_seen"),
            func.max(VehicleEntry.entry_date).label("last_seen"),
            func.sum(case((VehicleEntry.status == "in_progress", 1), else_=0)).label("open_entries"),
        )
        .group_by(VehicleEntry.vrn_normalized)
    )
    if norm:
        stmt = stmt.where(VehicleEntry.vrn_normalized.ilike(f"%{norm}%"))
    stmt = stmt.order_by(func.max(VehicleEntry.entry_date).desc().nullslast()).limit(limit)
    rows = (await db.execute(stmt)).all()
    vrns = [r.vrn_normalized for r in rows if r.vrn_normalized]
    latest_model: dict[str, str | None] = {}
    if vrns:
        rows2 = (
            await db.execute(
                select(VehicleEntry.vrn_normalized, VehicleEntry.model)
                .where(VehicleEntry.vrn_normalized.in_(vrns))
                .order_by(VehicleEntry.vrn_normalized, VehicleEntry.entry_date.desc())
            )
        ).all()
        for vrn, model in rows2:
            latest_model.setdefault(vrn, model)
    items = [
        {
            "vrn_normalized": r.vrn_normalized,
            "display_vrn": display_vrn(r.vrn_normalized),
            "model_last": latest_model.get(r.vrn_normalized),
            "visits": int(r.visits or 0),
            "first_seen": fmt_date(r.first_seen),
            "last_seen": fmt_date(r.last_seen),
            "open_entries": int(r.open_entries or 0),
        }
        for r in rows
        if r.vrn_normalized
    ]
    return {"items": items}


def _duration_hours(entry: VehicleEntry) -> float | None:
    if not (entry.entry_date and entry.out_date and entry.in_time and entry.out_time):
        return None
    start = datetime.combine(entry.entry_date, entry.in_time)
    end = datetime.combine(entry.out_date, entry.out_time)
    return round((end - start).total_seconds() / 3600, 2)


@router.get("/{vrn_normalized}/timeline")
async def vehicle_timeline(
    vrn_normalized: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    norm = normalize_vrn(vrn_normalized)
    if not norm:
        raise HTTPException(404, detail="invalid_vrn")
    rows = (
        (
            await db.execute(
                select(VehicleEntry)
                .where(VehicleEntry.vrn_normalized == norm)
                .order_by(VehicleEntry.entry_date.desc().nullslast(), VehicleEntry.id.desc())
            )
        )
        .unique()
        .scalars()
        .all()
    )
    entries = []
    for e in rows:
        duration = _duration_hours(e)
        flags: list[str] = []
        if e.status == "in_progress":
            flags.append("open_record")
        if duration is not None and duration < 0:
            flags.append("negative_duration")
        entries.append({**serialize_entry(e), "duration_hours": duration, "flags": flags})
    return {
        "vrn_normalized": norm,
        "display_vrn": display_vrn(norm),
        "entries": entries,
    }
