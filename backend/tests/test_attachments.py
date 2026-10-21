from tests.conftest import auth

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


async def upload(client, chat_id, headers, name="photo.png", data=PNG, ctype="image/png"):
    return await client.post(f"/chats/{chat_id}/attachments", files={"file": (name, data, ctype)}, headers=headers)


async def test_upload_send_and_download(client, world):
    dana, yoni = auth(world.dana["token"]), auth(world.yoni["token"])
    r = await upload(client, world.chat_id, dana)
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["kind"] == "image" and a["size"] == len(PNG) and a["filename"] == "photo.png"

    # a message with only a file
    r = await client.post(f"/chats/{world.chat_id}/messages", json={"attachment_ids": [a["id"]]}, headers=dana)
    assert r.status_code == 201, r.text
    assert [x["id"] for x in r.json()["attachments"]] == [a["id"]]

    state = (await client.get(f"/chats/{world.chat_id}", headers=yoni)).json()
    assert state["messages"][0]["attachments"][0]["kind"] == "image"

    r = await client.get(f"/attachments/{a['id']}/file", headers=yoni)
    assert r.status_code == 200 and r.content == PNG
    assert r.headers["content-type"] == "image/png"
    assert r.headers["content-disposition"].startswith("inline")
    assert r.headers["x-content-type-options"] == "nosniff"
    r = await client.get(f"/attachments/{a['id']}/file?download=1", headers=yoni)
    assert r.headers["content-disposition"].startswith("attachment")


async def test_attachment_rules(client, world):
    dana, yoni, omer = auth(world.dana["token"]), auth(world.yoni["token"]), auth(world.omer["token"])
    a = (await upload(client, world.chat_id, dana, "notes.pdf", b"%PDF-1.4", "application/pdf")).json()
    assert a["kind"] == "file"

    # someone else's upload, and an unsent upload, can't be used or seen by others
    r = await client.post(f"/chats/{world.chat_id}/messages", json={"attachment_ids": [a["id"]]}, headers=yoni)
    assert r.status_code == 422
    assert (await client.get(f"/attachments/{a['id']}/file", headers=yoni)).status_code == 404

    await client.post(f"/chats/{world.chat_id}/messages", json={"body": "doc", "attachment_ids": [a["id"]]}, headers=dana)
    # used once
    r = await client.post(f"/chats/{world.chat_id}/messages", json={"attachment_ids": [a["id"]]}, headers=dana)
    assert r.status_code == 422
    # non-members can't download or upload
    assert (await client.get(f"/attachments/{a['id']}/file", headers=omer)).status_code == 403
    assert (await upload(client, world.chat_id, omer)).status_code == 403
    # neither text nor files
    r = await client.post(f"/chats/{world.chat_id}/messages", json={"body": "  "}, headers=dana)
    assert r.status_code == 422


async def test_chat_post_attachments(client, world):
    admin, dana = auth(world.admin["token"]), auth(world.dana["token"])
    a = (await upload(client, world.chat_id, admin, "clip.mp4", b"\x00\x00\x00\x18ftypmp42", "video/mp4")).json()
    assert a["kind"] == "video"
    r = await client.patch(f"/admin/chats/{world.chat_id}", json={"attachment_ids": [a["id"]]}, headers=admin)
    assert r.status_code == 200, r.text
    state = (await client.get(f"/chats/{world.chat_id}", headers=dana)).json()
    assert [x["id"] for x in state["chat"]["attachments"]] == [a["id"]]
    assert (await client.get(f"/attachments/{a['id']}/file", headers=dana)).status_code == 200

    await client.patch(f"/admin/chats/{world.chat_id}", json={"remove_attachment_ids": [a["id"]]}, headers=admin)
    state = (await client.get(f"/chats/{world.chat_id}", headers=dana)).json()
    assert state["chat"]["attachments"] == []
