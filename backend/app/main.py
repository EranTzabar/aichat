import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.errors import install_error_handlers
from app.models import User
from app.routers import admin_groups, admin_users, admin_works, attachments, auth, me, messages, works
from app.security import hash_password
from app.services.attachments import cleanup_orphans
from app.services.avatars import upload_dir
from app.services.storage import get_storage
from app import ws
from aichat_mcp.server import build_server

API_PREFIX = "/api/v1"
log = logging.getLogger("uvicorn.error")  # shown in the server console


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
    log.info("attachments are stored on %s", "Cloudflare R2" if get_storage().name == "r2" else "disk")
    await cleanup_orphans()
    async with mcp_server.session_manager.run():
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
    expose_headers=["Mcp-Session-Id"],
)
install_error_handlers(app)

for r in (auth.router, works.router, messages.router, attachments.router, me.router, admin_users.router, admin_groups.router, admin_works.router, ws.router):
    app.include_router(r, prefix=API_PREFIX)


# ---------- MCP endpoint (/mcp): AI agents use AIChat through the same REST API, in-process ----------
# Agents connect with their own API key through the connect tool; the endpoint itself needs no key.
def _mcp_security() -> TransportSecuritySettings:
    if "*" in settings.mcp_allowed_hosts:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    return TransportSecuritySettings(
        allowed_hosts=settings.mcp_allowed_hosts, allowed_origins=settings.mcp_allowed_origins
    )


mcp_server = build_server("http://aichat" + API_PREFIX, transport=httpx.ASGITransport(app=app))
_mcp_http = mcp_server.streamable_http_app(
    streamable_http_path="/mcp", stateless_http=True, transport_security=_mcp_security()
)
app.router.routes.extend(_mcp_http.routes)
