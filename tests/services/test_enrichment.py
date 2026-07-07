from __future__ import annotations

import pytest

from scraper.services.enrichment import DetailPageEnricher, NullEnricher


class TestNullEnricher:
    async def test_returns_empty_and_makes_no_request(self):
        enricher = NullEnricher()
        result = await enricher.enrich({"series_url": "https://x/y"})
        assert result == {}


class TestDetailPageEnricher:
    async def test_fetches_url_and_parses(self, stub_middleware_factory, echo_parser):
        mw = stub_middleware_factory(html="hello")
        enricher = DetailPageEnricher(mw, echo_parser)
        result = await enricher.enrich({"series_url": "https://x/series-1"})
        assert mw.fetched == ["https://x/series-1"]
        assert result == {"description": "HELLO"}

    async def test_missing_url_skips_fetch(self, stub_middleware_factory, echo_parser):
        mw = stub_middleware_factory()
        enricher = DetailPageEnricher(mw, echo_parser)
        result = await enricher.enrich({"title": "no url here"})
        assert mw.fetched == []
        assert result == {}

    async def test_custom_url_key(self, stub_middleware_factory, echo_parser):
        mw = stub_middleware_factory(html="x")
        enricher = DetailPageEnricher(mw, echo_parser, url_key="detail_url")
        await enricher.enrich({"detail_url": "https://x/d", "series_url": "https://x/s"})
        assert mw.fetched == ["https://x/d"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
