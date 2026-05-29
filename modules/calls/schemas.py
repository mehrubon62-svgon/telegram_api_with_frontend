from datetime import datetime
from pydantic import BaseModel, Field

from models import CallType, CallStatus


class CallStart(BaseModel):
    callee_id: int | None = None        # для 1-1 звонка
    chat_id: int | None = None          # для group-call
    type: CallType = CallType.audio
    is_video: bool = False


class CallSignal(BaseModel):
    """Контейнер для WebRTC SDP/ICE — сервер их не парсит, просто
    транслирует другому участнику через WS."""
    target_user_id: int
    payload: dict = Field(description="SDP offer/answer/candidate")


class CallEnd(BaseModel):
    end_reason: str | None = Field(default=None, max_length=50)


class CallParticipantOut(BaseModel):
    user_id: int
    username: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None
    joined_at: datetime | None = None
    left_at: datetime | None = None
    is_muted: bool
    is_video_on: bool
    is_screen_sharing: bool


class CallOut(BaseModel):
    id: int
    chat_id: int | None = None
    initiator_id: int | None = None
    type: CallType
    status: CallStatus
    is_video: bool
    is_group: bool

    started_at: datetime
    answered_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    end_reason: str | None = None

    participants: list[CallParticipantOut] = Field(default_factory=list)


class ParticipantStateUpdate(BaseModel):
    is_muted: bool | None = None
    is_video_on: bool | None = None
    is_screen_sharing: bool | None = None
