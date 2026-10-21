from datetime import datetime, timedelta

from app.services import schedule
from tests.conftest import auth


async def make(client, admin, group_id, **fields):
    r = await client.post("/admin/chats", json={"group_id": group_id, "title": "Stand-up", **fields}, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()


async def my_chat(client, headers, chat_id):
    chats = (await client.get("/chats", headers=headers)).json()
    return next(w for w in chats if w["id"] == chat_id)


async def test_tagged_people_are_notified_until_they_open_the_chat(client, world):
    admin, yoni, dana = auth(world.admin["token"]), auth(world.yoni["token"]), auth(world.dana["token"])
    cursor = (await client.get("/me/updates", headers=yoni)).json()["cursor"]
    chat = await make(client, admin, world.group_id, tagged_user_ids=[world.yoni["id"]])
    assert [u["username"] for u in chat["tagged"]] == ["yoni"]

    assert (await my_chat(client, yoni, chat["id"]))["unread_mentions"] == 1
    assert (await my_chat(client, dana, chat["id"]))["unread_mentions"] == 0
    new_chats = (await client.get("/me/updates", params={"cursor": cursor}, headers=yoni)).json()["new_chats"]
    assert new_chats[0]["mentions_me"]

    await client.post(f"/chats/{chat['id']}/read", headers=yoni)
    assert (await my_chat(client, yoni, chat["id"]))["unread_mentions"] == 0


async def test_repeat_opens_a_copy_and_closes_the_previous_one(client, world):
    admin = auth(world.admin["token"])
    series = await make(client, admin, world.group_id, repeat={"every": "daily", "time": "09:00", "close_after_days": 2})
    assert series["repeat"]["time"] == "09:00" and series["next_copy_at"]

    tz = schedule.local_tz()
    tomorrow_9 = (datetime.fromisoformat(series["created_at"]).astimezone(tz) + timedelta(days=1)).replace(hour=9, minute=1)
    assert await schedule.run_due(tomorrow_9) == 1
    assert await schedule.run_due(tomorrow_9 + timedelta(minutes=5)) == 0  # once per slot

    state = (await client.get(f"/chats/{series['id']}", headers=admin)).json()["chat"]
    assert state["status"] == "closed" and len(state["copies"]) == 1
    copy = (await client.get(f"/chats/{state['copies'][0]['id']}", headers=admin)).json()["chat"]
    assert copy["title"] == f"Stand-up – {tomorrow_9:%Y-%m-%d}" and copy["status"] == "open"
    assert copy["series"]["id"] == series["id"] and copy["close_at"]

    assert await schedule.run_due(tomorrow_9 + timedelta(days=1)) == 1
    copy = (await client.get(f"/chats/{copy['id']}", headers=admin)).json()["chat"]
    assert copy["status"] == "closed"  # the next copy closed it


async def test_auto_close(client, world):
    admin = auth(world.admin["token"])
    chat = await make(client, admin, world.group_id, close_after_days=1)
    await schedule.run_due(datetime.now(schedule.local_tz()) + timedelta(hours=1))
    assert (await client.get(f"/chats/{chat['id']}", headers=admin)).json()["chat"]["status"] == "open"
    await schedule.run_due(datetime.now(schedule.local_tz()) + timedelta(days=1, hours=1))
    assert (await client.get(f"/chats/{chat['id']}", headers=admin)).json()["chat"]["status"] == "closed"
    events = (await client.get("/admin/audit", params={"action": "chat.close"}, headers=admin)).json()["events"]
    assert events[0]["via"] == "auto"


async def test_bad_automation_is_refused(client, world):
    admin = auth(world.admin["token"])
    for fields in (
        {"repeat": {"every": "daily", "time": "25:00"}},
        {"repeat": {"every": "weekly", "time": "09:00"}},
        {"tagged_user_ids": [999999]},
        {"close_after_days": 0},
    ):
        r = await client.post("/admin/chats", json={"group_id": world.group_id, "title": "x", **fields}, headers=admin)
        assert r.status_code == 422, (fields, r.text)
    r = await client.post("/admin/chats", json={"group_id": world.group_id, "title": "x"}, headers=auth(world.dana["token"]))
    assert r.status_code == 403
