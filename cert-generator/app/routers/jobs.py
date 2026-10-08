import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CertificateJob, CertificateRecipient
from app.schemas import JobCreateIn, JobCreateOut, JobRetryOut, JobStatusOut, RecipientOut
from app.tasks import generate_certificate_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("/", status_code=status.HTTP_202_ACCEPTED, response_model=JobCreateOut)
@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=JobCreateOut, include_in_schema=False)
def create_job(
    job_in: JobCreateIn,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    """Create a new certificate job and dispatch individual generation tasks.

    Supports an optional 'Idempotency-Key' header. If the exact same key is submitted
    within 24 hours, the existing job is returned without re-dispatching duplicate tasks.
    If the key is reused with a different request payload, returns 422.
    """
    if not job_in.recipients:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Recipients list cannot be empty.",
        )

    # Compute deterministic SHA-256 hash of the request payload
    payload_str = json.dumps(job_in.model_dump(mode="json"), sort_keys=True)
    payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    # WHY Idempotency Check:
    # Clients may retry timed-out requests or duplicate submissions.
    # Within a 24-hour window, returning the existing job ID guarantees at-most-once job creation.
    # If the same Idempotency-Key is reused with a DIFFERENT payload, we return 422 to prevent silent corruption.
    if idempotency_key:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        existing_job = (
            db.query(CertificateJob)
            .filter(
                CertificateJob.idempotency_key == idempotency_key,
                CertificateJob.created_at >= cutoff,
            )
            .first()
        )
        if existing_job:
            if existing_job.payload_hash and existing_job.payload_hash != payload_hash:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Idempotency-Key reused with a different request body",
                )
            return JobCreateOut(id=existing_job.id, total_count=existing_job.total_count)

    # Create parent CertificateJob and associated CertificateRecipient rows
    job = CertificateJob(
        total_count=len(job_in.recipients),
        template_name=job_in.template_name or "default",
        idempotency_key=idempotency_key,
        payload_hash=payload_hash if idempotency_key else None,
    )
    db.add(job)
    try:
        db.flush()
    except IntegrityError:
        # Handle concurrent requests submitting the same idempotency key simultaneously
        db.rollback()
        if idempotency_key:
            existing = (
                db.query(CertificateJob)
                .filter(CertificateJob.idempotency_key == idempotency_key)
                .first()
            )
            if existing:
                if existing.payload_hash and existing.payload_hash != payload_hash:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Idempotency-Key reused with a different request body",
                    )
                return JobCreateOut(id=existing.id, total_count=existing.total_count)
        raise

    recipient_records = []
    for r in job_in.recipients:
        rec = CertificateRecipient(
            job_id=job.id,
            name=r.name,
            email=str(r.email),
            extra_fields=r.extra_fields or {},
            status="PENDING",
        )
        recipient_records.append(rec)

    db.add_all(recipient_records)
    try:
        db.commit()
        db.refresh(job)
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing = (
                db.query(CertificateJob)
                .filter(CertificateJob.idempotency_key == idempotency_key)
                .first()
            )
            if existing:
                return JobCreateOut(id=existing.id, total_count=existing.total_count)
        raise

    # WHY Commit Before Task Dispatch:
    # Celery workers execute in separate processes/nodes and immediately query CertificateRecipient
    # from the database. Dispatching tasks before db.commit() causes race conditions where workers
    # attempt to read rows that are not yet committed and visible in the database.
    try:
        for rec in recipient_records:
            generate_certificate_task.delay(str(rec.id))
    except Exception as broker_exc:
        # WHY 503 on Broker Outage:
        # If Redis/Celery broker is temporarily down, the rows safely remain in PENDING state in PostgreSQL.
        # Returning 503 with the created job_id informs the client that their batch was stored and is recoverable
        # via the retry endpoint once broker connectivity is restored.
        logger.exception("Task broker unavailable during job task dispatch: %s", broker_exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": "Task broker is temporarily unavailable. Job created but tasks not enqueued. Use the retry endpoint once broker recovers.",
                "job_id": str(job.id),
            },
        )

    return JobCreateOut(id=job.id, total_count=job.total_count)


