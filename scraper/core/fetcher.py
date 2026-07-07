from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx
from curl_cffi.requests import AsyncSession


@dataclass
class FetchResponse:
    status_code: int
    text: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)


class Fetcher(ABC):
    """HTTP transport (Strategy) — swap httpx ↔ curl_cffi without touching scrapers.

    ``impersonate`` names a browser TLS fingerprint (e.g. "chrome142"); fetchers
    that cannot forge TLS ignore it. It comes from the active BrowserProfile so
    the TLS handshake agrees with the User-Agent.
    """

    @abstractmethod
    async def fetch(
        self,
        url: str,
        *,
        proxy: str | None = None,
        headers: dict[str, str] | None = None,
        impersonate: str | None = None,
    ) -> FetchResponse: ...

    @abstractmethod
    async def close(self) -> None: ...

    async def __aenter__(self) -> Fetcher:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()


class HttpxFetcher(Fetcher):
    """httpx-backed fetcher (HTTP/2). One client per proxy so connections reuse."""

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
        impersonate: str | None = None,  # httpx cannot forge TLS — accepted but unused
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


class CurlCffiFetcher(Fetcher):
    """curl_cffi fetcher that forges a real browser's TLS/JA3 fingerprint.

    httpx presents an unmistakably "Python" ClientHello no matter the headers;
    curl_cffi matches the JA3/HTTP2 fingerprint to the User-Agent.
    """

    def __init__(self, timeout: float = 30.0, default_impersonate: str = "chrome") -> None:
        self._default_impersonate = default_impersonate
        # Typed Any: curl_cffi's strict stubs otherwise reject the profile-supplied
        # impersonate string (a plain str vs their Literal of browser names).
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
