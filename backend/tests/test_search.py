from tests.conftest import auth


async def post(client, chat_id, headers, body, **extra):
    r = await client.post(f"/chats/{chat_id}/messages", json={"body": body, **extra}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def search(client, headers, q, **params):
    r = await client.get("/search", params={"q": q, **params}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def test_search_messages_chats_and_file_text(client, world):
    dana, yoni = auth(world.dana["token"]), auth(world.yoni["token"])
    m = await post(client, world.chat_id, dana, "We should migrate the database on Sunday")
    await post(client, world.chat_id, yoni, "Unrelated chatter")

    # A word in a message; a prefix ("migr") finds it too, and the snippet marks the match.
    data = await search(client, yoni, "migr")
    assert data["total"] == 1
    hit = data["results"][0]
    assert hit["type"] == "message" and hit["message_id"] == m["id"] and hit["chat_title"] == "Plan Q4"
    assert "«migrate»" in hit["snippet"] and hit["author"]["username"] == "dana"

    # All words must match.
    assert (await search(client, yoni, "migrate Monday"))["total"] == 0

    # The chat title.
    assert any(h["type"] == "chat" for h in (await search(client, yoni, "Q4"))["results"])

    # Words inside an attached text file (sent with a message).
    r = await client.post(
        f"/chats/{world.chat_id}/attachments",
        files={"file": ("notes.md", b"Budget forecast for the rollout", "application/octet-stream")},
        headers=dana,
    )
    a = r.json()
    # Not searchable while unsent.
    assert (await search(client, yoni, "forecast"))["total"] == 0
    await post(client, world.chat_id, dana, "", attachment_ids=[a["id"]])
    files = await search(client, yoni, "forecast", type="files")
    assert files["total"] == 1 and files["results"][0]["attachment"]["id"] == a["id"]
    # File names are searchable too.
    assert (await search(client, yoni, "notes", type="files"))["total"] == 1


async def test_search_respects_groups_and_filters(client, world):
    admin, dana, omer = auth(world.admin["token"]), auth(world.dana["token"]), auth(world.omer["token"])
    await post(client, world.chat_id, dana, "secret roadmap details")
    await post(client, world.chat_id, auth(world.yoni["token"]), "roadmap draft")

    # Omer is not in the group: nothing shows up.
    assert (await search(client, omer, "roadmap"))["total"] == 0
    # The admin sees everything.
    assert (await search(client, admin, "roadmap"))["total"] == 2

    only_dana = await search(client, admin, "roadmap", author_id=world.dana["id"])
    assert [h["author"]["username"] for h in only_dana["results"]] == ["dana"]
    assert (await search(client, admin, "roadmap", type="chats"))["total"] == 0
    assert (await search(client, admin, "roadmap", group_id=world.group_id))["total"] == 2

    page = await search(client, admin, "roadmap", limit=1, offset=1)
    assert page["total"] == 2 and len(page["results"]) == 1

    r = await client.get("/search", params={"q": "!!"}, headers=dana)
    assert r.status_code == 422
