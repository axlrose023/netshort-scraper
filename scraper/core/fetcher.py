from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx


@dataclass
class FetchResponse:
    status_code: int
    text: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)


class Fetcher(ABC):
    """Protocol for making HTTP requests.

    Swap implementations without touching any scraper logic:
    - HttpxFetcher  — async HTTP/1.1 + HTTP/2 (default, used here)
    - PlaywrightFetcher — headless browser for JS-heavy targets
    - MockFetcher    — deterministic fixture responses for tests
    """

    @abstractmethod
    async def fetch(
        self,
        url: str,
        *,
        proxy: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> FetchResponse: ...

    @abstractmethod
    async def close(self) -> None: ...

    async def __aenter__(self) -> Fetcher:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()


class HttpxFetcher(Fetcher):
    """Async HTTP fetcher backed by httpx (HTTP/2 enabled).

    One client instance is created per proxy URL so connections are reused.
    Falls back to a no-proxy client when proxy=None.
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout
        self._clients: dict[str | None, httpx.AsyncClient] = {}

    def _make_client(self, proxy: str | None) -> httpx.AsyncClient:
        # httpx 0.28+ uses `proxy` (str | None) instead of the old `proxies` dict
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
    ) -> FetchResponse:
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
