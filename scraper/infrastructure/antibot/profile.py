from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BrowserProfile:
    name: str
    browser: str
    platform: str
    user_agent: str
    accept: str
    accept_language: str
    impersonate: str
    sec_ch_ua: str = ""
    sec_ch_ua_platform: str = ""

    def headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": self.accept,
            "Accept-Language": self.accept_language,
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }
        if self.sec_ch_ua:
            headers["Sec-CH-UA"] = self.sec_ch_ua
            headers["Sec-CH-UA-Mobile"] = "?0"
            headers["Sec-CH-UA-Platform"] = self.sec_ch_ua_platform
        return headers
