"""MCP server tools, run in-process against the real API (httpx ASGI transport) as a given user."""
import base64
from contextlib import asynccontextmanager

import httpx
import pytest
from mcp import Client

from aichat_mcp.server import build_server
from app.main import app


def new_server():
    return build_server("http://test/api/v1", transport=httpx.ASGITransport(app=app))


class Agent:
    """An MCP client that connected with a user's key; adds its connection id to every tool call."""

    def __init__(self, session, connection: str):
        self.session = session
        self.connection = connection

    async def call_tool(self, name: str, args: dict):
        return await self.session.call_tool(name, {"connection": self.connection, **args})

    def __getattr__(self, name):
        return getattr(self.session, name)


@asynccontextmanager
async def mcp_for(token: str):
    async with Client(new_server()) as c:
        r = await c.call_tool("connect", {"api_key": token})
        assert not r.is_error, r.content
        yield Agent(c, r.structured_content["connection"])


def text(result) -> str:
    return "\n".join(c.text for c in result.content)


EXPECTED_TOOLS = {
    "connect", "disconnect", "whoami", "list_works", "get_work", "get_thread", "get_new_messages", "post_comment", "reply", "like_work",
    "like_message", "mark_read", "list_mentions", "list_people", "get_updates", "wait_for_updates",
    "upload_file", "read_attachment", "download_attachment",
}


async def test_lists_tools_resources_and_prompt(world):
    async with mcp_for(world.dana["token"]) as c:
        tools = {t.name: t for t in (await c.list_tools()).tools}
        assert EXPECTED_TOOLS <= set(tools)
        assert tools["get_work"].annotations.read_only_hint is True
        assert tools["post_comment"].annotations.read_only_hint is False
        templates = {t.uri_template for t in (await c.list_resource_templates()).resource_templates}
        assert {"aichat://{connection}/works{?filter}", "aichat://{connection}/works/{work_id}"} <= templates
        prompts = {p.name for p in (await c.list_prompts()).prompts}
        assert "aichat_guide" in prompts
        guide = await c.get_prompt("aichat_guide", {"goal": "help plan"})
        assert "help plan" in guide.messages[0].content.text


async def test_whoami_and_works(world):
    async with mcp_for(world.dana["token"]) as c:
        r = await c.call_tool("whoami", {})
        assert not r.is_error and "Dana" in text(r) and r.structured_content["username"] == "dana"
        r = await c.call_tool("list_works", {"filter": "new"})
        assert f"Work #{world.work_id}" in text(r)
        assert r.structured_content["items"][0]["id"] == world.work_id


async def test_comment_reply_like_and_read_thread(world):
    async with mcp_for(world.dana["token"]) as dana, mcp_for(world.yoni["token"]) as yoni:
        r = await dana.call_tool("post_comment", {"work_id": world.work_id, "body": "I take **scope**"})
        assert not r.is_error
        comment_id = r.structured_content["id"]

        r = await yoni.call_tool("reply", {"message_id": comment_id, "body": "I take the timeline"})
        assert not r.is_error and r.structured_content["reply_to"]["username"] == "dana"

        r = await yoni.call_tool("like_message", {"message_id": comment_id})
        assert r.structured_content == {"count": 1, "liked_by_me": True}
        r = await yoni.call_tool("like_work", {"work_id": world.work_id, "liked": False})
        assert r.structured_content["count"] == 0

        r = await dana.call_tool("get_work", {"work_id": world.work_id})
        thread = text(r)
        assert f"#{comment_id} Dana" in thread and "Yoni -> Dana" in thread and "(1 like)" in thread
        assert r.structured_content["work"]["id"] == world.work_id

        r = await dana.call_tool("list_mentions", {})
        assert "I take the timeline" in text(r)
        r = await dana.call_tool("mark_read", {"work_id": world.work_id})
        assert not r.is_error


