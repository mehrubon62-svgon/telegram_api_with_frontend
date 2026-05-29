"""
WebSocket endpoint /ws — единый канал реал-тайм событий.

Подключение:  ws://host/ws?token=<JWT_access_token>

Команды клиента (JSON):
    { "type": "send_message",  "chat_id": int, "text": str, "reply_to_id": int|null,
       "topic_id": int|null, "is_silent": bool, "attachments": [...] }
    { "type": "edit_message",  "message_id": int, "text": str|null, "entities": [..]|null }
    { "type": "delete_message","message_id": int, "for_everyone": bool }
    { "type": "typing",        "chat_id": int, "topic_id": int|null }
    { "type": "stop_typing",   "chat_id": int }
    { "type": "read",          "chat_id": int, "message_id": int }
    { "type": "react",         "message_id": int, "emoji": str, "is_big": bool }
    { "type": "ping" }

События сервера (JSON):
    { "type": "hello",          "user_id": int, "online_users": [int] }
    { "type": "pong",           "ts": iso }
    { "type": "error",          "code": str, "detail": str }
    { "type": "new_message",    "message": MessageOut }
    { "type": "message_edited", "message": MessageOut }
    { "type": "message_deleted","chat_id": int, "message_id": int, "for_everyone": bool }
    { "type": "typing",         "chat_id": int, "user_id": int, "topic_id": int|null }
    { "type": "stop_typing",    "chat_id": int, "user_id": int }
    { "type": "read",           "chat_id": int, "user_id": int, "message_id": int }
    { "type": "reaction",       "message_id": int, "user_id": int, "emoji": str, "added": bool }
    { "type": "presence",       "user_id": int, "is_online": bool, "last_seen": iso }

REST-эндпоинты тоже триггерят соответствующие server-events
(см. integration хуки в роутерах chats/messages).
"""
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from models import (
    SessionLocal,
    User,
    Message,
    MessageType,
    ChatMemberRole,
)

from modules.chats import crud as chats_crud
from modules.messages import crud as messages_crud

from modules.websockets.auth import authenticate_ws_token
from modules.websockets.manager import manager
from modules.websockets.events import (
    CMD_SEND, CMD_EDIT, CMD_DELETE, CMD_TYPING, CMD_STOP_TYPING,
    CMD_READ, CMD_REACT, CMD_PING,
    EVT_HELLO, EVT_PONG, EVT_ERROR,
    EVT_NEW_MESSAGE, EVT_MESSAGE_EDITED, EVT_MESSAGE_DELETED,
    EVT_TYPING, EVT_STOP_TYPING, EVT_READ, EVT_REACTION,
    broadcast_to_chat, broadcast_presence,
)


