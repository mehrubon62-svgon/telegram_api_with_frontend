"""HTTP API модуля messages.

Покрывает всё, что не требует real-time push:
  • CRUD сообщений (включая reply, forward, quote, scheduled)
  • история / поиск (по чату и глобально), хэштеги
  • редактирование с историей правок
  • удаление (для себя / для всех)
  • реакции (toggle), реакции списком
  • прочтения (mark_chat_read), список «кто прочитал»
  • mentions (unread / read-all)
  • драфты
  • закреплённые сообщения
  • forward в один или несколько чатов
  • опросы (создание / голос / закрытие)

Real-time события поверх этого пойдут через WebSocket в следующем модуле.
"""
from datetime import datetime, timezone
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from models import (
    get_db,
    User,
    Chat,
    ChatType,
    Message,
    MessageType,
    ChatMemberRole,
    ChatAdminAction,
    Attachment,
)
from dependencies import get_current_user

from modules.chats import crud as chats_crud
from modules.messages import crud
from modules.blocks import crud as blocks_crud
from modules.notifications import crud as notif_crud
from modules.websockets.events import (
    broadcast_to_chat_sync,
    EVT_NEW_MESSAGE,
    EVT_MESSAGE_EDITED,
    EVT_MESSAGE_DELETED,
    EVT_READ,
    EVT_REACTION,
)
from modules.websockets.manager import manager as ws_manager
import asyncio
from modules.messages.schemas import (
    MessageCreate,
    MessageEdit,
    MessageOut,
    MessageEditHistoryOut,
    AttachmentOut,
    SenderOut,
    ForwardOriginOut,
    ForwardRequest,
    ReadUpToRequest,
    ReadEntry,
    ReactionToggle,
    ReactionEntry,
    DraftIn,
    DraftOut,
    PollCreate,
    PollVoteIn,
    PollOut,
    PollOptionOut,
)


router = APIRouter(prefix="/messages", tags=["Messages"])
chat_messages_router = APIRouter(prefix="/chats", tags=["Messages"])
polls_router = APIRouter(prefix="/polls", tags=["Polls"])
hashtags_router = APIRouter(prefix="/hashtags", tags=["Hashtags"])


# =====================================================================
#  Permissions helpers
# =====================================================================

def _ensure_member(chat_id: int, user_id: int, db: Session):
    member = chats_crud.get_member(db, chat_id, user_id)
    if not member or not chats_crud.is_active_member(member):
        raise HTTPException(status_code=403, detail="Not a member of this chat")
    return member


def _ensure_can_send(chat: Chat, member, db: Session) -> None:
    """
    Канал — писать могут только админы.
    В group/supergroup — учитываем chat.can_send_messages, права участника, restricted_until.
    Private/saved/secret — всегда можно.
    """
    if chat.type == ChatType.channel:
        if not chats_crud.can_admin(member):
            rights = chats_crud.get_admin_rights(db, chat.id, member.user_id)
            if not (rights and rights.can_post_messages):
                raise HTTPException(status_code=403, detail="Only admins can post in this channel")
        return

    if chat.type in (ChatType.private, ChatType.saved, ChatType.secret):
        return

    if member.role == ChatMemberRole.banned:
        raise HTTPException(status_code=403, detail="You are banned from this chat")

    if member.role == ChatMemberRole.restricted:
        if member.restricted_until:
            until = member.restricted_until
            if until.tzinfo is None:
                until = until.replace(tzinfo=timezone.utc)
            if until > datetime.now(timezone.utc):
                if not member.can_send_messages:
                    raise HTTPException(status_code=403, detail="You are restricted from sending messages")

    if not chat.can_send_messages and not chats_crud.can_admin(member):
        raise HTTPException(status_code=403, detail="Sending messages is disabled in this chat")


def _can_edit(msg: Message, user: User, member) -> bool:
    """В Telegram редактировать чужие сообщения нельзя (за исключением админов
    каналов с can_edit_messages — это проверяется в роутере отдельно)."""
    return msg.sender_id == user.id


