from __future__ import annotations

from typing import Any

from curl_cffi.requests import AsyncSession

from scraper.infrastructure.http.base import Fetcher
from scraper.infrastructure.http.response import FetchResponse


class CurlCffiFetcher(Fetcher):
    def __init__(self, timeout: float = 30.0, default_impersonate: str = "chrome") -> None:
        self._default_impersonate = default_impersonate
        self._session: Any = AsyncSession(timeout=timeout)

    async def fetch(
        self,
        url: str,
        *,
        proxy: str | None = None,
        headers: dict[str, str] | None = None,
        impersonate: str | None = None,
    ) -> FetchResponse:
        proxies = {"http": proxy, "https": proxy} if proxy else None
        response = await self._session.get(
            url,
            headers=headers or {},
            impersonate=impersonate or self._default_impersonate,
            proxies=proxies,
        )
        return FetchResponse(
            status_code=response.status_code,
            text=response.text,
            url=str(response.url),
            headers=dict(response.headers),
        )

    async def close(self) -> None:
        await self._session.close()
