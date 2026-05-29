"""
Модели проекта Telegramm-клон.

Цель — приблизить структуру данных к настоящему Telegram (без стикеров,
подписок/премиума и платежей). Real-time события поверх этих моделей
будут идти через WebSocket (см. modules/websockets).
"""
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    ForeignKey,
    Enum as SQLEnum,
    Boolean,
    DateTime,
    Text,
    Float,
    JSON,
    UniqueConstraint,
    Index,
    create_engine,
)
from sqlalchemy.orm import (
    relationship,
    sessionmaker,
    DeclarativeBase,
    Session,
)

from config import DATABASE_URL


class Base(DeclarativeBase):
    pass


# ---- Engine / Session ----

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# =====================================================================
#  ENUMS
# =====================================================================

class RoleEnum(str, Enum):
    user = "user"
    admin = "admin"


class ChatType(str, Enum):
    private = "private"          # 1-на-1
    group = "group"              # обычная группа (до ~200 участников)
    supergroup = "supergroup"    # супергруппа (большая, с топиками)
    channel = "channel"          # канал (read-only для подписчиков)
    saved = "saved"              # «Избранное» — чат с самим собой
    secret = "secret"            # секретный чат (E2E на стороне клиентов)


class ChatMemberRole(str, Enum):
    creator = "creator"
    admin = "admin"
    member = "member"
    restricted = "restricted"
    left = "left"
    banned = "banned"


class MessageType(str, Enum):
    text = "text"
    photo = "photo"
    video = "video"
    video_note = "video_note"    # «кружок»
    animation = "animation"       # GIF
    audio = "audio"
    voice = "voice"
    file = "file"
    location = "location"
    live_location = "live_location"
    contact = "contact"
    poll = "poll"
    call = "call"                 # системное сообщение о звонке
    story_reply = "story_reply"   # ответ на сторис
    bot_inline = "bot_inline"     # сообщение от бота через inline-режим
    system = "system"             # «X добавил Y», «Y покинул чат» и т.д.


class CallType(str, Enum):
    audio = "audio"
    video = "video"


class CallStatus(str, Enum):
    ringing = "ringing"
    accepted = "accepted"
    declined = "declined"
    missed = "missed"
    ended = "ended"


class PrivacyLevel(str, Enum):
    everybody = "everybody"
    contacts = "contacts"
    nobody = "nobody"


class DevicePlatform(str, Enum):
    web = "web"
    android = "android"
    ios = "ios"
    desktop = "desktop"