def _can_delete(db: Session, chat: Chat, msg: Message, user: User, member) -> bool:
    if msg.sender_id == user.id:
        return True
    if member and chats_crud.can_admin(member):
        if member.role == ChatMemberRole.creator:
            return True
        rights = chats_crud.get_admin_rights(db, chat.id, user.id)
        return bool(rights and rights.can_delete_messages)
    return False


# =====================================================================
#  Serialization
# =====================================================================

def _serialize_attachment(a: Attachment) -> AttachmentOut:
    return AttachmentOut(
        id=a.id,
        file_url=a.file_url,
        thumbnail_url=a.thumbnail_url,
        file_name=a.file_name,
        mime_type=a.mime_type,
        size_bytes=a.size_bytes,
        width=a.width,
        height=a.height,
        duration=a.duration,
        waveform=a.waveform,
        caption=a.caption,
        has_spoiler=a.has_spoiler,
        is_view_once=a.is_view_once,
        position=a.position,
    )


def _serialize_message(msg: Message, *, attachments: list[Attachment], sender: User | None) -> MessageOut:
    forward = None
    if msg.forward_from_message_id or msg.forward_from_user_id or msg.forward_from_chat_id:
        forward = ForwardOriginOut(
            from_user_id=msg.forward_from_user_id,
            from_chat_id=msg.forward_from_chat_id,
            from_message_id=msg.forward_from_message_id,
            sender_name=msg.forward_sender_name,
            date=msg.forward_date,
        )
    return MessageOut(
        id=msg.id,
        chat_id=msg.chat_id,
        topic_id=msg.topic_id,
        sender=SenderOut.model_validate(sender) if sender else None,
        type=msg.type,
        text=msg.text,
        entities=msg.entities,
        reply_to_id=msg.reply_to_id,
        thread_root_id=msg.thread_root_id,
        reply_quote_text=msg.reply_quote_text,
        reply_quote_offset=msg.reply_quote_offset,
        reply_quote_entities=msg.reply_quote_entities,
        forward=forward,
        is_edited=msg.is_edited,
        is_deleted=msg.is_deleted,
        is_pinned=msg.is_pinned,
        is_silent=msg.is_silent,
        is_via_bot=msg.is_via_bot,
        via_bot_id=msg.via_bot_id,
        views_count=msg.views_count or 0,
        forwards_count=msg.forwards_count or 0,
        self_destruct_seconds=msg.self_destruct_seconds,
        expires_at=msg.expires_at,
        scheduled_at=msg.scheduled_at,
        is_scheduled=msg.is_scheduled,
        original_language=msg.original_language,
        reply_markup=msg.reply_markup,
        attachments=[_serialize_attachment(a) for a in attachments],
        created_at=msg.created_at,
        edited_at=msg.edited_at,
    )


def _serialize_messages(db: Session, msgs: list[Message]) -> list[MessageOut]:
    if not msgs:
        return []
    msg_ids = [m.id for m in msgs]
    atts_map = crud.get_attachments(db, msg_ids)
    sender_ids = {m.sender_id for m in msgs if m.sender_id}
    senders = {u.id: u for u in db.query(User).filter(User.id.in_(sender_ids)).all()} if sender_ids else {}
    return [
        _serialize_message(m, attachments=atts_map.get(m.id, []), sender=senders.get(m.sender_id))
        for m in msgs
    ]


def _serialize_one(db: Session, msg: Message) -> MessageOut:
    return _serialize_messages(db, [msg])[0]


def _aggregate_reactions(db: Session, message_id: int, user_id: int) -> list[ReactionEntry]:
    rows = crud.get_reactions(db, message_id)
    by_emoji: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        by_emoji[r.emoji].append(r.user_id)
    return [
        ReactionEntry(emoji=emoji, count=len(uids), chosen=user_id in uids, user_ids=uids)
        for emoji, uids in by_emoji.items()
    ]


# =====================================================================
#  Send
# =====================================================================

