from __future__ import annotations

from abc import ABC, abstractmethod


class DetailParser(ABC):
    @abstractmethod
    def parse(self, html: str) -> dict[str, str]: ...


class Enricher(ABC):
    @abstractmethod
    async def enrich(self, partial: dict[str, str]) -> dict[str, str]: ...
