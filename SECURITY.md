# Security Policy

## Supported versions
Only the latest code on the `main` branch gets security fixes.

## Reporting a vulnerability
**Please don't report security problems in public issues, discussions or pull requests.**

Report them privately through GitHub: open the repository's **Security** tab and click
**[Report a vulnerability](https://github.com/EranTzabar/aichat/security/advisories/new)**.

Please include:
- what the problem is and what an attacker could do with it,
- the steps to reproduce it (the affected page, API endpoint or MCP tool),
- the version (commit) you tested.

You'll get an answer within a few days. Once the problem is confirmed, a fix is prepared and released, and you
are credited in the advisory unless you'd rather not be.

## Running AIChat safely
- Change `JWT_SECRET` and the admin password (`ADMIN_PASSWORD`) before anyone else uses the site.
- Serve the site over HTTPS when it's reachable from other computers.
- Keep `MCP_ALLOWED_HOSTS` limited to the hosts that really need `/mcp`.
- Treat each user's API key like a password. Regenerate it (Admin → Users → (user) → API token) if it leaks.
