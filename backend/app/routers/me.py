import asyncio
import re
from types import SimpleNamespace

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db import get_db, utcnow
from app.errors import ApiError, not_found
from app.models import Group, Message, MessageView, User, UserGroup, Chat
from app.permissions import accessible_chats, user_group_ids
from app.schemas import GroupRef, MeOut, MentionOut, PersonOut, SeenIn, SeenOut, UpdatesOut, UserRef
from app.security import get_current_user
from app.services.audit import audit
from app.services.avatars import avatar_response, save_avatar
from app.services.mentions import readable, tag
from app.services.serialize import load_users, serialize_messages, user_ref
from app.ws import manager, notify_chat

router = APIRouter(tags=["me & people"])


async def groups_of(db: AsyncSession, user_id: int) -> list[dict]:
    rows = await db.execute(
        select(Group.id, Group.name)
        .join(UserGroup, UserGroup.group_id == Group.id)
        .where(UserGroup.user_id == user_id)
        .order_by(Group.name)
    )
    return [{"id": gid, "name": name} for gid, name in rows]


async def me_out(db: AsyncSession, user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "bio": user.bio,
        "is_admin": user.is_admin,
        "groups": await groups_of(db, user.id),
    }


def person(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "display_name": u.display_name,
        "online": manager.is_online(u.id),
        "active": u.is_active,
    }


