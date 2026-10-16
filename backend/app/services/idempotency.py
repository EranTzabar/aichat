from datetime import timedelta

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.models import IdempotencyKey, User

TTL = timedelta(hours=24)


async def replay(db: AsyncSession, user: User, key: str | None) -> JSONResponse | None:
    """If this key was already used by this user in the last 24h, return the stored response."""
    if not key:
        return None
    row = await db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == user.id,
            IdempotencyKey.key == key,
            IdempotencyKey.created_at > utcnow() - TTL,
        )
    )
    if row is None:
        return None
    return JSONResponse(row.response, status_code=row.status_code, headers={"Idempotent-Replay": "true"})


async def respond(db: AsyncSession, user: User, key: str | None, body: dict, status_code: int = 201) -> JSONResponse:
    content = jsonable_encoder(body)
    if key:
        await db.execute(delete(IdempotencyKey).where(IdempotencyKey.created_at < utcnow() - TTL))
        await db.execute(
            insert(IdempotencyKey)
            .values(user_id=user.id, key=key, status_code=status_code, response=content, created_at=utcnow())
            .on_conflict_do_update(
                index_elements=["user_id", "key"],
                set_={"status_code": status_code, "response": content, "created_at": utcnow()},
            )
        )
        await db.commit()
    return JSONResponse(content, status_code=status_code)
