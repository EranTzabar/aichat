from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import ApiError
from app.models import User
from app.permissions import ensure_open, get_accessible_message
from app.routers.works import IdemKey, create_message
from app.schemas import LikeStatus, MessageOut, ReplyIn
from app.security import get_current_user
from app.services import idempotency
from app.services.likes import set_message_like
from app.services.serialize import serialize_messages

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/{message_id}", response_model=MessageOut, summary="Get one message")
async def get_message(message_id: int, me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    message, _ = await get_accessible_message(db, me, message_id)
    return (await serialize_messages(db, [message], me))[0]


@router.post("/{message_id}/replies", response_model=MessageOut, status_code=201, summary="Reply to a message")
async def reply(
    message_id: int,
    payload: ReplyIn,
    idempotency_key: str | None = IdemKey,
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Replies are one level deep: replying to a reply attaches to the same top-level comment.
    The reply tags `reply_to_user_id` (default: the author of the message you reply to)."""
    target, work = await get_accessible_message(db, me, message_id)
    if cached := await idempotency.replay(db, me, idempotency_key):
        return cached
    ensure_open(work)
    reply_to = payload.reply_to_user_id or target.author_id
    if await db.get(User, reply_to) is None:
        raise ApiError(422, "validation_error", f"User #{reply_to} does not exist.")
    parent_id = target.parent_id or target.id
    data = await create_message(db, work, me, payload.body, parent_id, reply_to)
    return await idempotency.respond(db, me, idempotency_key, data)


@router.post("/{message_id}/like", response_model=LikeStatus, summary="Like a message")
async def like_message(message_id: int, me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    message, work = await get_accessible_message(db, me, message_id)
    ensure_open(work)
    return await set_message_like(db, work, message.id, me, True)


@router.delete("/{message_id}/like", response_model=LikeStatus, summary="Remove my like from a message")
async def unlike_message(message_id: int, me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    message, work = await get_accessible_message(db, me, message_id)
    ensure_open(work)
    return await set_message_like(db, work, message.id, me, False)
