import logging
import os
import uuid
from datetime import datetime

from app.celery_app import celery_app
from app.certificate import generate_certificate
from app.config import settings
from app.database import SessionLocal
from app.models import CertificateJob, CertificateRecipient

logger = logging.getLogger(__name__)


# Deliberately designed as a per-recipient task (rather than a batch task)
# so that one recipient's failure (e.g. invalid name, rendering exception)
# is fully isolated from all other recipients within the job. Other recipients
# will continue processing independently without being blocked or aborted.
@celery_app.task(name="generate_certificate_task")
def generate_certificate_task(recipient_id: str) -> None:
    """Generate certificate PDF for a single recipient and update status in database."""
    # Ensure generated output directory exists at runtime
    os.makedirs(settings.GENERATED_DIR, exist_ok=True)

    db = SessionLocal()
    recipient = None
    try:
        try:
            lookup_id = uuid.UUID(str(recipient_id))
        except (ValueError, TypeError, AttributeError):
            logger.error("Invalid recipient_id UUID format: %s", recipient_id)
            return

        recipient = db.query(CertificateRecipient).filter(CertificateRecipient.id == lookup_id).first()
        if not recipient:
            logger.warning("CertificateRecipient not found for id: %s", recipient_id)
            return

        # Resolve template name from associated job
        template_name = "default"
        if recipient.job and recipient.job.template_name:
            template_name = recipient.job.template_name
        else:
            job = db.query(CertificateJob).filter(CertificateJob.id == recipient.job_id).first()
            if job and job.template_name:
                template_name = job.template_name

        output_path = f"{settings.GENERATED_DIR}/{recipient_id}.pdf"
        template_path = f"{settings.TEMPLATES_DIR}/{template_name}.png"

        try:
            generate_certificate(
                recipient_name=recipient.name,
                extra_fields=recipient.extra_fields or {},
                output_path=output_path,
                template_path=template_path,
            )
            recipient.status = "SUCCESS"
            recipient.file_path = output_path
            recipient.error_message = None
            recipient.generated_at = datetime.utcnow()
        except Exception as exc:
            logger.exception("Failed to generate certificate for recipient %s: %s", recipient_id, exc)
            recipient.status = "FAILED"
            recipient.error_message = str(exc)[:500]

    finally:
        if recipient is not None:
            try:
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("Failed to commit recipient update for %s", recipient_id)
        db.close()
