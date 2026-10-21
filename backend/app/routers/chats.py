from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Header, Query, UploadFile
from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, utcnow
from app.models import Group, Message, User, UserGroup, Chat, ChatRead
from app.permissions import ensure_open, get_accessible_chat
from app.schemas import AttachmentOut, LikeStatus, MessageIn, MessageOut, ReadIn, ChatListItem, ChatStateOut
from app.security import get_current_user
from app.services import idempotency
from app.services.audit import audit
from app.services.attachments import attach, attachment_out, save_upload
from app.services.likes import set_chat_like
from app.services.mentions import readable, tags_user, chat_tags_user
from app.services.schedule import next_due
from app.services.serialize import build_chat_state, load_users, serialize_messages, user_ref
from app.ws import notify_chat

router = APIRouter(prefix="/chats", tags=["chats"])

IdemKey = Header(
    default=None,
    alias="Idempotency-Key",
    description="Optional. Retrying with the same key returns the first response instead of posting twice.",
)


def _unread_subquery(me: User, *where):
    last_read = (
        select(ChatRead.last_read_message_id)
        .where(ChatRead.chat_id == Chat.id, ChatRead.user_id == me.id)
        .correlate(Chat)
        .scalar_subquery()
    )
    return (
        select(func.count(Message.id))
        .where(Message.chat_id == Chat.id, Message.author_id != me.id, Message.id > func.coalesce(last_read, 0), *where)
        .correlate(Chat)
        .scalar_subquery()
    )


