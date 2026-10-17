from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import not_found
from app.models import Attachment, Group, User, Work
from app.schemas import WorkCreate, WorkOut, WorkUpdate
from app.security import require_admin
from app.services.attachments import attach, remove
from app.services.serialize import serialize_work
from app.ws import notify_work

router = APIRouter(prefix="/admin/works", tags=["admin: works"])


@router.post("", response_model=WorkOut, status_code=201, summary="Create a new work in a group")
async def create_work(payload: WorkCreate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    if await db.get(Group, payload.group_id) is None:
        raise not_found("Group", payload.group_id)
    work = Work(**payload.model_dump(), created_by=admin.id)
    db.add(work)
    await db.commit()
    data = await serialize_work(db, work, admin)
    await notify_work(db, work, {"type": "work.created", "work": data})
    return data


@router.patch("/{work_id}", response_model=WorkOut, summary="Edit a work or open/close it")
async def update_work(
    work_id: int, payload: WorkUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    work = await db.get(Work, work_id)
    if work is None:
        raise not_found("Work", work_id)
    fields = payload.model_dump(exclude_unset=True, exclude={"attachment_ids", "remove_attachment_ids"})
    for key, value in fields.items():
        if value is not None:
            setattr(work, key, value)
    await attach(db, admin, work, payload.attachment_ids, on_work=True)
    if payload.remove_attachment_ids:
        doomed = await db.scalars(
            select(Attachment).where(
                Attachment.id.in_(payload.remove_attachment_ids),
                Attachment.work_id == work.id,
                Attachment.on_work.is_(True),
            )
        )
        await remove(db, list(doomed))
    await db.commit()
    data = await serialize_work(db, work, admin)
    keys = ("id", "title", "body", "status", "attachments")
    await notify_work(db, work, {"type": "work.updated", "work": {k: data[k] for k in keys}})
    return data
