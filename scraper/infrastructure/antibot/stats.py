from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScraperStats:
    pages_fetched: int = 0
    retries: int = 0
    proxy_bans: int = 0
    errors: int = 0