# =====================================================================
#  USERS
# =====================================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=True, index=True)  # в TG юзернейм опционален
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), unique=True, nullable=True, index=True)
    hashed_password = Column(String(255), nullable=False)

    full_name = Column(String(150), nullable=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)

    language_code = Column(String(8), default="en", nullable=False)
    theme = Column(String(32), default="auto", nullable=False)  # auto/light/dark

    role = Column(SQLEnum(RoleEnum), default=RoleEnum.user, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)   # «синяя галочка»
    is_bot = Column(Boolean, default=False, nullable=False)
    is_online = Column(Boolean, default=False, nullable=False)
    last_seen = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Цвет имени пользователя (как в TG: пользователь выбирает один из палитры).
    # Хранится индексом из набора COLORS на фронте.
    name_color = Column(Integer, default=0, nullable=False)

    # Профиль (расширение)
    birthday = Column(DateTime(timezone=True), nullable=True)
    personal_channel_id = Column(Integer, ForeignKey("chats.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class UsernameHistory(Base):
    """История смен юзернейма пользователя."""
    __tablename__ = "username_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    username = Column(String(50), nullable=False)
    changed_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class UserSession(Base):
    """
    Активная сессия (устройство), в Telegram — «Активные сеансы».
    Привязана к refresh-токену.
    """
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_token = Column(String(255), unique=True, nullable=False, index=True)

    platform = Column(SQLEnum(DevicePlatform), default=DevicePlatform.web, nullable=False)
    device_name = Column(String(150), nullable=True)
    app_version = Column(String(50), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    country = Column(String(80), nullable=True)
    city = Column(String(120), nullable=True)

    is_current = Column(Boolean, default=False, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_active_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class UserDevice(Base):
    """Push-токен устройства (FCM/APNs/web-push)."""
    __tablename__ = "user_devices"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(SQLEnum(DevicePlatform), nullable=False)
    push_token = Column(String(500), unique=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class TwoFactorAuth(Base):
    """Облачный пароль (2FA в Telegram)."""
    __tablename__ = "two_factor_auth"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    hint = Column(String(150), nullable=True)
    recovery_email = Column(String(255), nullable=True)
    enabled_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class LoginAttempt(Base):
    """Аудит попыток входа."""
    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    identifier = Column(String(255), nullable=False)  # email/username/phone, который вводили
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    success = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class PrivacySetting(Base):
    """
    Настройки приватности пользователя — кому что видно.
    Один на пользователя.
    """
    __tablename__ = "privacy_settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    last_seen = Column(SQLEnum(PrivacyLevel), default=PrivacyLevel.everybody, nullable=False)
    profile_photo = Column(SQLEnum(PrivacyLevel), default=PrivacyLevel.everybody, nullable=False)
    phone_number = Column(SQLEnum(PrivacyLevel), default=PrivacyLevel.contacts, nullable=False)
    forwards = Column(SQLEnum(PrivacyLevel), default=PrivacyLevel.everybody, nullable=False)
    calls = Column(SQLEnum(PrivacyLevel), default=PrivacyLevel.everybody, nullable=False)
    groups_invite = Column(SQLEnum(PrivacyLevel), default=PrivacyLevel.everybody, nullable=False)
    birthday = Column(SQLEnum(PrivacyLevel), default=PrivacyLevel.contacts, nullable=False)
    bio = Column(SQLEnum(PrivacyLevel), default=PrivacyLevel.everybody, nullable=False)


# =====================================================================
#  CONTACTS / BLOCKS
# =====================================================================

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    custom_first_name = Column(String(80), nullable=True)
    custom_last_name = Column(String(80), nullable=True)
    is_mutual = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("owner_id", "contact_id", name="uq_contacts_owner_contact"),
    )


class Block(Base):
    __tablename__ = "blocks"

    id = Column(Integer, primary_key=True)
    blocker_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    blocked_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_blocks_pair"),
    )


# =====================================================================
#  CHATS
# =====================================================================

class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True)
    type = Column(SQLEnum(ChatType), nullable=False, index=True)

    title = Column(String(150), nullable=True)
    description = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    public_username = Column(String(50), unique=True, nullable=True, index=True)  # для публичных групп/каналов

    creator_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    last_message_id = Column(Integer, nullable=True)  # «мягкая» ссылка, без FK, чтобы избежать циклов
    pinned_message_id = Column(Integer, nullable=True)
    linked_chat_id = Column(Integer, ForeignKey("chats.id", ondelete="SET NULL"), nullable=True)  # канал ↔ обсуждение

    is_forum = Column(Boolean, default=False, nullable=False)         # супергруппа с топиками
    slow_mode_seconds = Column(Integer, default=0, nullable=False)
    is_history_visible = Column(Boolean, default=True, nullable=False)  # видна ли история новым участникам
    is_join_by_request = Column(Boolean, default=False, nullable=False)
    members_count = Column(Integer, default=0, nullable=False)        # денормализованный счётчик

    # Дефолтные права участников (битовая маска через флаги)
    can_send_messages = Column(Boolean, default=True, nullable=False)
    can_send_media = Column(Boolean, default=True, nullable=False)
    can_send_polls = Column(Boolean, default=True, nullable=False)
    can_add_users = Column(Boolean, default=True, nullable=False)
    can_pin_messages = Column(Boolean, default=False, nullable=False)
    can_change_info = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class ChatMember(Base):
    __tablename__ = "chat_members"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(SQLEnum(ChatMemberRole), default=ChatMemberRole.member, nullable=False)

    custom_title = Column(String(50), nullable=True)  # «должность» админа
    invited_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    is_muted = Column(Boolean, default=False, nullable=False)
    mute_until = Column(DateTime(timezone=True), nullable=True)
    is_pinned = Column(Boolean, default=False, nullable=False)         # чат закреплён в списке
    is_archived = Column(Boolean, default=False, nullable=False)

    last_read_message_id = Column(Integer, nullable=True)
    unread_count = Column(Integer, default=0, nullable=False)
    unread_mentions_count = Column(Integer, default=0, nullable=False)

    # Индивидуальные ограничения участника (если role == restricted)
    can_send_messages = Column(Boolean, default=True, nullable=False)
    can_send_media = Column(Boolean, default=True, nullable=False)
    restricted_until = Column(DateTime(timezone=True), nullable=True)

    joined_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    left_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", name="uq_chat_members_pair"),
    )


class ChatAdminRights(Base):
    """
    Тонкие права админа в чате/канале.
    Создаётся отдельной строкой для пользователей с ролью admin/creator.
    """
    __tablename__ = "chat_admin_rights"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    can_change_info = Column(Boolean, default=False, nullable=False)
    can_delete_messages = Column(Boolean, default=False, nullable=False)
    can_ban_users = Column(Boolean, default=False, nullable=False)
    can_invite_users = Column(Boolean, default=True, nullable=False)
    can_pin_messages = Column(Boolean, default=False, nullable=False)
    can_promote_members = Column(Boolean, default=False, nullable=False)
    can_manage_video_chats = Column(Boolean, default=False, nullable=False)
    can_post_messages = Column(Boolean, default=False, nullable=False)   # для каналов
    can_edit_messages = Column(Boolean, default=False, nullable=False)   # для каналов
    can_manage_topics = Column(Boolean, default=False, nullable=False)
    is_anonymous = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", name="uq_chat_admin_rights_pair"),
    )


