import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class CertificateJob(Base):
    __tablename__ = "certificate_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    total_count = Column(Integer, nullable=False)
    template_name = Column(String, default="default", nullable=False)

    # IMPORTANT: Do NOT add a status/success_count/failure_count column here.
    # Job status is deliberately computed live from CertificateRecipient rows at
    # read time (not stored/synced) — this avoids race conditions between Celery
    # workers and keeps a single source of truth. This will be implemented in Part 3.

    recipients = relationship("CertificateRecipient", back_populates="job", cascade="all, delete-orphan")


class CertificateRecipient(Base):
    __tablename__ = "certificate_recipients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("certificate_jobs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    extra_fields = Column(JSON, default=dict, nullable=False)
    status = Column(String, default="PENDING", nullable=False)
    error_message = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    generated_at = Column(DateTime, nullable=True)

    job = relationship("CertificateJob", back_populates="recipients")
