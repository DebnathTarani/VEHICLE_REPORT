import base64
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.deps import get_current_user, get_db, require_admin
from app.models import LlmProvider, User
from app.schemas import ProviderCreateIn, ProviderOut, ProviderPatchIn
from app.security import decrypt_secret, encrypt_secret
from app.services.extraction import provider_spec
from app.services.providers import gemini as gemini_client
from app.services.providers import openai_compat as openai_client
from app.services.providers.base import ExtractionError

router = APIRouter(prefix="/settings/providers", tags=["settings-providers"])

# 1x1 transparent PNG used for the vision capability probe
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


async def _out(db: AsyncSession, p: LlmProvider) -> dict:
    return ProviderOut.from_model(p, decrypt_secret(p.api_key_enc)).model_dump()


@router.get("", dependencies=[Depends(require_admin)])
async def list_providers(db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (await db.execute(select(LlmProvider).order_by(LlmProvider.name))).scalars().all()
    return [await _out(db, p) for p in rows]


@router.post("", dependencies=[Depends(require_admin)])
async def create_provider(
    body: ProviderCreateIn, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_user)
) -> dict:
    dup = (
        await db.execute(select(LlmProvider).where(LlmProvider.name == body.name))
    ).scalar_one_or_none()
    if dup:
        raise HTTPException(409, detail="provider_name_taken")
    count = (await db.execute(select(LlmProvider.id))).scalars().all()
    provider = LlmProvider(
        name=body.name.strip(),
        kind=body.kind,
        base_url=body.base_url or None,
        api_key_enc=encrypt_secret(body.api_key) if body.api_key else None,
        default_model=body.default_model.strip(),
        is_default=len(count) == 0,
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    await record_audit(db, admin, "create", "provider", provider.id, after={"name": provider.name, "kind": provider.kind})
    return await _out(db, provider)


@router.patch("/{provider_id}", dependencies=[Depends(require_admin)])
async def patch_provider(
    provider_id: int,
    body: ProviderPatchIn,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_user),
) -> dict:
    p = await db.get(LlmProvider, provider_id)
    if p is None:
        raise HTTPException(404, detail="provider_not_found")
    data = body.model_dump(exclude_unset=True)
    if "api_key" in data:
        key = data.pop("api_key")
        p.api_key_enc = encrypt_secret(key) if key else None
    for field in ("name", "kind", "base_url", "default_model", "enabled", "supports_guided_json", "disable_thinking"):
        if field in data:
            setattr(p, field, data[field])
    await db.commit()
    await db.refresh(p)
    await record_audit(db, admin, "update", "provider", p.id, after={"fields": sorted(data.keys())})
    return await _out(db, p)


@router.delete("/{provider_id}", dependencies=[Depends(require_admin)])
async def delete_provider(
    provider_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_user)
) -> dict:
    p = await db.get(LlmProvider, provider_id)
    if p is None:
        raise HTTPException(404, detail="provider_not_found")
    was_default = p.is_default
    await db.delete(p)
    await db.commit()
    if was_default:
        nxt = (
            await db.execute(select(LlmProvider).order_by(LlmProvider.id))
        ).scalars().first()
        if nxt:
            nxt.is_default = True
            await db.commit()
    await record_audit(db, admin, "delete", "provider", provider_id)
    return {"ok": True}


@router.post("/{provider_id}/default", dependencies=[Depends(require_admin)])
async def set_default(
    provider_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_user)
) -> dict:
    p = await db.get(LlmProvider, provider_id)
    if p is None:
        raise HTTPException(404, detail="provider_not_found")
    if not p.enabled:
        raise HTTPException(400, detail="provider_disabled")
    await db.execute(update(LlmProvider).values(is_default=False))
    p.is_default = True
    await db.commit()
    await record_audit(db, admin, "set_default", "provider", p.id)
    return {"ok": True}


@router.post("/{provider_id}/test", dependencies=[Depends(require_admin)])
async def test_provider(
    provider_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_user)
) -> dict:
    p = await db.get(LlmProvider, provider_id)
    if p is None:
        raise HTTPException(404, detail="provider_not_found")
    spec = provider_spec(p)
    client = gemini_client if spec.kind == "gemini" else openai_client
    models: list[str] = []
    message = "ok"
    ok = True
    vision = p.vision_status
    try:
        models = (await client.list_models(spec))[:100]
    except Exception as exc:  # network/provider errors are a normal outcome
        ok = False
        message = str(exc)[:400]
    if ok:
        try:
            await client.chat_with_image(spec, "Reply with exactly OK", _TINY_PNG, "image/png", None)
            vision = "supported"
        except ExtractionError as exc:
            text = str(exc).lower()
            if any(k in text for k in ("image", "vision", "modality", "multimodal")):
                vision = "unsupported"
            else:
                vision = "unknown"
                message = f"models ok, vision probe failed: {str(exc)[:200]}"
        except Exception as exc:
            vision = "unknown"
            message = f"models ok, vision probe failed: {str(exc)[:200]}"
    p.last_test = {"ok": ok, "message": message, "at": datetime.now(UTC).isoformat()}
    p.vision_status = vision
    await db.commit()
    return {"ok": ok, "message": message, "models": models, "vision": vision}
