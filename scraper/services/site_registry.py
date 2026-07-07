from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from scraper.contracts.enrichment import DetailParser, Enricher
from scraper.infrastructure.antibot.policies import BanPolicy
from scraper.infrastructure.antibot.request_middleware import RequestMiddleware
from scraper.sites.base import BaseScraper
from scraper.sites.netshort import NetshortBanPolicy, NetshortDetailParser, NetshortScraper


class ScraperFactory(Protocol):
    def __call__(
        self,
        *,
        middleware: RequestMiddleware,
        enricher: Enricher,
        config: dict[str, object] | None = None,
        max_pages: int | None = None,
    ) -> BaseScraper: ...


@dataclass(frozen=True)
class SiteDefinition:
    scraper_factory: ScraperFactory
    ban_policy_factory: Callable[[], BanPolicy] | None = None
    detail_parser_factory: Callable[[], DetailParser] | None = None


SITE_REGISTRY: dict[str, SiteDefinition] = {
    "netshort": SiteDefinition(
        scraper_factory=NetshortScraper,
        ban_policy_factory=NetshortBanPolicy,
        detail_parser_factory=NetshortDetailParser,
    ),
}
