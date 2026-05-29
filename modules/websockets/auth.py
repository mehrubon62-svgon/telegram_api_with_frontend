"""Аутентификация WS-подключения по JWT (token в query)."""
from jose import JWTError
from sqlalchemy.orm import Session

from models import User
from dependencies import decode_token


def authenticate_ws_token(db: Session, token: str) -> User | None:
    if not token:
        return None
    try:
        payload = decode_token(token)
    except JWTError:
        return None
    sub = payload.get("sub")
    if not sub:
        return None
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        return None
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        return None
    return user
