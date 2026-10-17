"""Where attachment bytes live: Cloudflare R2 when configured, otherwise the local disk. Same interface for both."""
import shutil
from collections.abc import AsyncIterator
from functools import cache
from pathlib import Path
from typing import BinaryIO, Protocol

from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.services.avatars import upload_dir

CHUNK = 1024 * 1024


class Storage(Protocol):
    name: str

    async def put(self, key: str, fileobj: BinaryIO, content_type: str) -> None: ...

    def stream(self, key: str) -> AsyncIterator[bytes]: ...

    async def delete(self, key: str) -> None: ...


class DiskStorage:
    name = "disk"

    def _path(self, key: str) -> Path:
        return upload_dir() / key

    async def put(self, key: str, fileobj: BinaryIO, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        def write() -> None:
            with path.open("wb") as out:
                shutil.copyfileobj(fileobj, out, CHUNK)

        await run_in_threadpool(write)

    async def stream(self, key: str) -> AsyncIterator[bytes]:
        f = await run_in_threadpool(self._path(key).open, "rb")
        try:
            while chunk := await run_in_threadpool(f.read, CHUNK):
                yield chunk
        finally:
            f.close()

    async def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class R2Storage:
    name = "r2"

    def __init__(self) -> None:
        import boto3  # only needed when R2 is configured

        self.bucket = settings.r2_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )

    async def put(self, key: str, fileobj: BinaryIO, content_type: str) -> None:
        # upload_fileobj splits big files into a multipart upload by itself.
        await run_in_threadpool(
            self.client.upload_fileobj, fileobj, self.bucket, key, ExtraArgs={"ContentType": content_type}
        )

    async def stream(self, key: str) -> AsyncIterator[bytes]:
        obj = await run_in_threadpool(self.client.get_object, Bucket=self.bucket, Key=key)
        body = obj["Body"]
        try:
            while chunk := await run_in_threadpool(body.read, CHUNK):
                yield chunk
        finally:
            body.close()

    async def delete(self, key: str) -> None:
        await run_in_threadpool(self.client.delete_object, Bucket=self.bucket, Key=key)


@cache
def _storage(kind: str) -> Storage:
    return R2Storage() if kind == "r2" else DiskStorage()


def get_storage() -> Storage:
    return _storage("r2" if settings.r2_enabled else "disk")
