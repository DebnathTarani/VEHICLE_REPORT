from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models import Location, User, VehicleEntry

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def summary(
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
) -> dict:
    today = date.today()
    locations = (
        (await db.execute(select(Location).where(Location.is_active.is_(True)).order_by(Location.name)))
        .scalars()
        .all()
    )
    per_location = []
    for loc in locations:
        entries_today = (
            await db.execute(
                select(func.count())
                .select_from(VehicleEntry)
                .where(VehicleEntry.location_id == loc.id, VehicleEntry.entry_date == today)
            )
        ).scalar_one()
        open_wip = (
            await db.execute(
                select(func.count())
                .select_from(VehicleEntry)
                .where(VehicleEntry.location_id == loc.id, VehicleEntry.status == "in_progress")
            )
        ).scalar_one()
        per_location.append(
            {
                "location_id": loc.id,
                "name": loc.name,
                "entries_today": entries_today,
                "open_wip": open_wip,
            }
        )

    from app.schemas import serialize_entry

    wip_rows = (
        (
            await db.execute(
                select(VehicleEntry)
                .where(VehicleEntry.status == "in_progress")
                .order_by(VehicleEntry.entry_date.asc().nullslast())
                .limit(50)
            )
        )
        .unique()
        .scalars()
        .all()
    )
    open_wip_list = [
        {**serialize_entry(e), "age_days": (today - e.entry_date).days if e.entry_date else 0}
        for e in wip_rows
    ]

    week_start = today - timedelta(days=6)
    week_counts = dict(
        (
            await db.execute(
                select(VehicleEntry.entry_date, func.count())
                .where(VehicleEntry.entry_date >= week_start, VehicleEntry.entry_date <= today)
                .group_by(VehicleEntry.entry_date)
            )
        ).all()
    )
    week_series = [
        {"date": (week_start + timedelta(days=i)).isoformat(), "count": week_counts.get(week_start + timedelta(days=i), 0)}
        for i in range(7)
    ]

    return {
        "date": today.isoformat(),
        "per_location": per_location,
        "open_wip": open_wip_list,
        "week_series": week_series,
    }
