from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.deps import get_current_user, get_db, require_admin
from app.models import Location, User
from app.schemas import LocationIn, LocationOut, LocationPatchIn

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("")
async def list_locations(
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
) -> list[LocationOut]:
    rows = (
        await db.execute(select(Location).where(Location.is_active.is_(True)).order_by(Location.name))
    ).scalars().all()
    return [LocationOut.model_validate(r) for r in rows]


@router.post("", dependencies=[Depends(require_admin)])
async def create_location(
    body: LocationIn, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_user)
) -> LocationOut:
    name = body.name.strip()
    if not name:
        raise HTTPException(422, detail="name required")
    dup = (await db.execute(select(Location).where(Location.name == name))).scalar_one_or_none()
    if dup:
        raise HTTPException(409, detail="location_exists")
    loc = Location(name=name)
    db.add(loc)
    await db.commit()
    await db.refresh(loc)
    await record_audit(db, admin, "create", "location", loc.id, after={"name": name})
    return LocationOut.model_validate(loc)


@router.patch("/{location_id}", dependencies=[Depends(require_admin)])
async def patch_location(
    location_id: int,
    body: LocationPatchIn,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_user),
) -> LocationOut:
    loc = await db.get(Location, location_id)
    if loc is None:
        raise HTTPException(404, detail="location_not_found")
    before = {"name": loc.name, "is_active": loc.is_active}
    if body.name is not None:
        loc.name = body.name.strip()
    if body.is_active is not None:
        loc.is_active = body.is_active
    await db.commit()
    await db.refresh(loc)
    await record_audit(db, admin, "update", "location", loc.id, before=before,
                       after={"name": loc.name, "is_active": loc.is_active})
    return LocationOut.model_validate(loc)
