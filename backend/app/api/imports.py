import os
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit
from app.config import get_settings
from app.deps import get_current_user, get_db, require_operator
from app.models import ImportImage, ImportJob, ImportRow, LlmProvider, Location, User, VehicleEntry
from app.schemas import (
    CommitIn,
    ImportJobDetailOut,
    ImportJobSummaryOut,
    ImportRowOut,
    RowPatchIn,
    validate_entry_payload,
)
from app.services.jobs import enqueue_job
from app.services.providers.base import image_mime
from app.services.vrn import normalize_vrn

ALLOWED_MIMES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"}

router = APIRouter(prefix="/imports", tags=["imports"])


def _is_real_image(data: bytes) -> bool:
    import io as _io

    try:
        from PIL import Image

        img = Image.open(_io.BytesIO(data))
        img.verify()
        return (img.format or "").upper() in {"PNG", "JPEG", "GIF", "WEBP", "BMP"}
    except Exception:
        return False


@router.post("")
async def create_import(
    files: Annotated[list[UploadFile], File()],
    provider_id: Annotated[int | None, Form()] = None,
    location_id: Annotated[int | None, Form()] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
) -> dict:
    settings = get_settings()
    if not files or len(files) > settings.max_upload_files:
        raise HTTPException(422, detail=f"upload 1-{settings.max_upload_files} images")

    location = None
    if location_id is not None:
        location = await db.get(Location, location_id)
        if location is None or not location.is_active:
            raise HTTPException(422, detail={"location_id": "unknown location"})
    else:
        actives = (
            (await db.execute(select(Location).where(Location.is_active.is_(True))))
            .scalars()
            .all()
        )
        if len(actives) == 1:
            location = actives[0]
        else:
            raise HTTPException(422, detail={"location_id": "location_required"})

    provider: LlmProvider | None = None
    if provider_id is not None:
        provider = await db.get(LlmProvider, provider_id)
        if provider is None or not provider.enabled:
            raise HTTPException(422, detail={"provider_id": "unknown or disabled provider"})
    else:
        provider = (
            await db.execute(
                select(LlmProvider).where(
                    LlmProvider.enabled.is_(True), LlmProvider.is_default.is_(True)
                )
            )
        ).scalar_one_or_none()
    if provider is None:
        raise HTTPException(422, detail={"provider_id": "no_enabled_provider"})

    job = ImportJob(
        created_by=user.id,
        provider_id=provider.id,
        location_id=location.id if location else None,
        status="queued",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    target_dir = os.path.join(settings.import_dir, f"job_{job.id}")
    os.makedirs(target_dir, exist_ok=True)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    for i, upload in enumerate(files):
        data = await upload.read()
        if not data:
            raise HTTPException(422, detail={"files": f"{upload.filename} is empty"})
        if len(data) > max_bytes:
            raise HTTPException(422, detail={"files": f"{upload.filename} exceeds {settings.max_upload_mb}MB"})
        if not _is_real_image(data):
            raise HTTPException(422, detail={"files": f"{upload.filename} is not a supported image"})
        safe_name = os.path.basename(upload.filename or f"image_{i}")
        path = os.path.join(target_dir, f"{i}_{safe_name}")
        with open(path, "wb") as fh:
            fh.write(data)
        db.add(ImportImage(job_id=job.id, filename=safe_name, storage_path=path))
    await db.commit()
    await record_audit(db, user, "create", "import_job", job.id, after={"images": len(files)})
    enqueue_job(job.id)
    return {"job_id": job.id}


@router.get("")
async def list_imports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    jobs = (
        (
            await db.execute(
                select(ImportJob).order_by(ImportJob.id.desc()).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .unique()
        .scalars()
        .all()
    )
    total = (await db.execute(select(ImportJob.id))).scalars().all()
    return {
        "items": [ImportJobSummaryOut.from_model(j).model_dump() for j in jobs],
        "total": len(total),
        "page": page,
        "page_size": page_size,
    }


async def _get_job(db: AsyncSession, job_id: int) -> ImportJob:
    job = await db.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(404, detail="job_not_found")
    return job


@router.get("/{job_id}")
async def get_import(job_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    job = await _get_job(db, job_id)
    return ImportJobDetailOut.from_model(job).model_dump()


@router.get("/{job_id}/images/{image_id}/file")
async def get_image_file(job_id: int, image_id: int, db: AsyncSession = Depends(get_db)) -> FileResponse:
    img = await db.get(ImportImage, image_id)
    if img is None or img.job_id != job_id:
        raise HTTPException(404, detail="image_not_found")
    if not os.path.exists(img.storage_path):
        raise HTTPException(410, detail="image_file_gone")
    with open(img.storage_path, "rb") as fh:
        mime = image_mime(fh.read(16))
    return FileResponse(img.storage_path, media_type=mime)


async def _get_row(db: AsyncSession, row_id: int) -> ImportRow:
    row = await db.get(ImportRow, row_id)
    if row is None:
        raise HTTPException(404, detail="row_not_found")
    return row


@router.patch("/rows/{row_id}")
async def patch_row(
    row_id: int,
    body: RowPatchIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
) -> dict:
    row = await _get_row(db, row_id)
    if row.status == "committed":
        raise HTTPException(409, detail="row_already_committed")
    if body.payload is not None:
        entry, errors = validate_entry_payload(body.payload)
        if entry is None:
            raise HTTPException(422, detail={"errors": errors})
        merged = {**body.payload}
        if "location_id" not in merged or not merged["location_id"]:
            img = await db.get(ImportImage, row.image_id)
            job = await db.get(ImportJob, img.job_id)
            merged["location_id"] = job.location_id
        _, errors2 = validate_entry_payload(merged)
        if errors2:
            raise HTTPException(422, detail={"errors": errors2})
        for field, value in merged.items():
            if row.payload.get(field) != value:
                if field not in row.edited_fields:
                    row.edited_fields = (row.edited_fields or []) + [field]
        row.payload = merged
    if body.status is not None:
        if body.status == "accepted":
            entry, errors = validate_entry_payload(row.payload)
            if entry is None:
                raise HTTPException(422, detail={"errors": errors})
        row.status = body.status
    await db.commit()
    await record_audit(db, user, "review", "import_row", row.id, after={"status": row.status})
    return ImportRowOut.from_model(row).model_dump()


@router.post("/rows/{row_id}/reject")
async def reject_row(
    row_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_operator)
) -> dict:
    row = await _get_row(db, row_id)
    if row.status == "committed":
        raise HTTPException(409, detail="row_already_committed")
    row.status = "rejected"
    await db.commit()
    await record_audit(db, user, "reject", "import_row", row.id)
    return {"id": row.id, "status": row.status}


@router.post("/{job_id}/commit")
async def commit_rows(
    job_id: int,
    body: CommitIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
) -> dict:
    job = await _get_job(db, job_id)
    stmt = (
        select(ImportRow)
        .join(ImportImage, ImportImage.id == ImportRow.image_id)
        .where(ImportImage.job_id == job.id, ImportRow.status == "accepted")
    )
    if body.row_ids:
        stmt = stmt.where(ImportRow.id.in_(body.row_ids))
    rows = (await db.execute(stmt)).scalars().all()
    if body.row_ids:
        requested = set(body.row_ids)
        found = {r.id for r in rows}
        if requested - found:
            raise HTTPException(400, detail=f"rows not accepted: {sorted(requested - found)}")
    if not rows:
        return {"committed": 0, "entry_ids": []}

    entry_ids: list[int] = []
    errors: dict[str, str] = {}
    for row in rows:
        payload = dict(row.payload or {})
        if not payload.get("location_id"):
            payload["location_id"] = job.location_id
        entry, errs = validate_entry_payload(payload)
        if entry is None:
            errors[str(row.id)] = "; ".join(f"{k}: {v}" for k, v in errs.items())
            continue
        record = VehicleEntry(
            **entry.model_dump(),
            vrn_normalized=normalize_vrn(entry.vrn),
            source="ai_import",
            import_row_id=row.id,
            created_by=user.id,
        )
        db.add(record)
        await db.flush()
        row.status = "committed"
        row.committed_entry_id = record.id
        entry_ids.append(record.id)
    if errors:
        await db.rollback()
        raise HTTPException(400, detail={"invalid_rows": errors})
    await db.commit()
    await record_audit(
        db, user, "commit_import", "import_job", job.id, after={"committed": len(entry_ids)}
    )
    return {"committed": len(entry_ids), "entry_ids": entry_ids}


@router.post("/{job_id}/images/{image_id}/retry")
async def retry_image(
    job_id: int,
    image_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
) -> dict:
    job = await _get_job(db, job_id)
    img = await db.get(ImportImage, image_id)
    if img is None or img.job_id != job.id:
        raise HTTPException(404, detail="image_not_found")
    img.status = "queued"
    img.error = None
    job.status = "queued"
    job.error = None
    await db.commit()
    await record_audit(db, user, "retry", "import_image", img.id)
    enqueue_job(job.id, image_ids=[img.id])
    return {"job_id": job.id}
