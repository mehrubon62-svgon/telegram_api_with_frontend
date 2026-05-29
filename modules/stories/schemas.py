from datetime import datetime
from pydantic import BaseModel, Field

from models import StoryPrivacyType


class StoryCreate(BaseModel):
    media_url: str
    thumbnail_url: str | None = None
    media_type: str = Field(pattern=r"^(photo|video)$")
    duration: int | None = Field(default=None, ge=1, le=60)
    width: int | None = None
    height: int | None = None

    caption: str | None = Field(default=None, max_length=2000)
    entities: list[dict] | None = None

    privacy: StoryPrivacyType = StoryPrivacyType.everybody
    allowed_user_ids: list[int] | None = None
    excluded_user_ids: list[int] | None = None

    pinned: bool = False
    allow_replies: bool = True
    allow_reactions: bool = True
    allow_forwards: bool = True

    chat_id: int | None = None  # для сторис каналов


class StoryAuthor(BaseModel):
    id: int
    username: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None

    class Config:
        from_attributes = True


class StoryOut(BaseModel):
    id: int
    author: StoryAuthor
    chat_id: int | None = None

    media_url: str
    thumbnail_url: str | None = None
    media_type: str
    duration: int | None = None
    width: int | None = None
    height: int | None = None

    caption: str | None = None
    entities: list[dict] | None = None

    privacy: StoryPrivacyType
    pinned: bool
    allow_replies: bool
    allow_reactions: bool
    allow_forwards: bool

    views_count: int
    reactions_count: int
    is_viewed: bool = False
    my_reaction: str | None = None

    expires_at: datetime
    created_at: datetime


class StoryFeedItem(BaseModel):
    """Лента сторис: автор + список его непросмотренных историй."""
    author: StoryAuthor
    has_unviewed: bool
    stories: list[StoryOut]


class StoryReactionIn(BaseModel):
    emoji: str = Field(min_length=1, max_length=16)


class StoryViewerOut(BaseModel):
    user_id: int
    username: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None
    viewed_at: datetime
    reaction: str | None = None


class StoryReplyIn(BaseModel):
    text: str = Field(min_length=1, max_length=4096)


class CloseFriendItem(BaseModel):
    user_id: int


class CloseFriendsUpdate(BaseModel):
    user_ids: list[int] = Field(default_factory=list)


class CloseFriendsOut(BaseModel):
    user_ids: list[int]
