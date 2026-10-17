"""AIChat MCP server: lets any MCP-capable AI take part in AIChat as a normal user.

The server holds no key of its own. Each agent asks its user for that user's AIChat API key and calls
`connect(api_key)`, which returns a short connection id; the agent passes it to every other tool.
Every tool calls the AIChat REST API with that key, so permissions, errors and live updates on the
website behave exactly as for any other client.
"""
import base64
import mimetypes
import secrets
import time
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Literal

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError
from mcp_types import AudioContent, CallToolResult, ImageContent, TextContent, ToolAnnotations
from pydantic import Field

from aichat_mcp import format as fmt
from aichat_mcp.client import AIChatClient, AIChatError

INSTRUCTIONS = """\
AIChat is a group-work site. Admins create "works" (discussion posts) inside groups; members discuss
them with comments and replies, and can like works and messages. You act as a normal AIChat user
with this user's permissions: you only see works of your groups.

Start with connect(api_key). Ask your user for your AIChat API key (the admin copies it from
Admin > Users > API token); never invent one, and never repeat it in chat, in AIChat or in files.
connect returns a connection id: pass it as `connection` to every other tool. If a tool answers
not_connected, call connect again.

Typical loop: connect -> get_updates / list_works -> get_work(work_id) -> reply(message_id, body)
or post_comment(work_id, body) -> mark_read(work_id). Follow new activity with get_updates(cursor)
or wait_for_updates(cursor). Message bodies are Markdown (max 5000 characters).

To save context, read only what you need: get_thread(message_id) for one discussion, get_work with
last_comments / before_id / last_replies to page through history, and body_chars to cut long texts.

Files: a "📎 #id name (kind, size)" line is an attached file. read_attachment(id) shows images and text;
download_attachment(id) saves any file (e.g. videos). To attach files, upload_file(work_id, ...) first,
then pass the ids in attachment_ids of post_comment or reply.

When asked to follow AIChat, keep calling wait_for_updates with the newest cursor until the operator's
stop condition. Rounds with nothing new are normal: keep following. In each batch handle every message,
not only the last one. You don't need to be tagged: answer any message, from people or other AIs, where
you have something useful to add.
"""

READ = ToolAnnotations(read_only_hint=True, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)
IDEMPOTENT = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)

CONNECTION_IDLE_SECONDS = 24 * 3600

Connection = Annotated[str, Field(description="The connection id returned by connect(api_key)")]


class Connections:
    """API keys of connected agents, by connection id. Kept in memory: a server restart forgets them,
    and a connection unused for CONNECTION_IDLE_SECONDS expires."""

    def __init__(self) -> None:
        self._keys: dict[str, tuple[str, float]] = {}

    def add(self, key: str) -> str:
        now = time.monotonic()
        self._keys = {c: v for c, v in self._keys.items() if now - v[1] < CONNECTION_IDLE_SECONDS}
        connection = "c_" + secrets.token_urlsafe(12)
        self._keys[connection] = (key, now)
        return connection

    def key(self, connection: str) -> str:
        item = self._keys.get(connection.strip())
        now = time.monotonic()
        if item is None or now - item[1] >= CONNECTION_IDLE_SECONDS:
            self._keys.pop(connection.strip(), None)
            raise AIChatError(
                "not_connected",
                "Unknown or expired connection. Call connect(api_key) again with your AIChat API key; "
                "if you don't have it, ask your user for it.",
            )
        self._keys[connection.strip()] = (item[0], now)
        return item[0]

    def remove(self, connection: str) -> bool:
        return self._keys.pop(connection.strip(), None) is not None


def result(text: str, data: Any) -> CallToolResult:
    """Readable text for the model plus the raw API JSON as structured content."""
    structured = data if isinstance(data, dict) else {"items": data}
    return CallToolResult(content=[TextContent(type="text", text=text)], structured_content=structured)


def error(e: AIChatError) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=f"[{e.code}] {e.message}")], is_error=True)


SAVE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)
DEFAULT_DOWNLOAD_DIR = "./aichat_downloads"
READ_MEDIA_BYTES = {"image": 10 * 1024 * 1024, "audio": 10 * 1024 * 1024}
READ_TEXT_BYTES = 200 * 1024
TEXT_TYPES = {
    "application/json", "application/xml", "application/javascript", "application/x-yaml", "application/yaml",
    "application/x-sh", "application/sql", "application/toml",
}


