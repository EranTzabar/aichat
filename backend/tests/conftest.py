import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://aichat:aichat@localhost:5433/aichat_test"
)
os.environ["UPLOAD_DIR"] = "uploads_test"
os.environ["R2_BUCKET"] = ""  # tests always store attachments on disk, even when .env has R2 keys

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app, seed_admin  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_db(schema):
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    await seed_admin()


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1") as c:
        yield c


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def login(client, username: str, password: str) -> str:
    r = await client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


class World:
    """Admin + group 'Design' + users dana & yoni in it + outsider 'omer' + one open chat."""

    admin: dict
    group_id: int
    dana: dict
    yoni: dict
    omer: dict
    chat_id: int


@pytest.fixture
async def world(client) -> World:
    w = World()
    w.admin = {"token": await login(client, "admin", "admin123"), "id": 1}
    h = auth(w.admin["token"])
    w.group_id = (await client.post("/admin/groups", json={"name": "Design"}, headers=h)).json()["id"]
    for name in ("dana", "yoni", "omer"):
        r = await client.post(
            "/admin/users",
            json={"username": name, "display_name": name.title(), "password": "secret1"},
            headers=h,
        )
        assert r.status_code == 201, r.text
        uid = r.json()["id"]
        if name != "omer":
            await client.put(f"/admin/users/{uid}/groups", json={"group_ids": [w.group_id]}, headers=h)
        setattr(w, name, {"id": uid, "token": await login(client, name, "secret1")})
    r = await client.post(
        "/admin/chats", json={"group_id": w.group_id, "title": "Plan Q4", "body": "Let's **plan**"}, headers=h
    )
    assert r.status_code == 201, r.text
    w.chat_id = r.json()["id"]
    return w