async def test_partial_history(world):
    async with mcp_for(world.dana["token"]) as dana, mcp_for(world.yoni["token"]) as yoni:
        ids = []
        for i in range(5):
            r = await yoni.call_tool("post_comment", {"work_id": world.work_id, "body": f"comment {i} " + "x" * 50})
            ids.append(r.structured_content["id"])
        for i in range(3):
            await dana.call_tool("reply", {"message_id": ids[2], "body": f"reply {i}"})

        # newest 2 comments; the text says how to page back and the structured result is trimmed too
        r = await dana.call_tool("get_work", {"work_id": world.work_id, "last_comments": 2})
        assert "comment 4" in text(r) and "comment 2" not in text(r)
        assert f"3 older comment(s) not shown: get_work({world.work_id}, before_id={ids[3]})" in text(r)
        assert [c["id"] for c in r.structured_content["messages"]] == ids[3:]
        assert r.structured_content["total_comments"] == 5

        r = await dana.call_tool(
            "get_work",
            {"work_id": world.work_id, "last_comments": 1, "before_id": ids[3], "last_replies": 1, "body_chars": 12},
        )
        out = text(r)
        assert "comment 2" in out and "comment 3" not in out
        assert f"2 earlier replies; get_thread({ids[2]}) shows all" in out
        assert "reply 2" in out and "reply 1" not in out
        assert f"[cut, 60 chars; get_thread({ids[2]}) shows it in full]" in out
        assert "2 newer comment(s) not shown" in out
        assert r.structured_content["messages"][0]["body_length"] == 60

        # one thread, asked for by a reply's id
        reply_id = r.structured_content["messages"][0]["replies"][0]["id"]
        r = await dana.call_tool("get_thread", {"message_id": reply_id})
        out = text(r)
        assert f"thread of comment #{ids[2]}" in out and "reply 0" in out and "reply 2" in out
        assert "comment 3" not in out
        assert r.structured_content["comment"]["id"] == ids[2]

        # a third-level reply: nested and indented under its reply, found by get_thread
        r = await yoni.call_tool("reply", {"message_id": reply_id, "body": "nested answer"})
        nested_id = r.structured_content["id"]
        r = await dana.call_tool("get_thread", {"message_id": nested_id})
        assert r.structured_content["comment"]["id"] == ids[2]
        assert f"          #{nested_id} Yoni -> Dana, reply to #{reply_id}" in text(r)


async def test_updates_tools(world):
    async with mcp_for(world.dana["token"]) as dana, mcp_for(world.yoni["token"]) as yoni:
        first = await dana.call_tool("get_updates", {})
        cursor = first.structured_content["cursor"]
        await yoni.call_tool("post_comment", {"work_id": world.work_id, "body": "news"})
        r = await dana.call_tool("wait_for_updates", {"cursor": cursor, "timeout_seconds": 5})
        assert "news" in text(r) and r.structured_content["cursor"] != cursor
        assert "EVERY message" in text(r)
        assert f'wait_for_updates(cursor="{r.structured_content["cursor"]}")' in text(r)
        assert "keep following" in text(r)


async def test_updates_tags_messages_for_me(world):
    async with mcp_for(world.dana["token"]) as dana, mcp_for(world.yoni["token"]) as yoni:
        cursor = (await dana.call_tool("get_updates", {})).structured_content["cursor"]
        await yoni.call_tool("post_comment", {"work_id": world.work_id, "body": "Dana, can you check this?"})
        r = await dana.call_tool("get_updates", {"cursor": cursor})
        assert "[MENTIONS YOU, question]" in text(r) and "1 addressed to you" in text(r)


async def test_errors_are_readable(world):
    async with mcp_for(world.omer["token"]) as c:
        r = await c.call_tool("get_work", {"work_id": world.work_id})
        assert r.is_error and "not_group_member" in text(r) and "Design" in text(r)


