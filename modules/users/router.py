"""
HTTP API модуля users.

Сюда вынесено всё, что должно работать ДО установки WebSocket-соединения
или то, что не требует real-time:
  • регистрация / логин / refresh / logout
  • профиль (me / update / change-password)
  • активные сессии (как «Активные сеансы» в Telegram)
  • 2FA (облачный пароль)
  • настройки приватности
  • поиск и публичный профиль пользователя
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from models import get_db, User
from dependencies import (
    create_access_token,
    get_current_user,
    get_request_meta,
)
from modules.users.schemas import (
    UserRegister,
    UserLogin,
    PhoneRegister,
    RequestCode,
    RequestCodeResult,
    VerifyCode,
    Token,
    RefreshRequest,
    PasswordChange,
    UserMe,
    UserPublic,
    UserUpdate,
    SessionOut,
    PrivacyOut,
    PrivacyUpdate,
    TwoFactorEnable,
    TwoFactorVerify,
    UsernameHistoryOut,
    UserProfileOut,
    CommonGroupOut,
)
from modules.users.crud import (
    get_user_by_id,
    get_user_by_email,
    get_user_by_username,
    get_user_by_phone,
    get_user_by_identifier,
    search_users,
    create_user,
    update_user,
    change_password,
    verify_password,
    get_username_history,
    create_session,
    get_session_by_token,
    list_user_sessions,
    revoke_session,
    revoke_session_by_id,
    revoke_all_user_sessions,
    touch_session,
    record_login_attempt,
    get_2fa,
    enable_2fa,
    disable_2fa,
    verify_2fa,
    get_privacy,
    update_privacy,
)


router = APIRouter(prefix="/users", tags=["Users"])


# =====================================================================
#  Auth
# =====================================================================

@router.post("/register", response_model=Token, status_code=201)
def register(data: UserRegister, request: Request, db: Session = Depends(get_db)):
    """Регистрация. Сразу возвращает access + refresh токены."""
    if get_user_by_email(db, data.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if data.username and get_user_by_username(db, data.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    if data.phone and get_user_by_phone(db, data.phone):
        raise HTTPException(status_code=400, detail="Phone already registered")

    user = create_user(
        db,
        email=data.email,
        password=data.password,
        username=data.username,
        full_name=data.full_name,
        phone=data.phone,
    )

    meta = get_request_meta(request)
    session = create_session(
        db,
        user.id,
        ip_address=meta["ip_address"],
        user_agent=meta["user_agent"],
    )
    return Token(
        access_token=create_access_token({"sub": str(user.id), "sid": session.id}),
        refresh_token=session.refresh_token,
    )


# =====================================================================
#  Phone auth (OTP) — demo: код возвращается прямо в ответе
# =====================================================================

@router.post("/auth/register-phone", response_model=Token, status_code=201)
def register_phone(data: PhoneRegister, request: Request, db: Session = Depends(get_db)):
    """Регистрация: номер + имя + username. Email генерируем синтетически."""
    if get_user_by_phone(db, data.phone):
        raise HTTPException(status_code=400, detail="Phone already registered")
    if get_user_by_username(db, data.username):
        raise HTTPException(status_code=400, detail="Username already taken")

    digits = "".join(ch for ch in data.phone if ch.isdigit())
    email = f"{digits}@tg.local"
    if get_user_by_email(db, email):
        raise HTTPException(status_code=400, detail="Phone already registered")

    import secrets as _secrets
    user = create_user(
        db,
        email=email,
        password=_secrets.token_urlsafe(16),  # пароль не используется при phone-login
        username=data.username,
        full_name=data.full_name,
        phone=data.phone,
    )
    meta = get_request_meta(request)
    session = create_session(db, user.id, ip_address=meta["ip_address"], user_agent=meta["user_agent"])
    return Token(
        access_token=create_access_token({"sub": str(user.id), "sid": session.id}),
        refresh_token=session.refresh_token,
    )


@router.post("/auth/request-code", response_model=RequestCodeResult)
def request_code(data: RequestCode, db: Session = Depends(get_db)):
    """
    Запрос кода входа по номеру. Возвращает код прямо в ответе (demo).
    В реале код бы ушёл по SMS.
    """
    import random
    from datetime import datetime, timedelta, timezone
    from modules.users.crud import hash_password
    from models import OtpCode, OtpPurpose

    user = get_user_by_phone(db, data.phone)
    code = f"{random.randint(0, 99999):05d}"

    # инвалидируем старые неиспользованные коды для этого номера
    db.query(OtpCode).filter(
        OtpCode.identifier == data.phone,
        OtpCode.used_at.is_(None),
    ).update({"used_at": datetime.now(timezone.utc)}, synchronize_session=False)

    otp = OtpCode(
        user_id=user.id if user else None,
        identifier=data.phone,
        code_hash=hash_password(code),
        purpose=OtpPurpose.login,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db.add(otp)
    db.commit()
    return RequestCodeResult(code=code, phone=data.phone, is_registered=user is not None)


@router.post("/auth/verify-code", response_model=Token)
def verify_code(data: VerifyCode, request: Request, db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    from models import OtpCode

    otp = (
        db.query(OtpCode)
        .filter(OtpCode.identifier == data.phone, OtpCode.used_at.is_(None))
        .order_by(OtpCode.id.desc())
        .first()
    )
    if not otp:
        raise HTTPException(status_code=400, detail="No code requested")

    exp = otp.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Code expired")

    if otp.attempts >= otp.max_attempts:
        raise HTTPException(status_code=400, detail="Too many attempts")

    if not verify_password(data.code, otp.code_hash):
        otp.attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid code")

    otp.used_at = datetime.now(timezone.utc)

    user = get_user_by_phone(db, data.phone)
    if not user:
        db.commit()
        # Нет аккаунта — клиент должен показать регистрацию
        raise HTTPException(status_code=404, detail="PHONE_NOT_REGISTERED")

    meta = get_request_meta(request)
    session = create_session(
        db, user.id,
        device_name=data.device_name,
        ip_address=meta["ip_address"], user_agent=meta["user_agent"],
    )
    db.commit()
    return Token(
        access_token=create_access_token({"sub": str(user.id), "sid": session.id}),
        refresh_token=session.refresh_token,
    )


@router.post("/login", response_model=Token)
def login(data: UserLogin, request: Request, db: Session = Depends(get_db)):
    """Логин по email / username / phone."""
    meta = get_request_meta(request)
    user = get_user_by_identifier(db, data.identifier)

    if not user or not verify_password(data.password, user.hashed_password):
        record_login_attempt(
            db,
            identifier=data.identifier,
            success=False,
            user_id=user.id if user else None,
            **meta,
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")

    record_login_attempt(db, identifier=data.identifier, success=True, user_id=user.id, **meta)

    # Если включена 2FA — на этом этапе вернём специальную ошибку, чтобы клиент
    # запросил облачный пароль через /2fa/verify-login (упрощённая схема).
    if get_2fa(db, user.id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="2FA_REQUIRED",
            headers={"X-2FA": "required"},
        )

    session = create_session(
        db,
        user.id,
        platform=data.platform,
        device_name=data.device_name,
        ip_address=meta["ip_address"],
        user_agent=meta["user_agent"],
    )
    return Token(
        access_token=create_access_token({"sub": str(user.id), "sid": session.id}),
        refresh_token=session.refresh_token,
    )


@router.post("/2fa/verify-login", response_model=Token)
def verify_login_with_2fa(
    data: UserLogin,
    code: TwoFactorVerify,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Завершение логина для пользователей с включённой 2FA.
    Сначала проверяется обычный пароль, затем облачный.
    """
    user = get_user_by_identifier(db, data.identifier)
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_2fa(db, user.id, code.password):
        raise HTTPException(status_code=401, detail="Invalid 2FA password")

    meta = get_request_meta(request)
    session = create_session(
        db,
        user.id,
        platform=data.platform,
        device_name=data.device_name,
        ip_address=meta["ip_address"],
        user_agent=meta["user_agent"],
    )
    return Token(
        access_token=create_access_token({"sub": str(user.id), "sid": session.id}),
        refresh_token=session.refresh_token,
    )