@router.get("", response_model=list[ChatListItem], summary="List chats I can access")
async def list_chats(
    filter: Literal["all", "joined", "new"] = Query(
        "all", description="joined = chats I created or wrote in; new = chats I have not written in yet"
    ),
    status: Literal["open", "closed"] | None = None,
    group_id: int | None = None,
    updated_since: datetime | None = Query(None, description="Only chats with activity at/after this time"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    message_count = (
        select(func.count(Message.id)).where(Message.chat_id == Chat.id).correlate(Chat).scalar_subquery()
    )
    joined = or_(
        Chat.created_by == me.id,
        exists().where(Message.chat_id == Chat.id, Message.author_id == me.id),
    )
    # A chat tagged for me counts as one unread tag until I open it (opening it adds my ChatRead row).
    chat_tag = case(
        (
            and_(
                Chat.created_by != me.id,
                chat_tags_user(me.id, me.username),
                ~exists().where(ChatRead.chat_id == Chat.id, ChatRead.user_id == me.id),
            ),
            1,
        ),
        else_=0,
    )
    unread_tags = _unread_subquery(me, tags_user(me.id, me.username)) + chat_tag
    q = (
        select(Chat, Group.name, message_count, _unread_subquery(me), unread_tags, joined)
        .join(Group, Group.id == Chat.group_id)
        .order_by(Chat.last_activity_at.desc(), Chat.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if not me.is_admin:
        q = q.where(Chat.group_id.in_(select(UserGroup.group_id).where(UserGroup.user_id == me.id)))
    if filter == "joined":
        q = q.where(joined)
    elif filter == "new":
        q = q.where(~joined)
    if status:
        q = q.where(Chat.status == status)
    if group_id is not None:
        q = q.where(Chat.group_id == group_id)
    if updated_since is not None:
        q = q.where(Chat.last_activity_at >= updated_since)

    rows = (await db.execute(q)).all()
    ids = [r[0].id for r in rows]
    last_msgs: dict[int, Message] = {}
    if ids:
        latest = await db.scalars(
            select(Message)
            .where(Message.chat_id.in_(ids))
            .ext(distinct_on(Message.chat_id))
            .order_by(Message.chat_id, Message.id.desc())
        )
        last_msgs = {m.chat_id: m for m in latest}
    users = await load_users(db, [m.author_id for m in last_msgs.values()])
    previews = dict(zip(last_msgs, await readable(db, [m.body[:200] for m in last_msgs.values()])))

    out = []
    for chat, group_name, count, unread, unread_tags, is_joined in rows:
        lm = last_msgs.get(chat.id)
        out.append(
            {
                "id": chat.id,
                "title": chat.title,
                "group_id": chat.group_id,
                "group_name": group_name,
                "status": chat.status,
                "created_at": chat.created_at,
                "last_activity_at": chat.last_activity_at,
                "message_count": count,
                "unread_count": unread,
                "unread_mentions": unread_tags,
                "joined": bool(is_joined),
                "last_message": {
                    "id": lm.id,
                    "author": user_ref(users[lm.author_id]),
                    "body_preview": previews[chat.id][:140],
                    "created_at": lm.created_at,
                }
                if lm
                else None,
                "repeat": chat.repeat,
                "next_copy_at": next_due(chat.repeat) if chat.repeat else None,
                "close_at": chat.close_at,
            }
        )
    return out


@router.get("/{chat_id}", response_model=ChatStateOut, summary="Full current state of a chat")
async def get_chat_state(chat_id: int, me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    chat = await get_accessible_chat(db, me, chat_id)
    return await build_chat_state(db, chat, me)


@router.get("/{chat_id}/messages", response_model=list[MessageOut], summary="Messages of a chat (flat, oldest first)")
async def list_messages(
    chat_id: int,
    since_id: int | None = Query(None, description="Only messages with id > since_id (for polling)"),
    before_id: int | None = Query(None, description="Page backwards: messages with id < before_id"),
    limit: int = Query(100, ge=1, le=500),
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat = await get_accessible_chat(db, me, chat_id)
    q = select(Message).where(Message.chat_id == chat.id)
    if since_id is not None:
        q = q.where(Message.id > since_id)
    if before_id is not None:
        q = q.where(Message.id < before_id).order_by(Message.id.desc()).limit(limit)
        messages = list(reversed((await db.scalars(q)).all()))
    else:
        messages = (await db.scalars(q.order_by(Message.id).limit(limit))).all()
    return await serialize_messages(db, messages, me)


async def create_message(
    db: AsyncSession,
    chat: Chat,
    me: User,
    body: str,
    parent_id: int | None,
    reply_to_user_id: int | None,
    attachment_ids: list[int] | None = None,
) -> dict:
    """Save a comment or reply and tell everyone."""
    message = Message(
        chat_id=chat.id, author_id=me.id, parent_id=parent_id, reply_to_user_id=reply_to_user_id, body=body
    )
    db.add(message)
    await db.flush()
    await attach(db, me, chat, attachment_ids or [], message_id=message.id)
    chat.last_activity_at = utcnow()
    preview = (await readable(db, [body[:200]]))[0][:120]
    details = {"preview": preview, "parent_id": parent_id, "reply_to_user_id": reply_to_user_id}
    if attachment_ids:
        details["attachment_ids"] = attachment_ids
    audit(db, me, "message.create", target=("message", message.id), chat=chat, details=details)
    await db.commit()
    data = (await serialize_messages(db, [message], me))[0]
    await notify_chat(db, chat, {"type": "message.created", "message": data})
    return data


async def thread_parent_id(db: AsyncSession, target: Message) -> int:
    """The parent for a reply to `target`: replies nest three levels, so a reply to a third-level message
    goes under the same second-level message."""
    if target.parent_id is not None:
        parent = await db.get(Message, target.parent_id)
        if parent.parent_id is not None:  # target is on the third level
            return target.parent_id
    return target.id


@router.post("/{chat_id}/messages", response_model=MessageOut, status_code=201, summary="Add a top-level comment")
async def post_comment(
    chat_id: int,
    payload: MessageIn,
    idempotency_key: str | None = IdemKey,
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat = await get_accessible_chat(db, me, chat_id)
    if cached := await idempotency.replay(db, me, idempotency_key):
        return cached
    ensure_open(chat)
    data = await create_message(db, chat, me, payload.body, None, None, payload.attachment_ids)
    return await idempotency.respond(db, me, idempotency_key, data)


@router.post("/{chat_id}/attachments", response_model=AttachmentOut, status_code=201, summary="Upload a file")
async def upload_attachment(
    chat_id: int,
    file: UploadFile = File(..., description="Any file. Images, MP3/WAV/OGG audio and MP4/WEBM/OGG video get previews."),
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a file to a chat, then send it with a comment or reply by passing its id in `attachment_ids`
    (admins: in `attachment_ids` of PATCH /admin/chats/{id} for the chat post). Unsent uploads are deleted
    after 24 hours."""
    chat = await get_accessible_chat(db, me, chat_id)
    if not me.is_admin:
        ensure_open(chat)
    return attachment_out(await save_upload(db, chat, me, file))


@router.post("/{chat_id}/read", summary="Mark the chat as read")
async def mark_read(
    chat_id: int,
    payload: ReadIn | None = None,
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat = await get_accessible_chat(db, me, chat_id)
    last_id = payload.last_read_message_id if payload else None
    if last_id is None:
        last_id = await db.scalar(select(func.coalesce(func.max(Message.id), 0)).where(Message.chat_id == chat.id))
    stmt = insert(ChatRead).values(chat_id=chat.id, user_id=me.id, last_read_message_id=last_id)
    await db.execute(
        stmt.on_conflict_do_update(
            index_elements=["chat_id", "user_id"],
            set_={
                "last_read_message_id": func.greatest(
                    ChatRead.last_read_message_id, stmt.excluded.last_read_message_id
                )
            },
        )
    )
    await db.commit()
    unread = await db.scalar(select(_unread_subquery(me)).select_from(Chat).where(Chat.id == chat.id))
    return {"chat_id": chat.id, "last_read_message_id": last_id, "unread_count": unread}


@router.post("/{chat_id}/like", response_model=LikeStatus, summary="Like the chat")
async def like_chat(chat_id: int, me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    chat = await get_accessible_chat(db, me, chat_id)
    ensure_open(chat)
    return await set_chat_like(db, chat, me, True)


@router.delete("/{chat_id}/like", response_model=LikeStatus, summary="Remove my like from the chat")
async def unlike_chat(chat_id: int, me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    chat = await get_accessible_chat(db, me, chat_id)
    ensure_open(chat)
    return await set_chat_like(db, chat, me, False)
