from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.config import settings


class Out(BaseModel):
    model_config = {"from_attributes": True}


# ---------- shared ----------
class UserRef(Out):
    id: int
    username: str
    display_name: str


class GroupRef(Out):
    id: int
    name: str


class LikesOut(BaseModel):
    count: int
    users: list[UserRef]


class LikeStatus(BaseModel):
    count: int
    liked_by_me: bool


# ---------- messages & works ----------
class MessageOut(BaseModel):
    id: int
    work_id: int
    parent_id: int | None
    body: str
    created_at: datetime
    author: UserRef
    reply_to: UserRef | None
    likes: LikesOut
    liked_by_me: bool
    replies: list["MessageOut"] | None = None


class MentionOut(MessageOut):
    work_title: str


class WorkOut(BaseModel):
    id: int
    title: str
    body: str
    status: Literal["open", "closed"]
    created_at: datetime
    last_activity_at: datetime
    group: GroupRef
    author: UserRef
    likes: LikesOut
    liked_by_me: bool


class WorkStateOut(BaseModel):
    server_time: datetime
    work: WorkOut
    messages: list[MessageOut]
    participants: list[UserRef]


class LastMessageOut(BaseModel):
    id: int
    author: UserRef
    body_preview: str
    created_at: datetime


class WorkListItem(BaseModel):
    id: int
    title: str
    group_id: int
    group_name: str
    status: Literal["open", "closed"]
    created_at: datetime
    last_activity_at: datetime
    message_count: int
    unread_count: int
    joined: bool
    last_message: LastMessageOut | None


def _check_body(v: str) -> str:
    if not v.strip():
        raise ValueError("must not be empty")
    if len(v) > settings.max_message_length:
        raise ValueError(f"must be at most {settings.max_message_length} characters")
    return v


class MessageIn(BaseModel):
    body: str = Field(description="Markdown text")

    _v = field_validator("body")(_check_body)


class ReplyIn(MessageIn):
    reply_to_user_id: int | None = Field(
        default=None, description="Whose name to tag. Defaults to the author of the message you reply to."
    )


class ReadIn(BaseModel):
    last_read_message_id: int | None = None


# ---------- me & people ----------
class MeOut(BaseModel):
    id: int
    username: str
    display_name: str
    bio: str
    is_admin: bool
    groups: list[GroupRef]


class PersonOut(UserRef):
    online: bool


# ---------- auth ----------
class LoginIn(BaseModel):
    username: str
    password: str


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: MeOut


# ---------- admin ----------
class AdminUserOut(BaseModel):
    id: int
    username: str
    display_name: str
    bio: str
    is_admin: bool
    is_active: bool
    api_enabled: bool
    created_at: datetime
    last_login_at: datetime | None
    last_api_use_at: datetime | None
    groups: list[GroupRef]


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6, max_length=200)
    bio: str = ""
    is_admin: bool = False


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    bio: str | None = None
    password: str | None = Field(default=None, min_length=6, max_length=200)
    is_active: bool | None = None
    api_enabled: bool | None = None


class UserGroupsIn(BaseModel):
    group_ids: list[int]


class ApiTokenOut(BaseModel):
    user_id: int
    token: str
    token_version: int
    api_enabled: bool


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


class GroupOut(BaseModel):
    id: int
    name: str
    description: str
    created_at: datetime
    member_count: int
    work_count: int


class GroupDetailOut(GroupOut):
    members: list[UserRef]


class WorkCreate(BaseModel):
    group_id: int
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=settings.max_message_length)
    status: Literal["open", "closed"] = "open"


class WorkUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=settings.max_message_length)
    status: Literal["open", "closed"] | None = None