@router.post("/refresh", response_model=Token)
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    session = get_session_by_token(db, payload.refresh_token)
    if not session or session.revoked:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    user = get_user_by_id(db, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    touch_session(db, session)
    return Token(
        access_token=create_access_token({"sub": str(user.id), "sid": session.id}),
        refresh_token=session.refresh_token,
    )


@router.post("/logout")
def logout(payload: RefreshRequest, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    revoke_session(db, payload.refresh_token)
    return {"detail": "Logged out"}


@router.post("/logout-all")
def logout_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    count = revoke_all_user_sessions(db, user.id)
    return {"detail": f"Revoked {count} sessions"}


# =====================================================================
#  Me / Profile
# =====================================================================

@router.get("/me", response_model=UserMe)
def get_me(user: User = Depends(get_current_user)):
    return user


@router.put("/me", response_model=UserMe)
def edit_me(
    data: UserUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    fields = data.model_dump(exclude_unset=True)

    if "username" in fields and fields["username"]:
        existing = get_user_by_username(db, fields["username"])
        if existing and existing.id != user.id:
            raise HTTPException(status_code=400, detail="Username already taken")

    if "phone" in fields and fields["phone"]:
        existing = get_user_by_phone(db, fields["phone"])
        if existing and existing.id != user.id:
            raise HTTPException(status_code=400, detail="Phone already in use")

    # Дату рождения можно задать только один раз — потом менять нельзя
    if "birthday" in fields and fields["birthday"] is not None:
        if user.birthday is not None:
            raise HTTPException(status_code=400, detail="Birthday can only be set once")

    return update_user(db, user, **fields)


@router.post("/me/change-password")
def change_my_password(
    data: PasswordChange,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(data.old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Old password is incorrect")
    change_password(db, user, data.new_password)
    revoke_all_user_sessions(db, user.id)
    return {"detail": "Password changed. Please log in again."}


@router.get("/me/username-history", response_model=list[UsernameHistoryOut])
def my_username_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_username_history(db, user.id)


# =====================================================================
#  Sessions
# =====================================================================

@router.get("/me/sessions", response_model=list[SessionOut])
def list_sessions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return list_user_sessions(db, user.id)


@router.delete("/me/sessions/{session_id}")
def terminate_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not revoke_session_by_id(db, user.id, session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"detail": "Session terminated"}


# =====================================================================
#  Privacy
# =====================================================================

@router.get("/me/privacy", response_model=PrivacyOut)
def my_privacy(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_privacy(db, user.id)


@router.put("/me/privacy", response_model=PrivacyOut)
def edit_privacy(
    data: PrivacyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return update_privacy(db, user.id, **data.model_dump(exclude_unset=True))


# =====================================================================
#  2FA
# =====================================================================

@router.post("/me/2fa/enable")
def enable_my_2fa(
    data: TwoFactorEnable,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    enable_2fa(db, user.id, data.password, data.hint, data.recovery_email)
    return {"detail": "2FA enabled"}


@router.post("/me/2fa/disable")
def disable_my_2fa(
    data: TwoFactorVerify,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_2fa(db, user.id, data.password):
        raise HTTPException(status_code=400, detail="Invalid 2FA password")
    disable_2fa(db, user.id)
    return {"detail": "2FA disabled"}


@router.get("/me/2fa")
def my_2fa_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = get_2fa(db, user.id)
    if not record:
        return {"enabled": False}
    return {
        "enabled": True,
        "hint": record.hint,
        "recovery_email": record.recovery_email,
        "enabled_at": record.enabled_at,
    }


# =====================================================================
#  Public lookup
# =====================================================================

@router.get("/search", response_model=list[UserPublic])
def search(
    q: str = Query(..., min_length=1, max_length=50),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return search_users(db, q)


@router.get("/by-username/{username}", response_model=UserPublic)
def get_by_username(
    username: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    user = get_user_by_username(db, username)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/{user_id}", response_model=UserPublic)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    user = get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/{user_id}/profile", response_model=UserProfileOut)
def get_user_profile(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    user = get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    from models import Contact, Block, ChatMember, Chat, ChatType, ChatMemberRole

    is_contact = (
        db.query(Contact)
        .filter(Contact.owner_id == current.id, Contact.contact_id == user_id)
        .first()
        is not None
    )
    is_blocked = (
        db.query(Block)
        .filter(Block.blocker_id == current.id, Block.blocked_id == user_id)
        .first()
        is not None
    )

    # Общие группы/каналы: чаты, где оба активные участники, тип group/supergroup/channel
    my_chats = (
        db.query(ChatMember.chat_id)
        .filter(
            ChatMember.user_id == current.id,
            ChatMember.role.notin_([ChatMemberRole.left, ChatMemberRole.banned]),
        )
    )
    their_chats = (
        db.query(ChatMember.chat_id)
        .filter(
            ChatMember.user_id == user_id,
            ChatMember.role.notin_([ChatMemberRole.left, ChatMemberRole.banned]),
        )
    )
    common = (
        db.query(Chat)
        .filter(
            Chat.id.in_(my_chats),
            Chat.id.in_(their_chats),
            Chat.type.in_([ChatType.group, ChatType.supergroup, ChatType.channel]),
        )
        .all()
    )

    return UserProfileOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        bio=user.bio,
        is_verified=user.is_verified,
        is_bot=user.is_bot,
        is_online=user.is_online,
        last_seen=user.last_seen,
        name_color=user.name_color,
        birthday=user.birthday,
        is_contact=is_contact,
        is_blocked=is_blocked,
        common_chats=[
            CommonGroupOut(
                id=c.id,
                title=c.title,
                public_username=c.public_username,
                avatar_url=c.avatar_url,
                members_count=c.members_count or 0,
            )
            for c in common
        ],
    )