class ChatInvite(Base):
    """Инвайт-ссылка с лимитами (как в TG)."""
    __tablename__ = "chat_invites"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    creator_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    code = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(80), nullable=True)
    member_limit = Column(Integer, nullable=True)   # NULL = без лимита
    expires_at = Column(DateTime(timezone=True), nullable=True)
    requires_approval = Column(Boolean, default=False, nullable=False)

    usage_count = Column(Integer, default=0, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class ChatJoinRequest(Base):
    """Заявка на вступление (для чатов с requires_approval)."""
    __tablename__ = "chat_join_requests"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    invite_id = Column(Integer, ForeignKey("chat_invites.id", ondelete="SET NULL"), nullable=True)
    bio = Column(Text, nullable=True)  # короткое сообщение от пользователя

    status = Column(String(20), default="pending", nullable=False)  # pending/approved/declined
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decided_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", name="uq_chat_join_requests_pair"),
    )


class ChatFolder(Base):
    """Папка чатов пользователя (как в TG: «Личные», «Работа»...)."""
    __tablename__ = "chat_folders"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(80), nullable=False)
    icon = Column(String(50), nullable=True)
    position = Column(Integer, default=0, nullable=False)

    # Фильтры по типам чатов
    include_contacts = Column(Boolean, default=False, nullable=False)
    include_non_contacts = Column(Boolean, default=False, nullable=False)
    include_groups = Column(Boolean, default=False, nullable=False)
    include_channels = Column(Boolean, default=False, nullable=False)
    include_bots = Column(Boolean, default=False, nullable=False)
    exclude_muted = Column(Boolean, default=False, nullable=False)
    exclude_read = Column(Boolean, default=False, nullable=False)
    exclude_archived = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class ChatFolderItem(Base):
    """Чаты, явно включённые/исключённые из папки."""
    __tablename__ = "chat_folder_items"

    id = Column(Integer, primary_key=True)
    folder_id = Column(Integer, ForeignKey("chat_folders.id", ondelete="CASCADE"), nullable=False, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    is_excluded = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("folder_id", "chat_id", name="uq_chat_folder_items_pair"),
    )


class ChatTopic(Base):
    """Топик в форумной супергруппе."""
    __tablename__ = "chat_topics"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    creator_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    title = Column(String(128), nullable=False)
    icon_color = Column(String(16), nullable=True)
    icon_emoji = Column(String(16), nullable=True)
    is_closed = Column(Boolean, default=False, nullable=False)
    is_hidden = Column(Boolean, default=False, nullable=False)
    is_general = Column(Boolean, default=False, nullable=False)

    last_message_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


