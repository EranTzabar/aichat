from tests.conftest import auth


async def audit(client, headers, **params):
    r = await client.get("/admin/audit", params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def api_token(client, admin, user_id):
    r = await client.get(f"/admin/users/{user_id}/api-token", headers=admin)
    assert r.status_code == 200, r.text
    return r.json()["token"]


async def test_website_and_api_actions_are_marked(client, world):
    admin, dana = auth(world.admin["token"]), auth(world.dana["token"])
    r = await client.post(f"/chats/{world.chat_id}/messages", json={"body": "From the website"}, headers=dana)
    web_id = r.json()["id"]
    key = auth(await api_token(client, admin, world.dana["id"]))
    r = await client.post(f"/chats/{world.chat_id}/messages", json={"body": "From my AI"}, headers=key)
    api_id = r.json()["id"]

    events = (await audit(client, admin, action="message.create", user_id=world.dana["id"]))["events"]
    by_target = {e["target_id"]: e for e in events}
    assert by_target[web_id]["via"] == "web" and by_target[api_id]["via"] == "api"
    e = by_target[api_id]
    assert e["chat"] == {"id": world.chat_id, "title": "Plan Q4"} and e["group"]["id"] == world.group_id
    assert e["details"]["preview"] == "From my AI" and e["actor"]["username"] == "dana"

    # Viewing the token is recorded too.
    viewed = (await audit(client, admin, action="user.token_view"))["events"]
    assert viewed[0]["target_id"] == world.dana["id"] and viewed[0]["actor"]["id"] == world.admin["id"]


async def test_logins_and_failed_logins(client, world):
    admin = auth(world.admin["token"])
    r = await client.post("/auth/login", json={"username": "dana", "password": "wrong"})
    assert r.status_code == 401
    r = await client.post("/auth/login", json={"username": "nobody", "password": "x"})
    assert r.status_code == 401

    failed = (await audit(client, admin, action="login.failed"))["events"]
    assert [e["details"]["username"] for e in failed] == ["nobody", "dana"]
    assert failed[0]["actor"] is None and failed[1]["actor"]["id"] == world.dana["id"]
    # "login" also matches "login.failed": the filter is a prefix.
    assert any(e["action"] == "login" for e in (await audit(client, admin, action="login"))["events"])


async def test_admin_changes_and_paging(client, world):
    admin = auth(world.admin["token"])
    r = await client.patch(f"/admin/chats/{world.chat_id}", json={"status": "closed"}, headers=admin)
    assert r.status_code == 200, r.text
    r = await client.patch(f"/admin/users/{world.yoni['id']}", json={"api_enabled": False}, headers=admin)
    assert r.status_code == 200, r.text

    closed = (await audit(client, admin, action="chat.close"))["events"][0]
    assert closed["details"]["status"] == ["open", "closed"]
    updated = (await audit(client, admin, action="user.update"))["events"][0]
    assert updated["details"] == {"api_enabled": [True, False]}

    # Paging with before_id.
    first = await audit(client, admin, limit=2)
    assert len(first["events"]) == 2 and first["next_before_id"] == first["events"][-1]["id"]
    second = await audit(client, admin, limit=2, before_id=first["next_before_id"])
    assert all(e["id"] < first["next_before_id"] for e in second["events"])


async def test_only_admin_reads_the_log(client, world):
    r = await client.get("/admin/audit", headers=auth(world.dana["token"]))
    assert r.status_code == 403
