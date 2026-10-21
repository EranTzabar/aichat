from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import ApiError, not_found
from app.models import Group, User, UserGroup, Chat
from app.schemas import GroupDetailOut, GroupIn, GroupOut, GroupUpdate
from app.security import require_admin
from app.services.audit import audit, changes
from app.services.serialize import user_ref
from app.ws import manager

router = APIRouter(prefix="/admin/groups", tags=["admin: groups"], dependencies=[Depends(require_admin)])


def _counts():
    members = select(func.count()).where(UserGroup.group_id == Group.id).correlate(Group).scalar_subquery()
    chats = select(func.count()).where(Chat.group_id == Group.id).correlate(Group).scalar_subquery()
    return members, chats


def _group_out(g: Group, members: int, chats: int) -> dict:
    return {
        "id": g.id,
        "name": g.name,
        "description": g.description,
        "created_at": g.created_at,
        "member_count": members,
        "chat_count": chats,
    }


async def _get_group(db: AsyncSession, group_id: int) -> Group:
    group = await db.get(Group, group_id)
    if group is None:
        raise not_found("Group", group_id)
    return group


async def _commit_unique(db: AsyncSession, name: str) -> None:
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ApiError(409, "group_name_taken", f"A group named '{name}' already exists.")


@router.get("", response_model=list[GroupOut])
async def list_groups(db: AsyncSession = Depends(get_db)):
    members, chats = _counts()
    rows = await db.execute(select(Group, members, chats).order_by(Group.name))
    return [_group_out(g, m, w) for g, m, w in rows]


@router.post("", response_model=GroupOut, status_code=201)
async def create_group(payload: GroupIn, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    group = Group(name=payload.name, description=payload.description)
    db.add(group)
    await _commit_unique(db, payload.name)
    audit(db, admin, "group.create", target=("group", group.id), group_id=group.id, details={"name": group.name})
    await db.commit()
    return _group_out(group, 0, 0)


@router.get("/{group_id}", response_model=GroupDetailOut)
async def get_group(group_id: int, db: AsyncSession = Depends(get_db)):
    group = await _get_group(db, group_id)
    members, chats = _counts()
    _, m, w = (await db.execute(select(Group, members, chats).where(Group.id == group_id))).one()
    users = await db.scalars(
        select(User).join(UserGroup, UserGroup.user_id == User.id).where(UserGroup.group_id == group_id).order_by(User.display_name)
    )
    return {**_group_out(group, m, w), "members": [user_ref(u) for u in users]}


@router.patch("/{group_id}", response_model=GroupDetailOut)
async def update_group(
    group_id: int, payload: GroupUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)
):
    group = await _get_group(db, group_id)
    data = payload.model_dump(exclude_unset=True)
    if details := changes(group, data):
        audit(db, admin, "group.update", target=("group", group.id), group_id=group.id, details=details)
    for key, value in data.items():
        if value is not None:
            setattr(group, key, value)
    await _commit_unique(db, group.name)
    return await get_group(group_id, db)


@router.delete("/{group_id}", status_code=204, summary="Delete the group with ALL its chats, messages and likes")
async def delete_group(group_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    group = await _get_group(db, group_id)
    member_ids = set((await db.scalars(select(UserGroup.user_id).where(UserGroup.group_id == group_id))).all())
    name = group.name
    chats = await db.scalar(select(func.count()).where(Chat.group_id == group_id))
    details = {"name": name, "chats": chats}
    audit(db, admin, "group.delete", target=("group", group_id), group_id=group_id, details=details)
    await db.delete(group)
    await db.commit()
    await manager.send_all({"type": "group.deleted", "group_id": group_id, "group_name": name})
    await manager.send_to(member_ids, {"type": "access.revoked", "group_id": group_id, "group_name": name})
