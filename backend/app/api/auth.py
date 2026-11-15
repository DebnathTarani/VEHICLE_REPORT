
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.config import get_settings
from app.deps import get_current_user, get_db
from app.models import Session as SessionModel
from app.models import User
from app.schemas import ChangePasswordIn, LoginIn, UserOut
from app.security import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    generate_token,
    hash_password,
    hash_token,
    session_expiry,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/csrf")
async def get_csrf(response: Response) -> dict:
    token = generate_token()
    response.set_cookie(
        CSRF_COOKIE, token, httponly=False, samesite="lax", secure=get_settings().app_env == "prod"
    )
    return {"csrf_token": token}


@router.post("/login")
async def login(body: LoginIn, response: Response, db: AsyncSession = Depends(get_db)) -> UserOut:
    user = (
        await db.execute(select(User).where(User.username == body.username))
    ).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, detail="invalid_credentials")
    token = generate_token()
    db.add(SessionModel(user_id=user.id, token_hash=hash_token(token), expires_at=session_expiry()))
    await db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=get_settings().app_env == "prod",
        max_age=get_settings().session_ttl_hours * 3600,
    )
    return UserOut.model_validate(user)


@router.post("/logout")
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    await db.execute(delete(SessionModel).where(SessionModel.user_id == user.id))
    await db.commit()
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/change-password")
async def change_password(
    body: ChangePasswordIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, detail="current_password_incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(400, detail="password_too_short")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    await db.commit()
    await record_audit(db, user, "change_password", "user", user.id)
    return {"ok": True}
