from __future__ import annotations

from abc import ABC, abstractmethod

from scraper.infrastructure.http.response import FetchResponse


class Fetcher(ABC):
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
