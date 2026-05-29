from pydantic import BaseModel


class UploadOut(BaseModel):
    """Универсальный ответ на upload — содержит ровно те поля,
    которые messages.AttachmentIn ждёт. Можно сразу подсунуть в send_message."""
    file_url: str
    thumbnail_url: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    duration: int | None = None
    waveform: list[int] | None = None


class AvatarUpdateOut(BaseModel):
    avatar_url: str
