from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from scraper.contracts.enrichment import Enricher
from scraper.infrastructure.antibot.request_middleware import RequestMiddleware
from scraper.schemas.series import SeriesItem
from scraper.utils.concurrency import map_bounded

logger = logging.getLogger(__name__)


class BaseScraper:
    _ENRICH_LIMIT: int = 50

    def __init__(
        self,
        middleware: RequestMiddleware,
        enricher: Enricher,
        max_pages: int | None = None,
    ) -> None:
        self.middleware = middleware
        self.enricher = enricher
        self.max_pages = max_pages

    def discover(self) -> AsyncIterator[dict[str, str]]:
        raise NotImplementedError

    async def scrape(self) -> AsyncIterator[SeriesItem]:
        done = 0
        async for item in map_bounded(self.discover(), self._enrich, limit=self._ENRICH_LIMIT):
            yield item
            done += 1
            if done % 500 == 0:
                logger.info("Enrichment progress: %d series", done)
        logger.info("Scrape complete — %d series enriched", done)

    async def _enrich(self, partial: dict[str, str]) -> SeriesItem:
        try:
            detail = await self.enricher.enrich(partial)
        except Exception as exc:
            logger.warning("Enrich failed for %s: %s", partial.get("series_url"), exc)
            detail = {}
        return SeriesItem.from_partial(partial, detail)
