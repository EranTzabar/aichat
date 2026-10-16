from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.errors import install_error_handlers
from app.models import User
from app.routers import admin_groups, admin_users, admin_works, auth, me, messages, works
from app.security import hash_password
from app.services.avatars import upload_dir
from app import ws

API_PREFIX = "/api/v1"


async def seed_admin() -> None:
    async with SessionLocal() as db:
        if await db.scalar(select(User.id).where(User.username == settings.admin_username)):
            return
        db.add(
            User(
                username=settings.admin_username,
                display_name="Admin",
                password_hash=hash_password(settings.admin_password),
                is_admin=True,
            )
        )
        await db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    upload_dir()
    await seed_admin()
    yield


app = FastAPI(
    title="AIChat API",
    version="1.0",
    description=(
        "Every user acts through a JWT: the website uses a session token from `/auth/login`; "
        "bots use the user's long-lived API token (the admin gets it from `/admin/users/{id}/api-token`). "
        "Send it as `Authorization: Bearer <token>`. Errors look like "
        '`{"error": {"code": "...", "message": "..."}}`.'
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
install_error_handlers(app)

for r in (auth.router, works.router, messages.router, me.router, admin_users.router, admin_groups.router, admin_works.router, ws.router):
    app.include_router(r, prefix=API_PREFIX)
