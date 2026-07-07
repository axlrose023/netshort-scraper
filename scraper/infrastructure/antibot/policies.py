from __future__ import annotations

from typing import ClassVar, Protocol

from scraper.schemas.http import FetchResponse


class BanPolicy(Protocol):
    def is_banned(self, response: FetchResponse) -> bool: ...

    def should_retry(self, response: FetchResponse) -> bool:
        return response.status_code in {500, 502, 503, 504}


class DefaultBanPolicy(BanPolicy):
    _BAN_CODES: ClassVar[set[int]] = {403, 429}

    def is_banned(self, response: FetchResponse) -> bool:
        return response.status_code in self._BAN_CODES
