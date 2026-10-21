from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import ApiError, not_found
from app.models import Group, User, UserGroup
from app.routers.me import groups_of
from app.schemas import AdminUserOut, ApiTokenOut, UserCreate, UserGroupsIn, UserUpdate
from app.security import create_api_token, hash_password, require_admin
from app.services.audit import audit, changes
from app.services.avatars import save_avatar
from app.ws import manager

router = APIRouter(prefix="/admin/users", tags=["admin: users"], dependencies=[Depends(require_admin)])


async def admin_user_out(db: AsyncSession, u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "display_name": u.display_name,
        "bio": u.bio,
        "is_admin": u.is_admin,
        "is_active": u.is_active,
        "api_enabled": u.api_enabled,
        "created_at": u.created_at,
        "last_login_at": u.last_login_at,
        "last_api_use_at": u.last_api_use_at,
        "groups": await groups_of(db, u.id),
    }


async def _get_user(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise not_found("User", user_id)
    return user


@router.get("", response_model=list[AdminUserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    users = (await db.scalars(select(User).order_by(User.id))).all()
    return [await admin_user_out(db, u) for u in users]


@router.post("", response_model=AdminUserOut, status_code=201)
async def create_user(
    payload: UserCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)
):
    if await db.scalar(select(User.id).where(User.username == payload.username)):
        raise ApiError(409, "username_taken", f"Username '{payload.username}' is already taken.")
    user = User(
        username=payload.username,
        display_name=payload.display_name,
        bio=payload.bio,
        password_hash=hash_password(payload.password),
        is_admin=payload.is_admin,
    )
    db.add(user)
    await db.flush()
    audit(db, admin, "user.create", target=("user", user.id), details={"username": user.username, "is_admin": user.is_admin})
    await db.commit()
    return await admin_user_out(db, user)


@router.get("/{user_id}", response_model=AdminUserOut)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    return await admin_user_out(db, await _get_user(db, user_id))


@router.patch("/{user_id}", response_model=AdminUserOut)
async def update_user(
    user_id: int, payload: UserUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)
):
    user = await _get_user(db, user_id)
    data = payload.model_dump(exclude_unset=True)
    if user.id == admin.id and data.get("is_active") is False:
        raise ApiError(422, "validation_error", "You can't disable your own admin account.")
    password = data.pop("password", None)
    details = changes(user, data)
    if password:
        user.password_hash = hash_password(password)
        details["password"] = "changed"
    for key, value in data.items():
        if value is not None:
            setattr(user, key, value)
    if details:
        audit(db, admin, "user.update", target=("user", user.id), details=details)
    await db.commit()
    return await admin_user_out(db, user)


@router.put("/{user_id}/groups", response_model=AdminUserOut, summary="Set the user's groups (existing groups only)")
async def set_user_groups(
    user_id: int, payload: UserGroupsIn, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)
):
    user = await _get_user(db, user_id)
    wanted = set(payload.group_ids)
    existing = set((await db.scalars(select(Group.id).where(Group.id.in_(wanted)))).all())
    if missing := wanted - existing:
        raise ApiError(
            422, "validation_error", f"Group(s) {sorted(missing)} do not exist. Create the group first."
        )
    current = set((await db.scalars(select(UserGroup.group_id).where(UserGroup.user_id == user.id))).all())
    removed, added = current - wanted, wanted - current
    if removed:
        await db.execute(delete(UserGroup).where(UserGroup.user_id == user.id, UserGroup.group_id.in_(removed)))
    db.add_all(UserGroup(user_id=user.id, group_id=g) for g in added)
    if added or removed:
        details = {"added": sorted(added), "removed": sorted(removed)}
        audit(db, admin, "user.groups", target=("user", user.id), details=details)
    await db.commit()

    names = dict((await db.execute(select(Group.id, Group.name).where(Group.id.in_(removed | added)))).all())
    for gid in removed:
        await manager.send_to(
            {user.id}, {"type": "access.revoked", "group_id": gid, "group_name": names.get(gid, str(gid))}
        )
    if added:
        await manager.send_to({user.id}, {"type": "groups.changed"})
    return await admin_user_out(db, user)


@router.get("/{user_id}/api-token", response_model=ApiTokenOut, summary="Get the user's current API token")
async def get_api_token(user_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    user = await _get_user(db, user_id)
    audit(db, admin, "user.token_view", target=("user", user.id))
    await db.commit()
    return _token_out(user)


def _token_out(user: User) -> dict:
    return {
        "user_id": user.id,
        "token": create_api_token(user),
        "token_version": user.token_version,
        "api_enabled": user.api_enabled,
    }


@router.post("/{user_id}/api-token/regenerate", response_model=ApiTokenOut, summary="New API token; old one stops working")
async def regenerate_api_token(
    user_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)
):
    user = await _get_user(db, user_id)
    user.token_version += 1
    audit(db, admin, "user.token_regenerate", target=("user", user.id), details={"token_version": user.token_version})
    await db.commit()
    return _token_out(user)


@router.post("/{user_id}/avatar", status_code=204)
async def upload_avatar(
    user_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)
):
    user = await _get_user(db, user_id)
    await save_avatar(db, user, file)
    audit(db, admin, "user.avatar", target=("user", user.id))
    await db.commit()
