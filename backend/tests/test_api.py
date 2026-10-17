from app.ws import manager
from tests.conftest import auth


def err(r):
    return r.json()["error"]["code"]


async def test_login_and_me(client, world):
    r = await client.get("/me", headers=auth(world.dana["token"]))
    assert r.status_code == 200
    assert r.json()["groups"] == [{"id": world.group_id, "name": "Design"}]

    r = await client.post("/auth/login", json={"username": "dana", "password": "nope"})
    assert r.status_code == 401 and err(r) == "invalid_credentials"


async def test_missing_token(client, world):
    r = await client.get("/works")
    assert r.status_code == 401 and err(r) == "not_authenticated"


async def test_admin_only(client, world):
    r = await client.get("/admin/users", headers=auth(world.dana["token"]))
    assert r.status_code == 403 and err(r) == "admin_only"


async def test_assign_unknown_group_rejected(client, world):
    r = await client.put(
        f"/admin/users/{world.dana['id']}/groups", json={"group_ids": [999]}, headers=auth(world.admin["token"])
    )
    assert r.status_code == 422 and "999" in r.json()["error"]["message"]


async def test_non_member_gets_clear_403(client, world):
    h = auth(world.omer["token"])
    for r in (
        await client.get(f"/works/{world.work_id}", headers=h),
        await client.post(f"/works/{world.work_id}/messages", json={"body": "hi"}, headers=h),
    ):
        assert r.status_code == 403
        assert err(r) == "not_group_member"
        assert "Design" in r.json()["error"]["message"]
    assert (await client.get("/works", headers=h)).json() == []


async def test_removed_member_loses_access(client, world):
    h = auth(world.dana["token"])
    assert (await client.get(f"/works/{world.work_id}", headers=h)).status_code == 200
    await client.put(f"/admin/users/{world.dana['id']}/groups", json={"group_ids": []}, headers=auth(world.admin["token"]))
    r = await client.get(f"/works/{world.work_id}", headers=h)
    assert r.status_code == 403 and err(r) == "not_group_member"


async def test_admin_can_post_anywhere(client, world):
    r = await client.post(f"/works/{world.work_id}/messages", json={"body": "admin here"}, headers=auth(world.admin["token"]))
    assert r.status_code == 201


async def test_work_state_shape_and_reply_threading(client, world):
    dana, yoni = auth(world.dana["token"]), auth(world.yoni["token"])
    c = (await client.post(f"/works/{world.work_id}/messages", json={"body": "comment"}, headers=dana)).json()
    r1 = (await client.post(f"/messages/{c['id']}/replies", json={"body": "reply 1"}, headers=yoni)).json()
    assert r1["parent_id"] == c["id"] and r1["reply_to"]["id"] == world.dana["id"]
    # reply to a reply -> third level under that reply, tags the reply's author
    r2 = (await client.post(f"/messages/{r1['id']}/replies", json={"body": "reply 2"}, headers=dana)).json()
    assert r2["parent_id"] == r1["id"] and r2["reply_to"]["id"] == world.yoni["id"]
    # reply on the third level -> stays on the third level, under the same reply
    r3 = (await client.post(f"/messages/{r2['id']}/replies", json={"body": "reply 3"}, headers=yoni)).json()
    assert r3["parent_id"] == r1["id"] and r3["reply_to"]["id"] == world.dana["id"]

    state = (await client.get(f"/works/{world.work_id}", headers=dana)).json()
    assert state["work"]["title"] == "Plan Q4" and state["work"]["status"] == "open"
    assert "server_time" in state
    assert len(state["messages"]) == 1
    [reply] = state["messages"][0]["replies"]
    assert reply["id"] == r1["id"]
    assert [r["id"] for r in reply["replies"]] == [r2["id"], r3["id"]]
    assert reply["replies"][0]["replies"] is None
    assert {p["id"] for p in state["participants"]} == {world.dana["id"], world.yoni["id"]}
    assert "avatar" not in str(state).lower()
    assert set(state["messages"][0]["author"]) == {"id", "username", "display_name"}


