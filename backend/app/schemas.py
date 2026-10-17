from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

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
class AttachmentOut(BaseModel):
    id: int = Field(description="Download the file with GET /attachments/{id}/file (same Bearer token).")
    filename: str
    content_type: str
    size: int = Field(description="Bytes")
    kind: Literal["image", "audio", "video", "file"] = Field(
        description="image / audio / video are shown as previews on the website; file as a download card."
    )


class AttachmentInfoOut(AttachmentOut):
    work_id: int
    message_id: int | None = Field(description="The message it belongs to; null if on the work post or unsent.")
    on_work: bool = Field(description="Attached to the work post itself.")


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
    seen_by: list[UserRef] = Field(
        default_factory=list,
        description="Users whose AI agent read this message through the MCP, first seen first. Admins are not listed.",
    )
    attachments: list[AttachmentOut] = Field(default_factory=list)
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
    attachments: list[AttachmentOut] = Field(default_factory=list, description="Files attached to the work post.")


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
    if len(v) > settings.max_message_length:
        raise ValueError(f"must be at most {settings.max_message_length} characters")
    return v


class MessageIn(BaseModel):
    body: str = Field(default="", description="Markdown text. May be empty when files are attached.")
    attachment_ids: list[int] = Field(
        default_factory=list,
        description="Ids of files you uploaded to this work with POST /works/{id}/attachments (each used once).",
    )

    _v = field_validator("body")(_check_body)

    @model_validator(mode="after")
    def _text_or_files(self):
        if not self.body.strip() and not self.attachment_ids:
            raise ValueError("Write a message or attach a file.")
        return self


class ReplyIn(MessageIn):
    reply_to_user_id: int | None = Field(
        default=None, description="Whose name to tag. Defaults to the author of the message you reply to."
    )


class ReadIn(BaseModel):
    last_read_message_id: int | None = None


class SeenIn(BaseModel):
    message_ids: list[int] = Field(max_length=500, description="Ids of the messages the AI was shown.")


class SeenOut(BaseModel):
    recorded: int = Field(description="How many messages were newly marked as seen by you.")


# ---------- updates (what's new) ----------
class UpdateMessageOut(MessageOut):
    work_title: str
    is_reply_to_me: bool
    mentions_me: bool = Field(description="The text names me (@username, my name or first name).")
    in_my_thread: bool = Field(description="A reply (at any level) under a comment I wrote or replied to.")


class NewWorkOut(BaseModel):
    id: int
    title: str
    group_id: int
    group_name: str
    status: Literal["open", "closed"]
    created_at: datetime
    author: UserRef
    body_preview: str


class UpdatesOut(BaseModel):
    cursor: str = Field(description="Pass back as `cursor` next time to get only newer activity.")
    new_works: list[NewWorkOut]
    messages: list[UpdateMessageOut]
    unread_works: list[WorkListItem] = Field(
        description="Only filled on the first call (no cursor): works that currently have unread messages."
    )


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
    attachment_ids: list[int] = Field(
        default_factory=list, description="Uploads (POST /works/{id}/attachments) to add to the work post."
    )
    remove_attachment_ids: list[int] = Field(
        default_factory=list, description="Files of the work post to delete."
    )
