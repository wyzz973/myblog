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
