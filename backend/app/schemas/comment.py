from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CommentCreateRequest(_Strict):
    who: str = Field(min_length=1, max_length=64)
    email: EmailStr
    body: str = Field(min_length=1, max_length=4000)


class CommentCreateResponse(_Strict):
    id: int
    status: Literal["pending", "approved", "spam"]


class PublicCommentItem(_Strict):
    id: int
    who: str
    body: str
    created_at: datetime
    admin_reply: "PublicAdminReply | None" = None


class PublicAdminReply(_Strict):
    id: int
    who: str
    body: str
    created_at: datetime


PublicCommentItem.model_rebuild()


class AdminCommentItem(_Strict):
    id: int
    post_id: str
    post_title: str | None
    parent_id: int | None
    who: str
    email_hash: str | None
    body: str
    status: str
    flag: bool
    actor: str
    created_at: datetime


class AdminCommentPatchRequest(_Strict):
    status: Literal["pending", "approved", "spam"] | None = None
    flag: bool | None = None
    reply_body: str | None = Field(default=None, min_length=1, max_length=4000)


class AdminCommentPatchResponse(_Strict):
    id: int
    status: str
    flag: bool
    reply_id: int | None = None
