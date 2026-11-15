from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models import User
from app.services import email as email_svc
from app.services import rc as rc_svc
from app.services.vrn import normalize_vrn

router = APIRouter(prefix="/rc", tags=["rc"])


@router.get("/{raw_vrn}")
async def rc_lookup(
    raw_vrn: str, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
) -> dict:
    general = await email_svc.get_setting(db, email_svc.GENERAL_KEY, email_svc.DEFAULT_GENERAL)
    if not general.get("rc_lookup_enabled"):
        return {"status": "disabled", "message": "RC lookup is disabled in Settings"}
    norm = normalize_vrn(raw_vrn)
    if not norm:
        return {"status": "unavailable", "message": "invalid VRN"}
    try:
        return await rc_svc.lookup_rc(db, norm)
    except Exception as exc:  # provider network failures never break the UI
        return {"status": "unavailable", "message": str(exc)[:300]}
