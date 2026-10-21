from tests.conftest import auth


async def test_id_tags_are_resolved_flagged_and_counted(client, world):
    dana, yoni = auth(world.dana["token"]), auth(world.yoni["token"])
    cursor = (await client.get("/me/updates", headers=dana)).json()["cursor"]

    body = f"<@{world.dana['id']}> and @yoni, please check."
    m = (await client.post(f"/chats/{world.chat_id}/messages", json={"body": body}, headers=yoni)).json()
    assert [u["username"] for u in m["mentions"]] == ["dana", "yoni"]

    msgs = (await client.get("/me/updates", params={"cursor": cursor}, headers=dana)).json()["messages"]
    assert msgs[0]["mentions_me"]

    chats = (await client.get("/chats", headers=dana)).json()
    chat = next(w for w in chats if w["id"] == world.chat_id)
    assert chat["unread_mentions"] == 1
    assert chat["last_message"]["body_preview"] == "@dana and @yoni, please check."

    await client.post(f"/chats/{world.chat_id}/read", headers=dana)
    chats = (await client.get("/chats", headers=dana)).json()
    assert next(w for w in chats if w["id"] == world.chat_id)["unread_mentions"] == 0


async def test_plain_username_tag_is_counted_but_not_a_longer_name(client, world):
    dana, yoni = auth(world.dana["token"]), auth(world.yoni["token"])
    for body in ("@dana.", "@danabot hi", "email dana@x.com"):
        await client.post(f"/chats/{world.chat_id}/messages", json={"body": body}, headers=yoni)
    chats = (await client.get("/chats", headers=dana)).json()
    assert next(w for w in chats if w["id"] == world.chat_id)["unread_mentions"] == 1


async def test_everyone_lists_all_users(client, world):
    people = (await client.get("/people", params={"everyone": True}, headers=auth(world.dana["token"]))).json()
    assert {p["username"] for p in people} >= {"dana", "yoni", "omer", "admin"}  # omer shares no group with dana