# =====================================================================
#  MESSAGES
# =====================================================================

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(Integer, ForeignKey("chat_topics.id", ondelete="SET NULL"), nullable=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    type = Column(SQLEnum(MessageType), default=MessageType.text, nullable=False)
    text = Column(Text, nullable=True)
    entities = Column(JSON, nullable=True)  # bold/italic/links/mentions/code

    reply_to_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True)
    thread_root_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True)

    # Quote-reply: цитата конкретного фрагмента из исходного сообщения
    reply_quote_text = Column(Text, nullable=True)
    reply_quote_offset = Column(Integer, nullable=True)
    reply_quote_entities = Column(JSON, nullable=True)

    # Inline keyboard / reply markup (для ботов)
    reply_markup = Column(JSON, nullable=True)

    # Локализация
    original_language = Column(String(8), nullable=True)

    # Forward
    forward_from_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    forward_from_chat_id = Column(Integer, ForeignKey("chats.id", ondelete="SET NULL"), nullable=True)
    forward_from_message_id = Column(Integer, nullable=True)
    forward_sender_name = Column(String(150), nullable=True)
    forward_date = Column(DateTime(timezone=True), nullable=True)

    # Доп.поведение
    is_edited = Column(Boolean, default=False, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False)
    is_silent = Column(Boolean, default=False, nullable=False)         # без звука уведомлений
    is_via_bot = Column(Boolean, default=False, nullable=False)
    via_bot_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Каналы / общие счётчики
    views_count = Column(Integer, default=0, nullable=False)
    forwards_count = Column(Integer, default=0, nullable=False)

    # TTL / self-destruct
    self_destruct_seconds = Column(Integer, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Отложенная отправка
    scheduled_at = Column(DateTime(timezone=True), nullable=True, index=True)
    is_scheduled = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    edited_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_messages_chat_created", "chat_id", "created_at"),
    )


class MessageEditHistory(Base):
    """История правок сообщения (для отображения «изменено»)."""
    __tablename__ = "message_edit_history"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=True)
    entities = Column(JSON, nullable=True)
    edited_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class Attachment(Base):
    """Вложение к сообщению (фото/видео/файл/аудио/voice/video_note)."""
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)

    file_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)
    file_name = Column(String(255), nullable=True)
    mime_type = Column(String(100), nullable=True)
    size_bytes = Column(BigInteger, nullable=True)

    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    duration = Column(Integer, nullable=True)        # сек, для аудио/видео
    waveform = Column(JSON, nullable=True)           # для voice
    caption = Column(Text, nullable=True)
    has_spoiler = Column(Boolean, default=False, nullable=False)
    is_view_once = Column(Boolean, default=False, nullable=False)  # «один просмотр»
    position = Column(Integer, default=0, nullable=False)  # порядок в альбоме


class MessageReaction(Base):
    __tablename__ = "message_reactions"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    emoji = Column(String(16), nullable=False)
    is_big = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("message_id", "user_id", "emoji", name="uq_message_reactions_unique"),
    )


class MessageRead(Base):
    """Read receipts: кто и когда прочитал сообщение."""
    __tablename__ = "message_reads"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    read_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("message_id", "user_id", name="uq_message_reads_pair"),
    )


class MessageView(Base):
    """Просмотры сообщения (для каналов)."""
    __tablename__ = "message_views"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    viewed_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("message_id", "user_id", name="uq_message_views_pair"),
    )


class MessageMention(Base):
    """Упоминания (@username) в сообщении."""
    __tablename__ = "message_mentions"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    mentioned_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class MessageLinkPreview(Base):
    """Web-page preview для ссылок в сообщении."""
    __tablename__ = "message_link_previews"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    url = Column(String(1000), nullable=False)
    site_name = Column(String(150), nullable=True)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)


class MessageLocation(Base):
    """Гео-сообщения и live-локации."""
    __tablename__ = "message_locations"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), unique=True, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=True)
    is_live = Column(Boolean, default=False, nullable=False)
    live_period_seconds = Column(Integer, nullable=True)
    heading = Column(Integer, nullable=True)
    last_updated_at = Column(DateTime(timezone=True), nullable=True)


class MessageContact(Base):
    """Сообщение-контакт (как в TG: переслать визитку)."""
    __tablename__ = "message_contacts"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    phone = Column(String(20), nullable=True)
    first_name = Column(String(80), nullable=True)
    last_name = Column(String(80), nullable=True)
    vcard = Column(Text, nullable=True)


# ---- Polls ----