async def test_likes_idempotent(client, world):
    h = auth(world.dana["token"])
    for _ in range(2):
        r = await client.post(f"/works/{world.work_id}/like", headers=h)
        assert r.json() == {"count": 1, "liked_by_me": True}
    m = (await client.post(f"/works/{world.work_id}/messages", json={"body": "x"}, headers=h)).json()
    await client.post(f"/messages/{m['id']}/like", headers=h)
    r = await client.post(f"/messages/{m['id']}/like", headers=auth(world.yoni["token"]))
    assert r.json() == {"count": 2, "liked_by_me": True}
    r = await client.delete(f"/messages/{m['id']}/like", headers=h)
    assert r.json() == {"count": 1, "liked_by_me": False}
    state = (await client.get(f"/works/{world.work_id}", headers=h)).json()
    assert state["work"]["likes"]["count"] == 1 and state["work"]["liked_by_me"]
    assert state["messages"][0]["likes"]["users"][0]["username"] == "yoni"


async def test_closed_work_is_read_only(client, world):
    await client.patch(f"/admin/works/{world.work_id}", json={"status": "closed"}, headers=auth(world.admin["token"]))
    h = auth(world.dana["token"])
    r = await client.post(f"/works/{world.work_id}/messages", json={"body": "hi"}, headers=h)
    assert r.status_code == 409 and err(r) == "work_closed"
    assert (await client.post(f"/works/{world.work_id}/like", headers=h)).status_code == 409
    assert (await client.get(f"/works/{world.work_id}", headers=h)).status_code == 200


async def test_since_id_and_mentions(client, world):
    dana, yoni = auth(world.dana["token"]), auth(world.yoni["token"])
    a = (await client.post(f"/works/{world.work_id}/messages", json={"body": "a"}, headers=dana)).json()
    b = (await client.post(f"/messages/{a['id']}/replies", json={"body": "b"}, headers=yoni)).json()
    r = await client.get(f"/works/{world.work_id}/messages", params={"since_id": a["id"]}, headers=dana)
    assert [m["id"] for m in r.json()] == [b["id"]]
    mentions = (await client.get("/me/mentions", headers=dana)).json()
    assert [m["id"] for m in mentions] == [b["id"]] and mentions[0]["work_title"] == "Plan Q4"
    assert (await client.get("/me/mentions", params={"since_id": b["id"]}, headers=dana)).json() == []


async def test_joined_new_filters_and_unread(client, world):
    dana, yoni = auth(world.dana["token"]), auth(world.yoni["token"])
    assert [w["id"] for w in (await client.get("/works", params={"filter": "new"}, headers=dana)).json()] == [world.work_id]
    assert (await client.get("/works", params={"filter": "joined"}, headers=dana)).json() == []
    await client.post(f"/works/{world.work_id}/messages", json={"body": "hi"}, headers=dana)
    assert (await client.get("/works", params={"filter": "new"}, headers=dana)).json() == []
    await client.post(f"/works/{world.work_id}/messages", json={"body": "yo"}, headers=yoni)
    await client.post(f"/works/{world.work_id}/messages", json={"body": "yo2"}, headers=yoni)
    item = (await client.get("/works", params={"filter": "joined"}, headers=dana)).json()[0]
    assert item["unread_count"] == 2 and item["message_count"] == 3
    assert item["last_message"]["body_preview"] == "yo2"
    r = await client.post(f"/works/{world.work_id}/read", headers=dana)
    assert r.json()["unread_count"] == 0


async def test_idempotency_key(client, world):
    h = {**auth(world.dana["token"]), "Idempotency-Key": "abc-1"}
    r1 = await client.post(f"/works/{world.work_id}/messages", json={"body": "once"}, headers=h)
    r2 = await client.post(f"/works/{world.work_id}/messages", json={"body": "once"}, headers=h)
    assert r1.status_code == r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]
    msgs = (await client.get(f"/works/{world.work_id}/messages", headers=h)).json()
    assert len(msgs) == 1


async def test_body_validation(client, world):
    h = auth(world.dana["token"])
    r = await client.post(f"/works/{world.work_id}/messages", json={"body": "x" * 5001}, headers=h)
    assert r.status_code == 422 and err(r) == "validation_error"
    r = await client.post(f"/works/{world.work_id}/messages", json={"body": "   "}, headers=h)
    assert r.status_code == 422


