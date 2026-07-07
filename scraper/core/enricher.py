from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

from scraper.core.antibot.middleware import RequestMiddleware

logger = logging.getLogger(__name__)


class DetailParser(ABC):
    """Turns a detail page's HTML into extra fields (Strategy). Site-specific,
    pure and synchronous; must never raise — return {} on parse failure."""

    @abstractmethod
    def parse(self, html: str) -> dict[str, str]: ...


class Enricher(ABC):
    """Turns a listing *partial* into extra fields (Strategy). Injected, so the
    *how* (detail page? API? nothing?) is swappable without touching discovery."""

    @abstractmethod
    async def enrich(self, partial: dict[str, str]) -> dict[str, str]: ...


class NullEnricher(Enricher):
    """No-op enrichment (``--skip-enrich``): keep the best-effort listing data."""

    async def enrich(self, partial: dict[str, str]) -> dict[str, str]:
        return {}


class DetailPageEnricher(Enricher):
    """Fetch a detail page and parse it via the injected site-specific DetailParser.

    The CPU-bound parse is offloaded to the executor so concurrent enrichments
    don't queue behind each other's parsing.
    """

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
