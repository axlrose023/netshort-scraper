from __future__ import annotations

import logging

from scraper.infrastructure.antibot.policies import DefaultBanPolicy
from scraper.schemas.http import FetchResponse

logger = logging.getLogger(__name__)


class NetshortBanPolicy(DefaultBanPolicy):
    _CF_MARKERS = ("Just a moment", "cf-browser-verification")

    def is_banned(self, response: FetchResponse) -> bool:
        if super().is_banned(response):
            return True
        if response.status_code == 200:
            for marker in self._CF_MARKERS:
                if marker in response.text:
                    logger.warning("Cloudflare JS challenge detected at %s", response.url)
                    return True
        return False
