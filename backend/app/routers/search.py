"""Full-text search over the chats, messages and attached files a user can see."""
import re
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import cast, func, literal, or_, select, union_all
from sqlalchemy.dialects.postgresql import REGCONFIG
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import ApiError
from app.models import Attachment, Group, Message, User, Chat
from app.permissions import accessible_chats
from app.schemas import SearchOut
from app.security import get_current_user
from app.services.attachments import attachment_out
from app.services.mentions import readable
from app.services.serialize import load_users, user_ref

router = APIRouter(tags=["search"])

WORD = re.compile(r"[^\W_]+")
SIMPLE = cast("simple", REGCONFIG)
HEADLINE = "StartSel=«, StopSel=», MaxWords=35, MinWords=12, MaxFragments=2, FragmentDelimiter=\" … \""
HEADLINE_CHARS = 100_000  # only the start of very long texts is used for the snippet


def ts_query(text: str):
    """Every word must match; each is a prefix, so 'plan' also finds 'planning'."""
    words = WORD.findall(text.lower())[:12]
    if not words:
        raise ApiError(422, "validation_error", "Search for at least one word.")
    return func.to_tsquery(SIMPLE, " & ".join(f"{w}:*" for w in words))


def headline(document, query):
    return func.ts_headline(SIMPLE, func.left(document, HEADLINE_CHARS), query, HEADLINE)


@router.get("/search", response_model=SearchOut, summary="Search chats, messages and attached files")
async def search(
    q: str = Query(..., min_length=2, max_length=200, description="Words to find (all must match; prefixes too)"),
    group_id: int | None = None,
    chat_id: int | None = None,
    author_id: int | None = Query(None, description="Only things written or uploaded by this user"),
    type: Literal["all", "chats", "messages", "files"] = "all",
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = ts_query(q)

    def scoped(stmt, author_col):
        stmt = stmt.where(accessible_chats(me.id, me.is_admin))
        if group_id is not None:
            stmt = stmt.where(Chat.group_id == group_id)
        if chat_id is not None:
            stmt = stmt.where(Chat.id == chat_id)
        if author_id is not None:
            stmt = stmt.where(author_col == author_id)
        return stmt

    parts = []
    if type in ("all", "chats"):
        parts.append(scoped(
            select(
                literal("chat").label("type"), Chat.id.label("ref_id"), Chat.id.label("chat_id"),
                func.ts_rank(Chat.search_tsv, query).label("rank"), Chat.created_at.label("at"),
            ).where(Chat.search_tsv.op("@@")(query)),
            Chat.created_by,
        ))
    if type in ("all", "messages"):
        parts.append(scoped(
            select(
                literal("message").label("type"), Message.id.label("ref_id"), Message.chat_id.label("chat_id"),
                func.ts_rank(Message.search_tsv, query).label("rank"), Message.created_at.label("at"),
            )
            .join(Chat, Chat.id == Message.chat_id)
            .where(Message.search_tsv.op("@@")(query)),
            Message.author_id,
        ))
    if type in ("all", "files"):
        parts.append(scoped(
            select(
                literal("file").label("type"), Attachment.id.label("ref_id"), Attachment.chat_id.label("chat_id"),
                func.ts_rank(Attachment.search_tsv, query).label("rank"), Attachment.created_at.label("at"),
            )
            .join(Chat, Chat.id == Attachment.chat_id)
            # Unsent uploads are private to their uploader.
            .where(Attachment.search_tsv.op("@@")(query), or_(Attachment.message_id.is_not(None), Attachment.on_chat)),
            Attachment.uploader_id,
        ))

    hits = union_all(*parts).subquery()
    total = await db.scalar(select(func.count()).select_from(hits))
    rows = (
        await db.execute(select(hits).order_by(hits.c.rank.desc(), hits.c.at.desc(), hits.c.ref_id.desc()).limit(limit).offset(offset))
    ).all()
    if not rows:
        return {"total": total or 0, "results": []}

    ids = {kind: [r.ref_id for r in rows if r.type == kind] for kind in ("chat", "message", "file")}
    chats = {w.id: w for w in await db.scalars(select(Chat).where(Chat.id.in_({r.chat_id for r in rows})))}
    groups = {g.id: g for g in await db.scalars(select(Group).where(Group.id.in_({w.group_id for w in chats.values()})))}

    snippets: dict[tuple[str, int], str] = {}
    authors: dict[tuple[str, int], int] = {}
    extra: dict[tuple[str, int], dict] = {}
    if ids["chat"]:
        doc = func.concat(Chat.title, "\n", Chat.body)
        for wid, snip in await db.execute(select(Chat.id, headline(doc, query)).where(Chat.id.in_(ids["chat"]))):
            snippets["chat", wid] = snip
            authors["chat", wid] = chats[wid].created_by
            extra["chat", wid] = {"message_id": None}
    if ids["message"]:
        for m, snip in await db.execute(select(Message, headline(Message.body, query)).where(Message.id.in_(ids["message"]))):
            snippets["message", m.id] = snip
            authors["message", m.id] = m.author_id
            extra["message", m.id] = {"message_id": m.id}
    if ids["file"]:
        doc = func.concat(Attachment.filename, "\n", func.coalesce(Attachment.text_content, ""))
        for a, snip in await db.execute(select(Attachment, headline(doc, query)).where(Attachment.id.in_(ids["file"]))):
            snippets["file", a.id] = snip
            authors["file", a.id] = a.uploader_id
            extra["file", a.id] = {"message_id": a.message_id, "attachment": attachment_out(a)}

    users = await load_users(db, authors.values())
    snippets = dict(zip(snippets, await readable(db, list(snippets.values()))))
    results = []
    for r in rows:
        key = (r.type, r.ref_id)
        chat = chats[r.chat_id]
        group = groups[chat.group_id]
        results.append({
            "type": r.type,
            "chat_id": chat.id,
            "chat_title": chat.title,
            "group": {"id": group.id, "name": group.name},
            "author": user_ref(users[authors[key]]),
            "created_at": r.at,
            "snippet": snippets[key],
            **extra[key],
        })
    return {"total": total, "results": results}
