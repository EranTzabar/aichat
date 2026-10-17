"""Turn ORM rows into API dicts. Loads related users/likes in bulk (no N+1)."""
from collections import defaultdict
from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.models import Group, Message, MessageLike, MessageView, User, Work, WorkLike
from app.services.attachments import message_attachments, work_attachments


def user_ref(u: User) -> dict:
    return {"id": u.id, "username": u.username, "display_name": u.display_name}


async def load_users(db: AsyncSession, ids: Iterable[int | None]) -> dict[int, User]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    rows = await db.scalars(select(User).where(User.id.in_(wanted)))
    return {u.id: u for u in rows}


def _likes(user_ids: list[int], users: dict[int, User], me_id: int) -> tuple[dict, bool]:
    return (
        {"count": len(user_ids), "users": [user_ref(users[i]) for i in user_ids]},
        me_id in user_ids,
    )


async def serialize_messages(db: AsyncSession, messages: Sequence[Message], me: User) -> list[dict]:
    """Flat list, same order as given."""
    if not messages:
        return []
    likes: dict[int, list[int]] = defaultdict(list)
    rows = await db.execute(
        select(MessageLike.message_id, MessageLike.user_id)
        .where(MessageLike.message_id.in_([m.id for m in messages]))
        .order_by(MessageLike.user_id)
    )
    for message_id, user_id in rows:
        likes[message_id].append(user_id)

    # Seen by: users whose AI read the message through the MCP. Admins are never listed.
    seen: dict[int, list[int]] = defaultdict(list)
    rows = await db.execute(
        select(MessageView.message_id, MessageView.user_id)
        .join(User, User.id == MessageView.user_id)
        .where(MessageView.message_id.in_([m.id for m in messages]), User.is_admin.is_(False))
        .order_by(MessageView.seen_at, MessageView.user_id)
    )
    for message_id, user_id in rows:
        seen[message_id].append(user_id)

    files = await message_attachments(db, [m.id for m in messages])

    user_ids = [m.author_id for m in messages] + [m.reply_to_user_id for m in messages]
    user_ids += [u for ids in likes.values() for u in ids]
    user_ids += [u for ids in seen.values() for u in ids]
    users = await load_users(db, user_ids)

    out = []
    for m in messages:
        like_obj, liked = _likes(likes[m.id], users, me.id)
        out.append(
            {
                "id": m.id,
                "work_id": m.work_id,
                "parent_id": m.parent_id,
                "body": m.body,
                "created_at": m.created_at,
                "author": user_ref(users[m.author_id]),
                "reply_to": user_ref(users[m.reply_to_user_id]) if m.reply_to_user_id else None,
                "likes": like_obj,
                "liked_by_me": liked,
                "seen_by": [user_ref(users[u]) for u in seen[m.id]],
                "attachments": files[m.id],
            }
        )
    return out


async def serialize_work(db: AsyncSession, work: Work, me: User) -> dict:
    group = await db.get(Group, work.group_id)
    like_ids = list(
        (
            await db.scalars(
                select(WorkLike.user_id).where(WorkLike.work_id == work.id).order_by(WorkLike.user_id)
            )
        ).all()
    )
    users = await load_users(db, [work.created_by, *like_ids])
    like_obj, liked = _likes(like_ids, users, me.id)
    return {
        "id": work.id,
        "title": work.title,
        "body": work.body,
        "status": work.status,
        "created_at": work.created_at,
        "last_activity_at": work.last_activity_at,
        "group": {"id": group.id, "name": group.name},
        "author": user_ref(users[work.created_by]),
        "likes": like_obj,
        "liked_by_me": liked,
        "attachments": await work_attachments(db, work.id),
    }


async def build_work_state(db: AsyncSession, work: Work, me: User) -> dict:
    messages = (
        await db.scalars(select(Message).where(Message.work_id == work.id).order_by(Message.id))
    ).all()
    flat = await serialize_messages(db, messages, me)

    # Up to three levels: comments and their replies get a `replies` list; third-level replies don't.
    by_id = {m["id"]: m for m in flat}
    top: list[dict] = []
    for m in flat:
        if m["parent_id"] is None:
            top.append(m)
        if m["parent_id"] is None or by_id[m["parent_id"]]["parent_id"] is None:
            m["replies"] = []
    for m in flat:
        if m["parent_id"] is not None:
            by_id[m["parent_id"]]["replies"].append(m)

    seen: dict[int, dict] = {}
    for m in flat:
        seen.setdefault(m["author"]["id"], m["author"])

    return {
        "server_time": utcnow(),
        "work": await serialize_work(db, work, me),
        "messages": top,
        "participants": list(seen.values()),
    }
