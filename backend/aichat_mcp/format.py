"""Compact, readable text versions of API responses for AI agents. Every id is kept so the AI can act on it."""


def _likes(obj: dict) -> str:
    n = obj["likes"]["count"]
    if not n:
        return ""
    mine = ", incl. you" if obj.get("liked_by_me") else ""
    return f" ({n} like{'s' if n != 1 else ''}{mine})"


def _indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line for line in text.splitlines()) or prefix


def file_size(n: int) -> str:
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def attachment_line(a: dict) -> str:
    return f"📎 #{a['id']} {a['filename']} ({a['kind']}, {file_size(a['size'])})"


def _attachments(obj: dict) -> str:
    return "".join("\n" + attachment_line(a) for a in obj.get("attachments") or [])


def person(u: dict) -> str:
    return f"{u['display_name']} (@{u['username']}, user {u['id']})"


def me(data: dict) -> str:
    groups = ", ".join(f"{g['name']} (group {g['id']})" for g in data["groups"]) or "none"
    role = "admin" if data["is_admin"] else "user"
    return f"You are {person(data)}, role: {role}.\nGroups: {groups}"


def _cut(m: dict, max_chars: int) -> dict:
    """Copy of a message (or chat) with its body cut to `max_chars` (0 = whole); `body_length` marks a cut."""
    if not max_chars or len(m["body"]) <= max_chars:
        return m
    return {**m, "body": m["body"][:max_chars].rstrip(), "body_length": len(m["body"])}


def slice_messages(items: list[dict], body_chars: int = 0) -> list[dict]:
    return [_cut(m, body_chars) for m in items]


def _slice_tree(m: dict, last_replies: int, body_chars: int) -> dict:
    """A comment or reply with its nested replies: the newest `last_replies` at each level, bodies cut."""
    replies = m.get("replies")
    if replies is None:
        return _cut(m, body_chars)
    kept = replies[-last_replies:] if last_replies else replies
    return {
        **_cut(m, body_chars),
        "replies": [_slice_tree(r, last_replies, body_chars) for r in kept],
        "hidden_replies": len(replies) - len(kept),
    }


def shown_ids(messages: list[dict]) -> list[int]:
    """Ids of these messages and all their nested replies (what the AI is shown)."""
    return [i for m in messages for i in (m["id"], *shown_ids(m.get("replies") or []))]


def find_thread(state: dict, message_id: int) -> dict | None:
    """The top-level comment whose thread contains `message_id`."""

    def contains(m: dict) -> bool:
        return m["id"] == message_id or any(contains(r) for r in m.get("replies") or [])

    return next((c for c in state["messages"] if contains(c)), None)


def slice_chat(
    state: dict, *, last_comments: int = 0, before_id: int | None = None, last_replies: int = 0, body_chars: int = 0
) -> dict:
    """Part of a chat to save context: the newest `last_comments` comments (older than `before_id`), the newest
    `last_replies` replies of each comment and reply, bodies cut to `body_chars`. 0 means no limit. Counts of
    what was left out are added, so the AI knows what it hasn't seen."""
    comments = state["messages"]
    older = [c for c in comments if before_id is None or c["id"] < before_id]
    shown = older[-last_comments:] if last_comments else older
    return {
        "chat": _cut(state["chat"], body_chars),
        "messages": [_slice_tree(c, last_replies, body_chars) for c in shown],
        "total_comments": len(comments),
        "hidden_older_comments": len(older) - len(shown),
        "hidden_newer_comments": len(comments) - len(older),
    }


def _body(m: dict, read_all: str) -> str:
    if "body_length" not in m:
        return m["body"]
    return m["body"] + f" ... [cut, {m['body_length']} chars; {read_all} shows it in full]"


def message_line(m: dict, *, show_chat: bool = False) -> str:
    who = m["author"]["display_name"]
    to = f" -> {m['reply_to']['display_name']}" if m.get("reply_to") else ""
    where = f" in chat #{m['chat_id']}" + (f" \"{m['chat_title']}\"" if m.get("chat_title") else "") if show_chat else ""
    kind = f", reply to #{m['parent_id']}" if m.get("parent_id") else ""
    seen = f" (seen by {len(m['seen_by'])})" if m.get("seen_by") else ""
    head = f"#{m['id']} {who}{to}{where}{kind} [{m['created_at'][:16].replace('T', ' ')}]{_likes(m)}{seen}:"
    return head + "\n" + _indent(_body(m, f"get_thread({m['id']})") + _attachments(m), "    ")


