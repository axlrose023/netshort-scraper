from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PipelineStats:
    processed: int = 0
    exported: int = 0
    dropped: int = 0


@dataclass
class ScraperStats:
    pages_fetched: int = 0
    retries: int = 0
    proxy_bans: int = 0
    errors: int = 0
