from __future__ import annotations

from scraper.services.enrichment.base import Enricher


class NullEnricher(Enricher):
    async def enrich(self, partial: dict[str, str]) -> dict[str, str]:
        return {}
