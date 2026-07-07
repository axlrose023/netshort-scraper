from __future__ import annotations

from scraper.infrastructure.antibot.profile import BrowserProfile

_CHROME_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
    "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
)
_FIREFOX_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
)

PROFILES: list[BrowserProfile] = [
    BrowserProfile(
        name="chrome142-macos",
        browser="chrome",
        platform="macos",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
        ),
        accept=_CHROME_ACCEPT,
        accept_language="en-US,en;q=0.9",
        impersonate="chrome142",
        sec_ch_ua='"Chromium";v="142", "Google Chrome";v="142", "Not?A_Brand";v="24"',
        sec_ch_ua_platform='"macOS"',
    ),
    BrowserProfile(
        name="chrome142-windows",
        browser="chrome",
        platform="windows",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
        ),
        accept=_CHROME_ACCEPT,
        accept_language="en-US,en;q=0.9",
        impersonate="chrome142",
        sec_ch_ua='"Chromium";v="142", "Google Chrome";v="142", "Not?A_Brand";v="24"',
        sec_ch_ua_platform='"Windows"',
    ),
    BrowserProfile(
        name="chrome142-linux",
        browser="chrome",
        platform="linux",
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
        ),
        accept=_CHROME_ACCEPT,
        accept_language="en-US,en;q=0.9",
        impersonate="chrome142",
        sec_ch_ua='"Chromium";v="142", "Google Chrome";v="142", "Not?A_Brand";v="24"',
        sec_ch_ua_platform='"Linux"',
    ),
    BrowserProfile(
        name="firefox144-windows",
        browser="firefox",
        platform="windows",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0"
        ),
        accept=_FIREFOX_ACCEPT,
        accept_language="en-US,en;q=0.5",
        impersonate="firefox144",
    ),
]
