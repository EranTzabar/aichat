"""Live push over WebSocket. Clients only listen; all actions go through REST."""
import asyncio
import logging
from collections import defaultdict

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.errors import ApiError
from app.models import User, UserGroup, Work
from app.security import authenticate_token

log = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.sockets: dict[int, set[WebSocket]] = defaultdict(set)
        # Long-poll requests (GET /me/updates?wait=) waiting for new activity, per user.
        self.waiters: dict[int, set[asyncio.Event]] = defaultdict(set)

    def online_ids(self) -> set[int]:
        return {uid for uid, socks in self.sockets.items() if socks}

    def is_online(self, user_id: int) -> bool:
        return bool(self.sockets.get(user_id))

    async def connect(self, user_id: int, ws: WebSocket) -> bool:
        first = not self.is_online(user_id)
        self.sockets[user_id].add(ws)
        return first

    def disconnect(self, user_id: int, ws: WebSocket) -> bool:
        self.sockets[user_id].discard(ws)
        if not self.sockets[user_id]:
            del self.sockets[user_id]
            return True
        return False

    def add_waiter(self, user_id: int) -> asyncio.Event:
        event = asyncio.Event()
        self.waiters[user_id].add(event)
        return event

    def remove_waiter(self, user_id: int, event: asyncio.Event) -> None:
        self.waiters[user_id].discard(event)
        if not self.waiters[user_id]:
            del self.waiters[user_id]

    def waiting_ids(self) -> set[int]:
        return {uid for uid, events in self.waiters.items() if events}

    def wake(self, user_ids: set[int]) -> None:
        for uid in user_ids:
            for event in self.waiters.get(uid, ()):
                event.set()

    async def send_to(self, user_ids: set[int], event: dict) -> None:
        data = jsonable_encoder(event)
        targets = [ws for uid in user_ids for ws in list(self.sockets.get(uid, ()))]
        results = await asyncio.gather(*(ws.send_json(data) for ws in targets), return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                log.debug("ws send failed: %s", r)

    async def send_all(self, event: dict) -> None:
        await self.send_to(self.online_ids(), event)


manager = ConnectionManager()


async def work_audience(db: AsyncSession, group_id: int) -> set[int]:
    """Users allowed to see works of this group: its members plus all admins."""
    rows = await db.scalars(
        select(User.id)
        .outerjoin(UserGroup, (UserGroup.user_id == User.id) & (UserGroup.group_id == group_id))
        .where(User.is_active, or_(User.is_admin, UserGroup.group_id.is_not(None)))
    )
    return set(rows.all())


async def notify_work(db: AsyncSession, work: Work, event: dict, wake: bool = True) -> None:
    """Push to open sockets and (when `wake`) wake long-poll waiters of everyone who can see the work."""
    online, waiting = manager.online_ids(), manager.waiting_ids() if wake else set()
    if not online and not waiting:
        return
    audience = await work_audience(db, work.group_id)
    manager.wake(audience & waiting)
    await manager.send_to(audience & online, {"work_id": work.id, **event})


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = Query(...)):
    async with SessionLocal() as db:
        try:
            user = await authenticate_token(token, db)
        except ApiError as e:
            await ws.close(code=4401, reason=e.code)
            return
    await ws.accept()
    if await manager.connect(user.id, ws):
        await manager.send_all({"type": "presence.changed", "user_id": user.id, "online": True})
    await ws.send_json({"type": "hello", "user_id": user.id, "online_user_ids": sorted(manager.online_ids())})
    try:
        while True:
            await ws.receive_text()  # clients may send pings; ignored
    except WebSocketDisconnect:
        pass
    finally:
        if manager.disconnect(user.id, ws):
            await manager.send_all({"type": "presence.changed", "user_id": user.id, "online": False})