class Poll(Base):
    __tablename__ = "polls"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), unique=True, nullable=False)
    question = Column(String(300), nullable=False)
    is_anonymous = Column(Boolean, default=True, nullable=False)
    allows_multiple_answers = Column(Boolean, default=False, nullable=False)
    is_quiz = Column(Boolean, default=False, nullable=False)
    correct_option_id = Column(Integer, nullable=True)
    explanation = Column(Text, nullable=True)
    is_closed = Column(Boolean, default=False, nullable=False)
    close_at = Column(DateTime(timezone=True), nullable=True)
    total_voters = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class PollOption(Base):
    __tablename__ = "poll_options"

    id = Column(Integer, primary_key=True)
    poll_id = Column(Integer, ForeignKey("polls.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(String(150), nullable=False)
    position = Column(Integer, default=0, nullable=False)
    voter_count = Column(Integer, default=0, nullable=False)


class PollVote(Base):
    __tablename__ = "poll_votes"

    id = Column(Integer, primary_key=True)
    poll_id = Column(Integer, ForeignKey("polls.id", ondelete="CASCADE"), nullable=False, index=True)
    option_id = Column(Integer, ForeignKey("poll_options.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    voted_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("poll_id", "option_id", "user_id", name="uq_poll_votes_unique"),
    )


# ---- Drafts / Pinned chats ----

class MessageDraft(Base):
    """Черновик сообщения в чате (один на пару user-chat-topic)."""
    __tablename__ = "message_drafts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(Integer, ForeignKey("chat_topics.id", ondelete="CASCADE"), nullable=True)
    text = Column(Text, nullable=True)
    reply_to_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class PinnedMessage(Base):
    """Закреплённые сообщения в чате (несколько штук, как в TG)."""
    __tablename__ = "pinned_messages"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    pinned_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    pinned_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("chat_id", "message_id", name="uq_pinned_messages_pair"),
    )


# =====================================================================
#  CALLS
# =====================================================================

class Call(Base):
    __tablename__ = "calls"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="SET NULL"), nullable=True, index=True)
    initiator_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    type = Column(SQLEnum(CallType), default=CallType.audio, nullable=False)
    status = Column(SQLEnum(CallStatus), default=CallStatus.ringing, nullable=False)
    is_video = Column(Boolean, default=False, nullable=False)
    is_group = Column(Boolean, default=False, nullable=False)

    started_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    answered_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    end_reason = Column(String(50), nullable=True)


class CallParticipant(Base):
    __tablename__ = "call_participants"

    id = Column(Integer, primary_key=True)
    call_id = Column(Integer, ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    joined_at = Column(DateTime(timezone=True), nullable=True)
    left_at = Column(DateTime(timezone=True), nullable=True)
    is_muted = Column(Boolean, default=False, nullable=False)
    is_video_on = Column(Boolean, default=False, nullable=False)
    is_screen_sharing = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("call_id", "user_id", name="uq_call_participants_pair"),
    )


# =====================================================================
#  NOTIFICATIONS / MUTE
# =====================================================================

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(50), nullable=False)        # message / mention / reaction / call / join_request ...
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=True)
    payload = Column(JSON, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class ChatMuteSetting(Base):
    """Настройки уведомлений конкретного чата (звук, превью, до какого времени muted)."""
    __tablename__ = "chat_mute_settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)

    is_muted = Column(Boolean, default=False, nullable=False)
    mute_until = Column(DateTime(timezone=True), nullable=True)
    show_previews = Column(Boolean, default=True, nullable=False)
    sound = Column(String(50), nullable=True)
    only_mentions = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "chat_id", name="uq_chat_mute_settings_pair"),
    )


# =====================================================================
#  HASHTAGS / SEARCH
# =====================================================================

class Hashtag(Base):
    __tablename__ = "hashtags"

    id = Column(Integer, primary_key=True)
    tag = Column(String(100), unique=True, nullable=False, index=True)
    usage_count = Column(Integer, default=0, nullable=False)


class MessageHashtag(Base):
    __tablename__ = "message_hashtags"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    hashtag_id = Column(Integer, ForeignKey("hashtags.id", ondelete="CASCADE"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("message_id", "hashtag_id", name="uq_message_hashtags_pair"),
    )


# =====================================================================
#  STORIES (TG 10.0+)
# =====================================================================

class StoryPrivacyType(str, Enum):
    everybody = "everybody"
    contacts = "contacts"
    close_friends = "close_friends"
    selected = "selected"


class Story(Base):
    __tablename__ = "stories"

    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="SET NULL"), nullable=True, index=True)  # сторис канала

    media_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)
    media_type = Column(String(20), nullable=False)  # photo / video
    duration = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    caption = Column(Text, nullable=True)
    entities = Column(JSON, nullable=True)

    privacy = Column(SQLEnum(StoryPrivacyType), default=StoryPrivacyType.everybody, nullable=False)
    allowed_user_ids = Column(JSON, nullable=True)   # для privacy=selected
    excluded_user_ids = Column(JSON, nullable=True)
    pinned = Column(Boolean, default=False, nullable=False)  # сохранена в профиле
    allow_replies = Column(Boolean, default=True, nullable=False)
    allow_reactions = Column(Boolean, default=True, nullable=False)
    allow_forwards = Column(Boolean, default=True, nullable=False)

    views_count = Column(Integer, default=0, nullable=False)
    reactions_count = Column(Integer, default=0, nullable=False)

    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class StoryView(Base):
    __tablename__ = "story_views"

    id = Column(Integer, primary_key=True)
    story_id = Column(Integer, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    viewed_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("story_id", "user_id", name="uq_story_views_pair"),
    )


