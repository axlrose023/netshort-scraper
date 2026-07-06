from __future__ import annotations

import random
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Coherent browser identity
# ---------------------------------------------------------------------------
#
# A scraper is fingerprinted on far more than its User-Agent. The cheap tells a
# detector looks for are *internal contradictions*: a Windows UA paired with a
# macOS `Sec-CH-UA-Platform`, a Firefox UA that nonetheless sends the
# Chromium-only `Sec-CH-UA` headers, or a TLS handshake (JA3) that says "Python"
# while the UA says "Chrome".
#
# BrowserProfile is the single source of truth for one identity: it emits a
# header set that agrees with itself, and it names the curl_cffi impersonation
# target so the TLS/HTTP2 fingerprint matches the UA. ConsistencyValidator
# rejects any profile that contradicts itself before it is ever used, and
# ProfilePool keeps one profile pinned per network identity for a whole run
# (SessionPolicy) so a given IP never suddenly changes browser.

_CHROME_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
    "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
)
_FIREFOX_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
)

# UA substrings that must appear for a given OS — used by the validator.
_PLATFORM_UA_TOKENS = {
    "macos": ("Macintosh", "Mac OS X"),
    "windows": ("Windows",),
    "linux": ("X11", "Linux"),
}
# The value the OS must present in `Sec-CH-UA-Platform` (Chromium only).
_PLATFORM_CH = {
    "macos": '"macOS"',
    "windows": '"Windows"',
    "linux": '"Linux"',
}
# Browser families that send Client Hints (`Sec-CH-UA*`). Others must not.
_CHROMIUM_FAMILY = {"chrome", "edge"}


@dataclass(frozen=True)
class BrowserProfile:
    """One self-consistent browser identity (headers + TLS impersonation target)."""

    name: str
    browser: str          # "chrome" | "edge" | "firefox" | "safari"
    platform: str         # "macos" | "windows" | "linux"
    user_agent: str
    accept: str
    accept_language: str
    impersonate: str      # curl_cffi target, e.g. "chrome142" — must match UA
    sec_ch_ua: str = ""            # Chromium-only; empty for firefox/safari
    sec_ch_ua_platform: str = ""   # e.g. '"macOS"'; empty for firefox/safari

    def headers(self) -> dict[str, str]:
        """Return a full, internally-consistent request header set."""
        h = {
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
        if self.sec_ch_ua:  # Client Hints — Chromium family only
            h["Sec-CH-UA"] = self.sec_ch_ua
            h["Sec-CH-UA-Mobile"] = "?0"
            h["Sec-CH-UA-Platform"] = self.sec_ch_ua_platform
        return h


# ---------------------------------------------------------------------------
# Consistency validation
# ---------------------------------------------------------------------------


class ProfileInconsistencyError(ValueError):
    """Raised when a BrowserProfile contradicts itself."""


class ConsistencyValidator:
    """Rejects self-contradictory profiles before they are ever sent.

    This is the guard the recommendation is about: it turns "random fields that
    may disagree" into "a fingerprint that always agrees with itself".
    """

    @staticmethod
    def errors(p: BrowserProfile) -> list[str]:
        errs: list[str] = []

        if p.platform not in _PLATFORM_UA_TOKENS:
            errs.append(f"unknown platform {p.platform!r}")
        else:
            tokens = _PLATFORM_UA_TOKENS[p.platform]
            if not any(tok in p.user_agent for tok in tokens):
                errs.append(f"UA does not match platform {p.platform!r} (expected one of {tokens})")

        if not p.impersonate.startswith(p.browser):
            errs.append(
                f"impersonate {p.impersonate!r} does not match browser family {p.browser!r}"
            )

        if not p.accept_language.strip():
            errs.append("empty Accept-Language")

        is_chromium = p.browser in _CHROMIUM_FAMILY
        if is_chromium:
            if not p.sec_ch_ua:
                errs.append("Chromium profile must set Sec-CH-UA")
            expected_ch = _PLATFORM_CH.get(p.platform, "")
            if p.sec_ch_ua_platform != expected_ch:
                errs.append(
                    f"Sec-CH-UA-Platform {p.sec_ch_ua_platform!r} != expected {expected_ch!r} "
                    f"for {p.platform!r}"
                )
        else:
            # Firefox / Safari do not send Client Hints — sending them is a tell.
            if p.sec_ch_ua or p.sec_ch_ua_platform:
                errs.append(f"{p.browser!r} must not send Sec-CH-UA headers")

        return errs

    @classmethod
    def check(cls, p: BrowserProfile) -> None:
        errs = cls.errors(p)
        if errs:
            raise ProfileInconsistencyError(f"profile {p.name!r}: " + "; ".join(errs))


# ---------------------------------------------------------------------------
# Built-in profile set — every entry passes ConsistencyValidator (see tests)
# ---------------------------------------------------------------------------

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
        # No Sec-CH-UA — Firefox does not send Client Hints.
    ),
]


# ---------------------------------------------------------------------------
# Session policy — one profile per network identity, sticky for the whole run
# ---------------------------------------------------------------------------


class ProfilePool:
    """Assigns a coherent BrowserProfile per network identity and keeps it stuck.

    The identity key is the proxy URL (or ``"direct"`` for no-proxy). A given IP
    therefore always presents the same browser for the life of the run — the UA,
    Client Hints and TLS fingerprint never change under a stable IP, and they
    rotate *together* only when the IP does. All profiles are validated up front.
    """

    def __init__(
        self,
        profiles: list[BrowserProfile] | None = None,
        seed: int | None = None,
    ) -> None:
        self._profiles = profiles if profiles is not None else PROFILES
        if not self._profiles:
            raise ValueError("ProfilePool needs at least one profile")
        for p in self._profiles:
            ConsistencyValidator.check(p)
        self._assigned: dict[str, BrowserProfile] = {}
        self._rng = random.Random(seed)

    def get(self, identity: str = "direct") -> BrowserProfile:
        if identity not in self._assigned:
            self._assigned[identity] = self._rng.choice(self._profiles)
        return self._assigned[identity]
