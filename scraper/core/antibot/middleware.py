from __future__ import annotations

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar
from urllib.parse import urlparse

from scraper.core.antibot.proxy_pool import ProxyPool
from scraper.core.fetcher import Fetcher, FetchResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Browser-realistic header pool
# ---------------------------------------------------------------------------

# Realistic browser UA strings — kept as single lines on purpose (E501 exempt).
_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",  # noqa: E501
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",  # noqa: E501
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",  # noqa: E501
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",  # noqa: E501
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]


def _browser_headers() -> dict[str, str]:
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",  # noqa: E501
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "no-cache",
    }


# ---------------------------------------------------------------------------
# Ban detection — site-specific, separated from retry orchestration
# ---------------------------------------------------------------------------

class BanPolicy(ABC):
    """Decides whether a response signals a block.

    Site-specific subclasses inspect status codes and body patterns.
    Generic retry logic never needs to know *why* it was blocked.
    """

    @abstractmethod
    def is_banned(self, response: FetchResponse) -> bool: ...

    def should_retry(self, response: FetchResponse) -> bool:
        """True for transient server errors regardless of ban status."""
        return response.status_code in {500, 502, 503, 504}


class DefaultBanPolicy(BanPolicy):
    """Treats HTTP 403 and 429 as bans; 5xx as retriable but not bans."""

    _BAN_CODES: ClassVar[set[int]] = {403, 429}

    def is_banned(self, response: FetchResponse) -> bool:
        return response.status_code in self._BAN_CODES


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------

@dataclass
class ScraperStats:
    pages_fetched: int = 0
    retries: int = 0
    proxy_bans: int = 0
    errors: int = 0

    def report(self) -> str:
        return (
            f"fetched={self.pages_fetched}  retries={self.retries}  "
            f"proxy_bans={self.proxy_bans}  errors={self.errors}"
        )


# ---------------------------------------------------------------------------
# Request middleware — generic, knows nothing about site-specific logic
# ---------------------------------------------------------------------------

class RequestMiddleware:
    """Wraps a Fetcher with: UA injection, per-domain rate limiting,
    retry/backoff, and proxy rotation on ban.

    NetshortScraper (and any other site scraper) calls only ``fetch(url)``.
    Everything else — proxies, retries, headers — is invisible to it.
    """

    def __init__(
        self,
        fetcher: Fetcher,
        proxy_pool: ProxyPool,
        ban_policy: BanPolicy | None = None,
        concurrency: int = 5,
        delay_min: float = 0.5,
        delay_max: float = 1.5,
        max_retries: int = 3,
        backoff_base: float = 2.0,
    ) -> None:
        self._fetcher = fetcher
        self._proxy_pool = proxy_pool
        self._ban_policy = ban_policy or DefaultBanPolicy()
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
        sem = self._semaphore(domain)
        proxy = self._proxy_pool.get_proxy(domain)

        async with sem:
            for attempt in range(self._max_retries + 1):
                if attempt > 0:
                    delay = self._backoff_base ** attempt + random.uniform(0, 1)
                    logger.debug(
                        "Retry %d/%d for %s (backoff %.1fs)",
                        attempt, self._max_retries, url, delay,
                    )
                    await asyncio.sleep(delay)
                    self.stats.retries += 1

                try:
                    response = await self._fetcher.fetch(
                        url, proxy=proxy, headers=_browser_headers()
                    )
                except Exception as exc:
                    logger.warning("Network error fetching %s: %s", url, exc)
                    self.stats.errors += 1
                    continue

                # --- Ban detection (site-specific policy) ---
                if self._ban_policy.is_banned(response):
                    logger.warning(
                        "Ban detected (HTTP %d) for %s via proxy %s",
                        response.status_code, url, proxy,
                    )
                    self.stats.proxy_bans += 1
                    if proxy:
                        self._proxy_pool.mark_banned(proxy, domain)
                        proxy = self._proxy_pool.get_proxy(domain)
                    continue

                # --- Transient server errors ---
                if self._ban_policy.should_retry(response):
                    logger.warning("Transient error (HTTP %d) for %s", response.status_code, url)
                    continue

                # --- Success ---
                self.stats.pages_fetched += 1
                await asyncio.sleep(random.uniform(self._delay_min, self._delay_max))
                return response

        self.stats.errors += 1
        raise RuntimeError(f"Max retries exceeded for {url}")

    async def close(self) -> None:
        await self._fetcher.close()
