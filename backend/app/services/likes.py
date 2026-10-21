from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MessageLike, User, Chat, ChatLike
from app.services.audit import audit
from app.services.serialize import user_ref
from app.ws import notify_chat


async def set_chat_like(db: AsyncSession, chat: Chat, user: User, liked: bool) -> dict:
    if liked:
        await db.execute(insert(ChatLike).values(chat_id=chat.id, user_id=user.id).on_conflict_do_nothing())
    else:
        await db.execute(delete(ChatLike).where(ChatLike.chat_id == chat.id, ChatLike.user_id == user.id))
    audit(db, user, "chat.like" if liked else "chat.unlike", target=("chat", chat.id), chat=chat)
    await db.commit()
    count = await db.scalar(select(func.count()).select_from(ChatLike).where(ChatLike.chat_id == chat.id))
    await _broadcast(db, chat, "chat", chat.id, count, user, liked)
    return {"count": count, "liked_by_me": liked}


async def set_message_like(db: AsyncSession, chat: Chat, message_id: int, user: User, liked: bool) -> dict:
    if liked:
        await db.execute(
            insert(MessageLike).values(message_id=message_id, user_id=user.id).on_conflict_do_nothing()
        )
    else:
        await db.execute(
            delete(MessageLike).where(MessageLike.message_id == message_id, MessageLike.user_id == user.id)
        )
    audit(db, user, "message.like" if liked else "message.unlike", target=("message", message_id), chat=chat)
    await db.commit()
    count = await db.scalar(
        select(func.count()).select_from(MessageLike).where(MessageLike.message_id == message_id)
    )
    await _broadcast(db, chat, "message", message_id, count, user, liked)
    return {"count": count, "liked_by_me": liked}


async def _broadcast(db, chat, target_type, target_id, count, user, liked) -> None:
    await notify_chat(
        db,
        chat,
        {
            "type": "like.changed",
            "target_type": target_type,
            "target_id": target_id,
            "count": count,
            "user": user_ref(user),
            "liked": liked,
        },
    )