router = APIRouter(prefix="/ws", tags=["WebSockets"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


# =====================================================================
#  Сериализация (минимальная) — повторно используем messages-router
# =====================================================================

def _serialize_message_for_ws(db: Session, msg: Message) -> dict[str, Any]:
    """Лёгкая сериализация под WS-событие. Полная — в REST."""
    from modules.messages.router import _serialize_one
    return _serialize_one(db, msg).model_dump(mode="json")


# =====================================================================
#  Главный endpoint
# =====================================================================

@router.websocket("")
async def websocket_endpoint(
    ws: WebSocket,
    token: str = Query(..., description="JWT access token"),
):
    db: Session = SessionLocal()
    try:
        user = authenticate_ws_token(db, token)
    except Exception:
        user = None

    if not user:
        await ws.close(code=4401)  # 4401 — кастомный «unauthorized»
        db.close()
        return

    await ws.accept()
    was_first = await manager.connect(user.id, ws)

    # Обновляем статус и шлём presence остальным
    user.is_online = True
    user.last_seen = _utcnow()
    db.commit()
    if was_first:
        await broadcast_presence(db, user.id, True, _utcnow_iso())

    # hello
    await ws.send_json({
        "type": EVT_HELLO,
        "user_id": user.id,
        "online_users": manager.online_user_ids(),
        "ts": _utcnow_iso(),
    })

    try:
        while True:
            msg = await ws.receive_json()
            try:
                await _handle_command(db, user, ws, msg)
            except Exception as e:
                await ws.send_json({"type": EVT_ERROR, "code": "internal", "detail": str(e)})
    except WebSocketDisconnect:
        pass
    finally:
        last_socket = await manager.disconnect(user.id, ws)
        if last_socket:
            user.is_online = False
            user.last_seen = _utcnow()
            db.commit()
            await broadcast_presence(db, user.id, False, _utcnow_iso())
        db.close()


# =====================================================================
#  Command dispatcher
# =====================================================================

async def _handle_command(
    db: Session,
    user: User,
    ws: WebSocket,
    msg: dict[str, Any],
) -> None:
    cmd = msg.get("type")

    if cmd == CMD_PING:
        await ws.send_json({"type": EVT_PONG, "ts": _utcnow_iso()})
        return

    if cmd == CMD_SEND:
        await _cmd_send(db, user, msg)
        return

    if cmd == CMD_EDIT:
        await _cmd_edit(db, user, msg)
        return

    if cmd == CMD_DELETE:
        await _cmd_delete(db, user, msg)
        return

    if cmd == CMD_TYPING:
        await _cmd_typing(db, user, msg, stopping=False)
        return

    if cmd == CMD_STOP_TYPING:
        await _cmd_typing(db, user, msg, stopping=True)
        return

    if cmd == CMD_READ:
        await _cmd_read(db, user, msg)
        return

    if cmd == CMD_REACT:
        await _cmd_react(db, user, msg)
        return

    await ws.send_json({"type": EVT_ERROR, "code": "unknown_command", "detail": f"Unknown command: {cmd}"})


# =====================================================================
#  send
# =====================================================================

async def _cmd_send(db: Session, user: User, msg: dict[str, Any]) -> None:
    chat_id = msg.get("chat_id")
    if not chat_id:
        return
    chat = chats_crud.get_chat(db, chat_id)
    if not chat:
        return
    member = chats_crud.get_member(db, chat_id, user.id)
    if not member or not chats_crud.is_active_member(member):
        return

    # Проверяем send-permissions через тот же helper, что и REST
    from modules.messages.router import _ensure_can_send
    try:
        _ensure_can_send(chat, member, db)
    except Exception:
        return  # тихо игнорим — REST даст 403, тут не критично

    text = msg.get("text")
    msg_type = msg.get("msg_type") or MessageType.text
    if isinstance(msg_type, str):
        try:
            msg_type = MessageType(msg_type)
        except ValueError:
            msg_type = MessageType.text

    attachments = msg.get("attachments") or []
    if not text and not attachments and msg_type == MessageType.text:
        return

    new_msg = messages_crud.create_message(
        db, chat,
        sender_id=user.id,
        type=msg_type,
        text=text,
        entities=msg.get("entities"),
        reply_to_id=msg.get("reply_to_id"),
        topic_id=msg.get("topic_id"),
        is_silent=bool(msg.get("is_silent", False)),
        attachments=attachments,
    )
    db.commit()
    db.refresh(new_msg)

    await broadcast_to_chat(db, chat_id, EVT_NEW_MESSAGE, {
        "message": _serialize_message_for_ws(db, new_msg),
    })


# =====================================================================
#  edit
# =====================================================================

async def _cmd_edit(db: Session, user: User, msg: dict[str, Any]) -> None:
    message_id = msg.get("message_id")
    if not message_id:
        return
    target = messages_crud.get_message(db, message_id)
    if not target or target.is_deleted or target.sender_id != user.id:
        return

    messages_crud.edit_message(
        db, target,
        text=msg.get("text"),
        entities=msg.get("entities"),
        reply_markup=msg.get("reply_markup"),
    )
    db.commit()
    db.refresh(target)

    await broadcast_to_chat(db, target.chat_id, EVT_MESSAGE_EDITED, {
        "message": _serialize_message_for_ws(db, target),
    })


# =====================================================================
#  delete
# =====================================================================

async def _cmd_delete(db: Session, user: User, msg: dict[str, Any]) -> None:
    message_id = msg.get("message_id")
    if not message_id:
        return
    target = messages_crud.get_message(db, message_id)
    if not target:
        return

    chat = chats_crud.get_chat(db, target.chat_id)
    member = chats_crud.get_member(db, target.chat_id, user.id)
    if not member or not chats_crud.is_active_member(member):
        return

    for_everyone = bool(msg.get("for_everyone", True))
    if for_everyone:
        # повторяем логику из REST: сам автор или админ-удалитель
        if target.sender_id != user.id and not chats_crud.can_admin(member):
            return

    messages_crud.delete_message(db, target, for_everyone=for_everyone)
    db.commit()

    await broadcast_to_chat(db, target.chat_id, EVT_MESSAGE_DELETED, {
        "chat_id": target.chat_id,
        "message_id": message_id,
        "for_everyone": for_everyone,
    })


# =====================================================================
#  typing / stop_typing
# =====================================================================

async def _cmd_typing(db: Session, user: User, msg: dict[str, Any], *, stopping: bool) -> None:
    chat_id = msg.get("chat_id")
    if not chat_id:
        return
    member = chats_crud.get_member(db, chat_id, user.id)
    if not member or not chats_crud.is_active_member(member):
        return

    event_type = EVT_STOP_TYPING if stopping else EVT_TYPING
    await broadcast_to_chat(db, chat_id, event_type, {
        "chat_id": chat_id,
        "user_id": user.id,
        "topic_id": msg.get("topic_id"),
    }, exclude_user_id=user.id)


# =====================================================================
#  read
# =====================================================================

async def _cmd_read(db: Session, user: User, msg: dict[str, Any]) -> None:
    chat_id = msg.get("chat_id")
    message_id = msg.get("message_id")
    if not chat_id or not message_id:
        return
    member = chats_crud.get_member(db, chat_id, user.id)
    if not member or not chats_crud.is_active_member(member):
        return

    new_ids = messages_crud.mark_chat_read(db, chat_id, user.id, up_to_message_id=message_id)
    db.commit()
    if not new_ids:
        return
    await broadcast_to_chat(db, chat_id, EVT_READ, {
        "chat_id": chat_id,
        "user_id": user.id,
        "message_id": message_id,
        "read_message_ids": new_ids,
    })


# =====================================================================
#  react
# =====================================================================

async def _cmd_react(db: Session, user: User, msg: dict[str, Any]) -> None:
    message_id = msg.get("message_id")
    emoji = msg.get("emoji")
    if not message_id or not emoji:
        return
    target = messages_crud.get_message(db, message_id)
    if not target or target.is_deleted:
        return
    member = chats_crud.get_member(db, target.chat_id, user.id)
    if not member or not chats_crud.is_active_member(member):
        return

    added, _ = messages_crud.toggle_reaction(
        db, message_id, user.id, emoji, is_big=bool(msg.get("is_big", False))
    )
    db.commit()

    await broadcast_to_chat(db, target.chat_id, EVT_REACTION, {
        "chat_id": target.chat_id,
        "message_id": message_id,
        "user_id": user.id,
        "emoji": emoji,
        "added": added,
    })
