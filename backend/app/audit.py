from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, User


async def record_audit(
    db: AsyncSession,
    user: User | None,
    action: str,
    entity: str,
    entity_id: int | str,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            entity=entity,
            entity_id=str(entity_id),
            before=before,
            after=after,
        )
    )
    await db.commit()
