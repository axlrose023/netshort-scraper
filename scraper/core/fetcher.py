from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

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
    - HttpxFetcher    — async HTTP/1.1 + HTTP/2 (fast, but a Python TLS fingerprint)
    - CurlCffiFetcher — curl_cffi with browser TLS/JA3 impersonation (stealth)
    - PlaywrightFetcher — headless browser for JS-heavy targets
    - MockFetcher    — deterministic fixture responses for tests

    ``impersonate`` names a browser TLS fingerprint (e.g. "chrome142"); fetchers
    that cannot forge TLS ignore it. It is supplied by the active BrowserProfile
    so the TLS handshake agrees with the User-Agent.
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
    """Async fetcher backed by curl_cffi with browser TLS/JA3 impersonation.

    Unlike httpx (whose TLS handshake is unmistakably "Python"), curl_cffi forges
    the exact ClientHello of a real browser, so the JA3/HTTP2 fingerprint matches
    the User-Agent. ``impersonate`` per request comes from the active
    BrowserProfile; ``default_impersonate`` is the fallback when none is given.
    """

    def __init__(self, timeout: float = 30.0, default_impersonate: str = "chrome") -> None:
        try:
            from curl_cffi.requests import AsyncSession
        except ImportError as exc:  # pragma: no cover - depends on optional install
            raise RuntimeError(
                "curl_cffi is not installed — run `uv add curl_cffi` to use the stealth fetcher"
            ) from exc
        self._timeout = timeout
        self._default_impersonate = default_impersonate
        # curl_cffi ships strict typing stubs; treat the session as Any so the
        # profile-supplied impersonate string is not fought by the Literal type.
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
