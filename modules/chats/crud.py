"""CRUD-операции для модуля chats."""
import secrets
from datetime import datetime, timezone

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from models import (
    Chat,
    ChatType,
    ChatMember,
    ChatMemberRole,
    ChatAdminRights,
    ChatInvite,
    ChatJoinRequest,
    ChatTopic,
    ChatFolder,
    ChatFolderItem,
    ChatMuteSetting,
    ChatBannedWord,
    ChatAdminLog,
    ChatAdminAction,
    User,
)


# =====================================================================
#  Helpers
# =====================================================================

def utc() -> datetime:
    return datetime.now(timezone.utc)


def get_chat(db: Session, chat_id: int) -> Chat | None:
    return db.query(Chat).filter(Chat.id == chat_id).first()


def get_chat_by_username(db: Session, username: str) -> Chat | None:
    return db.query(Chat).filter(Chat.public_username == username).first()


def get_member(db: Session, chat_id: int, user_id: int) -> ChatMember | None:
    return (
        db.query(ChatMember)
        .filter(ChatMember.chat_id == chat_id, ChatMember.user_id == user_id)
        .first()
    )


def is_active_member(member: ChatMember | None) -> bool:
    return bool(member) and member.role not in (ChatMemberRole.left, ChatMemberRole.banned)


def get_admin_rights(db: Session, chat_id: int, user_id: int) -> ChatAdminRights | None:
    return (
        db.query(ChatAdminRights)
        .filter(ChatAdminRights.chat_id == chat_id, ChatAdminRights.user_id == user_id)
        .first()
    )


def can_admin(member: ChatMember | None) -> bool:
    """Может ли участник выполнять админские действия в чате."""
    return is_active_member(member) and member.role in (ChatMemberRole.creator, ChatMemberRole.admin)


# =====================================================================
#  Admin log
# =====================================================================

def log_admin(
    db: Session,
    *,
    chat_id: int,
    actor_id: int | None,
    action: ChatAdminAction,
    target_user_id: int | None = None,
    payload: dict | None = None,
) -> None:
    db.add(ChatAdminLog(
        chat_id=chat_id,
        actor_id=actor_id,
        target_user_id=target_user_id,
        action=action,
        payload=payload,
    ))
    # commit делается общим вызовом — оставляем под транзакцию вызывающего


def list_admin_log(
    db: Session,
    chat_id: int,
    *,
    limit: int = 50,
    before_id: int | None = None,
    actions: list[ChatAdminAction] | None = None,
    actor_id: int | None = None,
) -> list[ChatAdminLog]:
    q = db.query(ChatAdminLog).filter(ChatAdminLog.chat_id == chat_id)
    if before_id is not None:
        q = q.filter(ChatAdminLog.id < before_id)
    if actions:
        q = q.filter(ChatAdminLog.action.in_(actions))
    if actor_id is not None:
        q = q.filter(ChatAdminLog.actor_id == actor_id)
    return q.order_by(ChatAdminLog.id.desc()).limit(limit).all()


# =====================================================================
#  Members
# =====================================================================

def add_member(
    db: Session,
    chat: Chat,
    user_id: int,
    *,
    role: ChatMemberRole = ChatMemberRole.member,
    invited_by_id: int | None = None,
) -> ChatMember:
    member = get_member(db, chat.id, user_id)
    if member:
        # реактивируем, если он раньше вышел
        if member.role in (ChatMemberRole.left, ChatMemberRole.banned):
            member.role = role
            member.left_at = None
            chat.members_count = (chat.members_count or 0) + 1
        return member

    member = ChatMember(
        chat_id=chat.id,
        user_id=user_id,
        role=role,
        invited_by_id=invited_by_id,
    )
    db.add(member)
    chat.members_count = (chat.members_count or 0) + 1
    return member


def remove_member(db: Session, chat: Chat, user_id: int, *, ban: bool = False) -> bool:
    member = get_member(db, chat.id, user_id)
    if not member or not is_active_member(member):
        return False
    member.role = ChatMemberRole.banned if ban else ChatMemberRole.left
    member.left_at = utc()
    chat.members_count = max((chat.members_count or 1) - 1, 0)
    return True


