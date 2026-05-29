from datetime import datetime
from pydantic import BaseModel, Field

from models import ChatType, ChatMemberRole


# =====================================================================
#  Chat — base
# =====================================================================

class ChatPermissions(BaseModel):
    can_send_messages: bool = True
    can_send_media: bool = True
    can_send_polls: bool = True
    can_add_users: bool = True
    can_pin_messages: bool = False
    can_change_info: bool = False


class ChatOut(BaseModel):
    id: int
    type: ChatType
    title: str | None = None
    description: str | None = None
    avatar_url: str | None = None
    public_username: str | None = None
    creator_id: int | None = None
    pinned_message_id: int | None = None
    last_message_id: int | None = None
    linked_chat_id: int | None = None

    is_forum: bool
    slow_mode_seconds: int
    is_history_visible: bool
    is_join_by_request: bool
    members_count: int

    permissions: ChatPermissions
    created_at: datetime

    class Config:
        from_attributes = True


class ChatListItem(BaseModel):
    """Чат для отображения в списке (с unread + my-state)."""
    chat: ChatOut
    is_pinned: bool
    is_archived: bool
    is_muted: bool
    unread_count: int
    unread_mentions_count: int
    last_read_message_id: int | None = None


# ---- Create ----

class CreatePrivateChat(BaseModel):
    user_id: int


class CreateGroupChat(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    member_ids: list[int] = Field(default_factory=list, max_length=500)
    is_supergroup: bool = False
    is_forum: bool = False


class CreateChannel(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    public_username: str | None = Field(default=None, min_length=5, max_length=50, pattern=r"^[a-zA-Z][a-zA-Z0-9_]{4,49}$")


class ChatUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    avatar_url: str | None = None
    public_username: str | None = Field(default=None, min_length=5, max_length=50, pattern=r"^[a-zA-Z][a-zA-Z0-9_]{4,49}$")
    slow_mode_seconds: int | None = Field(default=None, ge=0, le=21600)
    is_history_visible: bool | None = None
    is_join_by_request: bool | None = None
    is_forum: bool | None = None
    permissions: ChatPermissions | None = None


# =====================================================================
#  Members
# =====================================================================

class MemberOut(BaseModel):
    user_id: int
    username: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None
    role: ChatMemberRole
    custom_title: str | None = None
    is_muted: bool
    joined_at: datetime
    can_send_messages: bool
    can_send_media: bool
    restricted_until: datetime | None = None


class AddMembers(BaseModel):
    user_ids: list[int] = Field(min_length=1, max_length=200)


class ChangeRole(BaseModel):
    role: ChatMemberRole
    custom_title: str | None = Field(default=None, max_length=50)
    restricted_until: datetime | None = None


class AdminRightsOut(BaseModel):
    can_change_info: bool
    can_delete_messages: bool
    can_ban_users: bool
    can_invite_users: bool
    can_pin_messages: bool
    can_promote_members: bool
    can_manage_video_chats: bool
    can_post_messages: bool
    can_edit_messages: bool
    can_manage_topics: bool
    is_anonymous: bool

    class Config:
        from_attributes = True


class AdminRightsUpdate(BaseModel):
    can_change_info: bool | None = None
    can_delete_messages: bool | None = None
    can_ban_users: bool | None = None
    can_invite_users: bool | None = None
    can_pin_messages: bool | None = None
    can_promote_members: bool | None = None
    can_manage_video_chats: bool | None = None
    can_post_messages: bool | None = None
    can_edit_messages: bool | None = None
    can_manage_topics: bool | None = None
    is_anonymous: bool | None = None


# =====================================================================
#  Invites
# =====================================================================

class InviteCreate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    member_limit: int | None = Field(default=None, ge=1, le=99999)
    expires_at: datetime | None = None
    requires_approval: bool = False


class InviteOut(BaseModel):
    id: int
    code: str
    invite_url: str
    name: str | None = None
    member_limit: int | None = None
    expires_at: datetime | None = None
    requires_approval: bool
    usage_count: int
    is_revoked: bool
    creator_id: int | None = None
    created_at: datetime


class JoinRequestOut(BaseModel):
    id: int
    chat_id: int
    user_id: int
    bio: str | None = None
    status: str
    created_at: datetime
    decided_at: datetime | None = None


class JoinRequestCreate(BaseModel):
    bio: str | None = Field(default=None, max_length=500)


# =====================================================================
#  Topics
# =====================================================================

class TopicCreate(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    icon_color: str | None = None
    icon_emoji: str | None = Field(default=None, max_length=16)


class TopicUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=128)
    icon_color: str | None = None
    icon_emoji: str | None = Field(default=None, max_length=16)
    is_closed: bool | None = None
    is_hidden: bool | None = None


class TopicOut(BaseModel):
    id: int
    chat_id: int
    title: str
    icon_color: str | None = None
    icon_emoji: str | None = None
    is_closed: bool
    is_hidden: bool
    is_general: bool
    creator_id: int | None = None
    last_message_id: int | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# =====================================================================
#  Folders
# =====================================================================

class FolderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    icon: str | None = None
    include_contacts: bool = False
    include_non_contacts: bool = False
    include_groups: bool = False
    include_channels: bool = False
    include_bots: bool = False
    exclude_muted: bool = False
    exclude_read: bool = False
    exclude_archived: bool = True


class FolderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=80)
    icon: str | None = None
    position: int | None = None
    include_contacts: bool | None = None
    include_non_contacts: bool | None = None
    include_groups: bool | None = None
    include_channels: bool | None = None
    include_bots: bool | None = None
    exclude_muted: bool | None = None
    exclude_read: bool | None = None
    exclude_archived: bool | None = None


class FolderOut(BaseModel):
    id: int
    title: str
    icon: str | None = None
    position: int
    include_contacts: bool
    include_non_contacts: bool
    include_groups: bool
    include_channels: bool
    include_bots: bool
    exclude_muted: bool
    exclude_read: bool
    exclude_archived: bool
    chat_ids: list[int] = Field(default_factory=list)
    excluded_chat_ids: list[int] = Field(default_factory=list)


class FolderItem(BaseModel):
    chat_id: int
    is_excluded: bool = False


# =====================================================================
#  Mute / Pin / Archive
# =====================================================================

class MuteUpdate(BaseModel):
    is_muted: bool
    mute_until: datetime | None = None
    show_previews: bool | None = True
    only_mentions: bool | None = False
    sound: str | None = None


class PinUpdate(BaseModel):
    is_pinned: bool


class ArchiveUpdate(BaseModel):
    is_archived: bool


# =====================================================================
#  Linked chat
# =====================================================================

class LinkedChatUpdate(BaseModel):
    linked_chat_id: int | None = None  # None = разорвать связь


# =====================================================================
#  Banned words
# =====================================================================

class BannedWordCreate(BaseModel):
    word: str = Field(min_length=1, max_length=64)
    is_regex: bool = False
    case_sensitive: bool = False


class BannedWordOut(BaseModel):
    id: int
    word: str
    is_regex: bool
    case_sensitive: bool
    added_by_id: int | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# =====================================================================
#  Admin log
# =====================================================================

class AdminLogOut(BaseModel):
    id: int
    chat_id: int
    actor_id: int | None = None
    target_user_id: int | None = None
    action: str
    payload: dict | None = None
    created_at: datetime

    class Config:
        from_attributes = True
