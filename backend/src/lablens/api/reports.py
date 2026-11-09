"""Owner-scoped report upload, review, and deletion endpoints."""

import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lablens.api.schemas import (
    LabResultInput,
    LabResultResponse,
    LabResultUpdate,
    ReportResponse,
)
from lablens.core.config import get_settings
from lablens.db.models import AuditEvent, LabResult, ProcessingJob, Report, User
from lablens.db.session import get_session
from lablens.domain.ranges import NumericRangeComparison, compare_to_reference_range
from lablens.security.identity import get_current_user
from lablens.services.redis import get_redis
from lablens.services.storage import ObjectStorage, get_storage

router = APIRouter()
RANGE_RULE_VERSION = "range-v1"


def _report_response(report: Report) -> ReportResponse:
    return ReportResponse(
        id=str(report.id),
        status=report.status,
        media_type=report.media_type,
        byte_size=report.byte_size,
        page_count=report.page_count,
        created_at=report.created_at.isoformat(),
    )


def _result_response(result: LabResult) -> LabResultResponse:
    return LabResultResponse(
        id=str(result.id),
        test_name=result.test_name,
        value_text=result.value_text,
        numeric_value=result.numeric_value,
        unit=result.unit,
        reference_low=result.reference_low,
        reference_high=result.reference_high,
        reference_text=result.reference_text,
        lab_flag=result.lab_flag,
        page_number=result.page_number,
        review_status=result.review_status,
        range_status=result.range_status,
    )


