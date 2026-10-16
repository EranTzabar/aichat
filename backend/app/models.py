from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow

TS = DateTime(timezone=True)


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


class Work(Base):
    __tablename__ = "works"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(10), default="open")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    last_activity_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_work_id_id", "work_id", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=True
    )
    reply_to_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class WorkLike(Base):
    __tablename__ = "work_likes"

    work_id: Mapped[int] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class MessageLike(Base):
    __tablename__ = "message_likes"

    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class WorkRead(Base):
    __tablename__ = "work_reads"

    work_id: Mapped[int] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    last_read_message_id: Mapped[int] = mapped_column(Integer, default=0)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    status_code: Mapped[int] = mapped_column(Integer)
    response: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