def comment_block(c: dict, depth: int = 0) -> list[str]:
    """A comment and its nested replies (up to three levels), each level indented further."""
    pad = "  " + "    " * depth
    lines = [_indent(message_line(c), pad)]
    if hidden := c.get("hidden_replies"):
        lines.append(f"{pad}    ({hidden} earlier repl{'ies' if hidden != 1 else 'y'}; get_thread({c['id']}) shows all)")
    for r in c.get("replies") or []:
        lines += comment_block(r, depth + 1)
    return lines


WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def automation(w: dict) -> str:
    """"Tagged: @yoni · repeats every day at 09:00 · closes 2026-10-25 18:00" for a chat, or ""."""
    parts = []
    if w.get("tagged"):
        parts.append("Tagged: " + ", ".join(f"@{u['username']}" for u in w["tagged"]))
    if r := w.get("repeat"):
        day = f"every {WEEKDAYS[r['weekday']]}" if r["every"] == "weekly" else "every day"
        parts.append(f"repeats {day} at {r['time']} (each copy closes the previous one)")
    if w.get("series"):
        parts.append(f"a copy of the repeating chat #{w['series']['id']}")
    if w.get("close_at"):
        parts.append(f"closes automatically at {str(w['close_at'])[:16].replace('T', ' ')} UTC")
    return " · ".join(parts)


def thread(state: dict) -> str:
    """A chat as text; `state` is the API's chat state, or a slice_chat() result."""
    w = state["chat"]
    shown = state["messages"]
    lines = [
        f"Chat #{w['id']} \"{w['title']}\" [{w['status']}] - group {w['group']['name']} (group {w['group']['id']})"
        f" - posted by {w['author']['display_name']}{_likes(w)}",
    ]
    if about := automation(w):
        lines.append("  " + about)
    if w["body"] or w.get("attachments"):
        lines.append(_indent(_body(w, f"get_chat({w['id']}, body_chars=0)") + _attachments(w), "  "))
    if w["status"] == "closed":
        lines.append("(This chat is closed: read-only, no new messages or likes.)")
    lines.append("")

    total = state.get("total_comments", len(shown))
    if not total:
        lines.append("No comments yet.")
    elif len(shown) < total:
        lines.append(f"Showing {len(shown)} of {total} comments, oldest first.")
        if older := state.get("hidden_older_comments"):
            before = f"before_id={shown[0]['id']}" if shown else "last_comments=0"
            lines.append(f"{older} older comment(s) not shown: get_chat({w['id']}, {before}) shows them.")
        if state.get("hidden_newer_comments"):
            lines.append(f"{state['hidden_newer_comments']} newer comment(s) not shown: get_chat({w['id']}) shows the newest.")
        lines.append("")
    for c in shown:
        lines += comment_block(c)
    lines.append("")
    lines.append("Reply to a message with reply(message_id, body); add a new comment with post_comment(chat_id, body).")
    return "\n".join(lines)


def single_thread(chat: dict, comment: dict, focus_id: int) -> str:
    lines = [f"Chat #{chat['id']} \"{chat['title']}\" [{chat['status']}] - thread of comment #{comment['id']}"]
    if focus_id != comment["id"]:
        lines.append(f"(Message #{focus_id} is a reply in this thread.)")
    lines.append("")
    lines += comment_block(comment)
    return "\n".join(lines)

def chat_list(items: list[dict]) -> str:
    if not items:
        return "No chats found."
    out = []
    for w in items:
        flags = []
        if w["status"] == "closed":
            flags.append("closed")
        if w["unread_count"]:
            flags.append(f"{w['unread_count']} unread")
        if not w["joined"]:
            flags.append("you haven't written here yet")
        flag = f" [{', '.join(flags)}]" if flags else ""
        out.append(f"Chat #{w['id']} \"{w['title']}\" - group {w['group_name']} - {w['message_count']} messages{flag}")
        if w["last_message"]:
            lm = w["last_message"]
            out.append(f"    last: #{lm['id']} {lm['author']['display_name']}: {lm['body_preview'][:100]}")
    return "\n".join(out)


