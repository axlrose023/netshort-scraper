from __future__ import annotations

from typing import Protocol


class DetailParser(Protocol):
    def parse(self, html: str) -> dict[str, str]: ...


class Enricher(Protocol):
    async def enrich(self, partial: dict[str, str]) -> dict[str, str]: ...
