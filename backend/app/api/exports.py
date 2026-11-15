import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.entries import query_entries
from app.deps import get_current_user, get_db, require_admin
from app.models import User
from app.services import email as email_svc
from app.services.dates import parse_date_loose
from app.services.reporting import build_workbook

router = APIRouter(prefix="/exports", tags=["exports"])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/entries.xlsx")
async def export_entries_xlsx(
    location_id: int | None = Query(None),
    status: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    q: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> StreamingResponse:
    df = parse_date_loose(date_from) if date_from else None
    dt = parse_date_loose(date_to) if date_to else None
    rows, total = await query_entries(
        db,
        location_id=location_id,
        status=status,
        date_from=df,
        date_to=dt,
        q=q,
        limit=10000,
    )
    if total > 10000:
        raise HTTPException(400, detail="too many rows; narrow the filters")
    data = build_workbook(rows)
    stamp = date.today().strftime("%d-%m-%Y")
    filename = f"vehicle_report_{stamp}.xlsx"
    return StreamingResponse(
        io.BytesIO(data),
        media_type=XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class EmailReportIn(BaseModel):
    date: str | None = None


@router.post("/email-report", dependencies=[Depends(require_admin)])
async def email_report(body: EmailReportIn | None = None) -> dict:
    ok, message = await email_svc.send_daily_report(body.date if body else None)
    return {"ok": ok, "message": message}