async def _owned_report(report_id: UUID, owner: User, session: AsyncSession) -> Report:
    result = await session.execute(
        select(Report).where(
            Report.id == report_id,
            Report.owner_id == owner.id,
            Report.deleted_at.is_(None),
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


async def _check_upload_quota(owner: User, redis: Redis) -> None:
    settings = get_settings()
    key = f"lablens:upload-rate:{owner.id}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 3600)
    if count > settings.upload_limit_per_hour:
        raise HTTPException(status_code=429, detail="Upload limit reached; try again later")


def _detect_upload(data: bytes) -> tuple[str, str]:
    if data[:1024].find(b"%PDF-") >= 0:
        return "application/pdf", "pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    raise HTTPException(status_code=415, detail="Upload must be a PDF, PNG, or JPEG report")


@router.post("/reports", status_code=status.HTTP_202_ACCEPTED, response_model=ReportResponse)
async def upload_report(
    file: UploadFile = File(...),
    owner: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    storage: ObjectStorage = Depends(get_storage),
) -> ReportResponse:
    """Store a bounded private report and create a durable processing job."""
    await _check_upload_quota(owner, redis)
    settings = get_settings()
    if file.size is not None and file.size > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Report exceeds the upload size limit")
    try:
        content = await file.read(settings.max_upload_bytes + 1)
    finally:
        await file.close()
    if not content:
        raise HTTPException(status_code=400, detail="Report file is empty")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Report exceeds the upload size limit")
    media_type, extension = _detect_upload(content)

    report_id = uuid4()
    storage_key = f"{report_id.hex}.{extension}"
    await storage.put(storage_key, content, media_type)
    report = Report(
        id=report_id,
        owner_id=owner.id,
        storage_key=storage_key,
        media_type=media_type,
        byte_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        status="queued",
    )
    session.add(report)
    session.add(ProcessingJob(report_id=report_id, kind="inspect_report", status="queued"))
    session.add(AuditEvent(user_id=owner.id, action="report_uploaded", resource_id=report_id))
    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        await storage.delete(storage_key)
        raise HTTPException(status_code=503, detail="Report could not be saved") from exc
    await session.refresh(report)
    return _report_response(report)


@router.get("/reports", response_model=list[ReportResponse])
async def list_reports(
    owner: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[ReportResponse]:
    reports = await session.scalars(
        select(Report)
        .where(Report.owner_id == owner.id, Report.deleted_at.is_(None))
        .order_by(Report.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [_report_response(report) for report in reports]


@router.get("/reports/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: UUID,
    owner: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ReportResponse:
    return _report_response(await _owned_report(report_id, owner, session))


@router.get("/reports/{report_id}/document")
async def download_report(
    report_id: UUID,
    owner: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    storage: ObjectStorage = Depends(get_storage),
) -> Response:
    report = await _owned_report(report_id, owner, session)
    content = await storage.get(report.storage_key)
    session.add(AuditEvent(user_id=owner.id, action="report_downloaded", resource_id=report.id))
    await session.commit()
    suffix = "pdf" if report.media_type == "application/pdf" else "image"
    return Response(
        content=content,
        media_type=report.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="report-{report.id}.{suffix}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/reports/{report_id}", status_code=status.HTTP_202_ACCEPTED)
async def delete_report(
    report_id: UUID,
    owner: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    report = await _owned_report(report_id, owner, session)
    report.deleted_at = datetime.now(UTC)
    report.status = "deleting"
    session.add(ProcessingJob(report_id=report.id, kind="delete_report", status="queued"))
    session.add(
        AuditEvent(user_id=owner.id, action="report_deletion_requested", resource_id=report.id)
    )
    await session.commit()
    return {"status": "deletion_queued"}


@router.post("/reports/{report_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_report_processing(
    report_id: UUID,
    owner: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    report = await _owned_report(report_id, owner, session)
    if report.status != "processing_failed":
        raise HTTPException(status_code=409, detail="Report processing has not failed")
    job = await session.scalar(
        select(ProcessingJob).where(
            ProcessingJob.report_id == report.id,
            ProcessingJob.kind == "inspect_report",
        )
    )
    if job is None:
        raise HTTPException(status_code=409, detail="Processing job was not found")
    job.status = "queued"
    job.attempts = 0
    job.error_code = None
    report.status = "queued"
    session.add(
        AuditEvent(user_id=owner.id, action="report_processing_retried", resource_id=report.id)
    )
    await session.commit()
    return {"status": "queued"}


@router.post(
    "/reports/{report_id}/results",
    status_code=status.HTTP_201_CREATED,
    response_model=LabResultResponse,
)
async def add_result(
    report_id: UUID,
    payload: LabResultInput,
    owner: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LabResultResponse:
    report = await _owned_report(report_id, owner, session)
    if report.status != "awaiting_review":
        raise HTTPException(status_code=409, detail="Report is not ready for result review")
    result = LabResult(report_id=report.id, **payload.model_dump())
    session.add(result)
    session.add(AuditEvent(user_id=owner.id, action="result_added", resource_id=report.id))
    await session.commit()
    await session.refresh(result)
    return _result_response(result)


@router.get("/reports/{report_id}/results", response_model=list[LabResultResponse])
async def list_results(
    report_id: UUID,
    owner: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[LabResultResponse]:
    report = await _owned_report(report_id, owner, session)
    results = await session.scalars(
        select(LabResult).where(LabResult.report_id == report.id).order_by(LabResult.created_at)
    )
    return [_result_response(result) for result in results]


@router.patch("/reports/{report_id}/results/{result_id}", response_model=LabResultResponse)
async def update_result(
    report_id: UUID,
    result_id: UUID,
    payload: LabResultUpdate,
    owner: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LabResultResponse:
    report = await _owned_report(report_id, owner, session)
    result_query = await session.execute(
        select(LabResult).where(LabResult.id == result_id, LabResult.report_id == report.id)
    )
    result = result_query.scalar_one_or_none()
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    values = {
        key: getattr(result, key)
        for key in (
            "test_name",
            "value_text",
            "numeric_value",
            "unit",
            "reference_low",
            "reference_high",
            "reference_text",
            "lab_flag",
            "page_number",
        )
    }
    values.update(payload.model_dump(exclude_unset=True))
    validated = LabResultInput.model_validate(values)
    for key, value in validated.model_dump().items():
        setattr(result, key, value)
    result.review_status = "needs_review"
    result.range_status = None
    result.rule_version = None
    session.add(AuditEvent(user_id=owner.id, action="result_corrected", resource_id=report.id))
    await session.commit()
    await session.refresh(result)
    return _result_response(result)


@router.post(
    "/reports/{report_id}/results/{result_id}/confirm",
    response_model=LabResultResponse,
)
async def confirm_result(
    report_id: UUID,
    result_id: UUID,
    owner: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LabResultResponse:
    report = await _owned_report(report_id, owner, session)
    result_query = await session.execute(
        select(LabResult).where(LabResult.id == result_id, LabResult.report_id == report.id)
    )
    result = result_query.scalar_one_or_none()
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    result.review_status = "confirmed"
    comparison = None
    if (
        result.numeric_value is not None
        and result.reference_low is not None
        and result.reference_high is not None
    ):
        comparison = NumericRangeComparison(
            value=result.numeric_value,
            low=result.reference_low,
            high=result.reference_high,
        )
    result.range_status = compare_to_reference_range(comparison).value
    result.rule_version = RANGE_RULE_VERSION
    session.add(AuditEvent(user_id=owner.id, action="result_confirmed", resource_id=report.id))
    await session.commit()
    await session.refresh(result)
    return _result_response(result)
