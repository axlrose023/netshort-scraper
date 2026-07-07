from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from dataclasses import replace

from scraper.contracts.enrichment import Enricher
from scraper.infrastructure.antibot.proxy_pool import ProxyPool
from scraper.infrastructure.antibot.request_middleware import RequestMiddleware
from scraper.pipelines.csv_pipeline import Pipeline
from scraper.schemas.run import ScrapeResult, ScraperRunConfig
from scraper.services.config_loader import ConfigLoader
from scraper.services.enrichment import DetailPageEnricher, NullEnricher
from scraper.services.middleware_factory import RequestMiddlewareFactory
from scraper.services.site_registry import SITE_REGISTRY, SiteDefinition

logger = logging.getLogger(__name__)


class ScraperApplication:
    def __init__(
        self,
        sites: Mapping[str, SiteDefinition] | None = None,
        config_loader: ConfigLoader | None = None,
        middleware_factory: RequestMiddlewareFactory | None = None,
    ) -> None:
        self._sites = dict(sites or SITE_REGISTRY)
        self._config_loader = config_loader or ConfigLoader()
        self._middleware_factory = middleware_factory or RequestMiddlewareFactory()

    @property
    def sources(self) -> tuple[str, ...]:
        return tuple(self._sites)

    async def run(self, options: ScraperRunConfig) -> ScrapeResult:
        site = self._site(options.source)
        config = self._config_loader.load(options.source, options.config_path)
        rate_limit = self._config_loader.rate_limit(config)
        proxy_pool = ProxyPool()
        middleware = self._middleware_factory.build(options, site, rate_limit, proxy_pool)
        enricher = self._enricher(site, middleware, options.skip_enrich)
        scraper = site.scraper_factory(
            middleware=middleware,
            enricher=enricher,
            config=config,
            max_pages=options.max_pages,
        )
        self._log_start(options, proxy_pool)
        started = time.monotonic()

        try:
            with Pipeline(options.output) as pipeline:
                async for item in scraper.scrape():
                    pipeline.process(item)
                    if pipeline.stats.exported % 100 == 0 and pipeline.stats.exported:
                        elapsed = time.monotonic() - started
                        logger.info(
                            "Progress: %d exported, %d dropped, %.0fs elapsed",
                            pipeline.stats.exported,
                            pipeline.stats.dropped,
                            elapsed,
                        )
        finally:
            await middleware.close()

        elapsed = time.monotonic() - started
        return ScrapeResult(
            output_path=options.output,
            elapsed_seconds=elapsed,
            pipeline_stats=replace(pipeline.stats),
            request_stats=replace(middleware.stats),
        )

    def _site(self, source: str) -> SiteDefinition:
        try:
            return self._sites[source]
        except KeyError as exc:
            available = ", ".join(self.sources)
            raise ValueError(f"Unknown source {source!r}. Available sources: {available}") from exc

    def _enricher(
        self,
        site: SiteDefinition,
        middleware: RequestMiddleware,
        skip_enrich: bool,
    ) -> Enricher:
        if skip_enrich or site.detail_parser_factory is None:
            return NullEnricher()
        return DetailPageEnricher(middleware, site.detail_parser_factory())

    def _log_start(self, options: ScraperRunConfig, proxy_pool: ProxyPool) -> None:
        logger.info("Starting %s -> %s", options.source, options.output)
        logger.info(
            "Fetcher: %s%s",
            options.fetcher,
            " (browser TLS impersonation)"
            if options.fetcher == "curl"
            else " (Python TLS fingerprint)",
        )
        if proxy_pool.has_proxies():
            logger.info("Proxy pool: %d proxies configured", proxy_pool.available_count())
        else:
            logger.info("No proxies configured - using direct requests")