async def test_connect_and_disconnect(world):
    async with Client(new_server()) as c:
        r = await c.call_tool("whoami", {"connection": "c_unknown"})
        assert r.is_error and "not_connected" in text(r) and "connect(api_key)" in text(r)

        r = await c.call_tool("connect", {"api_key": "not-a-real-key"})
        assert r.is_error

        r = await c.call_tool("connect", {"api_key": "Bearer " + world.dana["token"]})
        connection = r.structured_content["connection"]
        assert not r.is_error and "Dana" in text(r) and world.dana["token"] not in text(r)

        r = await c.call_tool("whoami", {"connection": connection})
        assert r.structured_content["username"] == "dana"

        await c.call_tool("disconnect", {"connection": connection})
        r = await c.call_tool("whoami", {"connection": connection})
        assert r.is_error and "not_connected" in text(r)


async def test_each_agent_uses_its_own_key(world):
    async with mcp_for(world.dana["token"]) as dana, mcp_for(world.yoni["token"]) as yoni:
        assert (await dana.call_tool("whoami", {})).structured_content["username"] == "dana"
        assert (await yoni.call_tool("whoami", {})).structured_content["username"] == "yoni"


async def test_work_resource(world):
    async with mcp_for(world.dana["token"]) as c:
        res = await c.read_resource(f"aichat://{c.connection}/works/{world.work_id}")
        assert "Plan Q4" in res.contents[0].text


@pytest.mark.parametrize("tool", ["post_comment"])
async def test_closed_work_explained(world, client, tool):
    from tests.conftest import auth

    await client.patch(f"/admin/works/{world.work_id}", json={"status": "closed"}, headers=auth(world.admin["token"]))
    async with mcp_for(world.dana["token"]) as c:
        r = await c.call_tool(tool, {"work_id": world.work_id, "body": "x"})
        assert r.is_error and "closed" in text(r)


async def test_reading_marks_only_shown_messages_as_seen(world):
    async with mcp_for(world.dana["token"]) as dana, mcp_for(world.yoni["token"]) as yoni:
        ids = []
        for i in range(3):
            r = await yoni.call_tool("post_comment", {"work_id": world.work_id, "body": f"comment {i}"})
            ids.append(r.structured_content["id"])
        await yoni.call_tool("reply", {"message_id": ids[2], "body": "a reply"})

        await dana.call_tool("get_work", {"work_id": world.work_id, "last_comments": 1})
        r = await yoni.call_tool("get_work", {"work_id": world.work_id, "last_comments": 0})
        seen = {m["id"]: [u["username"] for u in m["seen_by"]] for m in r.structured_content["messages"]}
        assert seen == {ids[0]: [], ids[1]: [], ids[2]: ["dana"]}
        assert r.structured_content["messages"][2]["replies"][0]["seen_by"][0]["username"] == "dana"
        assert "(seen by 1)" in text(r)


async def test_files_upload_read_and_download(world, tmp_path):
    png = b"PNG

" + b"" * 32
    async with mcp_for(world.dana["token"]) as dana, mcp_for(world.yoni["token"]) as yoni:
        r = await dana.call_tool(
            "upload_file",
            {"work_id": world.work_id, "content_base64": base64.b64encode(png).decode(), "filename": "p.png"},
        )
        assert not r.is_error, text(r)
        att = r.structured_content["id"]
        r = await dana.call_tool("post_comment", {"work_id": world.work_id, "attachment_ids": [att]})
        assert not r.is_error, text(r)

        r = await yoni.call_tool("get_work", {"work_id": world.work_id})
        assert f"#{att} p.png (image" in text(r)

        r = await yoni.call_tool("read_attachment", {"attachment_id": att})
        assert r.content[1].type == "image" and base64.b64decode(r.content[1].data) == png

        r = await yoni.call_tool("download_attachment", {"attachment_id": att, "save_to": str(tmp_path)})
        assert not r.is_error, text(r)
        assert (tmp_path / "p.png").read_bytes() == png
