from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.enums import Role
from app.models import Session as SessionModel
from app.models import User
from app.security import hash_token
from app.services.dates import utcnow_naive


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    vr_session: str | None = Cookie(None),
) -> User:
    if not vr_session:
        raise HTTPException(401, detail="not_authenticated")
    result = await db.execute(
        select(SessionModel, User)
        .join(User, User.id == SessionModel.user_id)
        .where(SessionModel.token_hash == hash_token(vr_session))
    )
    pair = result.first()
    if not pair:
        raise HTTPException(401, detail="not_authenticated")
    session_row, user = pair
    expires = session_row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires < datetime.now(UTC) or not user.is_active:
        raise HTTPException(401, detail="not_authenticated")
    await db.execute(
        update(SessionModel)
        .where(SessionModel.id == session_row.id)
        .values(last_seen_at=utcnow_naive())
    )
    await db.commit()
    request.state.user = user
    return user


def require_roles(*roles: Role):
    async def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in {r.value for r in roles}:
            raise HTTPException(403, detail="insufficient_role")
        return user

    return dep


require_operator = require_roles(Role.admin, Role.operator)
require_admin = require_roles(Role.admin)


async def require_csrf(
    request: Request,
    x_csrf_token: str | None = Header(None),
    vr_csrf: str | None = Cookie(None),
) -> None:
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if not x_csrf_token or not vr_csrf or x_csrf_token != vr_csrf:
        raise HTTPException(403, detail="csrf_failed")
