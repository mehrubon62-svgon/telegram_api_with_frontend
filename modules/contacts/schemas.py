from datetime import datetime
from pydantic import BaseModel, Field


class ContactCreate(BaseModel):
    user_id: int
    custom_first_name: str | None = Field(default=None, max_length=80)
    custom_last_name: str | None = Field(default=None, max_length=80)


class ContactImportItem(BaseModel):
    phone: str = Field(min_length=4, max_length=20)
    first_name: str | None = Field(default=None, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)


class ContactImportRequest(BaseModel):
    contacts: list[ContactImportItem] = Field(min_length=1, max_length=1000)


class ContactUpdate(BaseModel):
    custom_first_name: str | None = Field(default=None, max_length=80)
    custom_last_name: str | None = Field(default=None, max_length=80)


class ContactOut(BaseModel):
    id: int
    user_id: int            # id пользователя-контакта
    username: str | None = None
    full_name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    custom_first_name: str | None = None
    custom_last_name: str | None = None
    is_mutual: bool
    is_online: bool
    last_seen: datetime
    created_at: datetime
