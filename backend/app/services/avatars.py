import html
import uuid
from pathlib import Path

from fastapi import UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import ApiError
from app.models import User

ALLOWED = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp"}
COLORS = ["#2563eb", "#7c3aed", "#db2777", "#ea580c", "#16a34a", "#0891b2", "#ca8a04", "#dc2626"]


def upload_dir() -> Path:
    path = Path(settings.upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def save_avatar(db: AsyncSession, user: User, file: UploadFile) -> None:
    ext = ALLOWED.get(file.content_type or "")
    if ext is None:
        raise ApiError(422, "validation_error", "Avatar must be a PNG, JPEG, GIF or WEBP image.")
    data = await file.read(settings.max_avatar_bytes + 1)
    if len(data) > settings.max_avatar_bytes:
        raise ApiError(422, "validation_error", "Avatar must be at most 2 MB.")
    name = f"{user.id}_{uuid.uuid4().hex}.{ext}"
    (upload_dir() / name).write_bytes(data)
    old = user.avatar_path
    user.avatar_path = name
    await db.commit()
    if old:
        (upload_dir() / old).unlink(missing_ok=True)


def initials_svg(user: User) -> str:
    parts = user.display_name.split()
    letters = "".join(p[0] for p in parts[:2]).upper() or user.username[:1].upper()
    color = COLORS[user.id % len(COLORS)]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        f'<rect width="64" height="64" fill="{color}"/>'
        '<text x="50%" y="50%" dy=".35em" text-anchor="middle" fill="#fff" '
        f'font-family="Arial, sans-serif" font-size="26" font-weight="600">{html.escape(letters)}</text></svg>'
    )


def avatar_response(user: User) -> Response:
    headers = {"Cache-Control": "no-cache"}
    if user.avatar_path:
        path = upload_dir() / user.avatar_path
        if path.exists():
            return FileResponse(path, headers=headers)
    return Response(initials_svg(user), media_type="image/svg+xml", headers=headers)
