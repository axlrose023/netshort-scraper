from __future__ import annotations

import httpx

from scraper.infrastructure.http.base import Fetcher
from scraper.infrastructure.http.response import FetchResponse


class HttpxFetcher(Fetcher):
    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout
        self._clients: dict[str | None, httpx.AsyncClient] = {}

    def _make_client(self, proxy: str | None) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._timeout,
            http2=True,
            follow_redirects=True,
            proxy=proxy,
        )

    async def _client_for(self, proxy: str | None) -> httpx.AsyncClient:
        if proxy not in self._clients:
            self._clients[proxy] = self._make_client(proxy)
        return self._clients[proxy]

    async def fetch(
        self,
        url: str,
        *,
        proxy: str | None = None,
        headers: dict[str, str] | None = None,
        impersonate: str | None = None,
    ) -> FetchResponse:
        del impersonate
        client = await self._client_for(proxy)
        response = await client.get(url, headers=headers or {})
        return FetchResponse(
            status_code=response.status_code,
            text=response.text,
            url=str(response.url),
            headers=dict(response.headers),
        )

    async def close(self) -> None:
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()
