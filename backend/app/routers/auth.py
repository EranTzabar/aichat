from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, utcnow
from app.errors import ApiError
from app.models import User
from app.routers.me import me_out
from app.schemas import LoginIn, LoginOut
from app.security import create_session_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginOut, summary="Log in to the website (returns a session JWT)")
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise ApiError(401, "invalid_credentials", "Wrong username or password.")
    if not user.is_active:
        raise ApiError(401, "user_disabled", "This user account is disabled.")
    user.last_login_at = utcnow()
    await db.commit()
    return {"access_token": create_session_token(user), "user": await me_out(db, user)}
