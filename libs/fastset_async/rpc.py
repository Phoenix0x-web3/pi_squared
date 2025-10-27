from __future__ import annotations

from typing import Any

from curl_cffi import requests


class BaseAsyncSession(requests.AsyncSession):
    def __init__(self, proxy: str | None = None, **session_kwargs):
        headers = session_kwargs.pop("headers", {})
        default_headers = {"Content-Type": "application/json", "Accept": "application/json"}
        headers = {**default_headers, **headers}
        init_kwargs = {"headers": headers, **session_kwargs}
        if proxy:
            init_kwargs["proxies"] = {"http": proxy, "https": proxy}
        super().__init__(**init_kwargs)

    @property
    def user_agent(self) -> str:
        return self.headers.get("user-agent", "")


class RPC:
    def __init__(self, *, proxy: str | None = None, timeout: int = 15, base_headers: dict | None = None):
        self.async_session: BaseAsyncSession | None = None
        self.proxy = proxy
        self.timeout = timeout
        self.base_headers = base_headers or {"Content-Type": "application/json", "Accept": "application/json"}

    async def _ensure_session(self):
        if self.async_session is None:
            self.async_session = BaseAsyncSession(proxy=self.proxy, headers=self.base_headers)

    async def _close_session(self):
        if self.async_session:
            await self.async_session.close()
            self.async_session = None

    async def get(self, url: str, headers: dict | None = None, **kwargs) -> Any:
        await self._ensure_session()
        try:
            hdrs = {**self.base_headers, **(headers or {})}
            return await self.async_session.get(url, headers=hdrs, timeout=self.timeout, **kwargs)
        finally:
            await self._close_session()

    async def post(self, url: str, headers: dict | None = None, **kwargs) -> Any:
        await self._ensure_session()
        try:
            hdrs = {**self.base_headers, **(headers or {})}
            return await self.async_session.post(url, headers=hdrs, timeout=self.timeout, **kwargs)
        finally:
            await self._close_session()

    async def put(self, url: str, headers: dict | None = None, **kwargs) -> Any:
        await self._ensure_session()
        try:
            hdrs = {**self.base_headers, **(headers or {})}
            return await self.async_session.put(url, headers=hdrs, timeout=self.timeout, **kwargs)
        finally:
            await self._close_session()

    async def delete(self, url: str, headers: dict | None = None, **kwargs) -> Any:
        await self._ensure_session()
        try:
            hdrs = {**self.base_headers, **(headers or {})}
            return await self.async_session.delete(url, headers=hdrs, timeout=self.timeout, **kwargs)
        finally:
            await self._close_session()
