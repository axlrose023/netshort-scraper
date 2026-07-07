from __future__ import annotations


class NullEnricher:
    async def enrich(self, partial: dict[str, str]) -> dict[str, str]:
        return {}
