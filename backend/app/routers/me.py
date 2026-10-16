from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import ApiError, not_found
from app.models import Group, Message, User, UserGroup, Work
from app.permissions import user_group_ids
from app.schemas import GroupRef, MeOut, MentionOut, PersonOut, UserRef
from app.security import get_current_user
from app.services.avatars import avatar_response, save_avatar
from app.services.serialize import serialize_messages
from app.ws import manager

router = APIRouter(tags=["me & people"])


async def groups_of(db: AsyncSession, user_id: int) -> list[dict]:
    rows = await db.execute(
        select(Group.id, Group.name)
        .join(UserGroup, UserGroup.group_id == Group.id)
        .where(UserGroup.user_id == user_id)
        .order_by(Group.name)
    )
    return [{"id": gid, "name": name} for gid, name in rows]


async def me_out(db: AsyncSession, user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "bio": user.bio,
        "is_admin": user.is_admin,
        "groups": await groups_of(db, user.id),
    }


def person(u: User) -> dict:
    return {"id": u.id, "username": u.username, "display_name": u.display_name, "online": manager.is_online(u.id)}


@router.get("/me", response_model=MeOut, summary="My profile and groups")
async def get_me(me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await me_out(db, me)


@router.get("/me/groups", response_model=list[GroupRef], summary="Groups I belong to")
async def my_groups(me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await groups_of(db, me.id)


@router.get("/me/mentions", response_model=list[MentionOut], summary="Replies addressed to me (newest first)")
async def my_mentions(
    since_id: int | None = Query(None, description="Only mentions with id > since_id"),
    before_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Message, Work.title)
        .join(Work, Work.id == Message.work_id)
        .where(Message.reply_to_user_id == me.id, Message.author_id != me.id)
        .order_by(Message.id.desc())
        .limit(limit)
    )
    if not me.is_admin:
        q = q.where(Work.group_id.in_(select(UserGroup.group_id).where(UserGroup.user_id == me.id)))
    if since_id is not None:
        q = q.where(Message.id > since_id)
    if before_id is not None:
        q = q.where(Message.id < before_id)
    rows = (await db.execute(q)).all()
    data = await serialize_messages(db, [m for m, _ in rows], me)
    for item, (_, title) in zip(data, rows):
        item["work_title"] = title
    return data


@router.post("/me/avatar", status_code=204, summary="Upload my avatar (website)")
async def upload_my_avatar(
    file: UploadFile = File(...), me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await save_avatar(db, me, file)


@router.get("/people", response_model=list[PersonOut], summary="People who share a group with me")
async def people(me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    q = select(User).where(User.is_active).order_by(User.display_name)
    if not me.is_admin:
        shared = select(UserGroup.user_id).where(
            UserGroup.group_id.in_(select(UserGroup.group_id).where(UserGroup.user_id == me.id))
        )
        q = q.where(or_(User.id.in_(shared), User.is_admin, User.id == me.id))
    return [person(u) for u in await db.scalars(q)]


@router.get("/groups/{group_id}/members", response_model=list[PersonOut], summary="Members of one of my groups")
async def group_members(group_id: int, me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    group = await db.get(Group, group_id)
    if group is None:
        raise not_found("Group", group_id)
    if not me.is_admin and group_id not in await user_group_ids(db, me):
        raise ApiError(403, "not_group_member", f"You are not a member of group '{group.name}'.")
    rows = await db.scalars(
        select(User)
        .join(UserGroup, UserGroup.user_id == User.id)
        .where(UserGroup.group_id == group_id, User.is_active)
        .order_by(User.display_name)
    )
    return [person(u) for u in rows]


@router.get("/users/{user_id}/avatar", summary="User icon image (public, for <img> tags)")
async def user_avatar(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if user is None:
        raise not_found("User", user_id)
    return avatar_response(user)


@router.get("/users/{user_id}", response_model=UserRef, summary="Basic info about a user")
async def get_user(user_id: int, _: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if user is None:
        raise not_found("User", user_id)
    return user
