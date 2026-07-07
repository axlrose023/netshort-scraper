from __future__ import annotations

import os
import random
from enum import Enum


class RotationMode(Enum):
    ROTATING = "rotating"
    STICKY = "sticky"


class ProxyPool:
    """A pool of HTTP/HTTPS proxy URLs from ``PROXY_LIST`` (comma-separated) or a
    passed list, with ROTATING or STICKY (per-domain) rotation. Falls back to
    direct requests when empty or all-banned, so the scraper runs without proxies.
    """

    def __init__(
        self,
        proxies: list[str] | None = None,
        mode: RotationMode = RotationMode.ROTATING,
    ) -> None:
        self._proxies: list[str] = proxies if proxies is not None else self._from_env()
        self._banned: set[str] = set()
        self._mode = mode
        self._sticky: dict[str, str] = {}

    def get_proxy(self, domain: str = "") -> str | None:
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
        self._banned.add(proxy)
        if self._sticky.get(domain) == proxy:
            del self._sticky[domain]

    def available_count(self) -> int:
        return len([p for p in self._proxies if p not in self._banned])

    def has_proxies(self) -> bool:
        return bool(self._proxies)

    @staticmethod
    def _from_env() -> list[str]:
        raw = os.environ.get("PROXY_LIST", "").strip()
        return [p.strip() for p in raw.split(",") if p.strip()] if raw else []
