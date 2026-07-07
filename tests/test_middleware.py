from __future__ import annotations

import pytest

from scraper.infrastructure.antibot import (
    BrowserProfile,
    DefaultBanPolicy,
    ProxyPool,
    RequestMiddleware,
)
from scraper.infrastructure.http import Fetcher, FetchResponse


class _RecordingFetcher(Fetcher):
    def __init__(self, statuses: list[int]) -> None:
        self._statuses = statuses
        self.calls: list[dict[str, str | None]] = []

    async def fetch(self, url, *, proxy=None, headers=None, impersonate=None):
        self.calls.append(
            {"proxy": proxy, "impersonate": impersonate, "ua": (headers or {}).get("User-Agent")}
        )
        status = self._statuses[len(self.calls) - 1]
        return FetchResponse(status_code=status, text="", url=url)

    async def close(self) -> None:
        pass


class _IdentityProfilePool:
    def get(self, identity: str = "direct") -> BrowserProfile:
        return BrowserProfile(
            name=identity,
            browser="chrome",
            platform="macos",
            user_agent=f"ua::{identity}",
            accept="",
            accept_language="en",
            impersonate=f"imp::{identity}",
        )


def _middleware(fetcher, proxies):
    return RequestMiddleware(
        fetcher=fetcher,
        proxy_pool=ProxyPool(proxies=proxies),
        ban_policy=DefaultBanPolicy(),
        profile_pool=_IdentityProfilePool(),
        delay_min=0,
        delay_max=0,
        max_retries=3,
        backoff_base=0,
    )


class TestFetchLoop:
    async def test_success_uses_matching_profile(self):
        fetcher = _RecordingFetcher([200])
        mw = _middleware(fetcher, proxies=[])
        await mw.fetch("https://site/x")
        call = fetcher.calls[-1]
        assert call["proxy"] is None
        assert call["ua"] == "ua::direct"
        assert call["impersonate"] == "imp::direct"

    async def test_fingerprint_rotates_with_proxy_after_ban(self):
        fetcher = _RecordingFetcher([403, 200])
        mw = _middleware(fetcher, proxies=["http://p1:1", "http://p2:2"])
        resp = await mw.fetch("https://site/x")

        assert resp.status_code == 200
        first, last = fetcher.calls[0], fetcher.calls[-1]
        assert first["proxy"] != last["proxy"]
        assert first["ua"] == f"ua::{first['proxy']}"
        assert last["ua"] == f"ua::{last['proxy']}"
        assert last["impersonate"] == f"imp::{last['proxy']}"

    async def test_raises_after_max_retries(self):
        fetcher = _RecordingFetcher([403, 403, 403, 403])
        mw = _middleware(fetcher, proxies=["http://p1:1"])
        try:
            await mw.fetch("https://site/x")
        except RuntimeError as exc:
            assert "Max retries" in str(exc)
        else:
            raise AssertionError("expected RuntimeError after exhausting retries")
        assert len(fetcher.calls) == 4


class TestMiddlewareConfig:
    def test_rejects_invalid_concurrency(self):
        with pytest.raises(ValueError, match="concurrency"):
            RequestMiddleware(
                fetcher=_RecordingFetcher([200]),
                proxy_pool=ProxyPool(proxies=[]),
                concurrency=0,
            )

    def test_rejects_inverted_delay_range(self):
        with pytest.raises(ValueError, match="delay_min"):
            RequestMiddleware(
                fetcher=_RecordingFetcher([200]),
                proxy_pool=ProxyPool(proxies=[]),
                delay_min=2,
                delay_max=1,
            )