class StoryReaction(Base):
    __tablename__ = "story_reactions"

    id = Column(Integer, primary_key=True)
    story_id = Column(Integer, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    emoji = Column(String(16), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("story_id", "user_id", name="uq_story_reactions_pair"),
    )


class CloseFriend(Base):
    """Список «близких друзей» — для StoryPrivacy=close_friends."""
    __tablename__ = "close_friends"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    friend_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("owner_id", "friend_id", name="uq_close_friends_pair"),
    )


# =====================================================================
#  BOTS
# =====================================================================

class Bot(Base):
    """Расширение профиля для is_bot=True пользователей."""
    __tablename__ = "bots"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    api_token = Column(String(120), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    about = Column(String(120), nullable=True)
    webhook_url = Column(String(500), nullable=True)

    supports_inline = Column(Boolean, default=False, nullable=False)
    inline_placeholder = Column(String(64), nullable=True)
    can_join_groups = Column(Boolean, default=True, nullable=False)
    can_read_all_group_messages = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class BotCommand(Base):
    """Команды бота (`/start`, `/help`)."""
    __tablename__ = "bot_commands"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    command = Column(String(40), nullable=False)
    description = Column(String(256), nullable=False)
    scope = Column(String(40), default="default", nullable=False)  # default / all_private_chats / all_group_chats / chat
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=True)

    __table_args__ = (
        UniqueConstraint("bot_id", "command", "scope", "chat_id", name="uq_bot_commands_unique"),
    )


class CallbackQuery(Base):
    """Нажатие на inline-кнопку с callback_data."""
    __tablename__ = "callback_queries"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True)
    chat_instance = Column(String(64), nullable=True)
    data = Column(String(64), nullable=True)
    answered = Column(Boolean, default=False, nullable=False)
    answer_text = Column(String(200), nullable=True)
    answer_show_alert = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class InlineQuery(Base):
    """Inline-запрос пользователя боту (`@bot search`)."""
    __tablename__ = "inline_queries"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    query = Column(String(256), nullable=False)
    offset = Column(String(64), nullable=True)
    chat_type = Column(String(20), nullable=True)
    answered = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


# =====================================================================
#  ADMIN LOG
# =====================================================================

class ChatAdminAction(str, Enum):
    member_promoted = "member_promoted"
    member_demoted = "member_demoted"
    member_kicked = "member_kicked"
    member_banned = "member_banned"
    member_unbanned = "member_unbanned"
    member_invited = "member_invited"
    member_joined = "member_joined"
    member_left = "member_left"
    member_restricted = "member_restricted"
    title_changed = "title_changed"
    description_changed = "description_changed"
    photo_changed = "photo_changed"
    photo_removed = "photo_removed"
    username_changed = "username_changed"
    permissions_changed = "permissions_changed"
    message_pinned = "message_pinned"
    message_unpinned = "message_unpinned"
    message_deleted = "message_deleted"
    message_edited = "message_edited"
    invite_created = "invite_created"
    invite_revoked = "invite_revoked"
    slow_mode_changed = "slow_mode_changed"
    history_visibility_changed = "history_visibility_changed"
    topic_created = "topic_created"
    topic_edited = "topic_edited"
    topic_closed = "topic_closed"
    topic_deleted = "topic_deleted"
    linked_chat_changed = "linked_chat_changed"


class ChatAdminLog(Base):
    """Журнал действий админов в чате (как «Recent actions» в TG)."""
    __tablename__ = "chat_admin_log"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    target_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(SQLEnum(ChatAdminAction), nullable=False, index=True)
    payload = Column(JSON, nullable=True)  # before/after значения, доп. поля
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


# =====================================================================
#  SECRET CHATS (E2E на стороне клиентов; на сервере храним только метаданные)
# =====================================================================

