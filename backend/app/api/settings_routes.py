from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.deps import get_current_user, get_db, require_admin
from app.models import User
from app.schemas import EmailSettingsIn, GeneralSettingsIn
from app.services import email as email_svc
from app.services.email import DEFAULT_GENERAL, EMAIL_KEY, GENERAL_KEY

router = APIRouter(prefix="/settings", tags=["settings"])


def _email_public(cfg: dict) -> dict:
    smtp = dict(cfg.get("smtp") or {})
    smtp.pop("password", None)
    smtp.pop("password_enc", None)
    smtp["password_set"] = bool((cfg.get("smtp") or {}).get("password") or (cfg.get("smtp") or {}).get("password_enc"))
    return {
        "enabled": bool(cfg.get("enabled")),
        "recipients": cfg.get("recipients") or [],
        "schedule_time": cfg.get("schedule_time"),
        "smtp": smtp,
    }


@router.get("/email", dependencies=[Depends(require_admin)])
async def get_email(db: AsyncSession = Depends(get_db)) -> dict:
    cfg = await email_svc.load_email_config(db)
    return _email_public(cfg)


@router.put("/email", dependencies=[Depends(require_admin)])
async def put_email(
    body: EmailSettingsIn, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_user)
) -> dict:
    current = await email_svc.load_email_config(db)
    keep = (current.get("smtp") or {}).get("password")
    incoming = body.model_dump()
    await email_svc.store_email_config(db, incoming, keep_password_from=keep)
    await email_svc.reschedule_email_job()
    await record_audit(db, admin, "update", "settings_email", EMAIL_KEY,
                       after={"enabled": body.enabled, "recipients": body.recipients,
                              "schedule_time": body.schedule_time})
    return _email_public(await email_svc.load_email_config(db))


@router.post("/email/test", dependencies=[Depends(require_admin)])
async def email_test(db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_user)) -> dict:
    cfg = await email_svc.load_email_config(db)
    ok, message = await email_svc.send_email(
        cfg, subject="Vehicle Report — test email", body="This is a test from Vehicle Report v2."
    )
    return {"ok": ok, "message": message}


@router.get("/general")
async def get_general(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    return await email_svc.get_setting(db, GENERAL_KEY, DEFAULT_GENERAL)


@router.put("/general", dependencies=[Depends(require_admin)])
async def put_general(
    body: GeneralSettingsIn, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_user)
) -> dict:
    await email_svc.set_setting(db, GENERAL_KEY, body.model_dump())
    await record_audit(db, admin, "update", "settings_general", GENERAL_KEY, after=body.model_dump())
    return await email_svc.get_setting(db, GENERAL_KEY, DEFAULT_GENERAL)
