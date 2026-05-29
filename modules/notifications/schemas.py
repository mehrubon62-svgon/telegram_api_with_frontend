from datetime import datetime
from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: int
    type: str
    chat_id: int | None = None
    message_id: int | None = None
    payload: dict | None = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UnreadCountOut(BaseModel):
    total: int
    by_type: dict[str, int]
