from pathlib import Path
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import MEDIA_DIR

from modules.users.router import router as users_router
from modules.contacts.router import router as contacts_router
from modules.chats.router import router as chats_router, folders_router
from modules.messages.router import (
    router as messages_router,
    chat_messages_router,
    polls_router,
    hashtags_router,
)
from modules.media.router import router as media_router
from modules.reactions.router import router as reactions_router
from modules.reads.router import router as reads_router
from modules.blocks.router import router as blocks_router
from modules.notifications.router import router as notifications_router
from modules.stories.router import router as stories_router, user_stories_router
from modules.calls.router import router as calls_router
from modules.reports.router import router as reports_router
from modules.websockets.router import router as ws_router
from modules.websockets.manager import manager as ws_manager


# Создаём папку для медиа, если её ещё нет
Path(MEDIA_DIR).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Сохраняем ссылку на главный event loop, чтобы sync-роутеры
    # могли пушить broadcast через WebSocket.
    ws_manager.bind_loop(asyncio.get_running_loop())
    yield


app = FastAPI(
    title="Telegramm Clone API",
    version="0.1.0",
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "tryItOutEnabled": True,
    },
)


app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(users_router)
app.include_router(contacts_router)
app.include_router(chats_router)
app.include_router(folders_router)
app.include_router(messages_router)
app.include_router(chat_messages_router)
app.include_router(polls_router)
app.include_router(hashtags_router)
app.include_router(media_router)
app.include_router(reactions_router)
app.include_router(reads_router)
app.include_router(blocks_router)
app.include_router(notifications_router)
app.include_router(stories_router)
app.include_router(user_stories_router)
app.include_router(calls_router)
app.include_router(reports_router)
app.include_router(ws_router)


# Раздача загруженных файлов
app.mount("/media-files", StaticFiles(directory=MEDIA_DIR), name="media-files")


@app.get("/")
def root():
    return {
        "name": "Telegramm Clone API",
        "version": "0.1.0",
        "docs": "/docs",
    }
