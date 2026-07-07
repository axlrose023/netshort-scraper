from __future__ import annotations

from scraper.infrastructure.http.base import Fetcher
from scraper.infrastructure.http.curl_fetcher import CurlCffiFetcher
from scraper.infrastructure.http.httpx_fetcher import HttpxFetcher
from scraper.schemas.run import FetcherName


class FetcherFactory:
    def build(self, name: FetcherName) -> Fetcher:
        if name == "curl":
            return CurlCffiFetcher(timeout=30.0)
        if name == "httpx":
            return HttpxFetcher(timeout=30.0)
        raise ValueError(f"Unknown fetcher {name!r}")
