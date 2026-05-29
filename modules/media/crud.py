"""
Сохранение медиа на диск.

Структура:
    media_files/
        photos/{user_id}/{uuid}.{ext}
        videos/{user_id}/{uuid}.{ext}
        voice/{user_id}/{uuid}.ogg
        video_notes/{user_id}/{uuid}.mp4
        audio/{user_id}/{uuid}.{ext}
        animations/{user_id}/{uuid}.{ext}
        files/{user_id}/{uuid}.{ext}
        avatars/{user_id}/{uuid}.{ext}
        chat_avatars/{chat_id}/{uuid}.{ext}
        stories/{user_id}/{uuid}.{ext}

Возвращаемый file_url — относительный путь /media-files/..., который
раздаётся StaticFiles из main.py.
"""
import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from config import MEDIA_DIR


# Лимиты в байтах
MAX_PHOTO = 20 * 1024 * 1024            # 20 MB
MAX_VIDEO = 2 * 1024 * 1024 * 1024      # 2 GB (как в TG)
MAX_VOICE = 50 * 1024 * 1024
MAX_VIDEO_NOTE = 200 * 1024 * 1024
MAX_AUDIO = 1.5 * 1024 * 1024 * 1024
MAX_FILE = 2 * 1024 * 1024 * 1024
MAX_AVATAR = 10 * 1024 * 1024
MAX_STORY = 100 * 1024 * 1024
MAX_GENERIC = MAX_FILE


# Допустимые mime-префиксы для категорий
PHOTO_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/heic", "image/heif"}
VIDEO_MIME = {"video/mp4", "video/quicktime", "video/webm", "video/x-matroska"}
VOICE_MIME = {"audio/ogg", "audio/opus", "audio/webm"}
AUDIO_MIME = {"audio/mpeg", "audio/mp4", "audio/aac", "audio/ogg", "audio/flac", "audio/wav", "audio/x-wav"}
ANIMATION_MIME = {"image/gif", "video/mp4"}


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _safe_ext(filename: str | None, default: str) -> str:
    if not filename:
        return default
    ext = Path(filename).suffix.lower().lstrip(".")
    # whitelist для базовой защиты от исполняемых
    if not ext or len(ext) > 8 or not ext.isalnum():
        return default
    return ext


def _public_url(rel_path: str) -> str:
    # rel_path — относительно MEDIA_DIR
    return f"/media-files/{rel_path}".replace("\\", "/")


async def save_upload(
    upload: UploadFile,
    *,
    subdir: str,
    owner_id: int,
    default_ext: str = "bin",
    max_size: int | None = None,
    allowed_mime: set[str] | None = None,
) -> tuple[str, int]:
    """
    Сохраняет UploadFile в `MEDIA_DIR/{subdir}/{owner_id}/{uuid}.{ext}`.
    Возвращает (public_url, size_bytes).
    """
    if upload.size is not None and max_size is not None and upload.size > max_size:
        raise HTTPException(status_code=413, detail=f"File too large (max {max_size} bytes)")

    if allowed_mime is not None and upload.content_type and upload.content_type not in allowed_mime:
        raise HTTPException(status_code=415, detail=f"Unsupported media type: {upload.content_type}")

    ext = _safe_ext(upload.filename, default_ext)
    target_dir = Path(MEDIA_DIR) / subdir / str(owner_id)
    _ensure_dir(target_dir)
    target_name = f"{uuid.uuid4().hex}.{ext}"
    target_path = target_dir / target_name

    # Стримим чанками, считаем размер
    written = 0
    chunk_size = 1024 * 1024
    with open(target_path, "wb") as fh:
        while True:
            chunk = await upload.read(chunk_size)
            if not chunk:
                break
            written += len(chunk)
            if max_size is not None and written > max_size:
                fh.close()
                target_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"File too large (max {max_size} bytes)")
            fh.write(chunk)

    rel = f"{subdir}/{owner_id}/{target_name}"
    return _public_url(rel), written


def remove_file_by_url(url: str) -> bool:
    """Удаляет файл по public-url. Используется при смене аватара."""
    if not url or not url.startswith("/media-files/"):
        return False
    rel = url[len("/media-files/"):]
    target = Path(MEDIA_DIR) / rel
    try:
        target.unlink(missing_ok=True)
        return True
    except OSError:
        return False
