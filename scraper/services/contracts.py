from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from scraper.infrastructure.antibot.stats import ScraperStats
from scraper.pipelines.stats import PipelineStats

FetcherName = Literal["curl", "httpx"]


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
