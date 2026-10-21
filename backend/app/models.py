from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, Computed, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow

TS = DateTime(timezone=True)


def search_column(expression: str) -> Mapped:
    """A full-text search vector kept up to date by Postgres; never loaded with the row."""
    return mapped_column(TSVECTOR, Computed(expression, persisted=True), deferred=True)


# The 'simple' config: no stemming, so Hebrew and English search the same way.
CHAT_TSV = "setweight(to_tsvector('simple'::regconfig, title), 'A') || setweight(to_tsvector('simple'::regconfig, body), 'B')"
MESSAGE_TSV = "to_tsvector('simple'::regconfig, body)"
ATTACHMENT_TSV = (
    "setweight(to_tsvector('simple'::regconfig, filename), 'A') || "
    "setweight(to_tsvector('simple'::regconfig, coalesce(text_content, '')), 'B')"
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    bio: Mapped[str] = mapped_column(Text, default="")
    password_hash: Mapped[str] = mapped_column(String(200))
    avatar_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    api_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    token_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    last_api_use_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class UserGroup(Base):
    __tablename__ = "user_groups"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)


class Chat(Base):
    __tablename__ = "chats"
    __table_args__ = (Index("ix_chats_search", "search_tsv", postgresql_using="gin"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(10), default="open")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    last_activity_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)
    search_tsv: Mapped[str] = search_column(CHAT_TSV)
    # Automation (see app/services/schedule.py).
    tagged_user_ids: Mapped[list[int]] = mapped_column(JSONB, default=list, server_default="[]")
    # {every: daily|weekly, weekday 0=Mon, time "HH:MM", close_after_days?}: opens a copy each time, closing the last.
    repeat: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    repeat_last_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    series_id: Mapped[int | None] = mapped_column(ForeignKey("chats.id", ondelete="SET NULL"), nullable=True, index=True)
    close_at: Mapped[datetime | None] = mapped_column(TS, nullable=True, index=True)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_chat_id_id", "chat_id", "id"),
        Index("ix_messages_search", "search_tsv", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=True
    )
    reply_to_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    search_tsv: Mapped[str] = search_column(MESSAGE_TSV)


class ChatLike(Base):
    __tablename__ = "chat_likes"

    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class MessageLike(Base):
    __tablename__ = "message_likes"

    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class Attachment(Base):
    """A file in a chat. Unsent (message_id NULL and not on_chat) right after upload; then it belongs to a
    message or to the chat post. The bytes live in storage (R2 or disk) under `storage_key`."""

    __tablename__ = "attachments"
    __table_args__ = (Index("ix_attachments_search", "search_tsv", postgresql_using="gin"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    uploader_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=True, index=True
    )
    on_chat: Mapped[bool] = mapped_column(Boolean, default=False)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(200))
    size: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    # The text of a text / code file (up to 1 MB), so search finds words inside it.
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True, deferred=True)
    search_tsv: Mapped[str] = search_column(ATTACHMENT_TSV)


class MessageView(Base):
    """A user's AI agent read this message through the MCP (shown on the site as "seen by")."""

    __tablename__ = "message_views"

    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    seen_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class ChatRead(Base):
    __tablename__ = "chat_reads"

    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    last_read_message_id: Mapped[int] = mapped_column(Integer, default=0)


class AuditEvent(Base):
    """One action in the audit log (admin only). `via`: web (website session), api (an API key, so an AI or a
    script) or auto (the server's scheduler). chat_id / group_id have no foreign key, so the row stays after the chat is deleted."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_actor_id_id", "actor_id", "id"),
        Index("ix_audit_events_action_id", "action", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    via: Mapped[str] = mapped_column(String(10))
    action: Mapped[str] = mapped_column(String(50))
    target_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chat_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    group_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    status_code: Mapped[int] = mapped_column(Integer)
    response: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
