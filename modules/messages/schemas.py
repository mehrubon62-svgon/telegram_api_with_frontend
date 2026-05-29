from datetime import datetime
from pydantic import BaseModel, Field

from models import MessageType


# =====================================================================
#  Attachments
# =====================================================================

class AttachmentIn(BaseModel):
    """Уже загруженный файл (см. модуль media)."""
    file_url: str
    thumbnail_url: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    duration: int | None = None
    waveform: list[int] | None = None
    caption: str | None = None
    has_spoiler: bool = False
    is_view_once: bool = False
    position: int = 0


class AttachmentOut(AttachmentIn):
    id: int

    class Config:
        from_attributes = True


# =====================================================================
#  Quote / forward
# =====================================================================

class QuoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    offset: int = 0
    entities: list[dict] | None = None


class ForwardOriginOut(BaseModel):
    from_user_id: int | None = None
    from_chat_id: int | None = None
    from_message_id: int | None = None
    sender_name: str | None = None
    date: datetime | None = None


# =====================================================================
#  Sender (минимум для UI)
# =====================================================================

class SenderOut(BaseModel):
    id: int
    username: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None
    name_color: int = 0

    class Config:
        from_attributes = True


# =====================================================================
#  Send / message
# =====================================================================

class MessageCreate(BaseModel):
    text: str | None = Field(default=None, max_length=4096)
    type: MessageType = MessageType.text
    entities: list[dict] | None = None
    reply_to_id: int | None = None
    reply_quote: QuoteIn | None = None
    topic_id: int | None = None

    is_silent: bool = False
    self_destruct_seconds: int | None = Field(default=None, ge=1, le=604800)
    scheduled_at: datetime | None = None
    original_language: str | None = Field(default=None, max_length=8)

    # Inline keyboard (для ботов / каналов)
    reply_markup: dict | None = None

    # Прикреплённые файлы (уже загруженные)
    attachments: list[AttachmentIn] = Field(default_factory=list, max_length=10)


class MessageEdit(BaseModel):
    text: str | None = Field(default=None, max_length=4096)
    entities: list[dict] | None = None
    reply_markup: dict | None = None


class MessageOut(BaseModel):
    id: int
    chat_id: int
    topic_id: int | None = None
    sender: SenderOut | None = None
    type: MessageType
    text: str | None = None
    entities: list[dict] | None = None

    reply_to_id: int | None = None
    thread_root_id: int | None = None
    reply_quote_text: str | None = None
    reply_quote_offset: int | None = None
    reply_quote_entities: list[dict] | None = None

    forward: ForwardOriginOut | None = None

    is_edited: bool
    is_deleted: bool
    is_pinned: bool
    is_silent: bool
    is_via_bot: bool
    via_bot_id: int | None = None

    views_count: int
    forwards_count: int

    self_destruct_seconds: int | None = None
    expires_at: datetime | None = None
    scheduled_at: datetime | None = None
    is_scheduled: bool
    original_language: str | None = None

    reply_markup: dict | None = None

    attachments: list[AttachmentOut] = Field(default_factory=list)
    reactions: list["ReactionEntry"] = Field(default_factory=list)

    created_at: datetime
    edited_at: datetime | None = None


class MessageEditHistoryOut(BaseModel):
    id: int
    text: str | None = None
    entities: list[dict] | None = None
    edited_at: datetime

    class Config:
        from_attributes = True


# =====================================================================
#  Forward
# =====================================================================

class ForwardRequest(BaseModel):
    from_chat_id: int
    message_ids: list[int] = Field(min_length=1, max_length=100)
    to_chat_ids: list[int] = Field(min_length=1, max_length=20)
    drop_author: bool = False
    drop_caption: bool = False


# =====================================================================
#  Read / mentions
# =====================================================================

class ReadUpToRequest(BaseModel):
    message_id: int


class ReadEntry(BaseModel):
    user_id: int
    read_at: datetime


# =====================================================================
#  Reactions
# =====================================================================

class ReactionToggle(BaseModel):
    emoji: str = Field(min_length=1, max_length=16)
    is_big: bool = False


class ReactionEntry(BaseModel):
    emoji: str
    count: int
    chosen: bool = False
    user_ids: list[int] = Field(default_factory=list)


# =====================================================================
#  Drafts
# =====================================================================

class DraftIn(BaseModel):
    text: str | None = Field(default=None, max_length=4096)
    reply_to_id: int | None = None
    topic_id: int | None = None


class DraftOut(BaseModel):
    chat_id: int
    topic_id: int | None = None
    text: str | None = None
    reply_to_id: int | None = None
    updated_at: datetime

    class Config:
        from_attributes = True


# =====================================================================
#  Polls
# =====================================================================

class PollCreate(BaseModel):
    question: str = Field(min_length=1, max_length=300)
    options: list[str] = Field(min_length=2, max_length=12)
    is_anonymous: bool = True
    allows_multiple_answers: bool = False
    is_quiz: bool = False
    correct_option_index: int | None = None
    explanation: str | None = Field(default=None, max_length=300)
    close_at: datetime | None = None


class PollVoteIn(BaseModel):
    option_ids: list[int] = Field(min_length=1)


class PollOptionOut(BaseModel):
    id: int
    text: str
    voter_count: int

    class Config:
        from_attributes = True


class PollOut(BaseModel):
    id: int
    message_id: int
    question: str
    options: list[PollOptionOut]
    is_anonymous: bool
    allows_multiple_answers: bool
    is_quiz: bool
    correct_option_id: int | None = None
    explanation: str | None = None
    is_closed: bool
    close_at: datetime | None = None
    total_voters: int
    chosen_option_ids: list[int] = Field(default_factory=list)



# Forward refs (ReactionEntry в MessageOut определён ниже него)
MessageOut.model_rebuild()
