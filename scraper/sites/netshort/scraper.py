from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from scraper.infrastructure.antibot.request_middleware import RequestMiddleware
from scraper.services.concurrency import map_bounded
from scraper.services.enrichment import Enricher
from scraper.sites.base import BaseScraper
from scraper.sites.netshort.sitemap_parser import NetshortSitemapParser

logger = logging.getLogger(__name__)


class NetshortScraper(BaseScraper):
    def __init__(
        self,
        middleware: RequestMiddleware,
        enricher: Enricher | None = None,
        config: dict[str, object] | None = None,
        max_pages: int | None = None,
        sitemap_parser: NetshortSitemapParser | None = None,
    ) -> None:
        super().__init__(middleware, enricher, max_pages)
        self._cfg: dict[str, object] = config or {}
        self._sitemap_parser = sitemap_parser or NetshortSitemapParser()
        self._sitemap_failures = 0

    async def discover(self) -> AsyncIterator[dict[str, str]]:
        sitemap_urls = await self._get_sub_sitemap_urls()
        if self.max_pages:
            sitemap_urls = sitemap_urls[: self.max_pages]
            logger.info("--max-pages set: limiting to %d sitemap files", len(sitemap_urls))

        logger.info("Fetching %d sub-sitemap files", len(sitemap_urls))
        self._sitemap_failures = 0
        series_meta: dict[str, dict[str, object]] = {}
        series_ep_count: dict[str, int] = {}
        processed = 0

        async for entries in map_bounded(sitemap_urls, self._fetch_and_parse_sitemap, limit=10):
            for entry in entries:
                sid = str(entry["id"])
                series_ep_count[sid] = series_ep_count.get(sid, 0) + 1
                if sid not in series_meta and entry.get("_is_ep1") and "title" in entry:
                    series_meta[sid] = entry
            processed += 1
            if processed % 10 == 0 or processed == len(sitemap_urls):
                logger.info("Sitemap progress: %d / %d files", processed, len(sitemap_urls))

        logger.info("Discovered %d unique series from sitemaps", len(series_meta))
        metadata_less = len(series_ep_count) - len(series_meta)
        if metadata_less:
            logger.warning(
                "%d series had no title-bearing episode-1 entry and were skipped "
                "(their episode-1 URL carries no video metadata)",
                metadata_less,
            )
        if self._sitemap_failures:
            logger.warning(
                "%d/%d sitemap files failed to download - result may be INCOMPLETE "
                "(episode counts undercounted, some series missing). Re-run, or "
                "configure PROXY_LIST if the site is throttling.",
                self._sitemap_failures,
                len(sitemap_urls),
            )

        for sid, meta in series_meta.items():
            yield {
                "id": sid,
                "title": str(meta.get("title", "")),
                "series_url": str(meta.get("series_url", "")),
                "cover_image_url": str(meta.get("cover_image_url", "")),
                "genre": str(meta.get("genre", "")),
                "episode_count": str(series_ep_count.get(sid, 1)),
                "tags": str(meta.get("tags", "")),
                "description": str(meta.get("description", "")),
            }

    async def _get_sub_sitemap_urls(self) -> list[str]:
        index_url = str(self._cfg["sitemap_index_url"])
        response = await self.middleware.fetch(index_url)
        urls = self._sitemap_parser.parse_index(response.text)
        logger.debug("Sitemap index has %d sub-sitemaps", len(urls))
        return urls

    async def _fetch_and_parse_sitemap(self, url: str) -> list[dict[str, object]]:
        try:
            response = await self.middleware.fetch(url)
        except Exception as exc:
            logger.warning("Sitemap fetch error for %s: %s", url, exc)
            self._sitemap_failures += 1
            return []
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sitemap_parser.parse_entries, response.text)

    @staticmethod
    def _parse_sitemap_xml(xml_text: str) -> list[dict[str, object]]:
        return NetshortSitemapParser().parse_entries(xml_text)
