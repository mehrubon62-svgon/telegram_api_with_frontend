"""HTTP API модуля chats.

Покрывает:
  • создание/чтение/апдейт/удаление чатов (private/group/supergroup/channel)
  • список чатов пользователя с unread/pinned/archived
  • участники, роли, права админов
  • инвайт-ссылки и заявки на вступление
  • топики (форумные супергруппы)
  • папки чатов
  • mute / pin / archive отдельного чата для пользователя
  • banned words
  • admin log
  • связка канал ↔ обсуждение
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from models import (
    get_db,
    User,
    Chat,
    ChatType,
    ChatMember,
    ChatMemberRole,
    ChatAdminAction,
)
from dependencies import get_current_user
from modules.users.crud import get_user_by_id

from modules.chats import crud
from modules.chats.schemas import (
    ChatOut,
    ChatPermissions,
    ChatListItem,
    CreatePrivateChat,
    CreateGroupChat,
    CreateChannel,
    ChatUpdate,
    MemberOut,
    AddMembers,
    ChangeRole,
    AdminRightsOut,
    AdminRightsUpdate,
    InviteCreate,
    InviteOut,
    JoinRequestOut,
    JoinRequestCreate,
    TopicCreate,
    TopicUpdate,
    TopicOut,
    FolderCreate,
    FolderUpdate,
    FolderOut,
    FolderItem,
    MuteUpdate,
    PinUpdate,
    ArchiveUpdate,
    LinkedChatUpdate,
    BannedWordCreate,
    BannedWordOut,
    AdminLogOut,
)


router = APIRouter(prefix="/chats", tags=["Chats"])


# =====================================================================
#  Helpers
# =====================================================================

def _serialize_chat(chat: Chat) -> ChatOut:
    return ChatOut(
        id=chat.id,
        type=chat.type,
        title=chat.title,
        description=chat.description,
        avatar_url=chat.avatar_url,
        public_username=chat.public_username,
        creator_id=chat.creator_id,
        pinned_message_id=chat.pinned_message_id,
        last_message_id=chat.last_message_id,
        linked_chat_id=chat.linked_chat_id,
        is_forum=chat.is_forum,
        slow_mode_seconds=chat.slow_mode_seconds,
        is_history_visible=chat.is_history_visible,
        is_join_by_request=chat.is_join_by_request,
        members_count=chat.members_count or 0,
        permissions=ChatPermissions(
            can_send_messages=chat.can_send_messages,
            can_send_media=chat.can_send_media,
            can_send_polls=chat.can_send_polls,
            can_add_users=chat.can_add_users,
            can_pin_messages=chat.can_pin_messages,
            can_change_info=chat.can_change_info,
        ),
        created_at=chat.created_at,
    )


def _serialize_invite(invite, base_url: str = "") -> InviteOut:
    return InviteOut(
        id=invite.id,
        code=invite.code,
        invite_url=f"{base_url}/chats/join/{invite.code}",
        name=invite.name,
        member_limit=invite.member_limit,
        expires_at=invite.expires_at,
        requires_approval=invite.requires_approval,
        usage_count=invite.usage_count,
        is_revoked=invite.is_revoked,
        creator_id=invite.creator_id,
        created_at=invite.created_at,
    )


def _serialize_folder(folder, items) -> FolderOut:
    chat_ids = [i.chat_id for i in items if not i.is_excluded]
    excluded = [i.chat_id for i in items if i.is_excluded]
    return FolderOut(
        id=folder.id,
        title=folder.title,
        icon=folder.icon,
        position=folder.position,
        include_contacts=folder.include_contacts,
        include_non_contacts=folder.include_non_contacts,
        include_groups=folder.include_groups,
        include_channels=folder.include_channels,
        include_bots=folder.include_bots,
        exclude_muted=folder.exclude_muted,
        exclude_read=folder.exclude_read,
        exclude_archived=folder.exclude_archived,
        chat_ids=chat_ids,
        excluded_chat_ids=excluded,
    )


def _ensure_member(chat_id: int, user_id: int, db: Session) -> ChatMember:
    member = crud.get_member(db, chat_id, user_id)
    if not member or not crud.is_active_member(member):
        raise HTTPException(status_code=403, detail="Not a member of this chat")
    return member


def _ensure_admin(chat_id: int, user_id: int, db: Session) -> ChatMember:
    member = _ensure_member(chat_id, user_id, db)
    if not crud.can_admin(member):
        raise HTTPException(status_code=403, detail="Admins only")
    return member


def _ensure_creator(chat_id: int, user_id: int, db: Session) -> ChatMember:
    member = _ensure_member(chat_id, user_id, db)
    if member.role != ChatMemberRole.creator:
        raise HTTPException(status_code=403, detail="Creator only")
    return member


def _get_chat_or_404(db: Session, chat_id: int) -> Chat:
    chat = crud.get_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


# =====================================================================
#  Create chats
# =====================================================================

@router.post("/private", response_model=ChatOut)
def open_private_chat(
    data: CreatePrivateChat,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    target = get_user_by_id(db, data.user_id)
    if not target or not target.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    chat = crud.get_or_create_private_chat(db, user.id, target.id)
    return _serialize_chat(chat)


@router.post("/group", response_model=ChatOut, status_code=201)
def create_group_chat(
    data: CreateGroupChat,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = crud.create_group(
        db,
        creator_id=user.id,
        title=data.title,
        description=data.description,
        member_ids=data.member_ids,
        is_supergroup=data.is_supergroup,
        is_forum=data.is_forum,
    )
    return _serialize_chat(chat)


@router.post("/channel", response_model=ChatOut, status_code=201)
def create_channel(
    data: CreateChannel,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if data.public_username and crud.get_chat_by_username(db, data.public_username):
        raise HTTPException(status_code=400, detail="Username already taken")
    chat = crud.create_channel(
        db,
        creator_id=user.id,
        title=data.title,
        description=data.description,
        public_username=data.public_username,
    )
    return _serialize_chat(chat)


# =====================================================================
#  My chats
# =====================================================================

@router.get("", response_model=list[ChatListItem])
def my_chats(
    archived: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = crud.list_user_chats(db, user.id, archived=archived, limit=limit, offset=offset)
    result = []
    for chat, member in rows:
        result.append(ChatListItem(
            chat=_serialize_chat(chat),
            is_pinned=member.is_pinned,
            is_archived=member.is_archived,
            is_muted=member.is_muted,
            unread_count=member.unread_count or 0,
            unread_mentions_count=member.unread_mentions_count or 0,
            last_read_message_id=member.last_read_message_id,
        ))
    return result


@router.get("/{chat_id}", response_model=ChatOut)
def get_chat(
    chat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = _get_chat_or_404(db, chat_id)
    if chat.type not in (ChatType.channel,) or not chat.public_username:
        _ensure_member(chat_id, user.id, db)
    return _serialize_chat(chat)


@router.put("/{chat_id}", response_model=ChatOut)
def update_chat(
    chat_id: int,
    data: ChatUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = _get_chat_or_404(db, chat_id)
    _ensure_admin(chat_id, user.id, db)

    fields = data.model_dump(exclude_unset=True)
    perms = fields.pop("permissions", None)

    # username уникальность
    if "public_username" in fields and fields["public_username"]:
        existing = crud.get_chat_by_username(db, fields["public_username"])
        if existing and existing.id != chat.id:
            raise HTTPException(status_code=400, detail="Username already taken")

    # snapshot для admin-log
    before_title = chat.title
    before_desc = chat.description
    before_avatar = chat.avatar_url
    before_username = chat.public_username

    crud.update_chat(db, chat, permissions=perms, **fields)

    if "title" in fields and fields["title"] != before_title:
        crud.log_admin(db, chat_id=chat.id, actor_id=user.id, action=ChatAdminAction.title_changed,
                       payload={"before": before_title, "after": fields["title"]})
    if "description" in fields and fields["description"] != before_desc:
        crud.log_admin(db, chat_id=chat.id, actor_id=user.id, action=ChatAdminAction.description_changed,
                       payload={"before": before_desc, "after": fields["description"]})
    if "avatar_url" in fields and fields["avatar_url"] != before_avatar:
        action = ChatAdminAction.photo_removed if not fields["avatar_url"] else ChatAdminAction.photo_changed
        crud.log_admin(db, chat_id=chat.id, actor_id=user.id, action=action)
    if "public_username" in fields and fields["public_username"] != before_username:
        crud.log_admin(db, chat_id=chat.id, actor_id=user.id, action=ChatAdminAction.username_changed,
                       payload={"before": before_username, "after": fields["public_username"]})
    if "slow_mode_seconds" in fields:
        crud.log_admin(db, chat_id=chat.id, actor_id=user.id, action=ChatAdminAction.slow_mode_changed,
                       payload={"value": fields["slow_mode_seconds"]})
    if "is_history_visible" in fields:
        crud.log_admin(db, chat_id=chat.id, actor_id=user.id, action=ChatAdminAction.history_visibility_changed,
                       payload={"value": fields["is_history_visible"]})
    if perms is not None:
        crud.log_admin(db, chat_id=chat.id, actor_id=user.id, action=ChatAdminAction.permissions_changed,
                       payload=perms)

    db.commit()
    db.refresh(chat)
    return _serialize_chat(chat)


@router.delete("/{chat_id}")
def delete_chat(
    chat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = _get_chat_or_404(db, chat_id)
    _ensure_creator(chat_id, user.id, db)
    crud.delete_chat(db, chat)
    db.commit()
    return {"detail": "Chat deleted"}


@router.post("/{chat_id}/leave")
def leave_chat(
    chat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = _get_chat_or_404(db, chat_id)
    member = _ensure_member(chat_id, user.id, db)
    if member.role == ChatMemberRole.creator and chat.type != ChatType.private:
        raise HTTPException(status_code=400, detail="Creator must transfer ownership before leaving")
    crud.remove_member(db, chat, user.id)
    crud.log_admin(db, chat_id=chat.id, actor_id=user.id, action=ChatAdminAction.member_left, target_user_id=user.id)
    db.commit()
    return {"detail": "Left chat"}


# =====================================================================
#  Members
# =====================================================================

@router.get("/{chat_id}/members", response_model=list[MemberOut])
def list_members(
    chat_id: int,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_member(chat_id, user.id, db)
    rows = crud.list_members(db, chat_id, limit=limit, offset=offset)
    return [
        MemberOut(
            user_id=u.id,
            username=u.username,
            full_name=u.full_name,
            avatar_url=u.avatar_url,
            role=m.role,
            custom_title=m.custom_title,
            is_muted=m.is_muted,
            joined_at=m.joined_at,
            can_send_messages=m.can_send_messages,
            can_send_media=m.can_send_media,
            restricted_until=m.restricted_until,
        )
        for m, u in rows
    ]


@router.post("/{chat_id}/members", response_model=list[MemberOut])
def add_members(
    chat_id: int,
    data: AddMembers,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = _get_chat_or_404(db, chat_id)
    member = _ensure_member(chat_id, user.id, db)
    if not (crud.can_admin(member) or chat.can_add_users):
        raise HTTPException(status_code=403, detail="Cannot add users")

    added = []
    for uid in data.user_ids:
        target = get_user_by_id(db, uid)
        if not target or not target.is_active:
            continue
        m = crud.add_member(db, chat, uid, invited_by_id=user.id)
        crud.log_admin(db, chat_id=chat.id, actor_id=user.id,
                       action=ChatAdminAction.member_invited, target_user_id=uid)
        added.append((m, target))
    db.commit()
    return [
        MemberOut(
            user_id=u.id,
            username=u.username,
            full_name=u.full_name,
            avatar_url=u.avatar_url,
            role=m.role,
            custom_title=m.custom_title,
            is_muted=m.is_muted,
            joined_at=m.joined_at,
            can_send_messages=m.can_send_messages,
            can_send_media=m.can_send_media,
            restricted_until=m.restricted_until,
        )
        for m, u in added
    ]


@router.delete("/{chat_id}/members/{user_id}")
def kick_member(
    chat_id: int,
    user_id: int,
    ban: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = _get_chat_or_404(db, chat_id)
    actor = _ensure_admin(chat_id, user.id, db)
    target = crud.get_member(db, chat_id, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")
    if target.role == ChatMemberRole.creator:
        raise HTTPException(status_code=403, detail="Cannot remove creator")
    if target.role == ChatMemberRole.admin and actor.role != ChatMemberRole.creator:
        raise HTTPException(status_code=403, detail="Only creator can remove admins")

    crud.remove_member(db, chat, user_id, ban=ban)
    crud.log_admin(
        db,
        chat_id=chat.id,
        actor_id=user.id,
        action=ChatAdminAction.member_banned if ban else ChatAdminAction.member_kicked,
        target_user_id=user_id,
    )
    db.commit()
    return {"detail": "Member removed"}


@router.post("/{chat_id}/members/{user_id}/role", response_model=MemberOut)
def change_member_role(
    chat_id: int,
    user_id: int,
    data: ChangeRole,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = _get_chat_or_404(db, chat_id)
    actor = _ensure_member(chat_id, user.id, db)
    if actor.role != ChatMemberRole.creator:
        # admin может только restrict’ить, но не promote
        if data.role in (ChatMemberRole.admin, ChatMemberRole.creator):
            raise HTTPException(status_code=403, detail="Only creator can promote admins")
        if not crud.can_admin(actor):
            raise HTTPException(status_code=403, detail="Admins only")

    target = crud.get_member(db, chat_id, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")
    if target.role == ChatMemberRole.creator:
        raise HTTPException(status_code=403, detail="Cannot change role of creator")

    before_role = target.role
    crud.change_role(
        db, chat, user_id,
        role=data.role,
        custom_title=data.custom_title,
        restricted_until=data.restricted_until,
    )
    if data.role == ChatMemberRole.admin:
        action = ChatAdminAction.member_promoted
    elif before_role == ChatMemberRole.admin and data.role == ChatMemberRole.member:
        action = ChatAdminAction.member_demoted
    elif data.role == ChatMemberRole.restricted:
        action = ChatAdminAction.member_restricted
    elif data.role == ChatMemberRole.banned:
        action = ChatAdminAction.member_banned
    else:
        action = ChatAdminAction.permissions_changed
    crud.log_admin(db, chat_id=chat.id, actor_id=user.id, action=action,
                   target_user_id=user_id, payload={"before": before_role.value, "after": data.role.value})
    db.commit()

    target = crud.get_member(db, chat_id, user_id)
    target_user = get_user_by_id(db, user_id)
    return MemberOut(
        user_id=target_user.id,
        username=target_user.username,
        full_name=target_user.full_name,
        avatar_url=target_user.avatar_url,
        role=target.role,
        custom_title=target.custom_title,
        is_muted=target.is_muted,
        joined_at=target.joined_at,
        can_send_messages=target.can_send_messages,
        can_send_media=target.can_send_media,
        restricted_until=target.restricted_until,
    )


@router.get("/{chat_id}/admin-rights/{user_id}", response_model=AdminRightsOut)
def get_member_rights(
    chat_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(chat_id, user.id, db)
    rights = crud.get_admin_rights(db, chat_id, user_id)
    if not rights:
        raise HTTPException(status_code=404, detail="No admin rights set")
    return rights


@router.put("/{chat_id}/admin-rights/{user_id}", response_model=AdminRightsOut)
def set_member_rights(
    chat_id: int,
    user_id: int,
    data: AdminRightsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_creator(chat_id, user.id, db)  # тонкие права меняет только creator
    target = crud.get_member(db, chat_id, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")
    rights = crud.upsert_admin_rights(db, chat_id, user_id, **data.model_dump(exclude_unset=True))
    crud.log_admin(db, chat_id=chat_id, actor_id=user.id,
                   action=ChatAdminAction.permissions_changed, target_user_id=user_id,
                   payload=data.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(rights)
    return rights


# =====================================================================
#  Invites
# =====================================================================

@router.get("/{chat_id}/invites", response_model=list[InviteOut])
def list_chat_invites(
    chat_id: int,
    include_revoked: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(chat_id, user.id, db)
    return [_serialize_invite(i) for i in crud.list_invites(db, chat_id, include_revoked=include_revoked)]


@router.post("/{chat_id}/invites", response_model=InviteOut, status_code=201)
def create_chat_invite(
    chat_id: int,
    data: InviteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(chat_id, user.id, db)
    invite = crud.create_invite(
        db, chat_id,
        creator_id=user.id,
        name=data.name,
        member_limit=data.member_limit,
        expires_at=data.expires_at,
        requires_approval=data.requires_approval,
    )
    crud.log_admin(db, chat_id=chat_id, actor_id=user.id, action=ChatAdminAction.invite_created,
                   payload={"code": invite.code, "name": invite.name})
    db.commit()
    db.refresh(invite)
    return _serialize_invite(invite)


@router.delete("/{chat_id}/invites/{invite_id}")
def revoke_chat_invite(
    chat_id: int,
    invite_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(chat_id, user.id, db)
    invite = crud.revoke_invite(db, invite_id)
    if not invite or invite.chat_id != chat_id:
        raise HTTPException(status_code=404, detail="Invite not found")
    crud.log_admin(db, chat_id=chat_id, actor_id=user.id, action=ChatAdminAction.invite_revoked,
                   payload={"code": invite.code})
    db.commit()
    return {"detail": "Invite revoked"}


@router.post("/join/{code}", response_model=ChatOut)
def join_by_invite(
    code: str,
    request_data: JoinRequestCreate | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    invite = crud.get_invite_by_code(db, code)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    active, reason = crud.is_invite_active(invite)
    if not active:
        raise HTTPException(status_code=400, detail=f"Invite is {reason}")

    chat = _get_chat_or_404(db, invite.chat_id)
    existing = crud.get_member(db, chat.id, user.id)
    if existing and crud.is_active_member(existing):
        return _serialize_chat(chat)

    if invite.requires_approval or chat.is_join_by_request:
        crud.create_join_request(db, chat.id, user.id, invite_id=invite.id,
                                 bio=request_data.bio if request_data else None)
        db.commit()
        raise HTTPException(status_code=202, detail="Join request submitted")

    crud.add_member(db, chat, user.id, invited_by_id=invite.creator_id)
    invite.usage_count += 1
    crud.log_admin(db, chat_id=chat.id, actor_id=user.id,
                   action=ChatAdminAction.member_joined, target_user_id=user.id,
                   payload={"via_invite": invite.code})
    db.commit()
    db.refresh(chat)
    return _serialize_chat(chat)


# =====================================================================
#  Join requests
# =====================================================================

@router.get("/{chat_id}/join-requests", response_model=list[JoinRequestOut])
def list_chat_join_requests(
    chat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(chat_id, user.id, db)
    return crud.list_join_requests(db, chat_id)


@router.post("/{chat_id}/join-requests/{request_id}/approve")
def approve_join_request(
    chat_id: int,
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = _get_chat_or_404(db, chat_id)
    _ensure_admin(chat_id, user.id, db)
    req = crud.decide_join_request(db, request_id, decided_by_id=user.id, approve=True)
    if not req or req.chat_id != chat_id:
        raise HTTPException(status_code=404, detail="Request not found")
    crud.add_member(db, chat, req.user_id, invited_by_id=user.id)
    crud.log_admin(db, chat_id=chat.id, actor_id=user.id,
                   action=ChatAdminAction.member_joined, target_user_id=req.user_id,
                   payload={"via_request": req.id})
    db.commit()
    return {"detail": "Approved"}


@router.post("/{chat_id}/join-requests/{request_id}/decline")
def decline_join_request(
    chat_id: int,
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(chat_id, user.id, db)
    req = crud.decide_join_request(db, request_id, decided_by_id=user.id, approve=False)
    if not req or req.chat_id != chat_id:
        raise HTTPException(status_code=404, detail="Request not found")
    db.commit()
    return {"detail": "Declined"}


# =====================================================================
#  Topics
# =====================================================================

@router.get("/{chat_id}/topics", response_model=list[TopicOut])
def list_chat_topics(
    chat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_member(chat_id, user.id, db)
    return crud.list_topics(db, chat_id)


@router.post("/{chat_id}/topics", response_model=TopicOut, status_code=201)
def create_chat_topic(
    chat_id: int,
    data: TopicCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = _get_chat_or_404(db, chat_id)
    if not chat.is_forum:
        raise HTTPException(status_code=400, detail="Chat is not a forum")
    _ensure_admin(chat_id, user.id, db)
    topic = crud.create_topic(db, chat_id, user.id,
                              title=data.title, icon_color=data.icon_color, icon_emoji=data.icon_emoji)
    crud.log_admin(db, chat_id=chat_id, actor_id=user.id,
                   action=ChatAdminAction.topic_created, payload={"title": data.title})
    db.commit()
    db.refresh(topic)
    return topic


@router.put("/{chat_id}/topics/{topic_id}", response_model=TopicOut)
def edit_chat_topic(
    chat_id: int,
    topic_id: int,
    data: TopicUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(chat_id, user.id, db)
    topic = crud.get_topic(db, chat_id, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    crud.update_topic(db, topic, **data.model_dump(exclude_unset=True))
    crud.log_admin(db, chat_id=chat_id, actor_id=user.id,
                   action=ChatAdminAction.topic_edited, payload={"topic_id": topic_id})
    db.commit()
    db.refresh(topic)
    return topic


@router.delete("/{chat_id}/topics/{topic_id}")
def delete_chat_topic(
    chat_id: int,
    topic_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(chat_id, user.id, db)
    topic = crud.get_topic(db, chat_id, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    if topic.is_general:
        raise HTTPException(status_code=400, detail="Cannot delete General topic")
    crud.delete_topic(db, topic)
    crud.log_admin(db, chat_id=chat_id, actor_id=user.id,
                   action=ChatAdminAction.topic_deleted, payload={"topic_id": topic_id})
    db.commit()
    return {"detail": "Topic deleted"}


# =====================================================================
#  Mute / Pin / Archive (per-user state)
# =====================================================================

@router.put("/{chat_id}/mute")
def update_chat_mute(
    chat_id: int,
    data: MuteUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_member(chat_id, user.id, db)
    crud.set_mute(
        db, user.id, chat_id,
        is_muted=data.is_muted,
        mute_until=data.mute_until,
        show_previews=data.show_previews,
        only_mentions=data.only_mentions,
        sound=data.sound,
    )
    db.commit()
    return {"detail": "Mute updated"}


@router.put("/{chat_id}/pin")
def update_chat_pinned_in_list(
    chat_id: int,
    data: PinUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_member(chat_id, user.id, db)
    crud.set_pinned(db, user.id, chat_id, data.is_pinned)
    db.commit()
    return {"detail": "Updated"}


@router.put("/{chat_id}/archive")
def update_chat_archived(
    chat_id: int,
    data: ArchiveUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_member(chat_id, user.id, db)
    crud.set_archived(db, user.id, chat_id, data.is_archived)
    db.commit()
    return {"detail": "Updated"}


# =====================================================================
#  Linked chat (channel ↔ discussion)
# =====================================================================

@router.put("/{chat_id}/linked", response_model=ChatOut)
def update_linked_chat(
    chat_id: int,
    data: LinkedChatUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = _get_chat_or_404(db, chat_id)
    _ensure_creator(chat_id, user.id, db)
    if data.linked_chat_id is not None:
        target = crud.get_chat(db, data.linked_chat_id)
        if not target:
            raise HTTPException(status_code=404, detail="Linked chat not found")
        # обычно: канал ↔ супергруппа
        if {chat.type, target.type} != {ChatType.channel, ChatType.supergroup}:
            raise HTTPException(status_code=400, detail="Linking only allowed between channel and supergroup")
    chat.linked_chat_id = data.linked_chat_id
    crud.log_admin(db, chat_id=chat.id, actor_id=user.id,
                   action=ChatAdminAction.linked_chat_changed,
                   payload={"linked_chat_id": data.linked_chat_id})
    db.commit()
    db.refresh(chat)
    return _serialize_chat(chat)


# =====================================================================
#  Banned words
# =====================================================================

@router.get("/{chat_id}/banned-words", response_model=list[BannedWordOut])
def list_chat_banned_words(
    chat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(chat_id, user.id, db)
    return crud.list_banned_words(db, chat_id)


@router.post("/{chat_id}/banned-words", response_model=BannedWordOut, status_code=201)
def add_chat_banned_word(
    chat_id: int,
    data: BannedWordCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(chat_id, user.id, db)
    record = crud.add_banned_word(
        db, chat_id,
        word=data.word, is_regex=data.is_regex, case_sensitive=data.case_sensitive,
        added_by_id=user.id,
    )
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{chat_id}/banned-words/{word_id}")
def remove_chat_banned_word(
    chat_id: int,
    word_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(chat_id, user.id, db)
    if not crud.remove_banned_word(db, chat_id, word_id):
        raise HTTPException(status_code=404, detail="Word not found")
    db.commit()
    return {"detail": "Removed"}


# =====================================================================
#  Admin log
# =====================================================================

@router.get("/{chat_id}/admin-log", response_model=list[AdminLogOut])
def get_admin_log(
    chat_id: int,
    limit: int = Query(50, ge=1, le=200),
    before_id: int | None = Query(None),
    actor_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_admin(chat_id, user.id, db)
    return crud.list_admin_log(db, chat_id, limit=limit, before_id=before_id, actor_id=actor_id)


# =====================================================================
#  Folders (для пользователя — вне конкретного chat_id)
# =====================================================================

folders_router = APIRouter(prefix="/folders", tags=["Chat Folders"])


@folders_router.get("", response_model=list[FolderOut])
def list_my_folders(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    folders = crud.list_folders(db, user.id)
    result = []
    for f in folders:
        items = crud.get_folder_items(db, f.id)
        result.append(_serialize_folder(f, items))
    return result


@folders_router.post("", response_model=FolderOut, status_code=201)
def create_my_folder(
    data: FolderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    folder = crud.create_folder(db, user.id, **data.model_dump())
    db.commit()
    db.refresh(folder)
    return _serialize_folder(folder, [])


@folders_router.put("/{folder_id}", response_model=FolderOut)
def update_my_folder(
    folder_id: int,
    data: FolderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    folder = crud.get_folder(db, user.id, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    crud.update_folder(db, folder, **data.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(folder)
    items = crud.get_folder_items(db, folder.id)
    return _serialize_folder(folder, items)


@folders_router.delete("/{folder_id}")
def delete_my_folder(
    folder_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    folder = crud.get_folder(db, user.id, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    crud.delete_folder(db, folder)
    db.commit()
    return {"detail": "Folder deleted"}


@folders_router.post("/{folder_id}/items")
def add_chat_to_folder(
    folder_id: int,
    item: FolderItem,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    folder = crud.get_folder(db, user.id, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    crud.add_folder_item(db, folder.id, item.chat_id, is_excluded=item.is_excluded)
    db.commit()
    return {"detail": "Added"}


@folders_router.delete("/{folder_id}/items/{chat_id}")
def remove_chat_from_folder(
    folder_id: int,
    chat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    folder = crud.get_folder(db, user.id, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    if not crud.remove_folder_item(db, folder.id, chat_id):
        raise HTTPException(status_code=404, detail="Item not found")
    db.commit()
    return {"detail": "Removed"}
