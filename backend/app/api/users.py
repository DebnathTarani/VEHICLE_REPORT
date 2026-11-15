from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.deps import get_current_user, get_db, require_admin
from app.models import User
from app.schemas import UserCreateIn, UserOut, UserPatchIn
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", dependencies=[Depends(require_admin)])
async def list_users(db: AsyncSession = Depends(get_db)) -> list[UserOut]:
    rows = (await db.execute(select(User).order_by(User.username))).scalars().all()
    return [UserOut.model_validate(u) for u in rows]


@router.post("", dependencies=[Depends(require_admin)])
async def create_user(
    body: UserCreateIn, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_user)
) -> UserOut:
    exists = (
        await db.execute(select(User).where(User.username == body.username))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(409, detail="username_taken")
    user = User(
        username=body.username.strip(),
        display_name=body.display_name.strip() or body.username.strip(),
        role=body.role,
        location_id=body.location_id,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await record_audit(db, admin, "create", "user", user.id, after={"username": user.username, "role": user.role})
    return UserOut.model_validate(user)


@router.patch("/{user_id}", dependencies=[Depends(require_admin)])
async def patch_user(
    user_id: int,
    body: UserPatchIn,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_user),
) -> UserOut:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, detail="user_not_found")
    data = body.model_dump(exclude_unset=True)
    if body.password:
        user.password_hash = hash_password(data.pop("password"))
    if data.get("role") or data.get("is_active") is False:
        new_role = data.get("role", user.role)
        new_active = data.get("is_active", user.is_active)
        if user.role == "admin" and (new_role != "admin" or not new_active):
            admins = (
                await db.execute(
                    select(User).where(User.role == "admin", User.is_active.is_(True))
                )
            ).scalars().all()
            if len([a for a in admins if a.id != user.id]) == 0:
                raise HTTPException(400, detail="cannot_remove_last_admin")
    before = {"role": user.role, "is_active": user.is_active, "location_id": user.location_id}
    for field in ("display_name", "role", "location_id", "is_active"):
        if field in data:
            setattr(user, field, data[field])
    await db.commit()
    await db.refresh(user)
    await record_audit(db, admin, "update", "user", user.id, before=before,
                       after={"role": user.role, "is_active": user.is_active, "location_id": user.location_id})
    return UserOut.model_validate(user)
