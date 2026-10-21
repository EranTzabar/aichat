"""Thin async client for the AIChat REST API (/api/v1). The MCP tools only talk to AIChat through this."""
import re
from pathlib import Path
from typing import Any

import httpx

DEFAULT_API_URL = "http://localhost:8002/api/v1"

TAG_RE = re.compile(r"<@(\d+)>")


def readable_tags(data: Any) -> Any:
    """Website tags are stored as `<@user id>`; AIs read and write them as `@username` (from each `mentions` list)."""
    if isinstance(data, list):
        return [readable_tags(x) for x in data]
    if not isinstance(data, dict):
        return data
    out = {k: readable_tags(v) for k, v in data.items()}
    if isinstance(out.get("body"), str) and "mentions" in out:
        names = {u["id"]: u["username"] for u in out["mentions"]}
        out["body"] = TAG_RE.sub(lambda m: f"@{names.get(int(m[1]), 'unknown')}", out["body"])
    return out


class AIChatError(Exception):
    """An error answered by the API ({"error": {"code", "message"}}) or a connection problem."""

    def __init__(self, code: str, message: str, status: int = 0):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


class AIChatClient:
    def __init__(self, base_url: str, token: str | None, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.transport = transport

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise AIChatError(
                "not_authenticated",
                "No AIChat API key. Ask your user for your key (the admin copies it from "
                "Admin > Users > API token) and call connect(api_key).",
            )
        return {"Authorization": f"Bearer {self.token}"}

    def _http(self) -> httpx.AsyncClient:
        # Long-poll requests may be held open up to 55s; uploads and downloads may take longer.
        return httpx.AsyncClient(transport=self.transport, timeout=httpx.Timeout(300.0, connect=10.0))

    def _network_error(self, e: Exception) -> AIChatError:
        return AIChatError("network_error", f"Can't reach the AIChat API at {self.base_url}: {e}")

    @staticmethod
    def _raise_for(res: httpx.Response, data: Any) -> None:
        if res.status_code >= 400:
            err = (data or {}).get("error", {}) if isinstance(data, dict) else {}
            raise AIChatError(
                err.get("code", "http_error"), err.get("message", f"Request failed ({res.status_code})"), res.status_code
            )

    async def request(
        self, method: str, path: str, *, params: dict | None = None, json: Any = None, files: Any = None
    ) -> Any:
        headers = self._headers()
        params = {k: v for k, v in (params or {}).items() if v is not None}
        try:
            async with self._http() as http:
                res = await http.request(
                    method, self.base_url + path, params=params, json=json, files=files, headers=headers
                )
        except httpx.HTTPError as e:
            raise self._network_error(e) from e
        if res.status_code == 204:
            return None
        try:
            data = res.json()
        except ValueError:
            data = None
        self._raise_for(res, data)
        return readable_tags(data)

    async def upload(self, path: str, filename: str, content: Any, content_type: str) -> Any:
        """POST a file as multipart `file`; `content` is bytes or an open binary file."""
        return await self.request("POST", path, files={"file": (filename, content, content_type)})

    async def download(self, path: str, max_bytes: int) -> tuple[bytes, str] | None:
        """The file's bytes and content type, or None when it is bigger than `max_bytes`."""
        headers = self._headers()
        try:
            async with self._http() as http, http.stream("GET", self.base_url + path, headers=headers) as res:
                if res.status_code >= 400:
                    await res.aread()
                    self._raise_for(res, _json(res))
                if int(res.headers.get("content-length") or 0) > max_bytes:
                    return None
                data = await res.aread()
                return data, res.headers.get("content-type", "application/octet-stream")
        except httpx.HTTPError as e:
            raise self._network_error(e) from e

    async def save(self, path: str, dest: Path) -> int:
        """Stream the file to `dest`; returns the number of bytes written."""
        headers = self._headers()
        written = 0
        try:
            async with self._http() as http, http.stream("GET", self.base_url + path, headers=headers) as res:
                if res.status_code >= 400:
                    await res.aread()
                    self._raise_for(res, _json(res))
                with dest.open("wb") as out:
                    async for chunk in res.aiter_bytes(1024 * 1024):
                        out.write(chunk)
                        written += len(chunk)
        except httpx.HTTPError as e:
            dest.unlink(missing_ok=True)
            raise self._network_error(e) from e
        return written

    async def get(self, path: str, **params) -> Any:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, json: Any = None) -> Any:
        return await self.request("POST", path, json=json)

    async def delete(self, path: str) -> Any:
        return await self.request("DELETE", path)


def _json(res: httpx.Response) -> Any:
    try:
        return res.json()
    except ValueError:
        return None
