from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from scraper.core.antibot.middleware import RequestMiddleware
from scraper.core.concurrency import map_bounded
from scraper.core.enricher import Enricher, NullEnricher
from scraper.core.pipeline import SeriesItem

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Template method: a site implements only ``discover()``; ``scrape()`` runs
    the fixed skeleton discover → enrich (injected Strategy) → build SeriesItem.

    Item construction lives solely in ``SeriesItem.from_partial`` — subclasses
    never assemble items by hand. The ``middleware`` (proxies/retries/rate limit)
    and ``enricher`` collaborators are injected; override ``scrape()`` only for a
    fundamentally different fetch strategy (GraphQL, infinite scroll).
    """

    # Fan-out window for the enrichment phase — how many enrich coroutines are
    # materialised at once (bounds memory). Per-request throttling is the
    # middleware semaphore, a separate cap. Subclasses may tune this per site.
    _ENRICH_LIMIT: int = 50

    def __init__(
        self,
        middleware: RequestMiddleware,
        enricher: Enricher | None = None,
        max_pages: int | None = None,
    ) -> None:
        self.middleware = middleware
        self.enricher = enricher or NullEnricher()
        self.max_pages = max_pages

    @abstractmethod
    def discover(self) -> AsyncIterator[dict[str, str]]:
        """Yield one partial-item dict per unique series (at minimum ``id``,
        ``title``, ``series_url``; other fields are best-effort, overridable by
        the ``Enricher``)."""
        ...

    async def scrape(self) -> AsyncIterator[SeriesItem]:
        partials = [partial async for partial in self.discover()]
        logger.info("Discovery complete — %d series queued for enrichment", len(partials))

        done = 0
        async for item in map_bounded(partials, self._enrich, limit=self._ENRICH_LIMIT):
            yield item
            done += 1
            if done % 500 == 0 or done == len(partials):
                logger.info("Enrichment progress: %d / %d", done, len(partials))

    async def _enrich(self, partial: dict[str, str]) -> SeriesItem:
        try:
            detail = await self.enricher.enrich(partial)
        except Exception as exc:
            logger.warning("Enrich failed for %s: %s", partial.get("series_url"), exc)
            detail = {}
        return SeriesItem.from_partial(partial, detail)
