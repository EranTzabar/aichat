"""Tags in message and chat text: `<@7>` (written by the website's @ picker, by user id) or `@username`."""
import re
from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, User, Chat

TAG_RE = re.compile(r"<@(\d+)>")
NAME_RE = re.compile(r"(?<![\w@<])@([A-Za-z0-9_.-]+)")


def tag(user_id: int) -> str:
    return f"<@{user_id}>"


def _names(text: str) -> list[str]:
    """`@word` candidates, also without trailing punctuation (`@dana.` → `dana`)."""
    out = []
    for word in NAME_RE.findall(text):
        out.append(word.lower())
        if word.rstrip(".-") != word:
            out.append(word.rstrip(".-").lower())
    return out


async def mentioned(db: AsyncSession, texts: Sequence[str]) -> list[list[User]]:
    """The users each text tags, in order of appearance, without repeats."""
    ids = {int(i) for t in texts for i in TAG_RE.findall(t)}
    names = {n for t in texts for n in _names(t)}
    if not ids and not names:
        return [[] for _ in texts]
    users = list(
        await db.scalars(select(User).where(or_(User.id.in_(ids), func.lower(User.username).in_(names))))
    )
    by_id = {u.id: u for u in users}
    by_name = {u.username.lower(): u for u in users}
    out = []
    for t in texts:
        found: dict[int, User] = {}
        for m in re.finditer(rf"{TAG_RE.pattern}|{NAME_RE.pattern}", t):
            if m[1]:
                u = by_id.get(int(m[1]))
            else:
                word = m[2].lower()
                u = by_name.get(word) or by_name.get(word.rstrip(".-"))
            if u:
                found.setdefault(u.id, u)
        out.append(list(found.values()))
    return out


async def readable(db: AsyncSession, texts: Sequence[str]) -> list[str]:
    """The texts with `<@id>` turned into `@username`, for plain-text previews and snippets."""
    ids = {int(i) for t in texts for i in TAG_RE.findall(t)}
    if not ids:
        return list(texts)
    names = dict((await db.execute(select(User.id, User.username).where(User.id.in_(ids)))).all())
    return [TAG_RE.sub(lambda m: f"@{names.get(int(m[1]), 'unknown')}", t) for t in texts]


def _text_tags(text, user_id: int, username: str):
    return or_(
        text.contains(tag(user_id)),
        text.op("~*")(rf"(^|[^[:alnum:]_@<])@{re.escape(username)}([^[:alnum:]_.-]|[.-]([^[:alnum:]_]|$)|$)"),
    )


def tags_user(user_id: int, username: str):
    """SQL condition: a message body that tags this user (by id or @username)."""
    return _text_tags(Message.body, user_id, username)


def chat_tags_user(user_id: int, username: str):
    """SQL condition: the chat was tagged for this user, or its description tags them."""
    return or_(Chat.tagged_user_ids.contains([user_id]), _text_tags(Chat.body, user_id, username))
