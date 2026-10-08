from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.config import settings


class RecipientIn(BaseModel):
    name: str
    email: EmailStr
    extra_fields: Dict[str, Any] = Field(default_factory=dict)


class JobCreateIn(BaseModel):
    recipients: List[RecipientIn] = Field(..., min_length=1)
    template_name: str = "default"

    @field_validator("recipients")
    @classmethod
    def validate_batch_size(cls, v: List[RecipientIn]) -> List[RecipientIn]:
        if len(v) > settings.MAX_RECIPIENTS_PER_JOB:
            raise ValueError(
                f"Batch size exceeds maximum limit of {settings.MAX_RECIPIENTS_PER_JOB} recipients. "
                f"Please split the batch into smaller requests."
            )
        return v


class RecipientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    status: str
    error_message: Optional[str] = None
    generated_at: Optional[datetime] = None


class JobCreateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    total_count: int


class JobStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    total_count: int
    success_count: int
    failure_count: int
    pending_count: int
    overall_status: str


class JobRetryOut(BaseModel):
    job_id: UUID
    requeued_count: int

