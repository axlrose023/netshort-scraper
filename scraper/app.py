from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Literal, Protocol

import yaml

from scraper.core.antibot.middleware import BanPolicy, RequestMiddleware, ScraperStats
from scraper.core.antibot.profile import ProfilePool
from scraper.core.antibot.proxy_pool import ProxyPool
from scraper.core.enricher import DetailPageEnricher, DetailParser, Enricher, NullEnricher
from scraper.core.fetcher import CurlCffiFetcher, Fetcher, HttpxFetcher
from scraper.core.pipeline import Pipeline, PipelineStats
from scraper.sites.base import BaseScraper
from scraper.sites.netshort import NetshortBanPolicy, NetshortDetailParser, NetshortScraper

logger = logging.getLogger(__name__)

FetcherName = Literal["curl", "httpx"]


class ScraperFactory(Protocol):
    def __call__(
        self,
        *,
        middleware: RequestMiddleware,
        enricher: Enricher | None = None,
        config: dict[str, object] | None = None,
        max_pages: int | None = None,
    ) -> BaseScraper: ...


@dataclass(frozen=True)
class SiteDefinition:
    scraper_factory: ScraperFactory
    ban_policy_factory: Callable[[], BanPolicy] | None = None
    detail_parser_factory: Callable[[], DetailParser] | None = None


@dataclass(frozen=True)
class ScraperRunConfig:
    source: str
    output: str
    config_path: str | None = None
    max_pages: int | None = None
    concurrency: int | None = None
    fetcher: FetcherName = "curl"
    skip_enrich: bool = False


@dataclass(frozen=True)
class ScrapeResult:
    output_path: str
    elapsed_seconds: float
    pipeline_stats: PipelineStats
    request_stats: ScraperStats


SITE_REGISTRY: dict[str, SiteDefinition] = {
    "netshort": SiteDefinition(
        scraper_factory=NetshortScraper,
        ban_policy_factory=NetshortBanPolicy,
        detail_parser_factory=NetshortDetailParser,
    ),
}


class ScraperApplication:
    """Facade that wires a site scraper to transport, anti-bot middleware and output.

    CLI code should pass a ScraperRunConfig to ``run()`` instead of constructing
    low-level collaborators itself. Adding a site is a registry change, not a
    new branch in the CLI.
    """

    def __init__(self, sites: Mapping[str, SiteDefinition] | None = None) -> None:
        self._sites = dict(sites or SITE_REGISTRY)

    @property
    def sources(self) -> tuple[str, ...]:
        return tuple(self._sites)

    async def run(self, options: ScraperRunConfig) -> ScrapeResult:
        site = self._site(options.source)
        cfg = self._load_config(options)
        rate_limit = self._rate_limit(cfg)

        proxy_pool = ProxyPool()
        middleware = RequestMiddleware(
            fetcher=self._build_fetcher(options.fetcher),
            proxy_pool=proxy_pool,
            ban_policy=site.ban_policy_factory() if site.ban_policy_factory else None,
            profile_pool=ProfilePool(),
            concurrency=self._int_option(options.concurrency, rate_limit, "concurrency", 5),
            delay_min=self._float_option(rate_limit, "delay_min", 0.5),
            delay_max=self._float_option(rate_limit, "delay_max", 1.5),
            max_retries=self._int_option(None, rate_limit, "max_retries", 3),
            backoff_base=self._float_option(rate_limit, "backoff_base", 2.0),
        )
        enricher = self._build_enricher(site, middleware, options.skip_enrich)
        scraper = site.scraper_factory(
            middleware=middleware,
            enricher=enricher,
            config=cfg,
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

    def _load_config(self, options: ScraperRunConfig) -> dict[str, object]:
        path = options.config_path or f"scraper/config/{options.source}.yaml"
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)

        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise ValueError(f"Config {path!r} must contain a YAML mapping")
        return {str(key): value for key, value in raw.items()}

    def _rate_limit(self, cfg: dict[str, object]) -> dict[str, object]:
        raw = cfg.get("rate_limit", {})
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise ValueError("Config field 'rate_limit' must be a mapping")
        return {str(key): value for key, value in raw.items()}

    def _build_fetcher(self, name: FetcherName) -> Fetcher:
        if name == "curl":
            return CurlCffiFetcher(timeout=30.0)
        if name == "httpx":
            return HttpxFetcher(timeout=30.0)
        raise ValueError(f"Unknown fetcher {name!r}")

    def _build_enricher(
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

    @staticmethod
    def _int_option(
        override: int | None,
        cfg: dict[str, object],
        key: str,
        default: int,
    ) -> int:
        value = override if override is not None else cfg.get(key, default)
        if isinstance(value, bool):
            raise ValueError(f"Config field {key!r} must be an integer")
        if isinstance(value, int):
            return value
        if not isinstance(value, str):
            raise ValueError(f"Config field {key!r} must be an integer")
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"Config field {key!r} must be an integer") from exc

    @staticmethod
    def _float_option(cfg: dict[str, object], key: str, default: float) -> float:
        value = cfg.get(key, default)
        if isinstance(value, bool):
            raise ValueError(f"Config field {key!r} must be a number")
        if isinstance(value, int | float):
            return float(value)
        if not isinstance(value, str):
            raise ValueError(f"Config field {key!r} must be a number")
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"Config field {key!r} must be a number") from exc
