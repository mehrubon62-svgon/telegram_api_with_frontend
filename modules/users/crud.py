"""CRUD-операции для модуля users."""
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import or_
from sqlalchemy.orm import Session

from models import (
    User,
    RoleEnum,
    UserSession,
    UserDevice,
    UsernameHistory,
    LoginAttempt,
    PrivacySetting,
    TwoFactorAuth,
    DevicePlatform,
)
from config import REFRESH_TOKEN_EXPIRE_DAYS


# =====================================================================
#  Passwords
# =====================================================================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# =====================================================================
#  User lookup
# =====================================================================

def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.lower()).first()


def get_user_by_phone(db: Session, phone: str) -> User | None:
    return db.query(User).filter(User.phone == phone).first()


def get_user_by_identifier(db: Session, identifier: str) -> User | None:
    """Найти юзера по email / username / phone."""
    ident = identifier.strip()
    return (
        db.query(User)
        .filter(
            or_(
                User.email == ident.lower(),
                User.username == ident,
                User.phone == ident,
            )
        )
        .first()
    )


def search_users(db: Session, query: str, limit: int = 20) -> list[User]:
    q = f"%{query.lower().lstrip('@')}%"
    return (
        db.query(User)
        .filter(
            User.username.ilike(q),
            User.is_active.is_(True),
        )
        .order_by(User.username.asc())
        .limit(limit)
        .all()
    )


# =====================================================================
#  Mutations
# =====================================================================

def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    username: str | None = None,
    full_name: str | None = None,
    phone: str | None = None,
    role: RoleEnum = RoleEnum.user,
) -> User:
    user = User(
        email=email.lower(),
        username=username,
        phone=phone,
        full_name=full_name,
        hashed_password=hash_password(password),
        role=role,
    )
    db.add(user)
    db.flush()  # получаем user.id

    # Сразу создаём дефолтные privacy-настройки
    db.add(PrivacySetting(user_id=user.id))
    if username:
        db.add(UsernameHistory(user_id=user.id, username=username))

    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user: User, **fields) -> User:
    """
    Обновляет произвольные поля. Если меняется username — пишем в историю.
    """
    new_username = fields.get("username")
    if new_username and new_username != user.username:
        db.add(UsernameHistory(user_id=user.id, username=new_username))

    for key, value in fields.items():
        if value is not None:
            setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, new_password: str) -> None:
    user.hashed_password = hash_password(new_password)
    db.commit()


def set_online(db: Session, user: User, online: bool) -> None:
    user.is_online = online
    user.last_seen = datetime.now(timezone.utc)
    db.commit()


def get_username_history(db: Session, user_id: int) -> list[UsernameHistory]:
    return (
        db.query(UsernameHistory)
        .filter(UsernameHistory.user_id == user_id)
        .order_by(UsernameHistory.changed_at.desc())
        .all()
    )


# =====================================================================
#  Sessions (refresh-токены + устройства)
# =====================================================================

def create_session(
    db: Session,
    user_id: int,
    *,
    platform: DevicePlatform = DevicePlatform.web,
    device_name: str | None = None,
    app_version: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> UserSession:
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    session = UserSession(
        user_id=user_id,
        refresh_token=token,
        platform=platform,
        device_name=device_name,
        app_version=app_version,
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session_by_token(db: Session, token: str) -> UserSession | None:
    return db.query(UserSession).filter(UserSession.refresh_token == token).first()


def list_user_sessions(db: Session, user_id: int) -> list[UserSession]:
    return (
        db.query(UserSession)
        .filter(UserSession.user_id == user_id, UserSession.revoked.is_(False))
        .order_by(UserSession.last_active_at.desc())
        .all()
    )


def revoke_session(db: Session, token: str) -> bool:
    session = get_session_by_token(db, token)
    if not session:
        return False
    session.revoked = True
    db.commit()
    return True


def revoke_session_by_id(db: Session, user_id: int, session_id: int) -> bool:
    session = (
        db.query(UserSession)
        .filter(UserSession.id == session_id, UserSession.user_id == user_id)
        .first()
    )
    if not session:
        return False
    session.revoked = True
    db.commit()
    return True


def revoke_all_user_sessions(db: Session, user_id: int, except_token: str | None = None) -> int:
    q = db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.revoked.is_(False),
    )
    if except_token:
        q = q.filter(UserSession.refresh_token != except_token)
    count = q.update({"revoked": True}, synchronize_session=False)
    db.commit()
    return count


def touch_session(db: Session, session: UserSession) -> None:
    session.last_active_at = datetime.now(timezone.utc)
    db.commit()


# =====================================================================
#  Login attempts (audit)
# =====================================================================

def record_login_attempt(
    db: Session,
    *,
    identifier: str,
    success: bool,
    user_id: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    attempt = LoginAttempt(
        identifier=identifier,
        success=success,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(attempt)
    db.commit()


# =====================================================================
#  2FA
# =====================================================================

def get_2fa(db: Session, user_id: int) -> TwoFactorAuth | None:
    return db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id).first()


def enable_2fa(
    db: Session,
    user_id: int,
    password: str,
    hint: str | None = None,
    recovery_email: str | None = None,
) -> TwoFactorAuth:
    existing = get_2fa(db, user_id)
    if existing:
        existing.hashed_password = hash_password(password)
        existing.hint = hint
        existing.recovery_email = recovery_email
        db.commit()
        db.refresh(existing)
        return existing

    record = TwoFactorAuth(
        user_id=user_id,
        hashed_password=hash_password(password),
        hint=hint,
        recovery_email=recovery_email,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def disable_2fa(db: Session, user_id: int) -> bool:
    record = get_2fa(db, user_id)
    if not record:
        return False
    db.delete(record)
    db.commit()
    return True


def verify_2fa(db: Session, user_id: int, password: str) -> bool:
    record = get_2fa(db, user_id)
    if not record:
        return False
    return verify_password(password, record.hashed_password)


# =====================================================================
#  Privacy
# =====================================================================

def get_privacy(db: Session, user_id: int) -> PrivacySetting:
    privacy = db.query(PrivacySetting).filter(PrivacySetting.user_id == user_id).first()
    if not privacy:
        privacy = PrivacySetting(user_id=user_id)
        db.add(privacy)
        db.commit()
        db.refresh(privacy)
    return privacy


def update_privacy(db: Session, user_id: int, **fields) -> PrivacySetting:
    privacy = get_privacy(db, user_id)
    for key, value in fields.items():
        if value is not None:
            setattr(privacy, key, value)
    db.commit()
    db.refresh(privacy)
    return privacy


# =====================================================================
#  Devices (push)
# =====================================================================

def register_device(
    db: Session,
    user_id: int,
    platform: DevicePlatform,
    push_token: str,
) -> UserDevice:
    device = db.query(UserDevice).filter(UserDevice.push_token == push_token).first()
    if device:
        device.user_id = user_id
        device.platform = platform
        device.is_active = True
        db.commit()
        db.refresh(device)
        return device

    device = UserDevice(user_id=user_id, platform=platform, push_token=push_token)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def unregister_device(db: Session, user_id: int, push_token: str) -> bool:
    device = (
        db.query(UserDevice)
        .filter(UserDevice.user_id == user_id, UserDevice.push_token == push_token)
        .first()
    )
    if not device:
        return False
    device.is_active = False
    db.commit()
    return True