class SecretChatKey(Base):
    __tablename__ = "secret_chat_keys"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    public_key = Column(Text, nullable=False)        # клиентский публичный ключ
    key_fingerprint = Column(String(64), nullable=False)
    layer = Column(Integer, default=1, nullable=False)
    rekey_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", name="uq_secret_chat_keys_pair"),
    )


# =====================================================================
#  REPORTS / SPAM
# =====================================================================

class ReportTargetType(str, Enum):
    user = "user"
    message = "message"
    chat = "chat"
    story = "story"


class ReportReason(str, Enum):
    spam = "spam"
    violence = "violence"
    pornography = "pornography"
    child_abuse = "child_abuse"
    drugs = "drugs"
    personal_data = "personal_data"
    fake_account = "fake_account"
    copyright = "copyright"
    illegal = "illegal"
    other = "other"


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True)
    reporter_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    target_type = Column(SQLEnum(ReportTargetType), nullable=False, index=True)
    target_id = Column(Integer, nullable=False, index=True)
    reason = Column(SQLEnum(ReportReason), nullable=False)
    comment = Column(Text, nullable=True)
    status = Column(String(20), default="pending", nullable=False)  # pending / reviewed / actioned / dismissed
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


# =====================================================================
#  OTP CODES (логин по телефону/email кодом)
# =====================================================================

class OtpPurpose(str, Enum):
    login = "login"
    register = "register"
    password_reset = "password_reset"
    phone_change = "phone_change"
    email_change = "email_change"


class OtpCode(Base):
    __tablename__ = "otp_codes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    identifier = Column(String(255), nullable=False, index=True)  # email или phone
    code_hash = Column(String(255), nullable=False)
    purpose = Column(SQLEnum(OtpPurpose), nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=5, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


# =====================================================================
#  PEOPLE NEARBY
# =====================================================================

class UserGeoIndex(Base):
    """Текущая геолокация пользователя для функции «Люди рядом»."""
    __tablename__ = "user_geo_index"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


# =====================================================================
#  PROFILE PHOTO HISTORY
# =====================================================================

class UserAvatar(Base):
    __tablename__ = "user_avatars"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    file_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)
    is_current = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


# =====================================================================
#  BUSINESS ACCOUNTS
# =====================================================================

class BusinessAccount(Base):
    __tablename__ = "business_accounts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)

    location_name = Column(String(150), nullable=True)
    location_address = Column(String(255), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    timezone = Column(String(64), nullable=True)
    chat_link_text = Column(String(80), nullable=True)
    intro_title = Column(String(80), nullable=True)
    intro_description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class BusinessHours(Base):
    """Рабочие часы по дням недели (0=Mon ... 6=Sun)."""
    __tablename__ = "business_hours"

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("business_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    weekday = Column(Integer, nullable=False)             # 0..6
    open_minute = Column(Integer, nullable=False)         # минут от 00:00
    close_minute = Column(Integer, nullable=False)


class QuickReply(Base):
    """Шаблоны быстрых ответов (`/shortcut → текст`)."""
    __tablename__ = "quick_replies"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    shortcut = Column(String(40), nullable=False)
    text = Column(Text, nullable=True)
    media_url = Column(String(500), nullable=True)
    position = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "shortcut", name="uq_quick_replies_unique"),
    )


class GreetingMessage(Base):
    """Приветственное сообщение для бизнес-аккаунта новым контактам."""
    __tablename__ = "greeting_messages"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    text = Column(Text, nullable=False)
    no_activity_days = Column(Integer, default=7, nullable=False)
    only_for_non_contacts = Column(Boolean, default=True, nullable=False)


class AwayMessage(Base):
    """Автоответ «Я в отъезде» с расписанием."""
    __tablename__ = "away_messages"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    text = Column(Text, nullable=False)
    schedule_type = Column(String(32), default="always", nullable=False)  # always / outside_hours / custom
    custom_schedule = Column(JSON, nullable=True)
    only_for_contacts = Column(Boolean, default=False, nullable=False)


# =====================================================================
#  BANNED WORDS / ANTISPAM
# =====================================================================

class ChatBannedWord(Base):
    __tablename__ = "chat_banned_words"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    word = Column(String(64), nullable=False)
    is_regex = Column(Boolean, default=False, nullable=False)
    case_sensitive = Column(Boolean, default=False, nullable=False)
    added_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("chat_id", "word", name="uq_chat_banned_words_unique"),
    )
