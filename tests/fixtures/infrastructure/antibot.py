from __future__ import annotations

import pytest

from scraper.infrastructure.antibot import BrowserProfile, DefaultBanPolicy, ProxyPool
from scraper.infrastructure.antibot.request_middleware import RequestMiddleware
from scraper.infrastructure.http import Fetcher
from scraper.schemas.http import FetchResponse


class RecordingFetcher(Fetcher):
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
        return None


class IdentityProfilePool:
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


@pytest.fixture
def recording_fetcher_factory():
    return RecordingFetcher


@pytest.fixture
def middleware_factory():
    def build(fetcher, proxies):
        return RequestMiddleware(
            fetcher=fetcher,
            proxy_pool=ProxyPool(proxies=proxies),
            ban_policy=DefaultBanPolicy(),
            profile_pool=IdentityProfilePool(),
            delay_min=0,
            delay_max=0,
            max_retries=3,
            backoff_base=0,
        )

    return build
