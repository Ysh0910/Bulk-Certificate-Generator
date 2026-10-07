import io
import os
import zipfile
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CertificateJob, CertificateRecipient

router = APIRouter(prefix="/api", tags=["certificates"])


@router.get("/certificates/{recipient_id}/")
@router.get("/certificates/{recipient_id}", include_in_schema=False)
def get_certificate(recipient_id: UUID, db: Session = Depends(get_db)):
    """Retrieve the generated certificate PDF for a recipient."""
    recipient = (
        db.query(CertificateRecipient)
        .filter(CertificateRecipient.id == recipient_id)
        .first()
    )
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate recipient not found",
        )

    if recipient.status != "SUCCESS":
        detail = "Certificate not yet generated or generation failed"
        if recipient.status == "FAILED" and recipient.error_message:
            detail = f"Certificate generation failed: {recipient.error_message}"
        elif recipient.status == "PENDING":
            detail = "Certificate is still pending generation"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )

    if not recipient.file_path or not os.path.exists(recipient.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate file not found on disk",
        )

    return FileResponse(
        recipient.file_path,
        media_type="application/pdf",
        filename=f"{recipient.name}_certificate.pdf",
    )


@router.get("/jobs/{job_id}/certificates/download")
@router.get("/jobs/{job_id}/certificates/download/", include_in_schema=False)
def download_job_certificates(job_id: UUID, db: Session = Depends(get_db)):
    """Download all successful certificates for a job bundled inside a zip archive."""
    job = db.query(CertificateJob).filter(CertificateJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    recipients = (
        db.query(CertificateRecipient)
        .filter(
            CertificateRecipient.job_id == job.id,
            CertificateRecipient.status == "SUCCESS",
        )
        .all()
    )

    if not recipients:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No successfully generated certificates found for this job",
        )

    # Build zip file in-memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        name_counts = {}
        for rec in recipients:
            if rec.file_path and os.path.exists(rec.file_path):
                base_name = rec.name or "certificate"
                if base_name in name_counts:
                    name_counts[base_name] += 1
                    arcname = f"{base_name}_{name_counts[base_name]}.pdf"
                else:
                    name_counts[base_name] = 1
                    arcname = f"{base_name}.pdf"

                zf.write(rec.file_path, arcname=arcname)

    zip_buffer.seek(0)

    headers = {
        "Content-Disposition": f'attachment; filename="job_{job.id}_certificates.zip"'
    }

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers=headers,
    )
