from datetime import datetime
from pydantic import BaseModel, Field

from models import ReportTargetType, ReportReason


class ReportCreate(BaseModel):
    target_type: ReportTargetType
    target_id: int
    reason: ReportReason
    comment: str | None = Field(default=None, max_length=2000)


class ReportOut(BaseModel):
    id: int
    reporter_id: int | None = None
    target_type: ReportTargetType
    target_id: int
    reason: ReportReason
    comment: str | None = None
    status: str
    created_at: datetime
    reviewed_at: datetime | None = None
    reviewed_by_id: int | None = None

    class Config:
        from_attributes = True


class ReportDecision(BaseModel):
    action: str = Field(pattern=r"^(reviewed|actioned|dismissed)$")
    note: str | None = Field(default=None, max_length=1000)
