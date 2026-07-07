from __future__ import annotations

from scraper.infrastructure.antibot.profile_pool import ProfilePool
from scraper.infrastructure.antibot.proxy_pool import ProxyPool
from scraper.infrastructure.antibot.request_middleware import RequestMiddleware
from scraper.schemas.run import ScraperRunConfig
from scraper.services.fetcher_factory import FetcherFactory
from scraper.services.site_registry import SiteDefinition
from scraper.services.value_reader import ValueReader


class RequestMiddlewareFactory:
    def __init__(
        self,
        fetcher_factory: FetcherFactory | None = None,
        values: ValueReader | None = None,
    ) -> None:
        self._fetcher_factory = fetcher_factory or FetcherFactory()
        self._values = values or ValueReader()

    def build(
        self,
        options: ScraperRunConfig,
        site: SiteDefinition,
        rate_limit: dict[str, object],
        proxy_pool: ProxyPool,
    ) -> RequestMiddleware:
        return RequestMiddleware(
            fetcher=self._fetcher_factory.build(options.fetcher),
            proxy_pool=proxy_pool,
            ban_policy=site.ban_policy_factory() if site.ban_policy_factory else None,
            profile_pool=ProfilePool(),
            concurrency=self._values.integer(
                rate_limit,
                "concurrency",
                5,
                options.concurrency,
            ),
            delay_min=self._values.number(rate_limit, "delay_min", 0.5),
            delay_max=self._values.number(rate_limit, "delay_max", 1.5),
            max_retries=self._values.integer(rate_limit, "max_retries", 3),
            backoff_base=self._values.number(rate_limit, "backoff_base", 2.0),
        )
