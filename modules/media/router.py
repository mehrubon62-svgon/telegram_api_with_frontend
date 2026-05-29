"""HTTP API модуля media.

Загрузка медиа происходит отдельным запросом — затем клиент кладёт
полученные file_url/mime_type в `attachments` при отправке сообщения
через POST /chats/{id}/messages.

Эта схема даёт несколько плюсов:
  • один файл можно использовать в нескольких сообщениях / форвардить
  • не блокируется WebSocket большими бинарями
  • можно догружать медиа поверх scheduled-сообщений
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from models import (
    get_db,
    User,
    UserAvatar,
    Chat,
    ChatType,
    ChatMemberRole,
    ChatAdminAction,
)
from dependencies import get_current_user
from modules.chats import crud as chats_crud

from modules.media import crud
from modules.media.schemas import UploadOut, AvatarUpdateOut


router = APIRouter(prefix="/media", tags=["Media"])


# =====================================================================
#  Generic upload (любой файл; messages-модуль решит сам, какой это тип)
# =====================================================================

@router.post("/upload", response_model=UploadOut)
async def upload_generic(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    file_url, size = await crud.save_upload(
        file, subdir="files", owner_id=user.id,
        max_size=int(crud.MAX_GENERIC),
    )
    return UploadOut(
        file_url=file_url,
        file_name=file.filename,
        mime_type=file.content_type,
        size_bytes=size,
    )


# =====================================================================
#  Photo
# =====================================================================

@router.post("/upload/photo", response_model=UploadOut)
async def upload_photo(
    file: UploadFile = File(...),
    width: int | None = Form(None),
    height: int | None = Form(None),
    user: User = Depends(get_current_user),
):
    file_url, size = await crud.save_upload(
        file, subdir="photos", owner_id=user.id, default_ext="jpg",
        max_size=crud.MAX_PHOTO, allowed_mime=crud.PHOTO_MIME,
    )
    return UploadOut(
        file_url=file_url,
        file_name=file.filename,
        mime_type=file.content_type,
        size_bytes=size,
        width=width,
        height=height,
    )


# =====================================================================
#  Video
# =====================================================================

@router.post("/upload/video", response_model=UploadOut)
async def upload_video(
    file: UploadFile = File(...),
    width: int | None = Form(None),
    height: int | None = Form(None),
    duration: int | None = Form(None),
    user: User = Depends(get_current_user),
):
    file_url, size = await crud.save_upload(
        file, subdir="videos", owner_id=user.id, default_ext="mp4",
        max_size=int(crud.MAX_VIDEO), allowed_mime=crud.VIDEO_MIME,
    )
    return UploadOut(
        file_url=file_url,
        file_name=file.filename,
        mime_type=file.content_type,
        size_bytes=size,
        width=width,
        height=height,
        duration=duration,
    )


# =====================================================================
#  Voice (голосовое)
# =====================================================================

@router.post("/upload/voice", response_model=UploadOut)
async def upload_voice(
    file: UploadFile = File(...),
    duration: int | None = Form(None),
    user: User = Depends(get_current_user),
):
    file_url, size = await crud.save_upload(
        file, subdir="voice", owner_id=user.id, default_ext="ogg",
        max_size=crud.MAX_VOICE, allowed_mime=crud.VOICE_MIME,
    )
    return UploadOut(
        file_url=file_url,
        file_name=file.filename,
        mime_type=file.content_type,
        size_bytes=size,
        duration=duration,
    )


# =====================================================================
#  Video note (кружок)
# =====================================================================

@router.post("/upload/video-note", response_model=UploadOut)
async def upload_video_note(
    file: UploadFile = File(...),
    duration: int | None = Form(None),
    user: User = Depends(get_current_user),
):
    file_url, size = await crud.save_upload(
        file, subdir="video_notes", owner_id=user.id, default_ext="mp4",
        max_size=crud.MAX_VIDEO_NOTE, allowed_mime=crud.VIDEO_MIME,
    )
    return UploadOut(
        file_url=file_url,
        file_name=file.filename,
        mime_type=file.content_type,
        size_bytes=size,
        duration=duration,
    )


# =====================================================================
#  Audio
# =====================================================================

@router.post("/upload/audio", response_model=UploadOut)
async def upload_audio(
    file: UploadFile = File(...),
    duration: int | None = Form(None),
    user: User = Depends(get_current_user),
):
    file_url, size = await crud.save_upload(
        file, subdir="audio", owner_id=user.id, default_ext="mp3",
        max_size=int(crud.MAX_AUDIO), allowed_mime=crud.AUDIO_MIME,
    )
    return UploadOut(
        file_url=file_url,
        file_name=file.filename,
        mime_type=file.content_type,
        size_bytes=size,
        duration=duration,
    )


# =====================================================================
#  Animation (GIF)
# =====================================================================

@router.post("/upload/animation", response_model=UploadOut)
async def upload_animation(
    file: UploadFile = File(...),
    width: int | None = Form(None),
    height: int | None = Form(None),
    duration: int | None = Form(None),
    user: User = Depends(get_current_user),
):
    file_url, size = await crud.save_upload(
        file, subdir="animations", owner_id=user.id, default_ext="mp4",
        max_size=crud.MAX_PHOTO, allowed_mime=crud.ANIMATION_MIME,
    )
    return UploadOut(
        file_url=file_url,
        file_name=file.filename,
        mime_type=file.content_type,
        size_bytes=size,
        width=width,
        height=height,
        duration=duration,
    )


# =====================================================================
#  File (документ)
# =====================================================================

@router.post("/upload/file", response_model=UploadOut)
async def upload_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    file_url, size = await crud.save_upload(
        file, subdir="files", owner_id=user.id,
        max_size=int(crud.MAX_FILE),
    )
    return UploadOut(
        file_url=file_url,
        file_name=file.filename,
        mime_type=file.content_type,
        size_bytes=size,
    )


# =====================================================================
#  Avatar пользователя
# =====================================================================

@router.post("/upload/avatar", response_model=AvatarUpdateOut)
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    file_url, _ = await crud.save_upload(
        file, subdir="avatars", owner_id=user.id, default_ext="jpg",
        max_size=crud.MAX_AVATAR, allowed_mime=crud.PHOTO_MIME,
    )

    # деактивируем старый current
    db.query(UserAvatar).filter(
        UserAvatar.user_id == user.id, UserAvatar.is_current.is_(True)
    ).update({"is_current": False}, synchronize_session=False)

    db.add(UserAvatar(user_id=user.id, file_url=file_url, is_current=True))
    user.avatar_url = file_url
    db.commit()
    return AvatarUpdateOut(avatar_url=file_url)


@router.delete("/avatar")
def remove_avatar(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.avatar_url:
        crud.remove_file_by_url(user.avatar_url)
    db.query(UserAvatar).filter(
        UserAvatar.user_id == user.id, UserAvatar.is_current.is_(True)
    ).update({"is_current": False}, synchronize_session=False)
    user.avatar_url = None
    db.commit()
    return {"detail": "Avatar removed"}


# =====================================================================
#  Chat avatar
# =====================================================================

@router.post("/upload/chat-avatar/{chat_id}", response_model=AvatarUpdateOut)
async def upload_chat_avatar(
    chat_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = chats_crud.get_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    member = chats_crud.get_member(db, chat_id, user.id)
    if not member or not chats_crud.is_active_member(member):
        raise HTTPException(status_code=403, detail="Not a member of this chat")
    if not (chats_crud.can_admin(member) or chat.can_change_info):
        rights = chats_crud.get_admin_rights(db, chat_id, user.id)
        if not (rights and rights.can_change_info):
            raise HTTPException(status_code=403, detail="Cannot change chat info")

    file_url, _ = await crud.save_upload(
        file, subdir="chat_avatars", owner_id=chat_id, default_ext="jpg",
        max_size=crud.MAX_AVATAR, allowed_mime=crud.PHOTO_MIME,
    )
    if chat.avatar_url:
        crud.remove_file_by_url(chat.avatar_url)
    chat.avatar_url = file_url
    chats_crud.log_admin(db, chat_id=chat.id, actor_id=user.id, action=ChatAdminAction.photo_changed)
    db.commit()
    return AvatarUpdateOut(avatar_url=file_url)


@router.delete("/chat-avatar/{chat_id}")
def remove_chat_avatar(
    chat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = chats_crud.get_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    member = chats_crud.get_member(db, chat_id, user.id)
    if not member or not chats_crud.is_active_member(member):
        raise HTTPException(status_code=403, detail="Not a member of this chat")
    if not (chats_crud.can_admin(member) or chat.can_change_info):
        raise HTTPException(status_code=403, detail="Cannot change chat info")

    if chat.avatar_url:
        crud.remove_file_by_url(chat.avatar_url)
    chat.avatar_url = None
    chats_crud.log_admin(db, chat_id=chat.id, actor_id=user.id, action=ChatAdminAction.photo_removed)
    db.commit()
    return {"detail": "Chat avatar removed"}


# =====================================================================
#  Story media
# =====================================================================

@router.post("/upload/story", response_model=UploadOut)
async def upload_story_media(
    file: UploadFile = File(...),
    width: int | None = Form(None),
    height: int | None = Form(None),
    duration: int | None = Form(None),
    user: User = Depends(get_current_user),
):
    allowed = crud.PHOTO_MIME | crud.VIDEO_MIME
    file_url, size = await crud.save_upload(
        file, subdir="stories", owner_id=user.id, default_ext="jpg",
        max_size=crud.MAX_STORY, allowed_mime=allowed,
    )
    return UploadOut(
        file_url=file_url,
        file_name=file.filename,
        mime_type=file.content_type,
        size_bytes=size,
        width=width,
        height=height,
        duration=duration,
    )
