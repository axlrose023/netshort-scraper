from __future__ import annotations

import pytest

from scraper.infrastructure.http import FetchResponse
from scraper.services.enrichment import DetailPageEnricher, DetailParser, NullEnricher


class _StubMiddleware:
    def __init__(self, html: str = "") -> None:
        self.html = html
        self.fetched: list[str] = []

    async def fetch(self, url: str) -> FetchResponse:
        self.fetched.append(url)
        return FetchResponse(status_code=200, text=self.html, url=url)


class _EchoParser(DetailParser):
    def parse(self, html: str) -> dict[str, str]:
        return {"description": html.upper()}


class TestNullEnricher:
    async def test_returns_empty_and_makes_no_request(self):
        enricher = NullEnricher()
        result = await enricher.enrich({"series_url": "https://x/y"})
        assert result == {}


class TestDetailPageEnricher:
    async def test_fetches_url_and_parses(self):
        mw = _StubMiddleware(html="hello")
        enricher = DetailPageEnricher(mw, _EchoParser())
        result = await enricher.enrich({"series_url": "https://x/series-1"})
        assert mw.fetched == ["https://x/series-1"]
        assert result == {"description": "HELLO"}

    async def test_missing_url_skips_fetch(self):
        mw = _StubMiddleware()
        enricher = DetailPageEnricher(mw, _EchoParser())
        result = await enricher.enrich({"title": "no url here"})
        assert mw.fetched == []
        assert result == {}

    async def test_custom_url_key(self):
        mw = _StubMiddleware(html="x")
        enricher = DetailPageEnricher(mw, _EchoParser(), url_key="detail_url")
        await enricher.enrich({"detail_url": "https://x/d", "series_url": "https://x/s"})
        assert mw.fetched == ["https://x/d"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
