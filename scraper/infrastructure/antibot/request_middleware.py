from __future__ import annotations

import asyncio
import logging
import random
from urllib.parse import urlparse

from scraper.infrastructure.antibot.policies import BanPolicy, DefaultBanPolicy
from scraper.infrastructure.antibot.profile_pool import ProfilePool
from scraper.infrastructure.antibot.proxy_pool import ProxyPool
from scraper.infrastructure.http.base import Fetcher
from scraper.schemas.http import FetchResponse
from scraper.schemas.stats import ScraperStats

logger = logging.getLogger(__name__)


class RequestMiddleware:
    def __init__(
        self,
        fetcher: Fetcher,
        proxy_pool: ProxyPool,
        ban_policy: BanPolicy | None = None,
        profile_pool: ProfilePool | None = None,
        concurrency: int = 5,
        delay_min: float = 0.5,
        delay_max: float = 1.5,
        max_retries: int = 3,
        backoff_base: float = 2.0,
    ) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        if delay_min < 0 or delay_max < 0:
            raise ValueError("delay_min and delay_max must be >= 0")
        if delay_min > delay_max:
            raise ValueError("delay_min must be <= delay_max")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if backoff_base < 0:
            raise ValueError("backoff_base must be >= 0")

        self._fetcher = fetcher
        self._proxy_pool = proxy_pool
        self._ban_policy = ban_policy or DefaultBanPolicy()
        self._profile_pool = profile_pool or ProfilePool()
        self._concurrency = concurrency
        self._delay_min = delay_min
        self._delay_max = delay_max
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self.stats = ScraperStats()

    def _domain(self, url: str) -> str:
        return urlparse(url).netloc

    def _semaphore(self, domain: str) -> asyncio.Semaphore:
        if domain not in self._semaphores:
            self._semaphores[domain] = asyncio.Semaphore(self._concurrency)
        return self._semaphores[domain]

    async def fetch(self, url: str) -> FetchResponse:
        domain = self._domain(url)
        semaphore = self._semaphore(domain)
        proxy = self._proxy_pool.get_proxy(domain)
        profile = self._profile_pool.get(proxy or "direct")

        async with semaphore:
            for attempt in range(self._max_retries + 1):
                if attempt > 0:
                    delay = self._backoff_base**attempt + random.uniform(0, 1)
                    logger.debug(
                        "Retry %d/%d for %s (backoff %.1fs)",
                        attempt,
                        self._max_retries,
                        url,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    self.stats.retries += 1

                try:
                    response = await self._fetcher.fetch(
                        url,
                        proxy=proxy,
                        headers=profile.headers(),
                        impersonate=profile.impersonate,
                    )
                except Exception as exc:
                    logger.warning("Network error fetching %s: %s", url, exc)
                    continue

                if self._ban_policy.is_banned(response):
                    logger.warning(
                        "Ban detected (HTTP %d) for %s via proxy %s",
                        response.status_code,
                        url,
                        proxy,
                    )
                    self.stats.proxy_bans += 1
                    if proxy:
                        self._proxy_pool.mark_banned(proxy, domain)
                        proxy = self._proxy_pool.get_proxy(domain)
                        profile = self._profile_pool.get(proxy or "direct")
                    continue

                if self._ban_policy.should_retry(response):
                    logger.warning("Transient error (HTTP %d) for %s", response.status_code, url)
                    continue

                self.stats.pages_fetched += 1
                await asyncio.sleep(random.uniform(self._delay_min, self._delay_max))
                return response

        self.stats.errors += 1
        raise RuntimeError(f"Max retries exceeded for {url}")

    async def close(self) -> None:
        await self._fetcher.close()
