from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

from models import RoleEnum, PrivacyLevel, DevicePlatform


# ---- Auth ----

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    username: str | None = Field(default=None, min_length=3, max_length=50, pattern=r"^[a-zA-Z][a-zA-Z0-9_]{2,49}$")
    full_name: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=20)


class UserLogin(BaseModel):
    identifier: str = Field(description="email / username / phone")
    password: str
    device_name: str | None = None
    platform: DevicePlatform = DevicePlatform.web


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)


# ---- 2FA ----

class TwoFactorEnable(BaseModel):
    password: str = Field(min_length=4, max_length=128)
    hint: str | None = Field(default=None, max_length=150)
    recovery_email: EmailStr | None = None


class TwoFactorVerify(BaseModel):
    password: str


# ---- Profile ----

class UserPublic(BaseModel):
    id: int
    username: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    is_verified: bool
    is_bot: bool
    is_online: bool
    last_seen: datetime

    class Config:
        from_attributes = True


class UserMe(UserPublic):
    email: str
    phone: str | None = None
    language_code: str
    theme: str
    role: RoleEnum
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=50, pattern=r"^[a-zA-Z][a-zA-Z0-9_]{2,49}$")
    full_name: str | None = Field(default=None, max_length=150)
    bio: str | None = Field(default=None, max_length=500)
    avatar_url: str | None = None
    phone: str | None = Field(default=None, max_length=20)
    language_code: str | None = Field(default=None, max_length=8)
    theme: str | None = None


# ---- Sessions ----

class SessionOut(BaseModel):
    id: int
    platform: DevicePlatform
    device_name: str | None = None
    app_version: str | None = None
    ip_address: str | None = None
    country: str | None = None
    city: str | None = None
    is_current: bool
    last_active_at: datetime
    created_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True


# ---- Privacy ----

class PrivacyOut(BaseModel):
    last_seen: PrivacyLevel
    profile_photo: PrivacyLevel
    phone_number: PrivacyLevel
    forwards: PrivacyLevel
    calls: PrivacyLevel
    groups_invite: PrivacyLevel

    class Config:
        from_attributes = True


class PrivacyUpdate(BaseModel):
    last_seen: PrivacyLevel | None = None
    profile_photo: PrivacyLevel | None = None
    phone_number: PrivacyLevel | None = None
    forwards: PrivacyLevel | None = None
    calls: PrivacyLevel | None = None
    groups_invite: PrivacyLevel | None = None


# ---- Username history ----

class UsernameHistoryOut(BaseModel):
    username: str
    changed_at: datetime

    class Config:
        from_attributes = True
