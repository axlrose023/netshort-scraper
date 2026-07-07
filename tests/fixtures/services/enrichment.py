from __future__ import annotations

import pytest

from scraper.schemas.http import FetchResponse
from scraper.services.enrichment import DetailParser


class StubMiddleware:
    def __init__(self, html: str = "") -> None:
        self.html = html
        self.fetched: list[str] = []

    async def fetch(self, url: str) -> FetchResponse:
        self.fetched.append(url)
        return FetchResponse(status_code=200, text=self.html, url=url)


class EchoParser(DetailParser):
    def parse(self, html: str) -> dict[str, str]:
        return {"description": html.upper()}


@pytest.fixture
def stub_middleware_factory():
    return StubMiddleware


@pytest.fixture
def echo_parser() -> EchoParser:
    return EchoParser()