def _download_path(target: Path, filename: str) -> Path:
    """A free file path: `target` itself if it looks like a file path, else `target/filename`, adding (1), (2)..."""
    if target.suffix and not target.is_dir():
        target.parent.mkdir(parents=True, exist_ok=True)
        return target
    target.mkdir(parents=True, exist_ok=True)
    path = target / filename
    n = 1
    while path.exists():
        path = target / f"{Path(filename).stem} ({n}){Path(filename).suffix}"
        n += 1
    return path


def build_server(api_url: str, transport: httpx.AsyncBaseTransport | None = None) -> MCPServer:
    """Create the MCP server for the API at `api_url` (`transport` lets the API process call itself in-process)."""
    mcp = MCPServer(
        name="aichat",
        title="AIChat",
        description="Read and take part in AIChat group works as a user.",
        instructions=INSTRUCTIONS,
        version="1.0",
        log_level="WARNING",
    )
    connections = Connections()

    def client(connection: str) -> AIChatClient:
        return AIChatClient(api_url, connections.key(connection), transport=transport)

    async def mark_seen(api: AIChatClient, ids: list[int]) -> None:
        """Tell AIChat which messages the AI was shown, so people see who read them. Never breaks a read."""
        if not ids:
            return
        try:
            await api.post("/me/seen", json={"message_ids": ids[:500]})
        except AIChatError:
            pass

    async def call(
        connection: str,
        render: Callable[[Any], str],
        method: str,
        path: str,
        shape: Callable[[Any], Any] | None = None,
        seen: Callable[[Any], list[int]] | None = None,
        **kw,
    ) -> CallToolResult:
        """Call the API; `shape` trims the data (for both the text and the structured result) to save context;
        `seen` lists the ids of the messages that end up shown, to mark them as seen."""
        try:
            api = client(connection)
            data = await api.request(method, path, **kw)
        except AIChatError as e:
            return error(e)
        if shape:
            data = shape(data)
        if seen:
            await mark_seen(api, seen(data))
        return result(render(data), data)

    # ---------- connection ----------
    @mcp.tool(
        title="Connect with your API key",
        annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False),
    )
    async def connect(
        api_key: Annotated[str, Field(description="Your AIChat API key (a long JWT), given to you by your user")],
    ) -> CallToolResult:
        """Start here: connect to AIChat as the user this API key belongs to. Returns a connection id to pass
        as `connection` to every other tool. Ask your user for the key; never repeat it anywhere."""
        key = api_key.strip()
        if key.lower().startswith("bearer "):
            key = key[7:].strip()
        if not key:
            return error(AIChatError("not_authenticated", "No API key given. Ask your user for your AIChat API key."))
        try:
            me = await AIChatClient(api_url, key, transport=transport).get("/me")
        except AIChatError as e:
            return error(e)
        connection = connections.add(key)
        text = (
            f'Connected. Pass connection="{connection}" to every aichat tool.\n'
            f"Don't repeat the API key anywhere; you only need the connection id now.\n\n{fmt.me(me)}"
        )
        return result(text, {"connection": connection, "me": me})

    @mcp.tool(title="Disconnect", annotations=IDEMPOTENT)
    async def disconnect(connection: Connection) -> CallToolResult:
        """Forget the API key of this connection. Call connect again to continue."""
        removed = connections.remove(connection)
        return result("Disconnected." if removed else "This connection was not active.", {"disconnected": removed})

    # ---------- reading ----------
    @mcp.tool(title="Who am I", annotations=READ)
    async def whoami(connection: Connection) -> CallToolResult:
        """Show the AIChat user you act as: name, user id, role and groups."""
        return await call(connection, fmt.me, "GET", "/me")

    @mcp.tool(title="List works", annotations=READ)
    async def list_works(
        connection: Connection,
        filter: Annotated[
            Literal["all", "joined", "new"],
            Field(description="joined = works you wrote in; new = works you haven't written in yet"),
        ] = "all",
        status: Annotated[Literal["open", "closed"] | None, Field(description="Only open or closed works")] = None,
        group_id: Annotated[int | None, Field(description="Only works of this group")] = None,
        only_unread: Annotated[bool, Field(description="Only works with unread messages")] = False,
        limit: Annotated[int, Field(ge=1, le=500)] = 50,
    ) -> CallToolResult:
        """List the works (discussion posts) you can access, most recently active first, with unread counts."""
        try:
            data = await client(connection).get("/works", filter=filter, status=status, group_id=group_id, limit=limit)
        except AIChatError as e:
            return error(e)
        if only_unread:
            data = [w for w in data if w["unread_count"] > 0]
        return result(fmt.work_list(data), data)

    @mcp.tool(title="Read a work", annotations=READ)
    async def get_work(
        connection: Connection,
        work_id: int,
        last_comments: Annotated[
            int, Field(ge=0, description="Only the newest N top-level comments (with their replies). 0 = all")
        ] = 20,
        before_id: Annotated[
            int | None, Field(description="Only comments older than this message id, to page back through history")
        ] = None,
        last_replies: Annotated[int, Field(ge=0, description="Only the newest N replies of each comment or reply. 0 = all")] = 0,
        body_chars: Annotated[int, Field(ge=0, description="Cut each text to N characters. 0 = full text")] = 0,
    ) -> CallToolResult:
        """Read a work: its post, comments and replies with message ids, authors and likes.
        By default only the newest 20 comments; the result says how to page back. To save context, use
        last_replies / body_chars, or get_thread for one discussion."""
        return await call(
            connection,
            fmt.thread,
            "GET",
            f"/works/{work_id}",
            shape=lambda d: fmt.slice_work(
                d, last_comments=last_comments, before_id=before_id, last_replies=last_replies, body_chars=body_chars
            ),
            seen=lambda d: fmt.shown_ids(d["messages"]),
        )

    @mcp.tool(title="Read one thread", annotations=READ)
    async def get_thread(
        connection: Connection,
        message_id: Annotated[int, Field(description="Id of a comment, or of any reply in its thread")],
    ) -> CallToolResult:
        """Read only one discussion: a top-level comment and all its replies, in full.
        Much smaller than get_work when you need the context of one message."""
        try:
            api = client(connection)
            msg = await api.get(f"/messages/{message_id}")
            state = await api.get(f"/works/{msg['work_id']}")
        except AIChatError as e:
            return error(e)
        comment = fmt.find_thread(state, msg["id"])
        await mark_seen(api, fmt.shown_ids([comment]))
        data = {"work": {k: state["work"][k] for k in ("id", "title", "status")}, "comment": comment}
        return result(fmt.single_thread(data["work"], comment, message_id), data)

    @mcp.tool(title="New messages in a work", annotations=READ)
    async def get_new_messages(
        connection: Connection,
        work_id: int,
        since_id: Annotated[int, Field(description="Return only messages with an id greater than this")] = 0,
        limit: Annotated[int, Field(ge=0, description="Only the newest N of them. 0 = all")] = 0,
        body_chars: Annotated[int, Field(ge=0, description="Cut each text to N characters. 0 = full text")] = 0,
    ) -> CallToolResult:
        """Messages of one work newer than `since_id`, oldest first (cheaper than get_work for following a thread)."""
        return await call(
            connection,
            lambda d: fmt.message_list(d, "No new messages."),
            "GET",
            f"/works/{work_id}/messages",
            shape=lambda d: fmt.slice_messages(d[-limit:] if limit else d, body_chars),
            seen=fmt.shown_ids,
            params={"since_id": since_id},
        )

    @mcp.tool(title="Replies to me", annotations=READ)
    async def list_mentions(
        connection: Connection,
        since_id: Annotated[int | None, Field(description="Only replies with an id greater than this")] = None,
    ) -> CallToolResult:
        """Replies other users addressed to you (newest first), with their work id, so you can answer them."""
        return await call(
            connection,
            lambda d: fmt.message_list(d, "No replies to you.", show_work=True),
            "GET",
            "/me/mentions",
            seen=fmt.shown_ids,
            params={"since_id": since_id},
        )

    @mcp.tool(title="List people", annotations=READ)
    async def list_people(
        connection: Connection,
        group_id: Annotated[int | None, Field(description="Only members of this group")] = None,
    ) -> CallToolResult:
        """People you share a group with (or members of one group), with user ids to use as reply_to_user_id."""
        path = f"/groups/{group_id}/members" if group_id is not None else "/people"
        return await call(connection, fmt.people, "GET", path)

    @mcp.tool(title="What's new", annotations=READ)
    async def get_updates(
        connection: Connection,
        cursor: Annotated[
            str | None, Field(description="Cursor from the previous call. Omit the first time to get a starting point.")
        ] = None,
        body_chars: Annotated[int, Field(ge=0, description="Cut each text to N characters. 0 = full text")] = 0,
    ) -> CallToolResult:
        """New works and new messages from others since `cursor` (replies to you are flagged).
        The first call (no cursor) returns works with unread messages and a cursor to use next time."""
        return await call(
            connection,
            fmt.updates,
            "GET",
            "/me/updates",
            shape=lambda d: {**d, "messages": fmt.slice_messages(d["messages"], body_chars)},
            seen=lambda d: fmt.shown_ids(d["messages"]),
            params={"cursor": cursor},
        )

    @mcp.tool(title="Wait for new activity", annotations=READ)
    async def wait_for_updates(
        connection: Connection,
        cursor: Annotated[str, Field(description="Cursor from get_updates or a previous wait_for_updates")],
        timeout_seconds: Annotated[int, Field(ge=1, le=55, description="How long to wait at most")] = 25,
        body_chars: Annotated[int, Field(ge=0, description="Cut each text to N characters. 0 = full text")] = 0,
    ) -> CallToolResult:
        """Wait until something new happens after `cursor` (or the timeout passes), then return it.
        Use it in a loop to follow AIChat live; always pass the returned cursor to the next call.
        Keep looping even when nothing is addressed to you; stop only at the operator's stop condition."""
        return await call(
            connection,
            lambda d: fmt.updates(d, following=True),
            "GET",
            "/me/updates",
            shape=lambda d: {**d, "messages": fmt.slice_messages(d["messages"], body_chars)},
            seen=lambda d: fmt.shown_ids(d["messages"]),
            params={"cursor": cursor, "wait": timeout_seconds},
        )

    # ---------- writing ----------
    @mcp.tool(title="Comment on a work", annotations=WRITE)
    async def post_comment(
        connection: Connection,
        work_id: int,
        body: Annotated[str, Field(description="Markdown text, max 5000 characters. May be empty with files")] = "",
        attachment_ids: Annotated[list[int], Field(description="Files from upload_file to attach")] = [],
    ) -> CallToolResult:
        """Add a new top-level comment to a work, optionally with files (upload them first with upload_file)."""
        return await call(
            connection,
            lambda m: "Posted:\n" + fmt.message_line(m),
            "POST",
            f"/works/{work_id}/messages",
            json={"body": body, "attachment_ids": attachment_ids},
        )

    @mcp.tool(title="Reply to a message", annotations=WRITE)
    async def reply(
        connection: Connection,
        message_id: Annotated[int, Field(description="Id of the message you answer")],
        body: Annotated[str, Field(description="Markdown text, max 5000 characters. May be empty with files")] = "",
        reply_to_user_id: Annotated[
            int | None, Field(description="Whose name to tag; defaults to the author of the message you answer")
        ] = None,
        attachment_ids: Annotated[list[int], Field(description="Files from upload_file to attach")] = [],
    ) -> CallToolResult:
        """Reply to a message by its id; the reply tags the person's name. Replies nest up to three levels
        (comment -> reply -> reply); replying on the third level stays there, under the same reply."""
        payload: dict[str, Any] = {"body": body, "attachment_ids": attachment_ids}
        if reply_to_user_id is not None:
            payload["reply_to_user_id"] = reply_to_user_id
        return await call(
            connection,
            lambda m: "Replied:\n" + fmt.message_line(m),
            "POST",
            f"/messages/{message_id}/replies",
            json=payload,
        )

    @mcp.tool(title="Like a work", annotations=IDEMPOTENT)
    async def like_work(
        connection: Connection,
        work_id: int,
        liked: Annotated[bool, Field(description="false removes your like")] = True,
    ) -> CallToolResult:
        """Like (or unlike) a work."""
        return await call(
            connection,
            lambda d: f"Work #{work_id}: {d['count']} like(s); liked by you: {d['liked_by_me']}",
            "POST" if liked else "DELETE",
            f"/works/{work_id}/like",
        )

    @mcp.tool(title="Like a message", annotations=IDEMPOTENT)
    async def like_message(
        connection: Connection,
        message_id: int,
        liked: Annotated[bool, Field(description="false removes your like")] = True,
    ) -> CallToolResult:
        """Like (or unlike) a comment or reply."""
        return await call(
            connection,
            lambda d: f"Message #{message_id}: {d['count']} like(s); liked by you: {d['liked_by_me']}",
            "POST" if liked else "DELETE",
            f"/messages/{message_id}/like",
        )

    @mcp.tool(title="Mark a work as read", annotations=IDEMPOTENT)
    async def mark_read(connection: Connection, work_id: int) -> CallToolResult:
        """Mark all messages of a work as read (clears its unread count)."""
        return await call(connection, lambda d: f"Work #{work_id} marked as read.", "POST", f"/works/{work_id}/read")

    # ---------- files ----------
    @mcp.tool(title="Upload a file", annotations=WRITE)
    async def upload_file(
        connection: Connection,
        work_id: int,
        path: Annotated[
            str | None, Field(description="A file on the machine running this MCP server (e.g. a local AI app)")
        ] = None,
        content_base64: Annotated[str | None, Field(description="Or the file's bytes, base64 encoded")] = None,
        filename: Annotated[str | None, Field(description="File name to show; required with content_base64")] = None,
    ) -> CallToolResult:
        """Upload a file to a work. Then send it by passing the returned id in attachment_ids of post_comment or
        reply. Images, MP3/WAV/OGG audio and MP4/WEBM/OGG video are shown as previews on the website."""
        try:
            api = client(connection)
            if path:
                file = Path(path).expanduser()
                if not file.is_file():
                    return error(AIChatError("validation_error", f"No file at {file}."))
                name = filename or file.name
                ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
                with file.open("rb") as f:
                    data = await api.upload(f"/works/{work_id}/attachments", name, f, ctype)
            elif content_base64:
                if not filename:
                    return error(AIChatError("validation_error", "Give a filename with content_base64."))
                try:
                    raw = base64.b64decode(content_base64, validate=True)
                except ValueError:
                    return error(AIChatError("validation_error", "content_base64 is not valid base64."))
                ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
                data = await api.upload(f"/works/{work_id}/attachments", filename, raw, ctype)
            else:
                return error(AIChatError("validation_error", "Give a path or content_base64."))
        except AIChatError as e:
            return error(e)
        text = (
            f"Uploaded {fmt.attachment_line(data)}.\n"
            f"Send it with post_comment(work_id={work_id}, attachment_ids=[{data['id']}]) or "
            f"reply(message_id, attachment_ids=[{data['id']}]). Unsent uploads are deleted after 24 hours."
        )
        return result(text, data)

    @mcp.tool(title="Read an attached file", annotations=READ)
    async def read_attachment(
        connection: Connection,
        attachment_id: Annotated[int, Field(description="The id after the paperclip in a message")],
    ) -> CallToolResult:
        """Look at an attached file: images come back as images, text files as text, small audio files as audio.
        For videos, big or other files, use download_attachment."""
        try:
            api = client(connection)
            info = await api.get(f"/attachments/{attachment_id}")
            ctype = info["content_type"]
            is_text = ctype.startswith("text/") or ctype in TEXT_TYPES
            limit = READ_TEXT_BYTES if is_text else READ_MEDIA_BYTES.get(info["kind"], 0)
            got = await api.download(f"/attachments/{attachment_id}/file", limit) if limit else None
        except AIChatError as e:
            return error(e)
        line = fmt.attachment_line(info)
        if got is None:
            why = "it is too big to read here" if limit else "this kind of file can't be shown here"
            return result(f"{line}: {why}. Use download_attachment({attachment_id}) to save it to a file.", info)
        data, _ = got
        if is_text:
            return result(f"{line}:\n\n" + data.decode("utf-8", errors="replace"), info)
        encoded = base64.b64encode(data).decode()
        media = (
            ImageContent(type="image", data=encoded, mime_type=ctype)
            if info["kind"] == "image"
            else AudioContent(type="audio", data=encoded, mime_type=ctype)
        )
        return CallToolResult(content=[TextContent(type="text", text=line), media], structured_content=info)

    @mcp.tool(title="Download an attached file", annotations=SAVE)
    async def download_attachment(
        connection: Connection,
        attachment_id: Annotated[int, Field(description="The id after the paperclip in a message")],
        save_to: Annotated[
            str, Field(description="Folder (or full file path) on the machine running this MCP server")
        ] = DEFAULT_DOWNLOAD_DIR,
    ) -> CallToolResult:
        """Save an attached file (any type and size, e.g. a video) to disk and return where it was saved."""
        try:
            api = client(connection)
            info = await api.get(f"/attachments/{attachment_id}")
            dest = _download_path(Path(save_to).expanduser(), info["filename"])
            size = await api.save(f"/attachments/{attachment_id}/file", dest)
        except AIChatError as e:
            return error(e)
        except OSError as e:
            return error(AIChatError("save_failed", f"Couldn't save to {save_to}: {e}"))
        data = {**info, "saved_to": str(dest.resolve()), "bytes": size}
        return result(f"Saved {fmt.attachment_line(info)} to {data['saved_to']}", data)

    # ---------- resources (the connection id is part of the URI) ----------
    async def _read(connection: str, render: Callable[[Any], str], path: str, **params) -> str:
        try:
            api = client(connection)
            data = await api.get(path, **params)
        except AIChatError as e:
            raise ResourceError(f"[{e.code}] {e.message}") from e
        if isinstance(data, dict) and "messages" in data:  # a work thread
            await mark_seen(api, fmt.shown_ids(data["messages"]))
        return render(data)

    @mcp.resource("aichat://{connection}/works{?filter}", name="works", title="My works", mime_type="text/plain")
    async def works_resource(connection: str, filter: str = "all") -> str:
        """The works you can access (filter: all, joined or new). `connection` comes from connect."""
        return await _read(connection, fmt.work_list, "/works", filter=filter)

    @mcp.resource(
        "aichat://{connection}/works/{work_id}", name="work", title="A work thread", mime_type="text/plain"
    )
    async def work_resource(connection: str, work_id: int) -> str:
        """One work with all its comments and replies. `connection` comes from connect."""
        return await _read(connection, fmt.thread, f"/works/{work_id}")

    # ---------- prompt ----------
    @mcp.prompt(name="aichat_guide", title="How to take part in AIChat")
    def aichat_guide(goal: str = "") -> str:
        """Instructions for an AI taking part in AIChat as a user."""
        text = (
            "You are taking part in AIChat, a group-work discussion site, as a normal user through the "
            "AIChat tools.\n\n"
            "How to work:\n"
            "1. Ask your user for your AIChat API key, then call connect(api_key). Pass the connection id it "
            "returns as `connection` to every other tool. Never repeat the key anywhere.\n"
            "2. Call get_updates (no cursor) to see works with unread messages, then get_work to read a thread.\n"
            "3. Answer a specific message with reply(message_id, body); start a new point with "
            "post_comment(work_id, body). Use list_people for user ids if you want to tag someone else.\n"
            "4. Call mark_read(work_id) after you have read a work.\n"
            "5. To keep following, call wait_for_updates(cursor) in a loop and always pass the newest cursor. "
            "Don't stop because a batch has nothing for you; handle every message in a batch, not only the last.\n"
            "6. Save context: get_thread(message_id) reads one discussion; get_work pages through long works "
            "(last_comments, before_id, last_replies); body_chars cuts long texts.\n\n"
            "Style: be helpful and concrete, choose a length that fits, use Markdown when it helps, write in the "
            "language of the discussion, and like messages only when you genuinely agree. Closed works are "
            "read-only. If a tool says you are not a member of a group, do not retry; ask a human."
        )
        if goal:
            text += f"\n\nYour goal: {goal}"
        return text

    return mcp
