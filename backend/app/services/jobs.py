import asyncio
import logging

from sqlalchemy import delete, select

from app.db import async_session_maker
from app.models import ImportImage, ImportJob, ImportRow, LlmProvider
from app.services.dates import utcnow_naive
from app.services.extraction import ExtractionError, extract_rows, provider_spec

logger = logging.getLogger(__name__)

_semaphore = asyncio.Semaphore(2)
_tasks: set[asyncio.Task] = set()


def enqueue_job(job_id: int, image_ids: list[int] | None = None) -> None:
    task = asyncio.create_task(process_job(job_id, image_ids))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def process_job(job_id: int, image_ids: list[int] | None = None) -> None:
    async with _semaphore:
        async with async_session_maker() as db:
            job = await db.get(ImportJob, job_id)
            if job is None:
                return
            provider: LlmProvider | None = None
            if job.provider_id:
                provider = await db.get(LlmProvider, job.provider_id)
            if provider is None:
                stmt = select(LlmProvider).where(
                    LlmProvider.enabled.is_(True), LlmProvider.is_default.is_(True)
                )
                provider = (await db.execute(stmt)).scalar_one_or_none()
            if provider is None or not provider.enabled:
                job.status = "failed"
                job.error = "no enabled LLM provider configured (see Settings > Providers)"
                job.finished_at = utcnow_naive()
                await db.commit()
                return

            job.status = "processing"
            job.provider_label = f"{provider.name} ({provider.default_model})"
            await db.commit()
            spec = provider_spec(provider)

            stmt = select(ImportImage).where(ImportImage.job_id == job_id)
            if image_ids:
                stmt = stmt.where(ImportImage.id.in_(image_ids))
            images = (await db.execute(stmt)).scalars().all()

            any_ok = any_failed = False
            for img in images:
                img.status = "processing"
                img.error = None
                await db.commit()
                try:
                    with open(img.storage_path, "rb") as fh:
                        data = fh.read()
                    result = await extract_rows(spec, data, location_id=job.location_id)
                    await db.execute(delete(ImportRow).where(ImportRow.image_id == img.id))
                    for payload, conf in zip(result.rows, result.confidences, strict=False):
                        db.add(
                            ImportRow(
                                image_id=img.id,
                                payload=payload,
                                confidence=conf,
                                status="pending_review",
                            )
                        )
                    img.status = "extracted"
                    img.provider = result.provider
                    img.model = result.model
                    img.ocr_available = result.ocr_available
                    if not result.rows:
                        img.error = "no rows detected in image"
                    any_ok = True
                except (ExtractionError, OSError, Exception) as exc:  # noqa: BLE001
                    logger.exception("image extraction failed id=%s", img.id)
                    img.status = "failed"
                    img.error = str(exc)[:1000]
                    any_failed = True
                await db.commit()

            job.finished_at = utcnow_naive()
            if any_ok and any_failed:
                job.status = "partial"
            elif any_ok:
                job.status = "done"
            else:
                job.status = "failed"
            await db.commit()
