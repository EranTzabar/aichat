from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import exists, func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, utcnow
from app.models import Group, Message, User, UserGroup, Work, WorkRead
from app.permissions import ensure_open, get_accessible_work
from app.schemas import LikeStatus, MessageIn, MessageOut, ReadIn, WorkListItem, WorkStateOut
from app.security import get_current_user
from app.services import idempotency
from app.services.likes import set_work_like
from app.services.serialize import build_work_state, load_users, serialize_messages, user_ref
from app.ws import notify_work

router = APIRouter(prefix="/works", tags=["works"])

IdemKey = Header(
    default=None,
    alias="Idempotency-Key",
    description="Optional. Retrying with the same key returns the first response instead of posting twice.",
)


def _unread_subquery(me: User):
    last_read = (
        select(WorkRead.last_read_message_id)
        .where(WorkRead.work_id == Work.id, WorkRead.user_id == me.id)
        .correlate(Work)
        .scalar_subquery()
    )
    return (
        select(func.count(Message.id))
        .where(Message.work_id == Work.id, Message.author_id != me.id, Message.id > func.coalesce(last_read, 0))
        .correlate(Work)
        .scalar_subquery()
    )


@router.get("", response_model=list[WorkListItem], summary="List works I can access")
async def list_works(
    filter: Literal["all", "joined", "new"] = Query(
        "all", description="joined = works I created or wrote in; new = works I have not written in yet"
    ),
    status: Literal["open", "closed"] | None = None,
    group_id: int | None = None,
    updated_since: datetime | None = Query(None, description="Only works with activity at/after this time"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    message_count = (
        select(func.count(Message.id)).where(Message.work_id == Work.id).correlate(Work).scalar_subquery()
    )
    joined = or_(
        Work.created_by == me.id,
        exists().where(Message.work_id == Work.id, Message.author_id == me.id),
    )
    q = (
        select(Work, Group.name, message_count, _unread_subquery(me), joined)
        .join(Group, Group.id == Work.group_id)
        .order_by(Work.last_activity_at.desc(), Work.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if not me.is_admin:
        q = q.where(Work.group_id.in_(select(UserGroup.group_id).where(UserGroup.user_id == me.id)))
    if filter == "joined":
        q = q.where(joined)
    elif filter == "new":
        q = q.where(~joined)
    if status:
        q = q.where(Work.status == status)
    if group_id is not None:
        q = q.where(Work.group_id == group_id)
    if updated_since is not None:
        q = q.where(Work.last_activity_at >= updated_since)

    rows = (await db.execute(q)).all()
    ids = [r[0].id for r in rows]
    last_msgs: dict[int, Message] = {}
    if ids:
        latest = await db.scalars(
            select(Message)
            .where(Message.work_id.in_(ids))
            .ext(distinct_on(Message.work_id))
            .order_by(Message.work_id, Message.id.desc())
        )
        last_msgs = {m.work_id: m for m in latest}
    users = await load_users(db, [m.author_id for m in last_msgs.values()])

    out = []
    for work, group_name, count, unread, is_joined in rows:
        lm = last_msgs.get(work.id)
        out.append(
            {
                "id": work.id,
                "title": work.title,
                "group_id": work.group_id,
                "group_name": group_name,
                "status": work.status,
                "created_at": work.created_at,
                "last_activity_at": work.last_activity_at,
                "message_count": count,
                "unread_count": unread,
                "joined": bool(is_joined),
                "last_message": {
                    "id": lm.id,
                    "author": user_ref(users[lm.author_id]),
                    "body_preview": lm.body[:140],
                    "created_at": lm.created_at,
                }
                if lm
                else None,
            }
        )
    return out


@router.get("/{work_id}", response_model=WorkStateOut, summary="Full current state of a work")
async def get_work_state(work_id: int, me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    work = await get_accessible_work(db, me, work_id)
    return await build_work_state(db, work, me)


@router.get("/{work_id}/messages", response_model=list[MessageOut], summary="Messages of a work (flat, oldest first)")
async def list_messages(
    work_id: int,
    since_id: int | None = Query(None, description="Only messages with id > since_id (for polling)"),
    before_id: int | None = Query(None, description="Page backwards: messages with id < before_id"),
    limit: int = Query(100, ge=1, le=500),
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    work = await get_accessible_work(db, me, work_id)
    q = select(Message).where(Message.work_id == work.id)
    if since_id is not None:
        q = q.where(Message.id > since_id)
    if before_id is not None:
        q = q.where(Message.id < before_id).order_by(Message.id.desc()).limit(limit)
        messages = list(reversed((await db.scalars(q)).all()))
    else:
        messages = (await db.scalars(q.order_by(Message.id).limit(limit))).all()
    return await serialize_messages(db, messages, me)


async def create_message(
    db: AsyncSession, work: Work, me: User, body: str, parent_id: int | None, reply_to_user_id: int | None
) -> dict:
    message = Message(
        work_id=work.id, author_id=me.id, parent_id=parent_id, reply_to_user_id=reply_to_user_id, body=body
    )
    db.add(message)
    work.last_activity_at = utcnow()
    await db.commit()
    data = (await serialize_messages(db, [message], me))[0]
    await notify_work(db, work, {"type": "message.created", "message": data})
    return data


@router.post("/{work_id}/messages", response_model=MessageOut, status_code=201, summary="Add a top-level comment")
async def post_comment(
    work_id: int,
    payload: MessageIn,
    idempotency_key: str | None = IdemKey,
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    work = await get_accessible_work(db, me, work_id)
    if cached := await idempotency.replay(db, me, idempotency_key):
        return cached
    ensure_open(work)
    data = await create_message(db, work, me, payload.body, None, None)
    return await idempotency.respond(db, me, idempotency_key, data)


@router.post("/{work_id}/read", summary="Mark the work as read")
async def mark_read(
    work_id: int,
    payload: ReadIn | None = None,
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    work = await get_accessible_work(db, me, work_id)
    last_id = payload.last_read_message_id if payload else None
    if last_id is None:
        last_id = await db.scalar(select(func.coalesce(func.max(Message.id), 0)).where(Message.work_id == work.id))
    stmt = insert(WorkRead).values(work_id=work.id, user_id=me.id, last_read_message_id=last_id)
    await db.execute(
        stmt.on_conflict_do_update(
            index_elements=["work_id", "user_id"],
            set_={
                "last_read_message_id": func.greatest(
                    WorkRead.last_read_message_id, stmt.excluded.last_read_message_id
                )
            },
        )
    )
    await db.commit()
    unread = await db.scalar(select(_unread_subquery(me)).select_from(Work).where(Work.id == work.id))
    return {"work_id": work.id, "last_read_message_id": last_id, "unread_count": unread}


@router.post("/{work_id}/like", response_model=LikeStatus, summary="Like the work")
async def like_work(work_id: int, me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    work = await get_accessible_work(db, me, work_id)
    ensure_open(work)
    return await set_work_like(db, work, me, True)


@router.delete("/{work_id}/like", response_model=LikeStatus, summary="Remove my like from the work")
async def unlike_work(work_id: int, me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    work = await get_accessible_work(db, me, work_id)
    ensure_open(work)
    return await set_work_like(db, work, me, False)
