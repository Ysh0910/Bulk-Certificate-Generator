import logging
import os
import uuid
from datetime import datetime

from celery.exceptions import Retry

from app.celery_app import celery_app
from app.certificate import InvalidRecipientError, generate_certificate
from app.config import settings
from app.database import SessionLocal
from app.models import CertificateJob, CertificateRecipient

logger = logging.getLogger(__name__)


# Deliberately designed as a per-recipient task (rather than a batch task)
# so that one recipient's failure (e.g. invalid name, rendering exception)
# is fully isolated from all other recipients within the job. Other recipients
# will continue processing independently without being blocked or aborted.
@celery_app.task(
    name="generate_certificate_task",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
)
def generate_certificate_task(self, recipient_id: str) -> None:
    """Generate certificate PDF for a single recipient and update status in database.

    Includes task-level idempotency (skips re-processing if already SUCCESS)
    and automatic retry with exponential backoff for transient failures.
    """
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

        # Task Idempotency Guard: skip if already successfully generated
        if recipient.status == "SUCCESS":
            logger.info("Certificate for recipient %s already generated. Skipping.", recipient_id)
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
        except InvalidRecipientError as exc:
            # Permanent validation error (e.g. missing name): do not retry
            logger.warning("Permanent validation error for recipient %s: %s", recipient_id, exc)
            recipient.status = "FAILED"
            recipient.error_message = str(exc)[:500]
        except Retry:
            raise
        except Exception as exc:
            # Transient error: retry with exponential backoff if attempts remain
            if self.request.retries < self.max_retries:
                countdown = 2 ** self.request.retries
                logger.warning(
                    "Transient error for recipient %s: %s. Retrying in %ds (attempt %d/%d)...",
                    recipient_id,
                    exc,
                    countdown,
                    self.request.retries + 1,
                    self.max_retries,
                )
                db.close()
                raise self.retry(exc=exc, countdown=countdown)

            # Max retries exhausted
            logger.exception("Max retries exceeded for recipient %s: %s", recipient_id, exc)
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