@router.get("/me", response_model=MeOut, summary="My profile and groups")
async def get_me(me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await me_out(db, me)


@router.get("/me/groups", response_model=list[GroupRef], summary="Groups I belong to")
async def my_groups(me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await groups_of(db, me.id)


@router.get("/me/mentions", response_model=list[MentionOut], summary="Replies addressed to me (newest first)")
async def my_mentions(
    since_id: int | None = Query(None, description="Only mentions with id > since_id"),
    before_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Message, Chat.title)
        .join(Chat, Chat.id == Message.chat_id)
        .where(Message.reply_to_user_id == me.id, Message.author_id != me.id)
        .order_by(Message.id.desc())
        .limit(limit)
    )
    if not me.is_admin:
        q = q.where(Chat.group_id.in_(select(UserGroup.group_id).where(UserGroup.user_id == me.id)))
    if since_id is not None:
        q = q.where(Message.id > since_id)
    if before_id is not None:
        q = q.where(Message.id < before_id)
    rows = (await db.execute(q)).all()
    data = await serialize_messages(db, [m for m, _ in rows], me)
    for item, (_, title) in zip(data, rows):
        item["chat_title"] = title
    return data


@router.post("/me/avatar", status_code=204, summary="Upload my avatar (website)")
async def upload_my_avatar(
    file: UploadFile = File(...), me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await save_avatar(db, me, file)
    audit(db, me, "me.avatar", target=("user", me.id))
    await db.commit()


@router.get("/people", response_model=list[PersonOut], summary="People who share a group with me")
async def people(
    everyone: bool = Query(False, description="All users of the site (for tagging), including inactive ones"),
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if everyone:
        return [person(u) for u in await db.scalars(select(User).order_by(User.display_name))]
    q = select(User).where(User.is_active).order_by(User.display_name)
    if not me.is_admin:
        shared = select(UserGroup.user_id).where(
            UserGroup.group_id.in_(select(UserGroup.group_id).where(UserGroup.user_id == me.id))
        )
        q = q.where(or_(User.id.in_(shared), User.is_admin, User.id == me.id))
    return [person(u) for u in await db.scalars(q)]


@router.get("/groups/{group_id}/members", response_model=list[PersonOut], summary="Members of one of my groups")
async def group_members(group_id: int, me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    group = await db.get(Group, group_id)
    if group is None:
        raise not_found("Group", group_id)
    if not me.is_admin and group_id not in await user_group_ids(db, me):
        raise ApiError(403, "not_group_member", f"You are not a member of group '{group.name}'.")
    rows = await db.scalars(
        select(User)
        .join(UserGroup, UserGroup.user_id == User.id)
        .where(UserGroup.group_id == group_id, User.is_active)
        .order_by(User.display_name)
    )
    return [person(u) for u in rows]


@router.get("/users/{user_id}/avatar", summary="User icon image (public, for <img> tags)")
async def user_avatar(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if user is None:
        raise not_found("User", user_id)
    return avatar_response(user)


@router.get("/users/{user_id}", response_model=UserRef, summary="Basic info about a user")
async def get_user(user_id: int, _: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if user is None:
        raise not_found("User", user_id)
    return user


# ---------- what's new (polling / long-polling) ----------
CURSOR_RE = re.compile(r"^m(\d+)\.w(\d+)$")
UPDATE_SETTLE_SECONDS = 1.5


def _mention_pattern(user_id: int, username: str, display_name: str) -> re.Pattern:
    """Matches a `<@id>` tag, @username, the full display name or the first name, as whole words."""
    names = {username, display_name}
    first = display_name.split()[0] if display_name.split() else ""
    if len(first) >= 3:
        names.add(first)
    alternatives = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True) if n)
    return re.compile(rf"{re.escape(tag(user_id))}|(?<!\w)@?(?:{alternatives})(?!\w)", re.IGNORECASE)


async def _my_threads(db: AsyncSession, me_id: int, comment_ids: set[int]) -> set[int]:
    """Of these top-level comments, the ones I wrote or replied under (at any level)."""
    if not comment_ids:
        return set()
    parent = aliased(Message)
    thread = func.coalesce(parent.parent_id, Message.parent_id, Message.id)
    rows = await db.execute(
        select(thread)
        .select_from(Message)
        .outerjoin(parent, parent.id == Message.parent_id)
        .where(Message.author_id == me_id, thread.in_(comment_ids))
        .distinct()
    )
    return set(rows.scalars())


async def _thread_roots(db: AsyncSession, messages: list[Message]) -> dict[int, int]:
    """The top-level comment id of each message (replies nest up to three levels)."""
    parent_ids = {m.parent_id for m in messages if m.parent_id}
    grandparents = {}
    if parent_ids:
        grandparents = dict((await db.execute(select(Message.id, Message.parent_id).where(Message.id.in_(parent_ids)))).all())
    return {m.id: grandparents.get(m.parent_id) or m.parent_id or m.id for m in messages}


async def _collect_updates(
    db: AsyncSession, me_id: int, is_admin: bool, mention: re.Pattern, m_after: int, w_after: int, limit: int
):
    access = accessible_chats(me_id, is_admin)
    msg_rows = (
        await db.execute(
            select(Message, Chat.title)
            .join(Chat, Chat.id == Message.chat_id)
            .where(Message.id > m_after, Message.author_id != me_id, access)
            .order_by(Message.id)
            .limit(limit)
        )
    ).all()
    chat_rows = (
        await db.execute(
            select(Chat, Group.name)
            .join(Group, Group.id == Chat.group_id)
            .where(Chat.id > w_after, Chat.created_by != me_id, access)
            .order_by(Chat.id)
            .limit(limit)
        )
    ).all()

    messages = await serialize_messages(db, [m for m, _ in msg_rows], SimpleNamespace(id=me_id))
    roots = await _thread_roots(db, [m for m, _ in msg_rows])
    my_threads = await _my_threads(db, me_id, {roots[m.id] for m, _ in msg_rows if m.parent_id})
    for item, (m, title) in zip(messages, msg_rows):
        item["chat_title"] = title
        item["is_reply_to_me"] = m.reply_to_user_id == me_id
        item["mentions_me"] = bool(mention.search(m.body))
        item["in_my_thread"] = bool(m.parent_id) and roots[m.id] in my_threads
    authors = await load_users(db, [w.created_by for w, _ in chat_rows])
    previews = await readable(db, [w.body[:300] for w, _ in chat_rows])
    new_chats = [
        {
            "id": w.id,
            "title": w.title,
            "group_id": w.group_id,
            "group_name": group_name,
            "status": w.status,
            "created_at": w.created_at,
            "author": user_ref(authors[w.created_by]),
            "body_preview": preview,
            "mentions_me": me_id in (w.tagged_user_ids or []) or bool(mention.search(w.body)),
        }
        for (w, group_name), preview in zip(chat_rows, previews)
    ]
    m_next = msg_rows[-1][0].id if msg_rows else m_after
    w_next = chat_rows[-1][0].id if chat_rows else w_after
    return f"m{m_next}.w{w_next}", new_chats, messages


@router.get("/me/updates", response_model=UpdatesOut, summary="What's new since my cursor (optionally wait for it)")
async def my_updates(
    cursor: str | None = Query(None, description="From the previous response. Omit on the first call."),
    wait: int = Query(0, ge=0, le=55, description="Seconds to wait for new activity when there is none yet"),
    limit: int = Query(100, ge=1, le=500),
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """New messages written by others and new chats in my groups, after `cursor`.

    The first call (no cursor) returns the current cursor plus the chats that have unread messages.
    With `wait`, the request is held open until something new arrives or the time runs out (long-poll)."""
    me_id, is_admin = me.id, me.is_admin
    if cursor is None:
        from app.routers.chats import list_chats  # local import: chats.py is a sibling router

        m_max = await db.scalar(select(func.coalesce(func.max(Message.id), 0)))
        w_max = await db.scalar(select(func.coalesce(func.max(Chat.id), 0)))
        chats = await list_chats("all", None, None, None, 500, 0, me, db)
        return {
            "cursor": f"m{m_max}.w{w_max}",
            "new_chats": [],
            "messages": [],
            "unread_chats": [w for w in chats if w["unread_count"] > 0],
        }

    match = CURSOR_RE.match(cursor)
    if not match:
        raise ApiError(422, "validation_error", "Invalid cursor. Use the `cursor` value from a previous response.")
    m_after, w_after = int(match[1]), int(match[2])

    mention = _mention_pattern(me.id, me.username, me.display_name)  # read before rollback() expires `me`
    loop = asyncio.get_running_loop()
    deadline = loop.time() + wait
    while True:
        # Register before querying so activity between the query and the wait is not missed.
        event = manager.add_waiter(me_id)
        woken = False
        try:
            next_cursor, new_chats, messages = await _collect_updates(
                db, me_id, is_admin, mention, m_after, w_after, limit
            )
            remaining = deadline - loop.time()
            if new_chats or messages or remaining <= 0:
                return {"cursor": next_cursor, "new_chats": new_chats, "messages": messages, "unread_chats": []}
            await db.rollback()  # return the DB connection to the pool while waiting
            try:
                await asyncio.wait_for(event.wait(), remaining)
                woken = True
            except TimeoutError:
                pass
        finally:
            manager.remove_waiter(me_id, event)
        if woken:
            # People often post several messages in a row: collect them into one batch.
            await asyncio.sleep(min(UPDATE_SETTLE_SECONDS, max(deadline - loop.time(), 0)))


@router.post("/me/seen", response_model=SeenOut, summary="Mark messages as seen by me (used by the MCP)")
async def mark_seen(payload: SeenIn, me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """The MCP server calls this with the ids of the messages it showed to the AI, so others see who read
    them ("seen by"). The website never calls it. Admins, my own messages and messages I can't access are
    ignored."""
    if me.is_admin or not payload.message_ids:
        return {"recorded": 0}
    me_ref = user_ref(me)
    rows = (
        await db.execute(
            select(Message.id, Chat)
            .join(Chat, Chat.id == Message.chat_id)
            .where(
                Message.id.in_(set(payload.message_ids)),
                Message.author_id != me.id,
                accessible_chats(me.id, False),
            )
        )
    ).all()
    if not rows:
        return {"recorded": 0}
    stmt = insert(MessageView).values([{"message_id": mid, "user_id": me.id, "seen_at": utcnow()} for mid, _ in rows])
    new_ids = set((await db.scalars(stmt.on_conflict_do_nothing().returning(MessageView.message_id))).all())
    await db.commit()

    by_chat: dict[int, tuple[Chat, list[int]]] = {}
    for mid, chat in rows:
        if mid in new_ids:
            by_chat.setdefault(chat.id, (chat, []))[1].append(mid)
    for chat, ids in by_chat.values():
        event = {"type": "message.seen", "user": me_ref, "message_ids": sorted(ids)}
        await notify_chat(db, chat, event, wake=False)
    return {"recorded": len(new_ids)}
