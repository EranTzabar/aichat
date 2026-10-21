from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError, not_found
from app.models import Group, Message, User, UserGroup, Chat


async def user_group_ids(db: AsyncSession, user: User) -> set[int]:
    rows = await db.scalars(select(UserGroup.group_id).where(UserGroup.user_id == user.id))
    return set(rows.all())


def accessible_chats(user_id: int, is_admin: bool):
    """A filter on Chat for the chats a user can see (admins see all)."""
    if is_admin:
        return True
    return Chat.group_id.in_(select(UserGroup.group_id).where(UserGroup.user_id == user_id))


async def ensure_chat_access(db: AsyncSession, user: User, chat: Chat) -> None:
    if user.is_admin or chat.group_id in await user_group_ids(db, user):
        return
    group = await db.get(Group, chat.group_id)
    name = group.name if group else str(chat.group_id)
    raise ApiError(
        403,
        "not_group_member",
        f"You are not a member of group '{name}', so you can't read or post in chat #{chat.id}. "
        "Ask the admin to add you.",
    )


async def get_accessible_chat(db: AsyncSession, user: User, chat_id: int) -> Chat:
    chat = await db.get(Chat, chat_id)
    if chat is None:
        raise not_found("Chat", chat_id)
    await ensure_chat_access(db, user, chat)
    return chat


async def get_accessible_message(db: AsyncSession, user: User, message_id: int) -> tuple[Message, Chat]:
    message = await db.get(Message, message_id)
    if message is None:
        raise not_found("Message", message_id)
    chat = await get_accessible_chat(db, user, message.chat_id)
    return message, chat


def ensure_open(chat: Chat) -> None:
    if chat.status != "open":
        raise ApiError(409, "chat_closed", f"Chat #{chat.id} is closed; it is read-only.")
