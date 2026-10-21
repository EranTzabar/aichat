"""Automation on chats, run by a loop started with the server (every 30 seconds):

- Repeat: a chat with `repeat` opens a copy "<title> – <date>" each day or week at a set time, and the previous one
  closes.
- Auto-close: a chat with `close_at` closes itself at that time.

Everything is done as the admin who set the chat up, and audited as "auto"."""
import asyncio
import logging
import re
from datetime import datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.errors import ApiError
from app.models import User, Chat
from app.services.audit import as_via, audit
from app.services.serialize import serialize_chat
from app.ws import notify_chat

log = logging.getLogger("uvicorn.error")

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
TICK_SECONDS = 30
UPDATED_KEYS = ("id", "title", "body", "status", "attachments")


def _bad(message: str) -> ApiError:
    return ApiError(422, "validation_error", message)


def check_repeat(cfg: dict | None) -> dict | None:
    """Validate a repeat setting and return it cleaned (unknown keys dropped), or None for "doesn't repeat"."""
    if not cfg:
        return None
    every, time_ = cfg.get("every"), str(cfg.get("time", ""))
    if every not in ("daily", "weekly"):
        raise _bad("repeat.every must be 'daily' or 'weekly'.")
    if not TIME_RE.match(time_):
        raise _bad("repeat.time must look like 09:00 (24-hour clock).")
    out: dict = {"every": every, "time": time_}
    if every == "weekly":
        weekday = cfg.get("weekday")
        if not isinstance(weekday, int) or not 0 <= weekday <= 6:
            raise _bad("repeat.weekday must be 0 (Monday) to 6 (Sunday).")
        out["weekday"] = weekday
    if (days := cfg.get("close_after_days")) is not None:
        if not isinstance(days, int) or not 1 <= days <= 365:
            raise _bad("repeat.close_after_days must be 1 to 365.")
        out["close_after_days"] = days
    return out


def local_tz() -> tzinfo:
    return ZoneInfo(settings.timezone) if settings.timezone else datetime.now().astimezone().tzinfo


def last_due(cfg: dict, now: datetime) -> datetime:
    """The latest scheduled time at or before `now` (both in the schedule's time zone)."""
    hour, minute = map(int, cfg["time"].split(":"))
    due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if cfg["every"] == "weekly":
        due -= timedelta(days=(now.weekday() - cfg["weekday"]) % 7)
        if due > now:
            due -= timedelta(days=7)
    elif due > now:
        due -= timedelta(days=1)
    return due


def next_due(cfg: dict, now: datetime | None = None) -> datetime:
    now = (now or datetime.now(local_tz())).astimezone(local_tz())
    return last_due(cfg, now) + timedelta(days=7 if cfg["every"] == "weekly" else 1)


def describe_repeat(cfg: dict) -> str:
    """"every day at 09:00" / "every Monday at 09:00"."""
    day = f"every {WEEKDAYS[cfg['weekday']]}" if cfg["every"] == "weekly" else "every day"
    return f"{day} at {cfg['time']}"


# ---------- repeating ----------
async def make_copy(db: AsyncSession, series: Chat, now: datetime) -> Chat | None:
    """Open the next copy of a repeating chat and close the previous one (None when it can't be made)."""
    admin = await db.get(User, series.created_by)
    if admin is None or not admin.is_admin or not admin.is_active:
        log.warning("chat #%s repeats, but the admin who set it up is no longer an active admin", series.id)
        series.repeat_last_at = now
        await db.commit()
        return None
    previous = (
        await db.scalars(
            select(Chat).where(or_(Chat.id == series.id, Chat.series_id == series.id), Chat.status == "open")
        )
    ).all()
    days = series.repeat.get("close_after_days")
    copy = Chat(
        group_id=series.group_id,
        title=f"{series.title} – {now.strftime('%Y-%m-%d')}"[:200],
        body=series.body,
        tagged_user_ids=list(series.tagged_user_ids or []),
        created_by=admin.id,
        series_id=series.id,
        close_at=now + timedelta(days=days) if days else None,
    )
    db.add(copy)
    await db.flush()
    for p in previous:
        p.status = "closed"
        audit(db, admin, "chat.close", target=("chat", p.id), chat=p, details={"status": ["open", "closed"], "series": series.id})
    series.repeat_last_at = now
    audit(db, admin, "chat.repeat", target=("chat", copy.id), chat=copy, details={"title": copy.title, "series": series.id})
    await db.commit()

    await notify_chat(db, copy, {"type": "chat.created", "chat": await serialize_chat(db, copy, admin)})
    for p in previous:
        data = await serialize_chat(db, p, admin)
        await notify_chat(db, p, {"type": "chat.updated", "chat": {k: data[k] for k in UPDATED_KEYS}})
    return copy


async def run_due(now: datetime | None = None) -> int:
    """Open the copies that are due and close the chats whose time has come. Returns how many copies were made."""
    now = (now or datetime.now(local_tz())).astimezone(local_tz())
    with as_via("auto"):
        async with SessionLocal() as db:
            made = 0
            for series in (await db.scalars(select(Chat).where(Chat.repeat.is_not(None)).order_by(Chat.id))).all():
                if last_due(series.repeat, now) > (series.repeat_last_at or series.created_at):
                    if await make_copy(db, series, now):
                        made += 1
            await _close_due(db, now)
    return made


async def _close_due(db: AsyncSession, now: datetime) -> None:
    due = (await db.scalars(select(Chat).where(Chat.status == "open", Chat.close_at <= now))).all()
    if not due:
        return
    for chat in due:
        chat.status = "closed"
        admin = await db.get(User, chat.created_by)
        details = {"status": ["open", "closed"], "close_at": chat.close_at.isoformat()}
        audit(db, admin, "chat.close", target=("chat", chat.id), chat=chat, details=details)
    await db.commit()
    for chat in due:
        data = await serialize_chat(db, chat, await db.get(User, chat.created_by))
        await notify_chat(db, chat, {"type": "chat.updated", "chat": {k: data[k] for k in UPDATED_KEYS}})


async def loop() -> None:
    """Started with the server: checks repeats and auto-close every 30 seconds."""
    while True:
        try:
            await run_due()
        except Exception:
            log.exception("chat scheduler failed")
        await asyncio.sleep(TICK_SECONDS)