@router.post("/{job_id}/retry", response_model=JobRetryOut)
@router.post("/{job_id}/retry/", response_model=JobRetryOut, include_in_schema=False)
def retry_job(job_id: UUID, db: Session = Depends(get_db)):
    """Re-enqueue all non-SUCCESS recipients for a job.

    WHY Retry Behavior:
    - Retry is designed for recovering from transient failures (e.g., temporary broker outage,
      worker crash, disk I/O timeout, network blips).
    - FAILED rows are reset to PENDING and their error messages cleared before re-enqueueing.
    - PENDING rows (orphaned by an interrupted dispatch or worker restart) are re-enqueued as-is.
    - Successfully generated recipients (SUCCESS) are never re-processed.
    - Note: Permanent data errors (e.g. blank recipient name) will fail validation again upon retry
      and require correcting the submitted donor data.
    """
    job = db.query(CertificateJob).filter(CertificateJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Fetch all recipients that have not succeeded yet
    non_success_recipients = (
        db.query(CertificateRecipient)
        .filter(
            CertificateRecipient.job_id == job.id,
            CertificateRecipient.status != "SUCCESS",
        )
        .all()
    )

    if not non_success_recipients:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "job_id": str(job.id),
                "requeued_count": 0,
            },
        )

    # Reset FAILED recipients back to PENDING and clear error messages
    for rec in non_success_recipients:
        if rec.status == "FAILED":
            rec.status = "PENDING"
            rec.error_message = None

    db.commit()

    # Re-dispatch Celery tasks for all pending recipients
    try:
        for rec in non_success_recipients:
            generate_certificate_task.delay(str(rec.id))
    except Exception as broker_exc:
        logger.exception("Task broker unavailable during retry dispatch: %s", broker_exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": "Task broker is temporarily unavailable. Could not requeue tasks.",
                "job_id": str(job.id),
            },
        )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "job_id": str(job.id),
            "requeued_count": len(non_success_recipients),
        },
    )


@router.get("/{job_id}/", response_model=JobStatusOut)
@router.get("/{job_id}", response_model=JobStatusOut, include_in_schema=False)
def get_job_status(job_id: UUID, db: Session = Depends(get_db)):
    """Fetch status for a job with counts and overall status computed live."""
    job = db.query(CertificateJob).filter(CertificateJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # WHY Live-Aggregation Query:
    # Instead of updating counter columns on CertificateJob during high-throughput worker execution
    # (which would cause severe row-lock contention and database deadlocks), we aggregate recipient
    # counts live on read. The composite index on (job_id, status) makes this GROUP BY query extremely fast.
    status_counts = (
        db.query(CertificateRecipient.status, func.count(CertificateRecipient.id))
        .filter(CertificateRecipient.job_id == job.id)
        .group_by(CertificateRecipient.status)
        .all()
    )
    counts = dict(status_counts)
    success_count = counts.get("SUCCESS", 0)
    failure_count = counts.get("FAILED", 0)
    pending_count = counts.get("PENDING", 0)

    # Compute overall_status live from constituent counts
    if pending_count > 0:
        overall_status = "PROCESSING"
    elif failure_count == 0:
        overall_status = "COMPLETED"
    else:
        overall_status = "COMPLETED_WITH_ERRORS"

    return JobStatusOut(
        id=job.id,
        created_at=job.created_at,
        total_count=job.total_count,
        success_count=success_count,
        failure_count=failure_count,
        pending_count=pending_count,
        overall_status=overall_status,
    )


@router.get("/{job_id}/recipients/", response_model=list[RecipientOut])
@router.get("/{job_id}/recipients", response_model=list[RecipientOut], include_in_schema=False)
def get_job_recipients(job_id: UUID, db: Session = Depends(get_db)):
    """Fetch all recipients for a job ordered by recipient name."""
    job = db.query(CertificateJob).filter(CertificateJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    recipients = (
        db.query(CertificateRecipient)
        .filter(CertificateRecipient.job_id == job.id)
        .order_by(CertificateRecipient.name)
        .all()
    )
    return recipients
