from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CertificateJob, CertificateRecipient
from app.schemas import JobCreateIn, JobCreateOut, JobStatusOut, RecipientOut
from app.tasks import generate_certificate_task

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
    """
    if not job_in.recipients:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Recipients list cannot be empty.",
        )

    # Idempotency check: return existing job if submitted within the last 24 hours
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
            return JobCreateOut(id=existing_job.id, total_count=existing_job.total_count)

    # In a single DB transaction: create CertificateJob and bulk-create recipients
    job = CertificateJob(
        total_count=len(job_in.recipients),
        template_name=job_in.template_name or "default",
        idempotency_key=idempotency_key,
    )
    db.add(job)
    db.flush()

    recipient_records = []
    for r in job_in.recipients:
        rec = CertificateRecipient(
            job_id=job.id,
            name=r.name,
            email=r.email,
            extra_fields=r.extra_fields or {},
            status="PENDING",
        )
        recipient_records.append(rec)

    db.add_all(recipient_records)
    db.commit()
    db.refresh(job)

    # Dispatch Celery tasks AFTER commit so persistent UUIDs exist in database
    for rec in recipient_records:
        generate_certificate_task.delay(str(rec.id))

    return JobCreateOut(id=job.id, total_count=job.total_count)


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

    # Query recipient counts grouped by status
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

    # Compute overall_status live
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
