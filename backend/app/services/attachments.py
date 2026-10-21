"""Attachments: upload, attach to a message or the chat post, serialize, clean up."""
import logging
import mimetypes
import re
import uuid
from collections import defaultdict
from datetime import timedelta
from pathlib import PurePath

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal, utcnow
from app.errors import ApiError
from app.models import Attachment, User, Chat
from app.services.audit import audit
from app.services.storage import get_storage, storage_for

log = logging.getLogger(__name__)

IMAGE = {"image/png", "image/jpeg", "image/gif", "image/webp"}  # no SVG: it can carry scripts
AUDIO = {"audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave", "audio/ogg"}
VIDEO = {"video/mp4", "video/webm", "video/ogg"}
ORPHAN_HOURS = 24
SEARCH_TEXT_BYTES = 1024 * 1024  # text files up to this size are searchable
TEXT_TYPES = {
    "application/json", "application/xml", "application/javascript", "application/x-yaml", "application/yaml",
    "application/x-sh", "application/sql", "application/toml",
}
# Browsers often send no type (or octet-stream) for these, so the name decides.
TEXT_EXTENSIONS = {
    ".md", ".txt", ".csv", ".tsv", ".log", ".json", ".yaml", ".yml", ".toml", ".ini", ".xml", ".html", ".css",
    ".js", ".ts", ".tsx", ".py", ".sql", ".sh", ".ps1", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs", ".rb",
    ".php", ".kt", ".swift",
}


def kind(content_type: str) -> str:
    """How the website shows a file: image / audio / video preview, or a plain file card."""
    if content_type in IMAGE:
        return "image"
    if content_type in AUDIO:
        return "audio"
    if content_type in VIDEO:
        return "video"
    return "file"


def is_text(filename: str, content_type: str) -> bool:
    """A text or code file (the same rules as the MCP read_attachment)."""
    if content_type.startswith("text/") or content_type in TEXT_TYPES:
        return True
    guessed = mimetypes.guess_type(filename)[0] or ""
    return guessed.startswith("text/") or PurePath(filename).suffix.lower() in TEXT_EXTENSIONS


def as_text(data: bytes) -> str | None:
    """The bytes as text, or None when they look binary."""
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def clean_filename(name: str | None) -> str:
    name = re.split(r"[\\/]", name or "")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip().strip(".")
    return name[-255:] or "file"


def attachment_out(a: Attachment) -> dict:
    return {
        "id": a.id,
        "filename": a.filename,
        "content_type": a.content_type,
        "size": a.size,
        "kind": kind(a.content_type),
    }


async def save_upload(db: AsyncSession, chat: Chat, me: User, file: UploadFile) -> Attachment:
    """Store an uploaded file (unsent: not yet part of a message). Starlette already spooled it to a temp file."""
    filename = clean_filename(file.filename)
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if not content_type or content_type == "application/octet-stream":
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if settings.max_attachment_mb and size > settings.max_attachment_mb * 1024 * 1024:
        raise ApiError(422, "validation_error", f"'{filename}' is larger than {settings.max_attachment_mb} MB.")
    text = None
    if size <= SEARCH_TEXT_BYTES and is_text(filename, content_type):
        text = as_text(file.file.read())
        file.file.seek(0)
    key = f"attachments/{chat.id}/{uuid.uuid4().hex}"
    await get_storage().put(key, file.file, content_type)
    a = Attachment(
        chat_id=chat.id,
        uploader_id=me.id,
        filename=filename,
        content_type=content_type,
        size=size,
        storage_key=key,
        text_content=text,
    )
    db.add(a)
    await db.flush()
    audit(db, me, "attachment.upload", target=("attachment", a.id), chat=chat,
          details={"filename": filename, "size": size, "content_type": content_type})
    await db.commit()
    return a


async def attach(
    db: AsyncSession, me: User, chat: Chat, ids: list[int], *, message_id: int | None = None, on_chat: bool = False
) -> None:
    """Attach my unsent uploads of this chat to a message or to the chat post (the caller commits)."""
    if not ids:
        return
    wanted = set(ids)
    rows = (
        await db.scalars(
            select(Attachment).where(
                Attachment.id.in_(wanted),
                Attachment.chat_id == chat.id,
                Attachment.uploader_id == me.id,
                Attachment.message_id.is_(None),
                Attachment.on_chat.is_(False),
            )
        )
    ).all()
    missing = wanted - {a.id for a in rows}
    if missing:
        ids_text = ", ".join(f"#{i}" for i in sorted(missing))
        raise ApiError(
            422,
            "validation_error",
            f"Attachment {ids_text} can't be used: upload it to chat #{chat.id} first (each upload is used once).",
        )
    for a in rows:
        a.message_id = message_id
        a.on_chat = on_chat


async def message_attachments(db: AsyncSession, message_ids: list[int]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = defaultdict(list)
    if message_ids:
        rows = await db.scalars(
            select(Attachment).where(Attachment.message_id.in_(message_ids)).order_by(Attachment.id)
        )
        for a in rows:
            out[a.message_id].append(attachment_out(a))
    return out


async def chat_attachments(db: AsyncSession, chat_id: int) -> list[dict]:
    rows = await db.scalars(
        select(Attachment).where(Attachment.chat_id == chat_id, Attachment.on_chat.is_(True)).order_by(Attachment.id)
    )
    return [attachment_out(a) for a in rows]


async def remove(db: AsyncSession, attachments: list[Attachment]) -> None:
    """Delete the rows (the caller commits) and the stored files."""
    for a in attachments:
        await db.delete(a)
        try:
            await storage_for(a.storage_key).delete(a.storage_key)
        except Exception:  # a missing object must not block the delete
            log.warning("could not delete stored file %s", a.storage_key, exc_info=True)


async def backfill_search_text() -> None:
    """Keep the text of text files uploaded before search existed, so search finds words inside them."""
    async with SessionLocal() as db:
        rows = (
            await db.scalars(
                select(Attachment).where(Attachment.text_content.is_(None), Attachment.size <= SEARCH_TEXT_BYTES)
            )
        ).all()
        rows = [a for a in rows if is_text(a.filename, a.content_type)]
        for a in rows:
            try:
                data = b"".join([chunk async for chunk in storage_for(a.storage_key).stream(a.storage_key)])
            except Exception as e:
                log.warning("attachment #%s (%s): stored file not found, so it isn't searchable (%s)", a.id, a.filename, e)
                data = b""
            a.text_content = as_text(data) or ""  # "" = checked: don't read it again on the next start
        if rows:
            await db.commit()
            log.info("made %d attached text file(s) searchable", len(rows))


async def cleanup_orphans() -> None:
    """Delete uploads that were never sent with a message or the chat post."""
    async with SessionLocal() as db:
        cutoff = utcnow() - timedelta(hours=ORPHAN_HOURS)
        rows = (
            await db.scalars(
                select(Attachment).where(
                    Attachment.message_id.is_(None), Attachment.on_chat.is_(False), Attachment.created_at < cutoff
                )
            )
        ).all()
        if rows:
            await remove(db, list(rows))
            await db.commit()
            log.info("deleted %d unsent attachment(s)", len(rows))
