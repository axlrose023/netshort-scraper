from __future__ import annotations

import pytest

from scraper.infrastructure.antibot import ProxyPool, RequestMiddleware


class TestFetchLoop:
    async def test_success_uses_matching_profile(
        self,
        recording_fetcher_factory,
        middleware_factory,
    ):
        fetcher = recording_fetcher_factory([200])
        mw = middleware_factory(fetcher, proxies=[])
        await mw.fetch("https://site/x")
        call = fetcher.calls[-1]
        assert call["proxy"] is None
        assert call["ua"] == "ua::direct"
        assert call["impersonate"] == "imp::direct"

    async def test_fingerprint_rotates_with_proxy_after_ban(
        self,
        recording_fetcher_factory,
        middleware_factory,
    ):
        fetcher = recording_fetcher_factory([403, 200])
        mw = middleware_factory(fetcher, proxies=["http://p1:1", "http://p2:2"])
        resp = await mw.fetch("https://site/x")

        assert resp.status_code == 200
        first, last = fetcher.calls[0], fetcher.calls[-1]
        assert first["proxy"] != last["proxy"]
        assert first["ua"] == f"ua::{first['proxy']}"
        assert last["ua"] == f"ua::{last['proxy']}"
        assert last["impersonate"] == f"imp::{last['proxy']}"

    async def test_raises_after_max_retries(self, recording_fetcher_factory, middleware_factory):
        fetcher = recording_fetcher_factory([403, 403, 403, 403])
        mw = middleware_factory(fetcher, proxies=["http://p1:1"])
        try:
            await mw.fetch("https://site/x")
        except RuntimeError as exc:
            assert "Max retries" in str(exc)
        else:
            raise AssertionError("expected RuntimeError after exhausting retries")
        assert len(fetcher.calls) == 4


class TestMiddlewareConfig:
    def test_rejects_invalid_concurrency(self, recording_fetcher_factory):
        with pytest.raises(ValueError, match="concurrency"):
            RequestMiddleware(
                fetcher=recording_fetcher_factory([200]),
                proxy_pool=ProxyPool(proxies=[]),
                concurrency=0,
            )

    def test_rejects_inverted_delay_range(self, recording_fetcher_factory):
        with pytest.raises(ValueError, match="delay_min"):
            RequestMiddleware(
                fetcher=recording_fetcher_factory([200]),
                proxy_pool=ProxyPool(proxies=[]),
                delay_min=2,
                delay_max=1,
            )
