"""
Имена WS-событий и хелперы рассылки в чат.

Каждое событие — JSON-объект с полем `type`. Имена событий стабильны;
клиент завязывается на них.
"""
import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from models import ChatMember, ChatMemberRole

from modules.websockets.manager import manager


# ---- client → server ----
CMD_SEND = "send_message"
CMD_EDIT = "edit_message"
CMD_DELETE = "delete_message"
CMD_TYPING = "typing"
CMD_STOP_TYPING = "stop_typing"
CMD_READ = "read"
CMD_REACT = "react"
CMD_PING = "ping"

# ---- server → client ----
EVT_HELLO = "hello"
EVT_PONG = "pong"
EVT_ERROR = "error"

EVT_NEW_MESSAGE = "new_message"
EVT_MESSAGE_EDITED = "message_edited"
EVT_MESSAGE_DELETED = "message_deleted"
EVT_TYPING = "typing"
EVT_STOP_TYPING = "stop_typing"
EVT_READ = "read"
EVT_REACTION = "reaction"

EVT_PRESENCE = "presence"

EVT_CHAT_CREATED = "chat_created"
EVT_CHAT_UPDATED = "chat_updated"
EVT_CHAT_DELETED = "chat_deleted"
EVT_MEMBER_ADDED = "member_added"
EVT_MEMBER_REMOVED = "member_removed"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chat_member_ids(db: Session, chat_id: int) -> list[int]:
    rows = (
        db.query(ChatMember.user_id)
        .filter(
            ChatMember.chat_id == chat_id,
            ChatMember.role.notin_([ChatMemberRole.left, ChatMemberRole.banned]),
        )
        .all()
    )
    return [r[0] for r in rows]


# =====================================================================
#  Универсальный broadcast в чат
# =====================================================================

async def broadcast_to_chat(
    db: Session,
    chat_id: int,
    event_type: str,
    payload: dict[str, Any],
    *,
    exclude_user_id: int | None = None,
) -> None:
    """Шлёт событие всем участникам чата (по всем их устройствам)."""
    user_ids = _chat_member_ids(db, chat_id)
    if exclude_user_id is not None:
        user_ids = [u for u in user_ids if u != exclude_user_id]
    if not user_ids:
        return
    await manager.send_to_users(user_ids, {
        "type": event_type,
        "ts": _utcnow_iso(),
        **payload,
    })


def broadcast_to_chat_sync(
    db: Session,
    chat_id: int,
    event_type: str,
    payload: dict[str, Any],
    *,
    exclude_user_id: int | None = None,
) -> None:
    """
    Sync-обёртка для вызова из обычных REST-роутеров.

    Шлёт через сохранённый главный event loop. Если loop ещё не привязан
    (например, в тестах без lifespan), broadcast тихо пропускается —
    REST-ответ всё равно вернётся клиенту, и он увидит изменение по
    следующему запросу.

    Важно: список получателей вычисляется ЗДЕСЬ синхронно, по сессии
    REST-роутера, и передаётся в корутину готовым. Сама `db` к моменту
    выполнения корутины может быть уже закрыта.
    """
    loop = manager.loop
    if loop is None or not loop.is_running():
        return

    user_ids = _chat_member_ids(db, chat_id)
    if exclude_user_id is not None:
        user_ids = [u for u in user_ids if u != exclude_user_id]
    if not user_ids:
        return

    event = {"type": event_type, "ts": _utcnow_iso(), **payload}

    async def _send_now():
        await manager.send_to_users(user_ids, event)

    asyncio.run_coroutine_threadsafe(_send_now(), loop)


# =====================================================================
#  Presence
# =====================================================================

async def broadcast_presence(
    db: Session,
    user_id: int,
    is_online: bool,
    last_seen_iso: str,
) -> None:
    """
    Шлёт presence всем, кто в одном чате с этим юзером.
    Не учитывает privacy.last_seen — это будет проверяться при отдаче
    в REST. Для real-time мы сообщаем «онлайн» только реальным сочатникам,
    а они уже у себя могут скрыть на UI согласно privacy.
    """
    chat_ids_q = (
        db.query(ChatMember.chat_id)
        .filter(
            ChatMember.user_id == user_id,
            ChatMember.role.notin_([ChatMemberRole.left, ChatMemberRole.banned]),
        )
    )
    rows = (
        db.query(ChatMember.user_id)
        .filter(
            ChatMember.chat_id.in_(chat_ids_q),
            ChatMember.user_id != user_id,
            ChatMember.role.notin_([ChatMemberRole.left, ChatMemberRole.banned]),
        )
        .distinct()
        .all()
    )
    target_ids = list({r[0] for r in rows})
    if not target_ids:
        return
    await manager.send_to_users(target_ids, {
        "type": EVT_PRESENCE,
        "user_id": user_id,
        "is_online": is_online,
        "last_seen": last_seen_iso,
        "ts": _utcnow_iso(),
    })



# =====================================================================
#  Личное событие конкретному пользователю (без чата)
# =====================================================================

EVT_NOTIFICATION = "notification"


def send_to_user_sync(user_id: int, event_type: str, payload: dict[str, Any]) -> None:
    """Шлёт событие конкретному пользователю по всем его сокетам.
    Используется из REST для пуша уведомлений (mention/reaction/...)."""
    loop = manager.loop
    if loop is None or not loop.is_running():
        return
    event = {"type": event_type, "ts": _utcnow_iso(), **payload}

    async def _send_now():
        await manager.send_to_user(user_id, event)

    asyncio.run_coroutine_threadsafe(_send_now(), loop)
