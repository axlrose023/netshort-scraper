from __future__ import annotations

import os
import random
from enum import Enum


class RotationMode(Enum):
    ROTATING = "rotating"   # pick a random proxy each call
    STICKY = "sticky"       # reuse the same proxy per domain until it's banned


class ProxyPool:
    """Manages a pool of HTTP/HTTPS proxy URLs.

    Configure via the ``PROXY_LIST`` environment variable (comma-separated proxy
    URLs) or by passing a list directly.  Falls back gracefully to direct
    (no-proxy) requests when the pool is empty or all proxies are banned, so the
    scraper stays runnable without real proxy credentials.

    Example env var::

        export PROXY_LIST="http://user:pass@host1:8080,http://user:pass@host2:8080"

    Supports two rotation modes:
    - ROTATING (default): a random available proxy is returned each call.
    - STICKY: the same proxy is reused for a domain until it is banned, then a
      new one is selected — useful for session-aware targets.
    """

    def __init__(
        self,
        proxies: list[str] | None = None,
        mode: RotationMode = RotationMode.ROTATING,
    ) -> None:
        self._proxies: list[str] = proxies if proxies is not None else self._from_env()
        self._banned: set[str] = set()
        self._mode = mode
        self._sticky: dict[str, str] = {}  # domain -> currently assigned proxy

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_proxy(self, domain: str = "") -> str | None:
        """Return a proxy URL for *domain*, or ``None`` for a direct request."""
        available = [p for p in self._proxies if p not in self._banned]
        if not available:
            return None

        if self._mode == RotationMode.STICKY:
            current = self._sticky.get(domain)
            if current and current in available:
                return current
            chosen = random.choice(available)
            self._sticky[domain] = chosen
            return chosen

        return random.choice(available)

    def mark_banned(self, proxy: str, domain: str = "") -> None:
        """Record *proxy* as blocked for *domain* and evict it from sticky cache."""
        self._banned.add(proxy)
        if self._sticky.get(domain) == proxy:
            del self._sticky[domain]

    def available_count(self) -> int:
        return len([p for p in self._proxies if p not in self._banned])

    def has_proxies(self) -> bool:
        return bool(self._proxies)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _from_env() -> list[str]:
        raw = os.environ.get("PROXY_LIST", "").strip()
        return [p.strip() for p in raw.split(",") if p.strip()] if raw else []
