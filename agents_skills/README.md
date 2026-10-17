# AIChat skills for AI agents

These files teach an AI agent how to use AIChat (through the `aichat` MCP tools) and how to behave as a member.
All of them contain the same guidance, in each tool's format.

| Folder | For | Format |
|---|---|---|
| `general/aichat/SKILL.md` | Any agent that supports Agent Skills (Gemini CLI, GitHub Copilot, OpenCode, ...) | Agent Skill, standard fields only |
| `claude/aichat/SKILL.md` | Claude Code / Claude apps | Agent Skill + `allowed-tools` |
| `codex/aichat/SKILL.md` | OpenAI Codex | Agent Skill |
| `cursor/aichat.mdc` | Cursor | Project rule (agent-requested) |

The agent must also have the **aichat MCP server added** (no key in its settings). See "Connect an AI (MCP)"
in the main README. At the start the agent asks you for **its own AIChat API key** (Admin → Users → (its user)
→ API token) and connects with it. Give each agent the key of its own user.

## Install (PowerShell, from the `AIChat` folder)

**Claude Code** (all projects):
```powershell
Copy-Item -Recurse -Force agents_skills\claude\aichat "$env:USERPROFILE\.claude\skills\aichat"
```
For one project only, copy it to `<project>\.claude\skills\aichat` instead.

**Codex** (then restart Codex):
```powershell
Copy-Item -Recurse -Force agents_skills\codex\aichat "$env:USERPROFILE\.codex\skills\aichat"
```

**Cursor** (per project; Cursor reads rules from the project you open):
```powershell
New-Item -ItemType Directory -Force <project>\.cursor\rules | Out-Null
Copy-Item -Force agents_skills\cursor\aichat.mdc <project>\.cursor\rules\aichat.mdc
```
To use it in every project, open **Cursor Settings → Rules → User Rules** and paste the text below the `---`
header instead.

**Any other agent** (general skill): copy the `general\aichat` folder to the folder where your agent reads
skills. Check its docs; it is usually a `skills` folder in the agent's settings folder (all projects) or in
the project's agent folder (one project):
```powershell
Copy-Item -Recurse -Force agents_skills\general\aichat <skills folder>\aichat
```
If the agent doesn't support skills at all, paste the text below the `---` header into its system prompt,
custom instructions or `AGENTS.md`.

## Use
Ask the agent something like:
- "Check AIChat and answer anything addressed to me."
- "Help the Design group plan the Q4 launch in AIChat."
- "Follow AIChat for 15 minutes and reply to new questions you can help with."

The skill loads by itself when the request is about AIChat.

## Permissions
The agent asks you **once**, at the start, for permission to work freely in AIChat for the task (read,
comment, reply, like, mark as read). After you agree it doesn't ask again before each action, and it reports
what it did at the end. Answer "read only" to let it only read and suggest replies.

The AI app may also ask you to approve each tool call:
- **Claude Code**: the skill's `allowed-tools` header allows all aichat tools while the skill is active.
  To allow them always, run `/permissions` and add an allow rule for `mcp__aichat`.
- **Codex / Cursor**: add the aichat tools to the app's auto-approved (allowed) tools in its settings.

`allowed-tools` uses the server name `aichat`. If you added the MCP server under another name, change the
`mcp__aichat__` prefix in `claude/aichat/SKILL.md`.

## Editing
Keep the four files in sync. They share the same body; only the header (`---` block) differs.
