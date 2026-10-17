"""Attachments: upload, attach to a message or the work post, serialize, clean up."""
import logging
import mimetypes
import re
import uuid
from collections import defaultdict
from datetime import timedelta

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal, utcnow
from app.errors import ApiError
from app.models import Attachment, User, Work
from app.services.storage import get_storage

log = logging.getLogger(__name__)

IMAGE = {"image/png", "image/jpeg", "image/gif", "image/webp"}  # no SVG: it can carry scripts
AUDIO = {"audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave", "audio/ogg"}
VIDEO = {"video/mp4", "video/webm", "video/ogg"}
ORPHAN_HOURS = 24


def kind(content_type: str) -> str:
    """How the website shows a file: image / audio / video preview, or a plain file card."""
    if content_type in IMAGE:
        return "image"
    if content_type in AUDIO:
        return "audio"
    if content_type in VIDEO:
        return "video"
    return "file"


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


async def save_upload(db: AsyncSession, work: Work, me: User, file: UploadFile) -> Attachment:
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
    key = f"attachments/{work.id}/{uuid.uuid4().hex}"
    await get_storage().put(key, file.file, content_type)
    a = Attachment(
        work_id=work.id,
        uploader_id=me.id,
        filename=filename,
        content_type=content_type,
        size=size,
        storage_key=key,
    )
    db.add(a)
    await db.commit()
    return a


async def attach(
    db: AsyncSession, me: User, work: Work, ids: list[int], *, message_id: int | None = None, on_work: bool = False
) -> None:
    """Attach my unsent uploads of this work to a message or to the work post (the caller commits)."""
    if not ids:
        return
    wanted = set(ids)
    rows = (
        await db.scalars(
            select(Attachment).where(
                Attachment.id.in_(wanted),
                Attachment.work_id == work.id,
                Attachment.uploader_id == me.id,
                Attachment.message_id.is_(None),
                Attachment.on_work.is_(False),
            )
        )
    ).all()
    missing = wanted - {a.id for a in rows}
    if missing:
        ids_text = ", ".join(f"#{i}" for i in sorted(missing))
        raise ApiError(
            422,
            "validation_error",
            f"Attachment {ids_text} can't be used: upload it to work #{work.id} first (each upload is used once).",
        )
    for a in rows:
        a.message_id = message_id
        a.on_work = on_work


async def message_attachments(db: AsyncSession, message_ids: list[int]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = defaultdict(list)
    if message_ids:
        rows = await db.scalars(
            select(Attachment).where(Attachment.message_id.in_(message_ids)).order_by(Attachment.id)
        )
        for a in rows:
            out[a.message_id].append(attachment_out(a))
    return out


async def work_attachments(db: AsyncSession, work_id: int) -> list[dict]:
    rows = await db.scalars(
        select(Attachment).where(Attachment.work_id == work_id, Attachment.on_work.is_(True)).order_by(Attachment.id)
    )
    return [attachment_out(a) for a in rows]


async def remove(db: AsyncSession, attachments: list[Attachment]) -> None:
    """Delete the rows (the caller commits) and the stored files."""
    storage = get_storage()
    for a in attachments:
        await db.delete(a)
        try:
            await storage.delete(a.storage_key)
        except Exception:  # a missing object must not block the delete
            log.warning("could not delete stored file %s", a.storage_key, exc_info=True)


async def cleanup_orphans() -> None:
    """Delete uploads that were never sent with a message or the work post."""
    async with SessionLocal() as db:
        cutoff = utcnow() - timedelta(hours=ORPHAN_HOURS)
        rows = (
            await db.scalars(
                select(Attachment).where(
                    Attachment.message_id.is_(None), Attachment.on_work.is_(False), Attachment.created_at < cutoff
                )
            )
        ).all()
        if rows:
            await remove(db, list(rows))
            await db.commit()
            log.info("deleted %d unsent attachment(s)", len(rows))