def message_list(items: list[dict], empty: str = "No messages.", show_chat: bool = False) -> str:
    if not items:
        return empty
    return "\n".join(message_line(m, show_chat=show_chat) for m in items)


def people(items: list[dict]) -> str:
    if not items:
        return "No people found."
    return "\n".join(f"{person(p)}{' - online' if p.get('online') else ''}" for p in items)


def search_results(data: dict, offset: int = 0) -> str:
    hits = data["results"]
    if not hits:
        return "Nothing found."
    out = [f"{data['total']} result(s); showing {offset + 1}-{offset + len(hits)}. Matched words are in «»."]
    for h in hits:
        where = f"chat #{h['chat_id']} \"{h['chat_title']}\""
        who = h["author"]["display_name"]
        if h["type"] == "chat":
            head = f"Chat #{h['chat_id']} \"{h['chat_title']}\" (the post) by {who}"
        elif h["type"] == "message":
            head = f"#{h['message_id']} in {where} by {who}"
        else:
            on = f"message #{h['message_id']}" if h["message_id"] else "the chat post"
            head = f"📎 {attachment_line(h['attachment'])} on {on} in {where}, by {who}"
        snippet = " ".join(h["snippet"].split())
        out.append(f"{head}:\n    {snippet}")
    if offset + len(hits) < data["total"]:
        out.append(f"More results: call search again with offset={offset + len(hits)}.")
    return "\n".join(out)


def _for_me(m: dict) -> bool:
    return bool(m.get("is_reply_to_me") or m.get("mentions_me") or m.get("in_my_thread"))


def _tags(m: dict) -> str:
    tags = []
    if m.get("is_reply_to_me"):
        tags.append("REPLY TO YOU")
    if m.get("mentions_me"):
        tags.append("MENTIONS YOU")
    if m.get("in_my_thread"):
        tags.append("IN YOUR THREAD")
    if "?" in m["body"]:
        tags.append("question")
    return f"[{', '.join(tags)}] " if tags else ""


def _messages_by_chat(items: list[dict]) -> str:
    chats: dict[int, list[dict]] = {}
    for m in items:
        chats.setdefault(m["chat_id"], []).append(m)
    blocks = []
    for chat_id, msgs in chats.items():
        lines = [f"Chat #{chat_id} \"{msgs[0]['chat_title']}\" - {len(msgs)} new:"]
        lines += [_indent(_tags(m) + message_line(m), "  ") for m in msgs]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


HANDLE_ALL = (
    "Go through EVERY message above, oldest first, not only the last one. Always answer the ones for you "
    "(REPLY TO YOU, MENTIONS YOU, IN YOUR THREAD). You don't need to be tagged: also answer any other message "
    "(from people or AIs) where you have something useful to add - questions, proposals, decisions, requests "
    "for ideas. Skip only small talk and points already answered. You may answer several, including earlier "
    "ones. Use get_thread(message_id) first if you need context."
)


def updates(data: dict, following: bool = False) -> str:
    parts = []
    if data.get("unread_chats"):
        parts.append("Chats with unread messages:\n" + chat_list(data["unread_chats"]))
    if data["new_chats"]:
        parts.append(
            "New chats:\n"
            + "\n".join(
                ("[MENTIONS YOU] " if w.get("mentions_me") else "")
                + f"Chat #{w['id']} \"{w['title']}\" - group {w['group_name']} - by {w['author']['display_name']}"
                + (f"\n    {w['body_preview'][:200]}" if w["body_preview"] else "")
                for w in data["new_chats"]
            )
        )
    if data["messages"]:
        n = len(data["messages"])
        for_me = sum(1 for m in data["messages"] if _for_me(m))
        parts.append(f"{n} new message(s), {for_me} addressed to you or in your threads.")
        parts.append(_messages_by_chat(data["messages"]))
        parts.append(HANDLE_ALL)
    if not parts:
        parts.append("Nothing new.")
    cursor = data["cursor"]
    parts.append(f"Next cursor: {cursor}")
    if following:
        parts.append(
            f'You are following AIChat: after handling this, call wait_for_updates(cursor="{cursor}") again. '
            "Messages that are not for you, or a round with nothing new, are normal - keep following. "
            "Stop only when your operator's stop condition is reached."
        )
    else:
        parts.append(f'To keep following, call wait_for_updates(cursor="{cursor}").')
    return "\n\n".join(parts)
