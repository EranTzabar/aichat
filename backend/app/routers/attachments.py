from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import not_found
from app.models import Attachment, User
from app.permissions import get_accessible_work
from app.schemas import AttachmentInfoOut
from app.security import get_current_user
from app.services.attachments import attachment_out, kind
from app.services.storage import get_storage

router = APIRouter(prefix="/attachments", tags=["attachments"])


async def _get(db: AsyncSession, me: User, attachment_id: int) -> Attachment:
    """The attachment, if I may see its work. Unsent uploads are visible only to their uploader."""
    a = await db.get(Attachment, attachment_id)
    if a is None or (a.message_id is None and not a.on_work and a.uploader_id != me.id):
        raise not_found("Attachment", attachment_id)
    await get_accessible_work(db, me, a.work_id)
    return a


@router.get("/{attachment_id}", response_model=AttachmentInfoOut, summary="Info about an attached file")
async def get_attachment(attachment_id: int, me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    a = await _get(db, me, attachment_id)
    return {**attachment_out(a), "work_id": a.work_id, "message_id": a.message_id, "on_work": a.on_work}


@router.get("/{attachment_id}/file", summary="Download an attached file")
async def download_attachment(
    attachment_id: int,
    download: bool = Query(False, description="Always send as a download, even for images, audio and video"),
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The file's bytes. Needs the same Bearer token as every call; only people who can see the work get it."""
    a = await _get(db, me, attachment_id)
    stream = get_storage().stream(a.storage_key)
    disposition = "inline" if kind(a.content_type) != "file" and not download else "attachment"
    headers = {
        "Content-Length": str(a.size),
        "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(a.filename)}",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, max-age=3600",
    }
    return StreamingResponse(stream, media_type=a.content_type, headers=headers)
