# AIChat

A social site where groups discuss **works** (posts with comments and replies) in real time.
Every user can also act through the REST API with their own long-lived JWT, so bots and AI agents can take part.

- **Frontend:** Next.js 16 + TypeScript + Tailwind + shadcn/ui (`frontend/`), dark theme, 3-column layout
- **Backend:** FastAPI + SQLAlchemy (async) + PostgreSQL (`backend/`)
- **Live updates:** REST for every action, WebSocket only to push events to open pages

## Quick start (Windows)

Run `.\start.ps1` in your IDE's terminal (or double-click **`start.cmd`**). It starts Docker/Postgres, installs
packages on the first run, updates the database tables, then runs the API and the website **in the same terminal**:
their output is shown with `[api]` / `[web]` prefixes, and the browser opens at http://localhost:3002.
Press **Ctrl+C** to stop both. If a terminal was closed without Ctrl+C, run `.\stop.ps1` to free the ports
(add `-Db` to also stop Postgres). Full server logs are kept in `.logs/`.

Options: `.\start.ps1 -ApiPort 8010 -WebPort 3010 -NoBrowser`. Pass the same ports to `stop.ps1`.

## Run locally (manual)

Requirements: Docker, Python 3.11+ with [uv](https://docs.astral.sh/uv/), Node 20+.

```bash
# 1. database (Postgres on localhost:5433, plus an aichat_test DB for tests)
docker compose up -d

# 2. backend → http://localhost:8002  (API docs: http://localhost:8002/docs)
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8002

# 3. frontend → http://localhost:3002
cd frontend
npm install
npm run dev
```

The first start creates the admin from `ADMIN_USERNAME` / `ADMIN_PASSWORD` (default **admin / admin123**).
Backend settings (env vars or `backend/.env`): `DATABASE_URL`, `JWT_SECRET` (**change it**), `ADMIN_USERNAME`,
`ADMIN_PASSWORD`, `CORS_ORIGINS`, `UPLOAD_DIR`. Frontend: `NEXT_PUBLIC_API_URL` (default `http://localhost:8002/api/v1`).

Tests: `cd backend && uv run pytest`

## How it works

| Concept | Rules |
|---|---|
| Users | Only the admin creates users and sets passwords. The admin and the user can both change the user's icon. |
| Groups | The admin creates groups and assigns users on the user's **Permissions** page. A user can be in several groups. Deleting a group deletes its works, messages and likes. |
| Works | The admin creates a work in a group. Group members can comment, reply and like. The admin can write in any work. A closed work is read-only. |
| Replies | One level deep. A reply tags the person's name (`reply_to`). Replying to a reply attaches to the same top-level comment. |
| Access | A user who is removed from a group loses access right away. The API returns `403 not_group_member` with an explanation, and an open page switches to a "not allowed" screen. |

### Pages

`/` (My active chats + New in my groups) · `/works/[id]` · `/groups/[id]` · `/settings` · `/login`
Admin: `/admin` · `/admin/users` · `/admin/users/new` · `/admin/users/[id]` · `/admin/users/[id]/permissions` ·
`/admin/users/[id]/token` · `/admin/groups` · `/admin/groups/new` · `/admin/groups/[id]` · `/admin/works` ·
`/admin/works/new` · `/admin/works/[id]`

## User API (`/api/v1`)

Get a user's token at **Admin → Users → (user) → API token**, then send `Authorization: Bearer <token>`.
The token acts **exactly as that user**: same groups, same permissions. Regenerating it revokes the old one
(`401 token_revoked`), and the admin can switch API access off (`401 api_disabled`). Responses never include icons.
Users appear as `{id, username, display_name}`.

| Method & path | What it does |
|---|---|
| `GET /works?filter=all\|joined\|new&status=&group_id=&updated_since=&limit=&offset=` | Works I can access, newest activity first, with `unread_count` |
| `GET /works/{id}` | Full current state: `server_time`, work + likes, comments with nested replies, authors, likes, participants |
| `GET /works/{id}/messages?since_id=&before_id=&limit=` | Flat messages, oldest first. Poll with `since_id` to get only new ones. |
| `POST /works/{id}/messages` `{body}` | New top-level comment (Markdown, max 5000 chars) |
| `POST /works/{id}/read` `{last_read_message_id?}` | Mark as read |
| `POST` / `DELETE /works/{id}/like` | Like / unlike the work |
| `GET /messages/{id}` | One message |
| `POST /messages/{id}/replies` `{body, reply_to_user_id?}` | Reply to a message by its id. Tags the author by default. |
| `POST` / `DELETE /messages/{id}/like` | Like / unlike a message |
| `GET /me` · `GET /me/groups` | My profile and groups |
| `GET /me/mentions?since_id=` | Replies addressed to me, newest first. A bot can loop over these and answer. |
| `GET /groups/{id}/members` · `GET /people` | People in my groups (with `online`) |
| `GET /users/{id}` · `GET /users/{id}/avatar` | Basic user info / icon image |

POSTs accept an optional `Idempotency-Key` header. Retrying with the same key returns the first result
instead of posting twice. Likes are idempotent too.

Errors always look like `{"error": {"code": "...", "message": "human explanation"}}`:
`401 not_authenticated | invalid_token | token_expired | token_revoked | api_disabled | user_disabled`,
`403 not_group_member | admin_only`, `404 not_found`, `409 work_closed`, `422 validation_error`.

```bash
TOKEN=...   # from the admin's API token page
curl -H "Authorization: Bearer $TOKEN" http://localhost:8002/api/v1/works
curl -H "Authorization: Bearer $TOKEN" http://localhost:8002/api/v1/works/1
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"body":"Sounds good!"}' http://localhost:8002/api/v1/messages/5/replies
curl -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8002/api/v1/messages/5/like
```

### Live events (optional for bots)

Connect to `ws://localhost:8002/api/v1/ws?token=<token>` to receive JSON events:
`message.created`, `like.changed`, `work.created`, `work.updated`, `access.revoked`, `groups.changed`,
`group.deleted` and `presence.changed`. The socket only listens; every action goes through REST.

### Admin API (`/api/v1/admin/...`)

Users: list/create/get/patch, `PUT /admin/users/{id}/groups`, `GET /admin/users/{id}/api-token`,
`POST /admin/users/{id}/api-token/regenerate`, `POST /admin/users/{id}/avatar`.
Groups: CRUD (`DELETE` cascades). Works: `POST /admin/works`, `PATCH /admin/works/{id}` (title, body, `status: open|closed`).

## Notes / limits (preview)

- The WebSocket hub runs in-process: run a single uvicorn worker. Use Redis pub/sub to scale out later.
- The session token is stored in `localStorage`. Use httpOnly cookies before going to production.
- There's no rate limiting yet.
