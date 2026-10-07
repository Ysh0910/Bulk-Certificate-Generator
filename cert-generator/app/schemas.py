from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class RecipientIn(BaseModel):
    name: str
    email: str
    extra_fields: Dict[str, Any] = Field(default_factory=dict)


class JobCreateIn(BaseModel):
    recipients: List[RecipientIn] = Field(..., min_length=1)
    template_name: str = "default"


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
