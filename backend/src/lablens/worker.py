"""Durable report job dispatcher and bounded document inspection worker."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import fitz
from arq import cron
from arq.connections import ArqRedis, RedisSettings
from sqlalchemy import select, update

from lablens.core.config import get_settings
from lablens.db.models import AuditEvent, ProcessingJob, Report
from lablens.db.session import SessionFactory
from lablens.services.storage import get_storage

settings = get_settings()


def _inspect_pdf(content: bytes, maximum_pages: int) -> int:
    with fitz.open(stream=content, filetype="pdf") as document:
        if document.needs_pass:
            raise ValueError("encrypted_document")
        page_count = document.page_count
    if page_count < 1 or page_count > maximum_pages:
        raise ValueError("page_limit_exceeded")
    return int(page_count)


async def dispatch_queued_jobs(context: dict[str, Any]) -> None:
    """Publish pending DB outbox rows; stable queue IDs make retries idempotent."""
    queue = context["redis"]
    if not isinstance(queue, ArqRedis):
        return
    now = datetime.now(UTC)
    async with SessionFactory() as session:
        await session.execute(
            update(ProcessingJob)
            .where(
                ProcessingJob.status == "running",
                ProcessingJob.updated_at < now - timedelta(minutes=5),
            )
            .values(status="queued", updated_at=now)
        )
        await session.commit()
        jobs = await session.scalars(
            select(ProcessingJob)
            .where(ProcessingJob.status == "queued")
            .order_by(ProcessingJob.created_at)
            .limit(100)
        )
        job_ids = [str(job.id) for job in jobs]
    for job_id in job_ids:
        await queue.enqueue_job(
            "process_report_job",
            job_id,
            _job_id=f"lablens:{job_id}",
        )


async def process_report_job(context: dict[str, Any], job_id: str) -> None:
    storage = get_storage()
    async with SessionFactory() as session:
        job = await session.scalar(
            select(ProcessingJob)
            .where(ProcessingJob.id == UUID(job_id), ProcessingJob.status == "queued")
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return
        report_id = job.report_id
        job.status = "running"
        job.attempts += 1
        await session.commit()
        report = await session.get(Report, report_id)
        if report is None:
            job.status = "complete"
            await session.commit()
            return
        if report.deleted_at is not None and job.kind != "delete_report":
            job.status = "complete"
            await session.commit()
            return

        try:
            if job.kind == "delete_report":
                await storage.delete(report.storage_key)
                session.add(
                    AuditEvent(
                        user_id=report.owner_id,
                        action="report_deleted",
                        resource_id=report.id,
                    )
                )
                await session.delete(report)
                await session.commit()
                return

            if job.kind != "inspect_report":
                raise ValueError("unsupported_job")
            content = await storage.get(report.storage_key)
            if report.media_type == "application/pdf":
                page_count = await asyncio.to_thread(_inspect_pdf, content, settings.max_pdf_pages)
            else:
                page_count = 1
            report.page_count = page_count
            # Extraction is intentionally left for human entry until a reviewed parser is selected.
            report.status = "awaiting_review"
            job.status = "complete"
            await session.commit()
        except Exception:
            await session.rollback()
            failed_job = await session.get(ProcessingJob, UUID(job_id))
            failed_report = await session.get(Report, report_id)
            if failed_job is not None:
                failed_job.status = "failed" if failed_job.attempts >= 4 else "queued"
                failed_job.error_code = "processing_failed"
            if failed_report is not None and failed_report.deleted_at is None:
                failed_report.status = "processing_failed"
            await session.commit()
            raise


class WorkerSettings:
    functions = [process_report_job]
    cron_jobs = [cron("dispatch_queued_jobs", second={0, 15, 30, 45})]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    queue_name = "lablens:reports"
    max_tries = 4
    job_timeout = 120