@chat_messages_router.post("/{chat_id}/messages", response_model=MessageOut, status_code=201)
def send_message(
    chat_id: int,
    data: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = chats_crud.get_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    member = _ensure_member(chat_id, user.id, db)
    _ensure_can_send(chat, member, db)

    # В private-чате нельзя слать заблокированному / если сам заблокирован
    if chat.type == ChatType.private:
        from models import ChatMember as CM
        other = (
            db.query(CM.user_id)
            .filter(CM.chat_id == chat_id, CM.user_id != user.id)
            .first()
        )
        if other:
            other_id = other[0]
            if blocks_crud.is_blocked(db, other_id, user.id):
                raise HTTPException(status_code=403, detail="You are blocked by this user")
            if blocks_crud.is_blocked(db, user.id, other_id):
                raise HTTPException(status_code=403, detail="Unblock the user first")

    if data.reply_to_id:
        parent = crud.get_message(db, data.reply_to_id)
        if not parent or parent.chat_id != chat_id or parent.is_deleted:
            raise HTTPException(status_code=400, detail="Reply target not found in this chat")

    if not data.text and not data.attachments and data.type == MessageType.text:
        raise HTTPException(status_code=400, detail="Message must have text or attachments")

    msg = crud.create_message(
        db, chat,
        sender_id=user.id,
        type=data.type,
        text=data.text,
        entities=data.entities,
        reply_to_id=data.reply_to_id,
        reply_quote=data.reply_quote.model_dump() if data.reply_quote else None,
        topic_id=data.topic_id,
        is_silent=data.is_silent,
        self_destruct_seconds=data.self_destruct_seconds,
        scheduled_at=data.scheduled_at,
        original_language=data.original_language,
        reply_markup=data.reply_markup,
        attachments=[a.model_dump() for a in data.attachments] if data.attachments else None,
    )
    db.commit()
    db.refresh(msg)
    out = _serialize_one(db, msg)

    if not msg.is_scheduled:
        broadcast_to_chat_sync(db, chat.id, EVT_NEW_MESSAGE, {"message": out.model_dump(mode="json")})

        # Уведомления для упомянутых пользователей
        from models import MessageMention
        from modules.websockets.events import send_to_user_sync, EVT_NOTIFICATION
        mentioned_ids = [
            m.mentioned_user_id
            for m in db.query(MessageMention).filter(MessageMention.message_id == msg.id).all()
        ]
        for uid in mentioned_ids:
            if uid == user.id:
                continue
            n = notif_crud.create_notification(
                db, user_id=uid, type="mention",
                chat_id=chat.id, message_id=msg.id,
                payload={"from_user_id": user.id, "preview": (msg.text or "")[:100]},
            )
            db.flush()
            send_to_user_sync(uid, EVT_NOTIFICATION, {
                "notification": {
                    "id": n.id, "type": "mention", "chat_id": chat.id,
                    "message_id": msg.id, "payload": n.payload, "is_read": False,
                }
            })
        db.commit()
    return out


# =====================================================================
#  History / single message
# =====================================================================

@chat_messages_router.get("/{chat_id}/messages", response_model=list[MessageOut])
def get_history(
    chat_id: int,
    topic_id: int | None = Query(None),
    before_id: int | None = Query(None),
    after_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = chats_crud.get_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    is_public_channel = chat.type == ChatType.channel and bool(chat.public_username)
    if not is_public_channel:
        _ensure_member(chat_id, user.id, db)

    if not chat.is_history_visible:
        member = chats_crud.get_member(db, chat_id, user.id)
        if member and member.joined_at:
            joined = member.joined_at
            if joined.tzinfo is None:
                joined = joined.replace(tzinfo=timezone.utc)
            # Скрываем доистаpические сообщения
            min_id_q = db.query(Message.id).filter(
                Message.chat_id == chat_id,
                Message.created_at >= joined,
            ).order_by(Message.id.asc()).first()
            min_id = min_id_q[0] if min_id_q else None
            if min_id is not None:
                if before_id is not None and before_id <= min_id:
                    return []
                # подменяем after_id чтобы не уходить ниже
                if after_id is None or after_id < min_id - 1:
                    after_id = min_id - 1

    msgs = crud.list_messages(
        db, chat_id,
        topic_id=topic_id,
        before_id=before_id,
        after_id=after_id,
        limit=limit,
    )
    return _serialize_messages(db, msgs)


@chat_messages_router.get("/{chat_id}/messages/{message_id}", response_model=MessageOut)
def get_one_message(
    chat_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = chats_crud.get_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    is_public_channel = chat.type == ChatType.channel and bool(chat.public_username)
    if not is_public_channel:
        _ensure_member(chat_id, user.id, db)
    msg = crud.get_message(db, message_id)
    if not msg or msg.chat_id != chat_id:
        raise HTTPException(status_code=404, detail="Message not found")

    # Считаем просмотр для канала
    if chat.type == ChatType.channel and msg.sender_id != user.id:
        crud.increment_views(db, message_id, user.id)
        db.commit()
        db.refresh(msg)
    return _serialize_one(db, msg)


# =====================================================================
#  Edit / delete
# =====================================================================

@chat_messages_router.put("/{chat_id}/messages/{message_id}", response_model=MessageOut)
def edit_message_endpoint(
    chat_id: int,
    message_id: int,
    data: MessageEdit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = chats_crud.get_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    member = _ensure_member(chat_id, user.id, db)
    msg = crud.get_message(db, message_id)
    if not msg or msg.chat_id != chat_id or msg.is_deleted:
        raise HTTPException(status_code=404, detail="Message not found")

    if not _can_edit(msg, user, member):
        # admin с can_edit_messages в каналах
        rights = chats_crud.get_admin_rights(db, chat.id, user.id)
        if not (rights and rights.can_edit_messages):
            raise HTTPException(status_code=403, detail="Cannot edit this message")

    crud.edit_message(db, msg, text=data.text, entities=data.entities, reply_markup=data.reply_markup)
    db.commit()
    db.refresh(msg)
    out = _serialize_one(db, msg)
    broadcast_to_chat_sync(db, msg.chat_id, EVT_MESSAGE_EDITED, {"message": out.model_dump(mode="json")})
    return out


@chat_messages_router.delete("/{chat_id}/messages/{message_id}")
def delete_message_endpoint(
    chat_id: int,
    message_id: int,
    for_everyone: bool = Query(True),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = chats_crud.get_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    member = _ensure_member(chat_id, user.id, db)
    msg = crud.get_message(db, message_id)
    if not msg or msg.chat_id != chat_id:
        raise HTTPException(status_code=404, detail="Message not found")

    if for_everyone and not _can_delete(db, chat, msg, user, member):
        raise HTTPException(status_code=403, detail="Cannot delete this message for everyone")

    crud.delete_message(db, msg, for_everyone=for_everyone)
    if msg.sender_id != user.id:
        chats_crud.log_admin(
            db, chat_id=chat.id, actor_id=user.id,
            action=ChatAdminAction.message_deleted,
            payload={"message_id": message_id},
        )
    db.commit()
    broadcast_to_chat_sync(db, chat.id, EVT_MESSAGE_DELETED, {
        "chat_id": chat.id, "message_id": message_id, "for_everyone": for_everyone,
    })
    return {"detail": "Deleted"}


@chat_messages_router.get("/{chat_id}/messages/{message_id}/edit-history",
                          response_model=list[MessageEditHistoryOut])
def message_edit_history(
    chat_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_member(chat_id, user.id, db)
    msg = crud.get_message(db, message_id)
    if not msg or msg.chat_id != chat_id:
        raise HTTPException(status_code=404, detail="Message not found")
    return crud.get_edit_history(db, message_id)


# =====================================================================
#  Pinned
# =====================================================================

@chat_messages_router.post("/{chat_id}/messages/{message_id}/pin")
def pin_message_endpoint(
    chat_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = chats_crud.get_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    member = _ensure_member(chat_id, user.id, db)

    if not chats_crud.can_admin(member) and not chat.can_pin_messages:
        rights = chats_crud.get_admin_rights(db, chat.id, user.id)
        if not (rights and rights.can_pin_messages):
            raise HTTPException(status_code=403, detail="Cannot pin messages")

    msg = crud.get_message(db, message_id)
    if not msg or msg.chat_id != chat_id or msg.is_deleted:
        raise HTTPException(status_code=404, detail="Message not found")

    crud.pin_message(db, chat, message_id, by_user_id=user.id)
    chats_crud.log_admin(
        db, chat_id=chat.id, actor_id=user.id,
        action=ChatAdminAction.message_pinned,
        payload={"message_id": message_id},
    )
    db.commit()
    return {"detail": "Pinned"}


@chat_messages_router.delete("/{chat_id}/messages/{message_id}/pin")
def unpin_message_endpoint(
    chat_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = chats_crud.get_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    member = _ensure_member(chat_id, user.id, db)

    if not chats_crud.can_admin(member):
        rights = chats_crud.get_admin_rights(db, chat.id, user.id)
        if not (rights and rights.can_pin_messages):
            raise HTTPException(status_code=403, detail="Cannot unpin messages")

    if not crud.unpin_message(db, chat, message_id):
        raise HTTPException(status_code=404, detail="Pinned message not found")
    chats_crud.log_admin(
        db, chat_id=chat.id, actor_id=user.id,
        action=ChatAdminAction.message_unpinned,
        payload={"message_id": message_id},
    )
    db.commit()
    return {"detail": "Unpinned"}


@chat_messages_router.get("/{chat_id}/pinned", response_model=list[MessageOut])
def get_pinned(
    chat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = chats_crud.get_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    is_public_channel = chat.type == ChatType.channel and bool(chat.public_username)
    if not is_public_channel:
        _ensure_member(chat_id, user.id, db)
    return _serialize_messages(db, crud.list_pinned(db, chat_id))


# =====================================================================
#  Forward
# =====================================================================

@router.post("/forward", response_model=list[MessageOut])
def forward_messages(
    data: ForwardRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    src_chat = chats_crud.get_chat(db, data.from_chat_id)
    if not src_chat:
        raise HTTPException(status_code=404, detail="Source chat not found")

    is_public_channel = src_chat.type == ChatType.channel and bool(src_chat.public_username)
    if not is_public_channel:
        _ensure_member(data.from_chat_id, user.id, db)

    src_messages = (
        db.query(Message)
        .filter(
            Message.chat_id == data.from_chat_id,
            Message.id.in_(data.message_ids),
            Message.is_deleted.is_(False),
            Message.is_scheduled.is_(False),
        )
        .order_by(Message.id.asc())
        .all()
    )
    if not src_messages:
        raise HTTPException(status_code=404, detail="No messages to forward")

    src_atts = crud.get_attachments(db, [m.id for m in src_messages])
    sender_ids = {m.sender_id for m in src_messages if m.sender_id}
    senders = {u.id: u for u in db.query(User).filter(User.id.in_(sender_ids)).all()} if sender_ids else {}

    forwarded: list[Message] = []
    for to_chat_id in data.to_chat_ids:
        chat = chats_crud.get_chat(db, to_chat_id)
        if not chat:
            continue
        member = chats_crud.get_member(db, to_chat_id, user.id)
        if not member or not chats_crud.is_active_member(member):
            continue
        try:
            _ensure_can_send(chat, member, db)
        except HTTPException:
            continue

        for src in src_messages:
            sender_name = None
            if data.drop_author:
                sender_name = "Unknown"
            else:
                src_sender = senders.get(src.sender_id)
                if src_sender:
                    sender_name = src_sender.full_name or src_sender.username

            new_atts = []
            for a in src_atts.get(src.id, []):
                new_atts.append({
                    "file_url": a.file_url,
                    "thumbnail_url": a.thumbnail_url,
                    "file_name": a.file_name,
                    "mime_type": a.mime_type,
                    "size_bytes": a.size_bytes,
                    "width": a.width,
                    "height": a.height,
                    "duration": a.duration,
                    "waveform": a.waveform,
                    "caption": None if data.drop_caption else a.caption,
                    "has_spoiler": a.has_spoiler,
                    "is_view_once": a.is_view_once,
                    "position": a.position,
                })

            new_msg = crud.create_message(
                db, chat,
                sender_id=user.id,
                type=src.type,
                text=src.text,
                entities=src.entities,
                forward_from_user_id=src.sender_id if not data.drop_author else None,
                forward_from_chat_id=src.chat_id if not data.drop_author else None,
                forward_from_message_id=src.id if not data.drop_author else None,
                forward_sender_name=sender_name if not data.drop_author else None,
                forward_date=src.created_at,
                attachments=new_atts,
            )
            forwarded.append(new_msg)

            src.forwards_count = (src.forwards_count or 0) + 1

    db.commit()
    return _serialize_messages(db, forwarded)


# =====================================================================
#  Reactions
# =====================================================================

@router.post("/{message_id}/reactions", response_model=list[ReactionEntry])
def toggle_reaction_endpoint(
    message_id: int,
    data: ReactionToggle,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    msg = crud.get_message(db, message_id)
    if not msg or msg.is_deleted:
        raise HTTPException(status_code=404, detail="Message not found")
    _ensure_member(msg.chat_id, user.id, db)
    crud.toggle_reaction(db, message_id, user.id, data.emoji, is_big=data.is_big)
    db.commit()
    aggregated = _aggregate_reactions(db, message_id, user.id)
    broadcast_to_chat_sync(db, msg.chat_id, EVT_REACTION, {
        "chat_id": msg.chat_id,
        "message_id": message_id,
        "user_id": user.id,
        "emoji": data.emoji,
    })
    return aggregated


@router.get("/{message_id}/reactions", response_model=list[ReactionEntry])
def get_reactions_endpoint(
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    msg = crud.get_message(db, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    _ensure_member(msg.chat_id, user.id, db)
    return _aggregate_reactions(db, message_id, user.id)


# =====================================================================
#  Reads
# =====================================================================

@chat_messages_router.post("/{chat_id}/read")
def mark_read(
    chat_id: int,
    data: ReadUpToRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_member(chat_id, user.id, db)
    new_ids = crud.mark_chat_read(db, chat_id, user.id, up_to_message_id=data.message_id)
    db.commit()
    if new_ids:
        broadcast_to_chat_sync(db, chat_id, EVT_READ, {
            "chat_id": chat_id,
            "user_id": user.id,
            "message_id": data.message_id,
            "read_message_ids": new_ids,
        })
    return {"new_read_message_ids": new_ids}


@router.get("/{message_id}/reads", response_model=list[ReadEntry])
def get_message_reads(
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    msg = crud.get_message(db, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    _ensure_member(msg.chat_id, user.id, db)
    rows = crud.list_message_reads(db, message_id)
    return [ReadEntry(user_id=r.user_id, read_at=r.read_at) for r in rows]


# =====================================================================
#  Mentions
# =====================================================================

@chat_messages_router.get("/{chat_id}/mentions/unread", response_model=list[MessageOut])
def get_unread_mentions(
    chat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_member(chat_id, user.id, db)
    msgs = crud.list_unread_mentions(db, chat_id, user.id)
    return _serialize_messages(db, msgs)


@chat_messages_router.post("/{chat_id}/mentions/read-all")
def mark_all_mentions_read(
    chat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_member(chat_id, user.id, db)
    count = crud.mark_mentions_read(db, chat_id, user.id)
    db.commit()
    return {"marked": count}


# =====================================================================
#  Drafts
# =====================================================================

@chat_messages_router.get("/{chat_id}/draft", response_model=DraftOut | None)
def get_my_draft(
    chat_id: int,
    topic_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_member(chat_id, user.id, db)
    draft = crud.get_draft(db, user.id, chat_id, topic_id)
    return draft


@chat_messages_router.put("/{chat_id}/draft", response_model=DraftOut)
def upsert_my_draft(
    chat_id: int,
    data: DraftIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_member(chat_id, user.id, db)
    draft = crud.upsert_draft(
        db, user.id, chat_id,
        text=data.text, reply_to_id=data.reply_to_id, topic_id=data.topic_id,
    )
    db.commit()
    db.refresh(draft)
    return draft


@chat_messages_router.delete("/{chat_id}/draft")
def delete_my_draft(
    chat_id: int,
    topic_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_member(chat_id, user.id, db)
    if not crud.delete_draft(db, user.id, chat_id, topic_id):
        raise HTTPException(status_code=404, detail="Draft not found")
    db.commit()
    return {"detail": "Draft deleted"}


# =====================================================================
#  Search
# =====================================================================

@chat_messages_router.get("/{chat_id}/search", response_model=list[MessageOut])
def search_messages_in_chat(
    chat_id: int,
    q: str = Query(..., min_length=1, max_length=200),
    before_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_member(chat_id, user.id, db)
    msgs = crud.search_in_chat(db, chat_id, q, limit=limit, before_id=before_id)
    return _serialize_messages(db, msgs)


@router.get("/search", response_model=list[MessageOut])
def search_messages_global(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    msgs = crud.search_global(db, user.id, q, limit=limit)
    return _serialize_messages(db, msgs)


# =====================================================================
#  Hashtags
# =====================================================================

@hashtags_router.get("/{tag}/messages", response_model=list[MessageOut])
def messages_by_hashtag(
    tag: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return _serialize_messages(db, crud.list_by_hashtag(db, tag, limit=limit))


# =====================================================================
#  Polls
# =====================================================================

def _serialize_poll(db: Session, poll, user_id: int) -> PollOut:
    options = crud.list_poll_options(db, poll.id)
    chosen = crud.get_user_votes(db, poll.id, user_id)
    return PollOut(
        id=poll.id,
        message_id=poll.message_id,
        question=poll.question,
        options=[PollOptionOut.model_validate(o) for o in options],
        is_anonymous=poll.is_anonymous,
        allows_multiple_answers=poll.allows_multiple_answers,
        is_quiz=poll.is_quiz,
        correct_option_id=poll.correct_option_id,
        explanation=poll.explanation,
        is_closed=poll.is_closed,
        close_at=poll.close_at,
        total_voters=poll.total_voters,
        chosen_option_ids=chosen,
    )


@chat_messages_router.post("/{chat_id}/polls", response_model=MessageOut, status_code=201)
def create_chat_poll(
    chat_id: int,
    data: PollCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = chats_crud.get_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    member = _ensure_member(chat_id, user.id, db)
    _ensure_can_send(chat, member, db)
    if not chat.can_send_polls and not chats_crud.can_admin(member):
        raise HTTPException(status_code=403, detail="Polls are disabled in this chat")

    msg = crud.create_message(
        db, chat,
        sender_id=user.id,
        type=MessageType.poll,
        text=data.question,
    )
    crud.create_poll(
        db,
        message_id=msg.id,
        question=data.question,
        options=data.options,
        is_anonymous=data.is_anonymous,
        allows_multiple_answers=data.allows_multiple_answers,
        is_quiz=data.is_quiz,
        correct_option_index=data.correct_option_index,
        explanation=data.explanation,
        close_at=data.close_at,
    )
    db.commit()
    db.refresh(msg)
    return _serialize_one(db, msg)


@polls_router.post("/{poll_id}/vote", response_model=PollOut)
def vote_in_poll(
    poll_id: int,
    data: PollVoteIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    poll = crud.get_poll(db, poll_id)
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")
    msg = crud.get_message(db, poll.message_id)
    _ensure_member(msg.chat_id, user.id, db)
    try:
        crud.vote_poll(db, poll, user.id, data.option_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    db.refresh(poll)
    return _serialize_poll(db, poll, user.id)


@polls_router.post("/{poll_id}/close", response_model=PollOut)
def close_poll_endpoint(
    poll_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    poll = crud.get_poll(db, poll_id)
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")
    msg = crud.get_message(db, poll.message_id)
    if msg.sender_id != user.id:
        member = _ensure_member(msg.chat_id, user.id, db)
        if not chats_crud.can_admin(member):
            raise HTTPException(status_code=403, detail="Only author or admin can close")
    crud.close_poll(db, poll)
    db.commit()
    db.refresh(poll)
    return _serialize_poll(db, poll, user.id)


@polls_router.get("/{poll_id}", response_model=PollOut)
def get_poll_endpoint(
    poll_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    poll = crud.get_poll(db, poll_id)
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")
    msg = crud.get_message(db, poll.message_id)
    _ensure_member(msg.chat_id, user.id, db)
    return _serialize_poll(db, poll, user.id)
