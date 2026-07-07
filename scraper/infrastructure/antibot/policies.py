from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from scraper.infrastructure.http.response import FetchResponse


class BanPolicy(ABC):
    @abstractmethod
    def is_banned(self, response: FetchResponse) -> bool: ...

    def should_retry(self, response: FetchResponse) -> bool:
        return response.status_code in {500, 502, 503, 504}


class DefaultBanPolicy(BanPolicy):
    _BAN_CODES: ClassVar[set[int]] = {403, 429}

    def is_banned(self, response: FetchResponse) -> bool:
        return response.status_code in self._BAN_CODES
