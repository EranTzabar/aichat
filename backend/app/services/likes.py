from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MessageLike, User, Work, WorkLike
from app.services.serialize import user_ref
from app.ws import notify_work


async def set_work_like(db: AsyncSession, work: Work, user: User, liked: bool) -> dict:
    if liked:
        await db.execute(insert(WorkLike).values(work_id=work.id, user_id=user.id).on_conflict_do_nothing())
    else:
        await db.execute(delete(WorkLike).where(WorkLike.work_id == work.id, WorkLike.user_id == user.id))
    await db.commit()
    count = await db.scalar(select(func.count()).select_from(WorkLike).where(WorkLike.work_id == work.id))
    await _broadcast(db, work, "work", work.id, count, user, liked)
    return {"count": count, "liked_by_me": liked}


async def set_message_like(db: AsyncSession, work: Work, message_id: int, user: User, liked: bool) -> dict:
    if liked:
        await db.execute(
            insert(MessageLike).values(message_id=message_id, user_id=user.id).on_conflict_do_nothing()
        )
    else:
        await db.execute(
            delete(MessageLike).where(MessageLike.message_id == message_id, MessageLike.user_id == user.id)
        )
    await db.commit()
    count = await db.scalar(
        select(func.count()).select_from(MessageLike).where(MessageLike.message_id == message_id)
    )
    await _broadcast(db, work, "message", message_id, count, user, liked)
    return {"count": count, "liked_by_me": liked}


async def _broadcast(db, work, target_type, target_id, count, user, liked) -> None:
    await notify_work(
        db,
        work,
        {
            "type": "like.changed",
            "target_type": target_type,
            "target_id": target_id,
            "count": count,
            "user": user_ref(user),
            "liked": liked,
        },
    )
