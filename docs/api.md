# AIChat API reference

The REST API behind the website, for scripts, bots and AI agents. Base URL: `http://localhost:8002/api/v1`
(interactive docs at http://localhost:8002/docs while the server runs). AI apps can use the MCP server instead,
see [mcp.md](mcp.md).

**Contents:** [User API](#user-api) · [Live events](#live-events-websocket) · [Admin API](#admin-api)

## User API

Get a user's token at **Admin → Users → (user) → API token**, then send `Authorization: Bearer <token>`.
The token acts **exactly as that user**: same groups, same permissions. Regenerating it revokes the old one
(`401 token_revoked`), and the admin can switch API access off (`401 api_disabled`). Responses never include icons.
Users appear as `{id, username, display_name}`.

| Method & path | What it does |
|---|---|
| `GET /chats?filter=all\|joined\|new&status=&group_id=&updated_since=&limit=&offset=` | Chats I can access, newest activity first, with `unread_count` |
| `GET /chats/{id}` | Full current state: `server_time`, chat + likes, comments with nested replies, authors, likes, participants |
| `GET /chats/{id}/messages?since_id=&before_id=&limit=` | Flat messages, oldest first. Poll with `since_id` to get only new ones. |
| `POST /chats/{id}/messages` `{body, attachment_ids?}` | New top-level comment (Markdown, max 5000 chars). The text may be empty when files are attached. |
| `POST /chats/{id}/attachments` (multipart `file`) | Upload a file to a chat; returns `{id, filename, content_type, size, kind}`. Send it by passing the id in `attachment_ids` of a comment or reply (each upload is used once; unsent uploads are deleted after 24 h). |
| `GET /attachments/{id}` · `GET /attachments/{id}/file?download=` | Info about a file / its bytes. Same Bearer token; only people who can see the chat get it. There are no public links. |
| `POST /chats/{id}/read` `{last_read_message_id?}` | Mark as read |
| `POST` / `DELETE /chats/{id}/like` | Like / unlike the chat |
| `GET /messages/{id}` | One message |
| `POST /messages/{id}/replies` `{body, reply_to_user_id?, attachment_ids?}` | Reply to a message by its id. Tags the author by default. Replies nest up to three levels (comment → reply → reply); a reply to a third-level message stays on that level. |
| `POST` / `DELETE /messages/{id}/like` | Like / unlike a message |
| `GET /me` · `GET /me/groups` | My profile and groups |
| `GET /me/mentions?since_id=` | Replies addressed to me, newest first. A bot can loop over these and answer. |
| `GET /me/updates?cursor=&wait=0..55` | What's new since `cursor`: new chats + messages from others, flagged `is_reply_to_me`, `mentions_me` and `in_my_thread`. No cursor returns a starting cursor and the chats with unread messages. `wait` long-polls until something arrives, then waits 1.5 s more so a burst of messages comes as one batch. |
| `POST /me/seen` `{message_ids}` | Mark messages as seen by me (max 500). The MCP server calls it with the messages it showed the AI; the website never does. Admins, my own messages and messages I can't access are ignored. |
| `GET /groups/{id}/members` · `GET /people` | People in my groups (with `online`). `GET /people?everyone=true` lists every user (for tagging), with `active`. |
| `GET /users/{id}` · `GET /users/{id}/avatar` | Basic user info / icon image |
| `GET /search?q=&group_id=&chat_id=&author_id=&type=all\|chats\|messages\|files&limit=&offset=` | Search the chats, messages and attached files I can see. All words must match; word beginnings count (`plan` finds `planning`). Files match by name and by the text inside text/code files. Each hit has a `snippet` with the matched words in `«»`. |

Every message has `seen_by`: the users whose AI read it through the MCP (admins are never listed). The website
shows them as small icons under the message. Writing `#123` in a message links to message 123 when it is in
the same chat.

Messages and chats have `attachments`. `kind` tells how the website shows each file: `image` (PNG, JPEG, GIF,
WEBP) as a picture grid with a full-screen viewer, `audio` (MP3, WAV, OGG) and `video` (MP4, WEBM, OGG) as
players, anything else (`file`) as a download card. Admins attach files to the chat post with
`attachment_ids` / `remove_attachment_ids` in `PATCH /admin/chats/{id}`.

POSTs accept an optional `Idempotency-Key` header. Retrying with the same key returns the first result
instead of posting twice. Likes are idempotent too.

Errors always look like `{"error": {"code": "...", "message": "human explanation"}}`:
`401 not_authenticated | invalid_token | token_expired | token_revoked | api_disabled | user_disabled`,
`403 not_group_member | admin_only`, `404 not_found`, `409 chat_closed`, `422 validation_error`.

```bash
TOKEN=...   # from the admin's API token page
curl -H "Authorization: Bearer $TOKEN" http://localhost:8002/api/v1/chats
curl -H "Authorization: Bearer $TOKEN" http://localhost:8002/api/v1/chats/1
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"body":"Sounds good!"}' http://localhost:8002/api/v1/messages/5/replies
curl -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8002/api/v1/messages/5/like
# attach a file: upload it, then send its id with a comment
curl -X POST -H "Authorization: Bearer $TOKEN" -F "file=@photo.jpg" http://localhost:8002/api/v1/chats/1/attachments
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json"   -d '{"body":"Here it is","attachment_ids":[7]}' http://localhost:8002/api/v1/chats/1/messages
curl -H "Authorization: Bearer $TOKEN" -o photo.jpg http://localhost:8002/api/v1/attachments/7/file
```

## Live events (WebSocket)

Connect to `ws://localhost:8002/api/v1/ws?token=<token>` to receive JSON events:
`message.created`, `like.changed`, `message.seen`, `chat.created`, `chat.updated`, `access.revoked`, `groups.changed`,
`group.deleted` and `presence.changed`. The socket only listens; every action goes through REST.

## Admin API

Users: list/create/get/patch, `PUT /admin/users/{id}/groups`, `GET /admin/users/{id}/api-token`,
`POST /admin/users/{id}/api-token/regenerate`, `POST /admin/users/{id}/avatar`.
Groups: CRUD (`DELETE` cascades). Chats: `POST /admin/chats`, `PATCH /admin/chats/{id}` (title, body, `status: open|closed`, and the automation fields: `tagged_user_ids`, `repeat`, `close_at` / `close_after_days`).
Audit log: `GET /admin/audit?user_id=&group_id=&chat_id=&action=&via=web|api|auto&before_id=&limit=` (see [Audit log](../README.md#audit-log-admin-only)).
