"""
ConnectionManager: реестр активных WebSocket-подключений и broadcast.

In-memory хранилище: { user_id: set[WebSocket] }.
Один пользователь может быть подключён с нескольких устройств — каждое
устройство получает свою копию событий. Когда последний сокет
пользователя отключается — рассылается presence offline.
"""
import asyncio
import json
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Сохраняет ссылку на главный event loop приложения.
        Вызывается из lifespan; нужен, чтобы sync-роутеры могли пушить
        broadcast через run_coroutine_threadsafe."""
        self._loop = loop

    @property
    def loop(self) -> asyncio.AbstractEventLoop | None:
        return self._loop

    # =====================================================================
    #  Connect / disconnect
    # =====================================================================

    async def connect(self, user_id: int, ws: WebSocket) -> bool:
        """Регистрирует подключение. Возвращает True, если это первое
        подключение пользователя (нужно чтобы решить, шлём ли presence online)."""
        async with self._lock:
            sockets = self._connections.setdefault(user_id, set())
            was_empty = len(sockets) == 0
            sockets.add(ws)
            return was_empty

    async def disconnect(self, user_id: int, ws: WebSocket) -> bool:
        """Удаляет подключение. Возвращает True, если у пользователя
        больше не осталось активных сокетов (ушёл в offline)."""
        async with self._lock:
            sockets = self._connections.get(user_id)
            if not sockets:
                return False
            sockets.discard(ws)
            if not sockets:
                self._connections.pop(user_id, None)
                return True
            return False

    def is_online(self, user_id: int) -> bool:
        return bool(self._connections.get(user_id))

    def online_user_ids(self) -> list[int]:
        return list(self._connections.keys())

    # =====================================================================
    #  Sending
    # =====================================================================

    async def _send(self, ws: WebSocket, payload: dict[str, Any]) -> None:
        try:
            await ws.send_text(json.dumps(payload, default=str))
        except Exception:
            # Тихо игнорируем; реальный disconnect отлавливается в роутере
            pass

    async def send_to_user(self, user_id: int, event: dict[str, Any]) -> int:
        """Шлёт всем сокетам конкретного пользователя. Возвращает кол-во доставок."""
        sockets = list(self._connections.get(user_id, ()))
        if not sockets:
            return 0
        await asyncio.gather(*(self._send(s, event) for s in sockets))
        return len(sockets)

    async def send_to_users(self, user_ids: list[int], event: dict[str, Any]) -> int:
        """Шлёт нескольким пользователям сразу."""
        targets: list[WebSocket] = []
        for uid in user_ids:
            targets.extend(self._connections.get(uid, ()))
        if not targets:
            return 0
        await asyncio.gather(*(self._send(s, event) for s in targets))
        return len(targets)

    async def send_to_user_except(
        self,
        user_id: int,
        exclude: WebSocket | None,
        event: dict[str, Any],
    ) -> int:
        sockets = [s for s in self._connections.get(user_id, ()) if s is not exclude]
        if not sockets:
            return 0
        await asyncio.gather(*(self._send(s, event) for s in sockets))
        return len(sockets)


# Глобальный менеджер. Импортируется и WS-роутером, и REST-роутерами,
# чтобы триггерить рассылку из обычных эндпоинтов.
manager = ConnectionManager()
