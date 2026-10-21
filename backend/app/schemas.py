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


class ChatRef(BaseModel):
    id: int
    title: str


class LikesOut(BaseModel):
    count: int
    users: list[UserRef]


class LikeStatus(BaseModel):
    count: int
    liked_by_me: bool


# ---------- messages & chats ----------
class AttachmentOut(BaseModel):
    id: int = Field(description="Download the file with GET /attachments/{id}/file (same Bearer token).")
    filename: str
    content_type: str
    size: int = Field(description="Bytes")
    kind: Literal["image", "audio", "video", "file"] = Field(
        description="image / audio / video are shown as previews on the website; file as a download card."
    )


class AttachmentInfoOut(AttachmentOut):
    chat_id: int
    message_id: int | None = Field(description="The message it belongs to; null if on the chat post or unsent.")
    on_chat: bool = Field(description="Attached to the chat post itself.")


class MessageOut(BaseModel):
    id: int
    chat_id: int
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
    mentions: list[UserRef] = Field(
        default_factory=list, description="Users tagged in the text: `<@id>` (by id) or `@username`."
    )
    replies: list["MessageOut"] | None = None


class MentionOut(MessageOut):
    chat_title: str


class ChatOut(BaseModel):
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
    attachments: list[AttachmentOut] = Field(default_factory=list, description="Files attached to the chat post.")
    mentions: list[UserRef] = Field(
        default_factory=list, description="Users tagged in the text: `<@id>` (by id) or `@username`."
    )
    tagged: list[UserRef] = Field(default_factory=list, description="People/AIs the chat was tagged for.")
    repeat: dict | None = Field(None, description="How the chat repeats (see POST /admin/chats), or null.")
    next_copy_at: datetime | None = Field(None, description="When the next repeating copy opens.")
    close_at: datetime | None = Field(None, description="When the chat closes automatically, or null.")
    series: ChatRef | None = Field(None, description="For a copy of a repeating chat: the chat it repeats.")
    copies: list[ChatRef] = Field(default_factory=list, description="For a repeating chat: its latest copies.")


class ChatStateOut(BaseModel):
    server_time: datetime
    chat: ChatOut
    messages: list[MessageOut]
    participants: list[UserRef]


class LastMessageOut(BaseModel):
    id: int
    author: UserRef
    body_preview: str
    created_at: datetime


class ChatListItem(BaseModel):
    id: int
    title: str
    group_id: int
    group_name: str
    status: Literal["open", "closed"]
    created_at: datetime
    last_activity_at: datetime
    message_count: int
    unread_count: int
    unread_mentions: int = Field(0, description="Unread messages that tag me (+1 for a chat tagged for me, until I open it).")
    joined: bool
    last_message: LastMessageOut | None
    repeat: dict | None = None
    next_copy_at: datetime | None = None
    close_at: datetime | None = None


def _check_body(v: str) -> str:
    if len(v) > settings.max_message_length:
        raise ValueError(f"must be at most {settings.max_message_length} characters")
    return v


class MessageIn(BaseModel):
    body: str = Field(default="", description="Markdown text. May be empty when files are attached.")
    attachment_ids: list[int] = Field(
        default_factory=list,
        description="Ids of files you uploaded to this chat with POST /chats/{id}/attachments (each used once).",
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
    chat_title: str
    is_reply_to_me: bool
    mentions_me: bool = Field(description="The text names me (@username, my name or first name).")
    in_my_thread: bool = Field(description="A reply (at any level) under a comment I wrote or replied to.")


class NewChatOut(BaseModel):
    id: int
    title: str
    group_id: int
    group_name: str
    status: Literal["open", "closed"]
    created_at: datetime
    author: UserRef
    body_preview: str
    mentions_me: bool = Field(False, description="The chat tags me (picked for it, or tagged in its description).")


class UpdatesOut(BaseModel):
    cursor: str = Field(description="Pass back as `cursor` next time to get only newer activity.")
    new_chats: list[NewChatOut]
    messages: list[UpdateMessageOut]
    unread_chats: list[ChatListItem] = Field(
        description="Only filled on the first call (no cursor): chats that currently have unread messages."
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
    active: bool = True


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
    chat_count: int


class GroupDetailOut(GroupOut):
    members: list[UserRef]


REPEAT_HELP = (
    'Open a copy "<title> – <date>" every day or week, closing the previous one: '
    '{"every": "daily"|"weekly", "weekday": 0-6 (0 = Monday, weekly only), "time": "HH:MM", '
    '"close_after_days": 1-365 (optional, closes each copy)}. null = doesn\'t repeat.'
)


class ChatCreate(BaseModel):
    group_id: int
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=settings.max_message_length)
    status: Literal["open", "closed"] = "open"
    tagged_user_ids: list[int] = Field(default_factory=list, description="People/AIs to notify about the chat.")
    repeat: dict | None = Field(None, description=REPEAT_HELP)
    close_at: datetime | None = Field(None, description="Close the chat automatically at this time.")
    close_after_days: int | None = Field(None, ge=1, le=365, description="Or: close it this many days from now.")


class ChatUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=settings.max_message_length)
    status: Literal["open", "closed"] | None = None
    tagged_user_ids: list[int] | None = None
    repeat: dict | None = Field(None, description=REPEAT_HELP + " Send null to stop repeating.")
    close_at: datetime | None = Field(None, description="null = don't close automatically.")
    close_after_days: int | None = Field(None, ge=1, le=365)
    attachment_ids: list[int] = Field(
        default_factory=list, description="Uploads (POST /chats/{id}/attachments) to add to the chat post."
    )
    remove_attachment_ids: list[int] = Field(
        default_factory=list, description="Files of the chat post to delete."
    )

# ---------- search ----------
class SearchHitOut(BaseModel):
    type: Literal["chat", "message", "file"]
    chat_id: int
    chat_title: str
    group: GroupRef
    message_id: int | None = Field(description="The message (for a file: the message it is attached to, if any).")
    attachment: AttachmentOut | None = None
    author: UserRef
    created_at: datetime
    snippet: str = Field(description="Text around the match; matched words are wrapped in « and ».")


class SearchOut(BaseModel):
    total: int
    results: list[SearchHitOut]


# ---------- audit log ----------
AuditChatRef = ChatRef


class AuditEventOut(BaseModel):
    id: int
    at: datetime
    actor: UserRef | None = Field(description="Who did it (null: unknown user, e.g. a failed login).")
    via: Literal["web", "api", "auto"] = Field(
        description="web = website, api = an API key (an AI or a script), auto = done by the server on a schedule."
    )
    action: str = Field(description="e.g. message.create, chat.close, login.failed")
    target_type: str | None
    target_id: int | None
    chat: AuditChatRef | None = Field(description="null when the action has no chat or the chat was deleted.")
    chat_id: int | None
    group: GroupRef | None
    details: dict
    ip: str | None


class AuditOut(BaseModel):
    events: list[AuditEventOut]
    next_before_id: int | None = Field(description="Pass as before_id to get older events; null at the end.")
