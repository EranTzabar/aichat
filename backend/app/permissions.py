from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError, not_found
from app.models import Group, Message, User, UserGroup, Work


async def user_group_ids(db: AsyncSession, user: User) -> set[int]:
    rows = await db.scalars(select(UserGroup.group_id).where(UserGroup.user_id == user.id))
    return set(rows.all())


async def ensure_work_access(db: AsyncSession, user: User, work: Work) -> None:
    if user.is_admin or work.group_id in await user_group_ids(db, user):
        return
    group = await db.get(Group, work.group_id)
    name = group.name if group else str(work.group_id)
    raise ApiError(
        403,
        "not_group_member",
        f"You are not a member of group '{name}', so you can't read or post in work #{work.id}. "
        "Ask the admin to add you.",
    )


async def get_accessible_work(db: AsyncSession, user: User, work_id: int) -> Work:
    work = await db.get(Work, work_id)
    if work is None:
        raise not_found("Work", work_id)
    await ensure_work_access(db, user, work)
    return work


async def get_accessible_message(db: AsyncSession, user: User, message_id: int) -> tuple[Message, Work]:
    message = await db.get(Message, message_id)
    if message is None:
        raise not_found("Message", message_id)
    work = await get_accessible_work(db, user, message.work_id)
    return message, work


def ensure_open(work: Work) -> None:
    if work.status != "open":
        raise ApiError(409, "work_closed", f"Work #{work.id} is closed; it is read-only.")
