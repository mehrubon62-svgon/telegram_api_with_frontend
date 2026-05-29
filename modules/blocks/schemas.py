from datetime import datetime
from pydantic import BaseModel


class BlockCreate(BaseModel):
    user_id: int


class BlockOut(BaseModel):
    id: int
    user_id: int
    username: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None
    blocked_at: datetime
