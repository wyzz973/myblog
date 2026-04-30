from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(_Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class LoginResponse(_Strict):
    access: str
    token_type: str = "bearer"
    expires_in: int


class LoginChallengeResponse(_Strict):
    tfa_required: Literal[True] = True
    challenge: str


class RefreshResponse(_Strict):
    access: str
    token_type: str = "bearer"
    expires_in: int


class TfaSetupResponse(_Strict):
    secret: str
    otpauth_uri: str
    qr_svg: str


class TfaEnableRequest(_Strict):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class TfaDisableRequest(_Strict):
    current_code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class TfaRecoveryCodesResponse(_Strict):
    recovery_codes: list[str]


class TfaChallengeRequest(_Strict):
    challenge: str = Field(min_length=8, max_length=64)
    code: str = Field(min_length=6, max_length=9)


class TfaRegenerateRequest(_Strict):
    current_code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class MagicLinkRequest(_Strict):
    email: EmailStr


class MagicLinkToggleRequest(_Strict):
    enabled: bool


class PasswordChangeRequest(_Strict):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class ApiTokenCreateRequest(_Strict):
    name: str = Field(min_length=1, max_length=64)
    scope: Literal["read", "write"]


class ApiTokenCreateResponse(_Strict):
    id: int
    name: str
    scope: str
    token: str  # raw, shown ONCE


class ApiTokenListItem(_Strict):
    id: int
    name: str
    scope: str
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime
