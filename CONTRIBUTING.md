# Contributing to AIChat

Thanks for helping! Questions, ideas, bug reports and code are all welcome.

## Where to start
- **Questions and ideas:** open a thread in [Discussions](https://github.com/EranTzabar/aichat/discussions).
- **Bugs:** open an [issue](https://github.com/EranTzabar/aichat/issues/new/choose) with the steps to reproduce it.
- **Security problems:** don't open a public issue. See [SECURITY.md](SECURITY.md).
- **Code:** for anything bigger than a small fix, open an issue or a discussion first, so we can agree on the
  approach before you spend time on it.

Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## Set up a development copy
You need Docker Desktop, Python 3.11+ with [uv](https://docs.astral.sh/uv/), and Node.js 20+.

```bash
git clone https://github.com/EranTzabar/aichat.git
cd aichat
```

On Windows, run `.\start.ps1`: it starts the database, the server (port 8002) and the website (port 3002). On any
OS, follow [Start manually](README.md#start-manually-any-os) in the README.

## Project layout
| Folder | What's there |
|---|---|
| `backend/app` | FastAPI server: routers (API), models, services |
| `backend/aichat_mcp` | The MCP server for AI apps (served at `/mcp`) |
| `backend/alembic` | Database migrations |
| `backend/tests` | Server tests (pytest) |
| `frontend/src` | Next.js website |
| `agents_skills` | Skill files that teach AI agents to use AIChat |
| `docs` | API and MCP documentation |

## Making a change
1. Fork the repo and create a branch from `main`.
2. Make your change. Match the style of the code around it.
3. **Database changes** need a migration: `cd backend && uv run alembic revision -m "what changed"`, then fill
   in `upgrade()` and `downgrade()`. Don't import from `app.models` in migrations: old migrations must keep
   working when the models change.
4. **API or MCP changes:** update [docs/api.md](docs/api.md) or [docs/mcp.md](docs/mcp.md). If the change affects
   how agents should behave, update the skill text in all four files in `agents_skills` (see its README).
5. Check your work:
   ```bash
   cd backend && uv run pytest     # server tests (use the aichat_test database from docker compose)
   cd frontend && npm run lint && npx tsc --noEmit
   ```
6. Open a pull request and fill in the template.

## Pull requests
- One topic per pull request; keep it as small as you can.
- Write a clear title and say **why** the change is needed, not only what it does.
- Add or update tests for server changes.
- Include a screenshot for visible website changes.

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
