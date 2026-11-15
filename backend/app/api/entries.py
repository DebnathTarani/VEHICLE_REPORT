from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.deps import get_current_user, get_db, require_admin, require_operator
from app.models import Location, User, VehicleEntry
from app.schemas import BulkEntryIn, serialize_entry, validate_entry_payload
from app.services.dates import parse_date_loose
from app.services.vrn import normalize_vrn

router = APIRouter(prefix="/entries", tags=["entries"])


async def query_entries(
    db: AsyncSession,
    location_id: int | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[VehicleEntry], int]:
    conds = []
    if location_id is not None:
        conds.append(VehicleEntry.location_id == location_id)
    if status:
        conds.append(VehicleEntry.status == status)
    if date_from:
        conds.append(VehicleEntry.entry_date >= date_from)
    if date_to:
        conds.append(VehicleEntry.entry_date <= date_to)
    if q:
        norm = q.strip()
        conds.append(
            or_(
                VehicleEntry.vrn.ilike(f"%{norm}%"),
                VehicleEntry.vrn_normalized.ilike(f"%{normalize_vrn(norm)}%"),
                VehicleEntry.model.ilike(f"%{norm}%"),
                VehicleEntry.remarks.ilike(f"%{norm}%"),
            )
        )
    stmt = select(VehicleEntry)
    count_stmt = select(func.count()).select_from(VehicleEntry)
    for c in conds:
        stmt = stmt.where(c)
        count_stmt = count_stmt.where(c)
    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(
        VehicleEntry.entry_date.desc().nullslast(), VehicleEntry.location_id, VehicleEntry.sr_no
    )
    if limit is not None:
        stmt = stmt.offset(offset).limit(limit)
    rows = (await db.execute(stmt)).unique().scalars().all()
    return list(rows), total


async def _ensure_location(db: AsyncSession, location_id: int) -> Location:
    loc = await db.get(Location, location_id)
    if loc is None or not loc.is_active:
        raise HTTPException(422, detail={"location_id": "unknown location"})
    return loc


def _validated_or_422(payload: dict[str, Any]) -> Any:
    entry, errors = validate_entry_payload(payload)
    if entry is None:
        raise HTTPException(422, detail={"errors": errors})
    return entry


@router.get("")
async def list_entries(
    location_id: int | None = Query(None),
    status: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    df = parse_date_loose(date_from) if date_from else None
    dt = parse_date_loose(date_to) if date_to else None
    if date_from and df is None:
        raise HTTPException(400, detail="invalid date_from")
    if date_to and dt is None:
        raise HTTPException(400, detail="invalid date_to")
    rows, total = await query_entries(
        db,
        location_id=location_id,
        status=status,
        date_from=df,
        date_to=dt,
        q=q,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return {
        "items": [serialize_entry(e) for e in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("")
async def create_entry(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
) -> dict:
    entry = _validated_or_422(payload)
    await _ensure_location(db, entry.location_id)
    record = VehicleEntry(
        **entry.model_dump(),
        vrn_normalized=normalize_vrn(entry.vrn),
        source="manual",
        created_by=user.id,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    await record_audit(db, user, "create", "entry", record.id, after=payload)
    return serialize_entry(record)


@router.post("/bulk")
async def create_bulk(
    body: BulkEntryIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
) -> dict:
    validated = []
    all_errors: dict[str, str] = {}
    for i, payload in enumerate(body.items):
        entry, errors = validate_entry_payload(payload)
        if entry is None:
            for field, msg in errors.items():
                all_errors[f"{i}.{field}"] = msg
            continue
        validated.append((i, entry))
    if all_errors:
        raise HTTPException(422, detail={"errors": all_errors})
    created: list[int] = []
    for _i, entry in validated:
        await _ensure_location(db, entry.location_id)
        record = VehicleEntry(
            **entry.model_dump(),
            vrn_normalized=normalize_vrn(entry.vrn),
            source="manual",
            created_by=user.id,
        )
        db.add(record)
        await db.flush()
        created.append(record.id)
    await db.commit()
    await record_audit(db, user, "create_bulk", "entry", f"{len(created)} rows", after={"count": len(created)})
    return {"created": created}


@router.patch("/{entry_id}")
async def patch_entry(
    entry_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
) -> dict:
    record = await db.get(VehicleEntry, entry_id)
    if record is None:
        raise HTTPException(404, detail="entry_not_found")
    merged = {
        "location_id": payload.get("location_id", record.location_id),
        "sr_no": payload.get("sr_no", record.sr_no),
        "vrn": payload.get("vrn", record.vrn),
        "model": payload.get("model", record.model),
        "entry_date": payload.get("entry_date", record.entry_date),
        "in_time": payload.get("in_time", record.in_time),
        "out_date": payload.get("out_date", record.out_date),
        "out_time": payload.get("out_time", record.out_time),
        "status": payload.get("status", record.status),
        "remarks": payload.get("remarks", record.remarks),
    }
    entry = _validated_or_422(merged)
    await _ensure_location(db, entry.location_id)
    before = serialize_entry(record)
    for field, value in entry.model_dump().items():
        setattr(record, field, value)
    record.vrn_normalized = normalize_vrn(entry.vrn)
    await db.commit()
    await db.refresh(record)
    await record_audit(db, user, "update", "entry", record.id, before=before, after=serialize_entry(record))
    return serialize_entry(record)


@router.delete("/{entry_id}")
async def delete_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> dict:
    record = await db.get(VehicleEntry, entry_id)
    if record is None:
        raise HTTPException(404, detail="entry_not_found")
    before = serialize_entry(record)
    await db.delete(record)
    await db.commit()
    await record_audit(db, user, "delete", "entry", entry_id, before=before)
    return {"ok": True}