def list_members(db: Session, chat_id: int, *, limit: int = 200, offset: int = 0):
    """Возвращает список (ChatMember, User) активных участников."""
    return (
        db.query(ChatMember, User)
        .join(User, User.id == ChatMember.user_id)
        .filter(
            ChatMember.chat_id == chat_id,
            ChatMember.role.notin_([ChatMemberRole.left, ChatMemberRole.banned]),
        )
        .order_by(ChatMember.joined_at.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def list_member_ids(db: Session, chat_id: int) -> list[int]:
    rows = (
        db.query(ChatMember.user_id)
        .filter(
            ChatMember.chat_id == chat_id,
            ChatMember.role.notin_([ChatMemberRole.left, ChatMemberRole.banned]),
        )
        .all()
    )
    return [r[0] for r in rows]


def change_role(
    db: Session,
    chat: Chat,
    user_id: int,
    *,
    role: ChatMemberRole,
    custom_title: str | None = None,
    restricted_until: datetime | None = None,
) -> ChatMember | None:
    member = get_member(db, chat.id, user_id)
    if not member:
        return None
    member.role = role
    if custom_title is not None:
        member.custom_title = custom_title
    if role == ChatMemberRole.restricted:
        member.restricted_until = restricted_until
    else:
        member.restricted_until = None
    return member


def upsert_admin_rights(
    db: Session,
    chat_id: int,
    user_id: int,
    **fields,
) -> ChatAdminRights:
    rights = get_admin_rights(db, chat_id, user_id)
    if not rights:
        rights = ChatAdminRights(chat_id=chat_id, user_id=user_id)
        db.add(rights)
    for key, value in fields.items():
        if value is not None:
            setattr(rights, key, value)
    return rights


# =====================================================================
#  Chats — create / list
# =====================================================================

def get_or_create_private_chat(db: Session, user_a: int, user_b: int) -> Chat:
    """1-на-1 чат между двумя пользователями. Если уже есть — возвращает его."""
    if user_a == user_b:
        # «Избранное» — saved chat
        existing = (
            db.query(Chat)
            .join(ChatMember, ChatMember.chat_id == Chat.id)
            .filter(Chat.type == ChatType.saved, ChatMember.user_id == user_a)
            .first()
        )
        if existing:
            return existing
        chat = Chat(type=ChatType.saved, creator_id=user_a, members_count=0)
        db.add(chat)
        db.flush()
        add_member(db, chat, user_a, role=ChatMemberRole.creator)
        db.commit()
        db.refresh(chat)
        return chat

    # Ищем существующий приватный чат с двумя нужными участниками
    sub_a = (
        db.query(ChatMember.chat_id)
        .filter(ChatMember.user_id == user_a)
    )
    sub_b = (
        db.query(ChatMember.chat_id)
        .filter(ChatMember.user_id == user_b)
    )
    chat = (
        db.query(Chat)
        .filter(
            Chat.type == ChatType.private,
            Chat.id.in_(sub_a),
            Chat.id.in_(sub_b),
        )
        .first()
    )
    if chat:
        return chat

    chat = Chat(type=ChatType.private, creator_id=user_a, members_count=0)
    db.add(chat)
    db.flush()
    add_member(db, chat, user_a, role=ChatMemberRole.member)
    add_member(db, chat, user_b, role=ChatMemberRole.member)
    db.commit()
    db.refresh(chat)
    return chat


def create_group(
    db: Session,
    *,
    creator_id: int,
    title: str,
    description: str | None,
    member_ids: list[int],
    is_supergroup: bool = False,
    is_forum: bool = False,
) -> Chat:
    chat = Chat(
        type=ChatType.supergroup if is_supergroup else ChatType.group,
        title=title,
        description=description,
        creator_id=creator_id,
        is_forum=is_forum and is_supergroup,
        members_count=0,
    )
    db.add(chat)
    db.flush()
    add_member(db, chat, creator_id, role=ChatMemberRole.creator)
    for uid in set(member_ids):
        if uid != creator_id:
            add_member(db, chat, uid, role=ChatMemberRole.member, invited_by_id=creator_id)

    if chat.is_forum:
        db.add(ChatTopic(
            chat_id=chat.id,
            creator_id=creator_id,
            title="General",
            is_general=True,
        ))

    db.commit()
    db.refresh(chat)
    return chat


def create_channel(
    db: Session,
    *,
    creator_id: int,
    title: str,
    description: str | None,
    public_username: str | None,
) -> Chat:
    chat = Chat(
        type=ChatType.channel,
        title=title,
        description=description,
        public_username=public_username,
        creator_id=creator_id,
        # У каналов писать могут только админы по умолчанию
        can_send_messages=False,
        members_count=0,
    )
    db.add(chat)
    db.flush()
    add_member(db, chat, creator_id, role=ChatMemberRole.creator)
    db.commit()
    db.refresh(chat)
    return chat


def update_chat(db: Session, chat: Chat, **fields) -> Chat:
    permissions = fields.pop("permissions", None)
    for key, value in fields.items():
        if value is not None:
            setattr(chat, key, value)
    if permissions is not None:
        for key, value in permissions.items():
            setattr(chat, key, value)
    return chat


def delete_chat(db: Session, chat: Chat) -> None:
    db.delete(chat)


def list_user_chats(
    db: Session,
    user_id: int,
    *,
    archived: bool | None = False,
    limit: int = 100,
    offset: int = 0,
):
    """
    Возвращает список (Chat, ChatMember) активных чатов пользователя.
    Сортировка: pinned сверху, дальше по последнему сообщению (id desc).
    """
    q = (
        db.query(Chat, ChatMember)
        .join(ChatMember, ChatMember.chat_id == Chat.id)
        .filter(
            ChatMember.user_id == user_id,
            ChatMember.role.notin_([ChatMemberRole.left, ChatMemberRole.banned]),
        )
    )
    if archived is not None:
        q = q.filter(ChatMember.is_archived.is_(archived))

    q = q.order_by(
        ChatMember.is_pinned.desc(),
        Chat.last_message_id.desc().nullslast(),
        Chat.id.desc(),
    )
    return q.offset(offset).limit(limit).all()


# =====================================================================
#  Invites
# =====================================================================

def create_invite(
    db: Session,
    chat_id: int,
    *,
    creator_id: int,
    name: str | None = None,
    member_limit: int | None = None,
    expires_at: datetime | None = None,
    requires_approval: bool = False,
) -> ChatInvite:
    invite = ChatInvite(
        chat_id=chat_id,
        creator_id=creator_id,
        code=secrets.token_urlsafe(12),
        name=name,
        member_limit=member_limit,
        expires_at=expires_at,
        requires_approval=requires_approval,
    )
    db.add(invite)
    return invite


def list_invites(db: Session, chat_id: int, *, include_revoked: bool = False) -> list[ChatInvite]:
    q = db.query(ChatInvite).filter(ChatInvite.chat_id == chat_id)
    if not include_revoked:
        q = q.filter(ChatInvite.is_revoked.is_(False))
    return q.order_by(ChatInvite.created_at.desc()).all()


def get_invite_by_code(db: Session, code: str) -> ChatInvite | None:
    return db.query(ChatInvite).filter(ChatInvite.code == code).first()


def revoke_invite(db: Session, invite_id: int) -> ChatInvite | None:
    invite = db.query(ChatInvite).filter(ChatInvite.id == invite_id).first()
    if not invite:
        return None
    invite.is_revoked = True
    return invite


def is_invite_active(invite: ChatInvite) -> tuple[bool, str | None]:
    if invite.is_revoked:
        return False, "revoked"
    if invite.expires_at:
        exp = invite.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < utc():
            return False, "expired"
    if invite.member_limit is not None and invite.usage_count >= invite.member_limit:
        return False, "limit_reached"
    return True, None


# =====================================================================
#  Join requests
# =====================================================================

def create_join_request(
    db: Session,
    chat_id: int,
    user_id: int,
    *,
    invite_id: int | None = None,
    bio: str | None = None,
) -> ChatJoinRequest:
    existing = (
        db.query(ChatJoinRequest)
        .filter(ChatJoinRequest.chat_id == chat_id, ChatJoinRequest.user_id == user_id)
        .first()
    )
    if existing:
        if existing.status == "pending":
            return existing
        existing.status = "pending"
        existing.invite_id = invite_id
        existing.bio = bio
        existing.decided_at = None
        existing.decided_by_id = None
        return existing
    req = ChatJoinRequest(
        chat_id=chat_id,
        user_id=user_id,
        invite_id=invite_id,
        bio=bio,
    )
    db.add(req)
    return req


def list_join_requests(db: Session, chat_id: int) -> list[ChatJoinRequest]:
    return (
        db.query(ChatJoinRequest)
        .filter(ChatJoinRequest.chat_id == chat_id, ChatJoinRequest.status == "pending")
        .order_by(ChatJoinRequest.created_at.asc())
        .all()
    )


def decide_join_request(
    db: Session,
    request_id: int,
    *,
    decided_by_id: int,
    approve: bool,
) -> ChatJoinRequest | None:
    req = db.query(ChatJoinRequest).filter(ChatJoinRequest.id == request_id).first()
    if not req or req.status != "pending":
        return None
    req.status = "approved" if approve else "declined"
    req.decided_at = utc()
    req.decided_by_id = decided_by_id
    return req


# =====================================================================
#  Topics
# =====================================================================

def create_topic(
    db: Session,
    chat_id: int,
    creator_id: int,
    *,
    title: str,
    icon_color: str | None = None,
    icon_emoji: str | None = None,
) -> ChatTopic:
    topic = ChatTopic(
        chat_id=chat_id,
        creator_id=creator_id,
        title=title,
        icon_color=icon_color,
        icon_emoji=icon_emoji,
    )
    db.add(topic)
    return topic


def list_topics(db: Session, chat_id: int) -> list[ChatTopic]:
    return (
        db.query(ChatTopic)
        .filter(ChatTopic.chat_id == chat_id)
        .order_by(ChatTopic.is_general.desc(), ChatTopic.id.asc())
        .all()
    )


def get_topic(db: Session, chat_id: int, topic_id: int) -> ChatTopic | None:
    return (
        db.query(ChatTopic)
        .filter(ChatTopic.chat_id == chat_id, ChatTopic.id == topic_id)
        .first()
    )


def update_topic(db: Session, topic: ChatTopic, **fields) -> ChatTopic:
    for key, value in fields.items():
        if value is not None:
            setattr(topic, key, value)
    return topic


def delete_topic(db: Session, topic: ChatTopic) -> None:
    db.delete(topic)


# =====================================================================
#  Folders
# =====================================================================

def list_folders(db: Session, user_id: int) -> list[ChatFolder]:
    return (
        db.query(ChatFolder)
        .filter(ChatFolder.user_id == user_id)
        .order_by(ChatFolder.position.asc(), ChatFolder.id.asc())
        .all()
    )


def get_folder(db: Session, user_id: int, folder_id: int) -> ChatFolder | None:
    return (
        db.query(ChatFolder)
        .filter(ChatFolder.id == folder_id, ChatFolder.user_id == user_id)
        .first()
    )


def create_folder(db: Session, user_id: int, **fields) -> ChatFolder:
    folder = ChatFolder(user_id=user_id, **fields)
    db.add(folder)
    return folder


def update_folder(db: Session, folder: ChatFolder, **fields) -> ChatFolder:
    for key, value in fields.items():
        if value is not None:
            setattr(folder, key, value)
    return folder


def delete_folder(db: Session, folder: ChatFolder) -> None:
    db.delete(folder)


def get_folder_items(db: Session, folder_id: int) -> list[ChatFolderItem]:
    return db.query(ChatFolderItem).filter(ChatFolderItem.folder_id == folder_id).all()


def add_folder_item(db: Session, folder_id: int, chat_id: int, *, is_excluded: bool = False) -> ChatFolderItem:
    existing = (
        db.query(ChatFolderItem)
        .filter(ChatFolderItem.folder_id == folder_id, ChatFolderItem.chat_id == chat_id)
        .first()
    )
    if existing:
        existing.is_excluded = is_excluded
        return existing
    item = ChatFolderItem(folder_id=folder_id, chat_id=chat_id, is_excluded=is_excluded)
    db.add(item)
    return item


def remove_folder_item(db: Session, folder_id: int, chat_id: int) -> bool:
    item = (
        db.query(ChatFolderItem)
        .filter(ChatFolderItem.folder_id == folder_id, ChatFolderItem.chat_id == chat_id)
        .first()
    )
    if not item:
        return False
    db.delete(item)
    return True


# =====================================================================
#  Mute / Pin / Archive
# =====================================================================

def set_mute(
    db: Session,
    user_id: int,
    chat_id: int,
    *,
    is_muted: bool,
    mute_until: datetime | None = None,
    show_previews: bool | None = None,
    only_mentions: bool | None = None,
    sound: str | None = None,
) -> ChatMuteSetting:
    setting = (
        db.query(ChatMuteSetting)
        .filter(ChatMuteSetting.user_id == user_id, ChatMuteSetting.chat_id == chat_id)
        .first()
    )
    if not setting:
        setting = ChatMuteSetting(user_id=user_id, chat_id=chat_id)
        db.add(setting)
    setting.is_muted = is_muted
    setting.mute_until = mute_until
    if show_previews is not None:
        setting.show_previews = show_previews
    if only_mentions is not None:
        setting.only_mentions = only_mentions
    if sound is not None:
        setting.sound = sound

    member = get_member(db, chat_id, user_id)
    if member:
        member.is_muted = is_muted
        member.mute_until = mute_until
    return setting


def is_chat_muted(db: Session, user_id: int, chat_id: int) -> bool:
    member = get_member(db, chat_id, user_id)
    if member and member.is_muted:
        if not member.mute_until:
            return True
        until = member.mute_until
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        return until > utc()
    return False


def set_pinned(db: Session, user_id: int, chat_id: int, pinned: bool) -> bool:
    member = get_member(db, chat_id, user_id)
    if not member:
        return False
    member.is_pinned = pinned
    return True


def set_archived(db: Session, user_id: int, chat_id: int, archived: bool) -> bool:
    member = get_member(db, chat_id, user_id)
    if not member:
        return False
    member.is_archived = archived
    return True


# =====================================================================
#  Banned words
# =====================================================================

def add_banned_word(
    db: Session,
    chat_id: int,
    *,
    word: str,
    is_regex: bool = False,
    case_sensitive: bool = False,
    added_by_id: int | None = None,
) -> ChatBannedWord:
    existing = (
        db.query(ChatBannedWord)
        .filter(ChatBannedWord.chat_id == chat_id, ChatBannedWord.word == word)
        .first()
    )
    if existing:
        existing.is_regex = is_regex
        existing.case_sensitive = case_sensitive
        return existing
    record = ChatBannedWord(
        chat_id=chat_id,
        word=word,
        is_regex=is_regex,
        case_sensitive=case_sensitive,
        added_by_id=added_by_id,
    )
    db.add(record)
    return record


def list_banned_words(db: Session, chat_id: int) -> list[ChatBannedWord]:
    return (
        db.query(ChatBannedWord)
        .filter(ChatBannedWord.chat_id == chat_id)
        .order_by(ChatBannedWord.id.asc())
        .all()
    )


def remove_banned_word(db: Session, chat_id: int, word_id: int) -> bool:
    record = (
        db.query(ChatBannedWord)
        .filter(ChatBannedWord.chat_id == chat_id, ChatBannedWord.id == word_id)
        .first()
    )
    if not record:
        return False
    db.delete(record)
    return True
