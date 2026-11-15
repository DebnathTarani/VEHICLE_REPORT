import asyncio
import logging
import smtplib
from datetime import date
from email.message import EmailMessage

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.config import get_settings
from app.db import async_session_maker
from app.models import SettingKV, VehicleEntry
from app.security import decrypt_secret, encrypt_secret
from app.services import reporting

logger = logging.getLogger(__name__)

EMAIL_KEY = "email_settings"
GENERAL_KEY = "general_settings"

DEFAULT_EMAIL = {
    "enabled": False,
    "recipients": [],
    "schedule_time": None,
    "smtp": {"host": None, "port": 587, "username": None, "use_tls": True, "from_address": None},
}
DEFAULT_GENERAL = {"display_date_format": "DD-MM-YYYY", "rc_lookup_enabled": False}

_scheduler: AsyncIOScheduler | None = None


async def get_setting(db, key: str, default: dict) -> dict:
    row = await db.get(SettingKV, key)
    value = dict(default)
    if row and isinstance(row.value, dict):
        value.update(row.value)
    return value


async def set_setting(db, key: str, value: dict) -> None:
    row = await db.get(SettingKV, key)
    if row is None:
        db.add(SettingKV(key=key, value=value))
    else:
        row.value = value
    await db.commit()


async def load_email_config(db) -> dict:
    cfg = await get_setting(db, EMAIL_KEY, DEFAULT_EMAIL)
    smtp = dict(cfg.get("smtp") or {})
    smtp["password"] = decrypt_secret(smtp.pop("password_enc", None))
    cfg["smtp"] = smtp
    return cfg


async def store_email_config(db, incoming: dict, keep_password_from: str | None = None) -> None:
    stored = await get_setting(db, EMAIL_KEY, DEFAULT_EMAIL)
    smtp = dict(incoming.get("smtp") or {})
    password = smtp.pop("password", None) or keep_password_from
    stored_smtp = dict(stored.get("smtp") or {})
    stored_smtp.update(smtp)
    if password:
        stored_smtp["password_enc"] = encrypt_secret(password)
    stored.update(
        {
            "enabled": bool(incoming.get("enabled")),
            "recipients": [r.strip() for r in incoming.get("recipients") or [] if r.strip()],
            "schedule_time": incoming.get("schedule_time"),
            "smtp": stored_smtp,
        }
    )
    await set_setting(db, EMAIL_KEY, stored)


def _send_blocking(cfg: dict, subject: str, body: str, attachment: bytes | None, filename: str) -> None:
    smtp_cfg = cfg["smtp"]
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_cfg.get("from_address") or smtp_cfg.get("username") or "vehicle-report@localhost"
    msg["To"] = ", ".join(cfg["recipients"])
    msg.set_content(body)
    if attachment:
        msg.add_attachment(
            attachment,
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename,
        )
    with smtplib.SMTP(smtp_cfg["host"], int(smtp_cfg.get("port", 587)), timeout=get_settings().smtp_timeout_seconds) as server:
        if smtp_cfg.get("use_tls", True):
            server.starttls()
        if smtp_cfg.get("username"):
            server.login(smtp_cfg["username"], smtp_cfg.get("password") or "")
        server.send_message(msg)


async def send_email(cfg: dict, subject: str, body: str, attachment: bytes | None = None, filename: str = "report.xlsx") -> tuple[bool, str]:
    if not cfg.get("enabled"):
        return False, "email is disabled in settings"
    if not cfg.get("recipients"):
        return False, "no recipients configured"
    smtp = cfg.get("smtp") or {}
    if not smtp.get("host"):
        return False, "SMTP host not configured"
    try:
        await asyncio.to_thread(_send_blocking, cfg, subject, body, attachment, filename)
        return True, f"sent to {len(cfg['recipients'])} recipient(s)"
    except Exception as exc:  # pragma: no cover - network
        logger.exception("email send failed")
        return False, str(exc)


async def build_daily_report(date_str: str | None = None) -> tuple[bytes, str, str] | None:
    """Returns (workbook_bytes, filename, display_date) or None when no entries."""
    async with async_session_maker() as db:
        target = date.fromisoformat(date_str) if date_str else date.today()
        stmt = (
            select(VehicleEntry)
            .where(VehicleEntry.entry_date == target)
            .order_by(VehicleEntry.location_id, VehicleEntry.sr_no)
        )
        entries = list((await db.execute(stmt)).scalars().all())
        if not entries:
            return None
        display = target.strftime("%d-%m-%Y")
        wb = reporting.build_workbook(entries, title=f"Report {display}")
        return wb, f"vehicle_report_{display}.xlsx", display


async def send_daily_report(date_str: str | None = None) -> tuple[bool, str]:
    async with async_session_maker() as db:
        cfg = await load_email_config(db)
    result = await build_daily_report(date_str)
    if result is None:
        return False, "no entries for this date"
    wb, filename, display = result
    return await send_email(
        cfg,
        subject=f"Vehicle Report - {display}",
        body=f"Hi,\n\nPlease find attached the vehicle report for {display}.\n\nRegards,\nVehicle Report System",
        attachment=wb,
        filename=filename,
    )


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
        _scheduler.start()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


async def reschedule_email_job() -> None:
    if _scheduler is None:
        return

    async with async_session_maker() as db:
        cfg = await load_email_config(db)
    sched = cfg.get("schedule_time")
    if cfg.get("enabled") and sched and ":" in sched:
        hour, minute = (int(x) for x in sched.split(":")[:2])
        _scheduler.add_job(
            send_daily_report,
            CronTrigger(hour=hour, minute=minute),
            id="daily-email",
            replace_existing=True,
        )
    elif _scheduler.get_job("daily-email"):
        _scheduler.remove_job("daily-email")
