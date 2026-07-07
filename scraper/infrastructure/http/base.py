from __future__ import annotations

from typing import Protocol, Self

from scraper.schemas.http import FetchResponse


class Fetcher(Protocol):
    async def fetch(
        self,
        url: str,
        *,
        proxy: str | None = None,
        headers: dict[str, str] | None = None,
        impersonate: str | None = None,
    ) -> FetchResponse: ...

    async def close(self) -> None: ...

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
