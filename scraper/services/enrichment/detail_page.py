from __future__ import annotations

import asyncio

from scraper.contracts.enrichment import DetailParser
from scraper.infrastructure.antibot.request_middleware import RequestMiddleware


class DetailPageEnricher:
    def __init__(
        self,
        middleware: RequestMiddleware,
        parser: DetailParser,
        url_key: str = "series_url",
    ) -> None:
        self._middleware = middleware
        self._parser = parser
        self._url_key = url_key

    async def enrich(self, partial: dict[str, str]) -> dict[str, str]:
        url = partial.get(self._url_key, "")
        if not url:
            return {}
        response = await self._middleware.fetch(url)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._parser.parse, response.text)
