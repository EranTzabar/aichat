from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, utcnow
from app.errors import ApiError, not_found
from app.models import Attachment, Group, User, Chat
from app.schemas import ChatCreate, ChatOut, ChatUpdate
from app.security import require_admin
from app.services import schedule
from app.services.attachments import attach, remove
from app.services.audit import audit, changes
from app.services.serialize import load_users, serialize_chat
from app.ws import notify_chat

router = APIRouter(prefix="/admin/chats", tags=["admin: chats"])


def _plain(value):
    return value.isoformat() if isinstance(value, datetime) else value


async def _automation(db: AsyncSession, data: dict) -> dict:
    """Check the automation fields that were sent and turn them into column values."""
    out = {}
    if (ids := data.get("tagged_user_ids")) is not None:
        ids = sorted(set(ids))
        found = await load_users(db, ids)
        if missing := [i for i in ids if i not in found]:
            raise ApiError(422, "validation_error", f"User(s) {missing} do not exist.")
        out["tagged_user_ids"] = ids
    if "repeat" in data:
        out["repeat"] = schedule.check_repeat(data["repeat"])
    if data.get("close_after_days"):
        out["close_at"] = utcnow() + timedelta(days=data["close_after_days"])
    elif "close_at" in data:
        out["close_at"] = data["close_at"]
    return out


@router.post("", response_model=ChatOut, status_code=201, summary="Create a new chat in a group")
async def create_chat(payload: ChatCreate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    if await db.get(Group, payload.group_id) is None:
        raise not_found("Group", payload.group_id)
    auto = await _automation(db, payload.model_dump(exclude_unset=True))
    fields = payload.model_dump(include={"group_id", "title", "body", "status"})
    chat = Chat(**fields, **auto, created_by=admin.id)
    if chat.repeat:
        chat.repeat_last_at = utcnow()  # the chat itself is the first one; copies start at the next time
    db.add(chat)
    await db.flush()
    details = {"title": chat.title, **{k: _plain(v) for k, v in auto.items() if v}}
    audit(db, admin, "chat.create", target=("chat", chat.id), chat=chat, details=details)
    await db.commit()
    data = await serialize_chat(db, chat, admin)
    await notify_chat(db, chat, {"type": "chat.created", "chat": data})
    return data


@router.patch("/{chat_id}", response_model=ChatOut, summary="Edit a chat, open/close it, or change its automation")
async def update_chat(
    chat_id: int, payload: ChatUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    chat = await db.get(Chat, chat_id)
    if chat is None:
        raise not_found("Chat", chat_id)
    sent = payload.model_dump(exclude_unset=True)
    fields = {k: v for k, v in sent.items() if k in ("title", "body", "status")}
    auto = await _automation(db, sent)
    details = changes(chat, fields)
    details.update(
        {k: [_plain(getattr(chat, k)), _plain(v)] for k, v in auto.items() if getattr(chat, k) != v}
    )
    action = "chat.update"
    if "status" in details:
        action = "chat.close" if chat.status == "open" else "chat.reopen"
    for key, value in fields.items():
        if value is not None:
            setattr(chat, key, value)
    for key, value in auto.items():
        if key == "repeat" and value and value != chat.repeat:
            chat.repeat_last_at = utcnow()  # a new schedule starts from now, not from the past
        setattr(chat, key, value)
    await attach(db, admin, chat, payload.attachment_ids or [], on_chat=True)
    if payload.remove_attachment_ids:
        doomed = await db.scalars(
            select(Attachment).where(
                Attachment.id.in_(payload.remove_attachment_ids),
                Attachment.chat_id == chat.id,
                Attachment.on_chat.is_(True),
            )
        )
        doomed = list(doomed)
        await remove(db, doomed)
        for a in doomed:
            audit(db, admin, "attachment.remove", target=("attachment", a.id), chat=chat, details={"filename": a.filename})
    if payload.attachment_ids:
        details["attachment_ids"] = payload.attachment_ids
    if details:
        audit(db, admin, action, target=("chat", chat.id), chat=chat, details=details)
    await db.commit()
    data = await serialize_chat(db, chat, admin)
    keys = ("id", "title", "body", "status", "attachments", "mentions", "tagged", "repeat", "next_copy_at", "close_at")
    await notify_chat(db, chat, {"type": "chat.updated", "chat": {k: data[k] for k in keys}})
    return data
