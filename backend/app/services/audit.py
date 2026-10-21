"""Audit log: who did what, and whether from the website, an API key (an AI or a script) or automatically
(repeating chats, auto-close).

Each request runs in its own context: `AuditContext` keeps the caller's IP, and `authenticate_token` notes how the
user signed in. `audit()` adds the row to the caller's session, so it is saved by the caller's commit."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal, utcnow
from app.models import AuditEvent, User, Chat

_via: ContextVar[str] = ContextVar("audit_via", default="web")
_ip: ContextVar[str | None] = ContextVar("audit_ip", default=None)


def set_via(via: str) -> None:
    _via.set(via)


@contextmanager
def as_via(via: str):
    """Record the actions inside this block as made from `via` (e.g. "auto" for the scheduler)."""
    token = _via.set(via)
    try:
        yield
    finally:
        _via.reset(token)


class AuditContext:
    """ASGI middleware: keep the caller's IP for this request. The MCP calls the API in-process, so a nested
    request keeps the outer request's IP."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        client = scope.get("client")
        ip = _ip.get() or (client[0] if client else None)
        tokens = (_ip.set(ip), _via.set("web"))
        try:
            await self.app(scope, receive, send)
        finally:
            _ip.reset(tokens[0])
            _via.reset(tokens[1])


def audit(
    db: AsyncSession,
    actor: User | None,
    action: str,
    *,
    target: tuple[str, int] | None = None,
    chat: Chat | None = None,
    group_id: int | None = None,
    details: dict | None = None,
    via: str | None = None,
) -> None:
    """Add an audit row (the caller commits). `target` is (type, id), e.g. ("message", 41)."""
    db.add(
        AuditEvent(
            actor_id=actor.id if actor else None,
            via=via or _via.get(),
            action=action,
            target_type=target[0] if target else None,
            target_id=target[1] if target else None,
            chat_id=chat.id if chat else None,
            group_id=group_id if group_id is not None else (chat.group_id if chat else None),
            details=details or {},
            ip=_ip.get(),
        )
    )


def _short(value):
    return value[:200] + "…" if isinstance(value, str) and len(value) > 200 else value


def changes(obj, data: dict) -> dict:
    """{field: [old, new]} for the fields that really change (call before setting them). Long text is cut."""
    return {
        k: [_short(getattr(obj, k)), _short(v)] for k, v in data.items() if v is not None and getattr(obj, k) != v
    }


async def prune() -> int:
    """Delete rows older than AUDIT_KEEP_DAYS (0 = keep forever)."""
    if not settings.audit_keep_days:
        return 0
    async with SessionLocal() as db:
        cutoff = utcnow() - timedelta(days=settings.audit_keep_days)
        result = await db.execute(delete(AuditEvent).where(AuditEvent.at < cutoff))
        await db.commit()
        return result.rowcount or 0
