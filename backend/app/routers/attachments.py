import logging
from collections.abc import AsyncIterator
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import ApiError, not_found
from app.models import Attachment, User
from app.permissions import get_accessible_chat
from app.schemas import AttachmentInfoOut
from app.security import get_current_user
from app.services.attachments import attachment_out, kind
from app.services.storage import storage_for

log = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/attachments", tags=["attachments"])


async def _get(db: AsyncSession, me: User, attachment_id: int) -> Attachment:
    """The attachment, if I may see its chat. Unsent uploads are visible only to their uploader."""
    a = await db.get(Attachment, attachment_id)
    if a is None or (a.message_id is None and not a.on_chat and a.uploader_id != me.id):
        raise not_found("Attachment", attachment_id)
    await get_accessible_chat(db, me, a.chat_id)
    return a


async def _open(a: Attachment) -> AsyncIterator[bytes]:
    """The file's bytes as a stream. The first chunk is read now, so a missing file is a clean 404, not a broken
    download."""
    chunks = storage_for(a.storage_key).stream(a.storage_key)
    try:
        first = await anext(chunks, b"")
    except Exception:
        log.warning("stored file of attachment #%s is missing (%s)", a.id, a.storage_key, exc_info=True)
        raise ApiError(404, "not_found", f"The file of attachment #{a.id} is missing from storage.") from None

    async def rest() -> AsyncIterator[bytes]:
        yield first
        async for chunk in chunks:
            yield chunk

    return rest()


@router.get("/{attachment_id}", response_model=AttachmentInfoOut, summary="Info about an attached file")
async def get_attachment(attachment_id: int, me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    a = await _get(db, me, attachment_id)
    return {**attachment_out(a), "chat_id": a.chat_id, "message_id": a.message_id, "on_chat": a.on_chat}


@router.get("/{attachment_id}/file", summary="Download an attached file")
async def download_attachment(
    attachment_id: int,
    download: bool = Query(False, description="Always send as a download, even for images, audio and video"),
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The file's bytes. Needs the same Bearer token as every call; only people who can see the chat get it."""
    a = await _get(db, me, attachment_id)
    stream = await _open(a)
    disposition = "inline" if kind(a.content_type) != "file" and not download else "attachment"
    headers = {
        "Content-Length": str(a.size),
        "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(a.filename)}",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, max-age=3600",
    }
    return StreamingResponse(stream, media_type=a.content_type, headers=headers)
