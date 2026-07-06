from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

from scraper.core.antibot.middleware import RequestMiddleware

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Detail-page parsing — site-specific Strategy
# ---------------------------------------------------------------------------


class DetailParser(ABC):
    """Extracts extra fields from a detail page's HTML (Strategy).

    Pure, synchronous, site-specific. Knows nothing about HTTP, proxies, or
    concurrency — it only turns HTML into a dict of fields to merge into the item.
    Must never raise: return an empty dict on parse failure.
    """

    @abstractmethod
    def parse(self, html: str) -> dict[str, str]: ...


# ---------------------------------------------------------------------------
# Enrichment — how a partial item gets its detail fields (Strategy)
# ---------------------------------------------------------------------------


class Enricher(ABC):
    """Turns a listing *partial* into a dict of additional fields (Strategy).

    Injected into a scraper instead of being hard-coded, so the *how* of
    enrichment (fetch a detail page? call an API? nothing at all?) is swappable
    without touching discovery logic or item construction.
    """

    @abstractmethod
    async def enrich(self, partial: dict[str, str]) -> dict[str, str]: ...


class NullEnricher(Enricher):
    """No-op enrichment — the item keeps whatever the listing phase provided.

    Used for ``--skip-enrich``: discovery already carries a best-effort
    description/metadata, so no detail-page round-trips are made.
    """

    async def enrich(self, partial: dict[str, str]) -> dict[str, str]:
        return {}


class DetailPageEnricher(Enricher):
    """Generic detail-page enrichment: fetch a URL, then parse it off-thread.

    Reusable across sites — the only site-specific piece is the injected
    ``DetailParser``. The CPU-bound parse is offloaded to the default executor
    so concurrent enrichments never queue behind each other's parsing work.
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
