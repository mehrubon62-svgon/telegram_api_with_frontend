from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from models import get_db, User, RoleEnum
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES


api_key_scheme = APIKeyHeader(
    name="Authorization",
    description="Введите: Bearer <ваш_токен>",
    auto_error=True,
)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Декодирует JWT и возвращает payload.
    Бросает JWTError при невалидном токене (истёк/подменён/etc).
    Используется в WebSocket-аутентификации.
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def _extract_token(value: str) -> str:
    if not value:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = value.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header. Expected: 'Bearer <token>'",
        )
    return parts[1].strip()


def get_current_user(
    authorization: str = Depends(api_key_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = _extract_token(authorization)
    try:
        payload = decode_token(token)
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exception
        user_id = int(sub)
    except (JWTError, ValueError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def get_request_meta(request: Request) -> dict:
    """Возвращает IP и User-Agent — пригодится для аудита логинов и сессий."""
    ip = request.client.host if request.client else None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    return {
        "ip_address": ip,
        "user_agent": request.headers.get("user-agent"),
    }
