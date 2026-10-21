from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import AuditEvent, Group, Chat
from app.schemas import AuditOut
from app.security import require_admin
from app.services.serialize import load_users, user_ref

router = APIRouter(prefix="/admin/audit", tags=["admin: audit log"], dependencies=[Depends(require_admin)])


@router.get("", response_model=AuditOut, summary="The audit log, newest first")
async def list_audit(
    user_id: int | None = Query(None, description="Only actions by this user"),
    group_id: int | None = None,
    chat_id: int | None = None,
    action: str | None = Query(None, max_length=50, description="Action or its start, e.g. `message.` or `login`"),
    via: Literal["web", "api", "auto"] | None = None,
    before_id: int | None = Query(None, description="Only events older than this id (for paging)"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Every change made on the site: messages, uploads, likes, chats, users, groups, tokens and logins. Reading
    (opening a chat, marking read or seen) is not recorded."""
    q = select(AuditEvent)
    if user_id is not None:
        q = q.where(AuditEvent.actor_id == user_id)
    if group_id is not None:
        q = q.where(AuditEvent.group_id == group_id)
    if chat_id is not None:
        q = q.where(AuditEvent.chat_id == chat_id)
    if action:
        q = q.where(AuditEvent.action.startswith(action, autoescape=True))
    if via:
        q = q.where(AuditEvent.via == via)
    if before_id is not None:
        q = q.where(AuditEvent.id < before_id)
    rows = (await db.scalars(q.order_by(AuditEvent.id.desc()).limit(limit + 1))).all()
    more = len(rows) > limit
    rows = rows[:limit]

    users = await load_users(db, (e.actor_id for e in rows))
    chat_ids = {e.chat_id for e in rows if e.chat_id}
    group_ids = {e.group_id for e in rows if e.group_id}
    chats = dict((await db.execute(select(Chat.id, Chat.title).where(Chat.id.in_(chat_ids)))).all()) if chat_ids else {}
    groups = dict((await db.execute(select(Group.id, Group.name).where(Group.id.in_(group_ids)))).all()) if group_ids else {}
    events = [
        {
            "id": e.id,
            "at": e.at,
            "actor": user_ref(users[e.actor_id]) if e.actor_id in users else None,
            "via": e.via,
            "action": e.action,
            "target_type": e.target_type,
            "target_id": e.target_id,
            "chat": {"id": e.chat_id, "title": chats[e.chat_id]} if e.chat_id in chats else None,
            "chat_id": e.chat_id,
            "group": {"id": e.group_id, "name": groups[e.group_id]} if e.group_id in groups else None,
            "details": e.details,
            "ip": e.ip,
        }
        for e in rows
    ]
    return {"events": events, "next_before_id": rows[-1].id if more else None}