async def test_api_token_revocation_and_disable(client, world):
    admin = auth(world.admin["token"])
    uid = world.yoni["id"]
    old = (await client.get(f"/admin/users/{uid}/api-token", headers=admin)).json()["token"]
    assert (await client.get("/me", headers=auth(old))).status_code == 200
    new = (await client.post(f"/admin/users/{uid}/api-token/regenerate", headers=admin)).json()["token"]
    r = await client.get("/me", headers=auth(old))
    assert r.status_code == 401 and err(r) == "token_revoked"
    assert (await client.get("/me", headers=auth(new))).status_code == 200
    await client.patch(f"/admin/users/{uid}", json={"api_enabled": False}, headers=admin)
    r = await client.get("/me", headers=auth(new))
    assert r.status_code == 401 and err(r) == "api_disabled"
    u = (await client.get(f"/admin/users/{uid}", headers=admin)).json()
    assert u["last_api_use_at"] is not None and u["last_login_at"] is not None


async def test_group_delete_cascades(client, world):
    await client.post(f"/works/{world.work_id}/messages", json={"body": "x"}, headers=auth(world.dana["token"]))
    admin = auth(world.admin["token"])
    assert (await client.delete(f"/admin/groups/{world.group_id}", headers=admin)).status_code == 204
    assert (await client.get(f"/works/{world.work_id}", headers=admin)).status_code == 404
    assert (await client.get("/me/groups", headers=auth(world.dana["token"]))).json() == []


async def test_avatar_fallback_svg(client, world):
    r = await client.get(f"/users/{world.dana['id']}/avatar")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")


class FakeSocket:
    def __init__(self):
        self.events = []

    async def send_json(self, data):
        self.events.append(data)


async def test_broadcast_reaches_group_members_only(client, world):
    sockets = {name: FakeSocket() for name in ("dana", "yoni", "omer", "admin")}
    for name, sock in sockets.items():
        await manager.connect(getattr(world, name)["id"], sock)
    try:
        await client.post(f"/works/{world.work_id}/messages", json={"body": "live!"}, headers=auth(world.dana["token"]))
        for name in ("dana", "yoni", "admin"):
            ev = [e for e in sockets[name].events if e["type"] == "message.created"]
            assert ev and ev[0]["message"]["body"] == "live!" and ev[0]["work_id"] == world.work_id
        assert not [e for e in sockets["omer"].events if e["type"] == "message.created"]
    finally:
        for name, sock in sockets.items():
            manager.disconnect(getattr(world, name)["id"], sock)


async def test_seen_by_is_recorded_only_through_me_seen(client, world):
    dana, yoni, omer = auth(world.dana["token"]), auth(world.yoni["token"]), auth(world.omer["token"])
    admin = auth(world.admin["token"])
    theirs = (await client.post(f"/works/{world.work_id}/messages", json={"body": "yoni's"}, headers=yoni)).json()
    mine = (await client.post(f"/works/{world.work_id}/messages", json={"body": "dana's"}, headers=dana)).json()
    assert theirs["seen_by"] == []

    # loading the work (as the website does) marks nothing
    await client.get(f"/works/{world.work_id}", headers=dana)
    state = (await client.get(f"/works/{world.work_id}", headers=yoni)).json()
    assert all(m["seen_by"] == [] for m in state["messages"])

    r = await client.post("/me/seen", json={"message_ids": [theirs["id"], mine["id"]]}, headers=dana)
    assert r.json() == {"recorded": 1}  # own message ignored
    r = await client.post("/me/seen", json={"message_ids": [theirs["id"]]}, headers=dana)
    assert r.json() == {"recorded": 0}  # already seen
    assert (await client.post("/me/seen", json={"message_ids": [theirs["id"]]}, headers=admin)).json() == {"recorded": 0}
    assert (await client.post("/me/seen", json={"message_ids": [theirs["id"]]}, headers=omer)).json() == {"recorded": 0}

    msg = (await client.get(f"/messages/{theirs['id']}", headers=yoni)).json()
    assert [u["id"] for u in msg["seen_by"]] == [world.dana["id"]]
