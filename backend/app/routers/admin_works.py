from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import not_found
from app.models import Group, User, Work
from app.schemas import WorkCreate, WorkOut, WorkUpdate
from app.security import require_admin
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
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(work, key, value)
    await db.commit()
    data = await serialize_work(db, work, admin)
    await notify_work(db, work, {"type": "work.updated", "work": {k: data[k] for k in ("id", "title", "body", "status")}})
    return data
