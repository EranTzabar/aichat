import asyncio
import time

from tests.conftest import auth


async def test_first_call_gives_cursor_and_unread(client, world):
    await client.post(f"/works/{world.work_id}/messages", json={"body": "hi"}, headers=auth(world.yoni["token"]))
    r = await client.get("/me/updates", headers=auth(world.dana["token"]))
    data = r.json()
    assert r.status_code == 200 and data["cursor"].startswith("m")
    assert [w["id"] for w in data["unread_works"]] == [world.work_id]
    assert data["messages"] == [] and data["new_works"] == []


async def test_updates_only_others_and_new_works(client, world):
    dana, yoni = auth(world.dana["token"]), auth(world.yoni["token"])
    cursor = (await client.get("/me/updates", headers=dana)).json()["cursor"]

    mine = (await client.post(f"/works/{world.work_id}/messages", json={"body": "mine"}, headers=dana)).json()
    theirs = (await client.post(f"/messages/{mine['id']}/replies", json={"body": "answer"}, headers=yoni)).json()
    new_work = await client.post(
        "/admin/works", json={"group_id": world.group_id, "title": "Second"}, headers=auth(world.admin["token"])
    )

    data = (await client.get("/me/updates", params={"cursor": cursor}, headers=dana)).json()
    assert [m["id"] for m in data["messages"]] == [theirs["id"]]
    assert data["messages"][0]["is_reply_to_me"] and data["messages"][0]["work_title"] == "Plan Q4"
    assert [w["id"] for w in data["new_works"]] == [new_work.json()["id"]]

    again = (await client.get("/me/updates", params={"cursor": data["cursor"]}, headers=dana)).json()
    assert again["messages"] == [] and again["new_works"] == []


async def test_mentions_and_my_threads_are_flagged(client, world):
    dana, yoni = auth(world.dana["token"]), auth(world.yoni["token"])
    top = (await client.post(f"/works/{world.work_id}/messages", json={"body": "Topic"}, headers=yoni)).json()
    await client.post(f"/messages/{top['id']}/replies", json={"body": "I'm in"}, headers=dana)
    cursor = (await client.get("/me/updates", headers=dana)).json()["cursor"]

    posts = [
        (f"/messages/{top['id']}/replies", "Follow-up for everyone"),  # Yoni answers himself, in Dana's thread
        (f"/works/{world.work_id}/messages", "What do you think, @dana?"),
        (f"/works/{world.work_id}/messages", "Dandelions are nice"),
    ]
    for path, body in posts:
        await client.post(path, json={"body": body}, headers=yoni)

    msgs = (await client.get("/me/updates", params={"cursor": cursor}, headers=dana)).json()["messages"]
    flags = [(m["is_reply_to_me"], m["mentions_me"], m["in_my_thread"]) for m in msgs]
    assert flags == [(False, False, True), (False, True, False), (False, False, False)]


async def test_wait_collects_a_burst_into_one_batch(client, world):
    dana, yoni = auth(world.dana["token"]), auth(world.yoni["token"])
    cursor = (await client.get("/me/updates", headers=dana)).json()["cursor"]

    async def post_burst():
        await asyncio.sleep(0.3)
        for body in ("one", "two", "three"):
            await client.post(f"/works/{world.work_id}/messages", json={"body": body}, headers=yoni)
            await asyncio.sleep(0.2)

    poster = asyncio.create_task(post_burst())
    r = await client.get("/me/updates", params={"cursor": cursor, "wait": 10}, headers=dana)
    await poster
    assert [m["body"] for m in r.json()["messages"]] == ["one", "two", "three"]


async def test_non_member_sees_nothing(client, world):
    omer = auth(world.omer["token"])
    cursor = (await client.get("/me/updates", headers=omer)).json()["cursor"]
    await client.post(f"/works/{world.work_id}/messages", json={"body": "secret"}, headers=auth(world.dana["token"]))
    data = (await client.get("/me/updates", params={"cursor": cursor}, headers=omer)).json()
    assert data["messages"] == []


async def test_invalid_cursor(client, world):
    r = await client.get("/me/updates", params={"cursor": "nope"}, headers=auth(world.dana["token"]))
    assert r.status_code == 422


async def test_wait_returns_early_when_someone_posts(client, world):
    dana = auth(world.dana["token"])
    cursor = (await client.get("/me/updates", headers=dana)).json()["cursor"]

    async def post_later():
        await asyncio.sleep(0.5)
        await client.post(f"/works/{world.work_id}/messages", json={"body": "ping"}, headers=auth(world.yoni["token"]))

    started = time.monotonic()
    poster = asyncio.create_task(post_later())
    r = await client.get("/me/updates", params={"cursor": cursor, "wait": 10}, headers=dana)
    await poster
    assert time.monotonic() - started < 5
    assert [m["body"] for m in r.json()["messages"]] == ["ping"]


async def test_wait_times_out_with_nothing_new(client, world):
    dana = auth(world.dana["token"])
    cursor = (await client.get("/me/updates", headers=dana)).json()["cursor"]
    started = time.monotonic()
    r = await client.get("/me/updates", params={"cursor": cursor, "wait": 1}, headers=dana)
    assert 0.9 < time.monotonic() - started < 5
    assert r.json()["messages"] == [] and r.json()["cursor"] == cursor
