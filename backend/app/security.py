from datetime import timedelta

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db, utcnow
from app.errors import ApiError
from app.models import User

ALGORITHM = "HS256"
bearer = HTTPBearer(auto_error=False, description="Session JWT (from login) or the user's API JWT")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_session_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "type": "session",
        "exp": utcnow() + timedelta(hours=settings.session_ttl_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def create_api_token(user: User) -> str:
    """Long-lived token; revoked by bumping user.token_version."""
    payload = {"sub": str(user.id), "type": "api", "ver": user.token_version}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


async def authenticate_token(token: str, db: AsyncSession) -> User:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ApiError(401, "token_expired", "Your session has expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise ApiError(401, "invalid_token", "The token is invalid.")

    try:
        user = await db.get(User, int(payload["sub"]))
    except (KeyError, ValueError):
        user = None
    if user is None:
        raise ApiError(401, "invalid_token", "The token is invalid.")
    if not user.is_active:
        raise ApiError(401, "user_disabled", "This user account is disabled.")

    if payload.get("type") == "api":
        if payload.get("ver") != user.token_version:
            raise ApiError(401, "token_revoked", "This API token was revoked. Ask the admin for the new token.")
        if not user.api_enabled:
            raise ApiError(401, "api_disabled", "API access is disabled for this user.")
        now = utcnow()
        if user.last_api_use_at is None or now - user.last_api_use_at > timedelta(minutes=1):
            user.last_api_use_at = now
            await db.commit()
    elif payload.get("type") != "session":
        raise ApiError(401, "invalid_token", "The token is invalid.")
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise ApiError(401, "not_authenticated", "Missing 'Authorization: Bearer <token>' header.")
    return await authenticate_token(credentials.credentials, db)


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise ApiError(403, "admin_only", "Only the admin can do this.")
    return user
