from __future__ import annotations

from scraper.infrastructure.antibot.profile import BrowserProfile

_PLATFORM_UA_TOKENS = {
    "macos": ("Macintosh", "Mac OS X"),
    "windows": ("Windows",),
    "linux": ("X11", "Linux"),
}
_PLATFORM_CH = {
    "macos": '"macOS"',
    "windows": '"Windows"',
    "linux": '"Linux"',
}
_BROWSER_UA_TOKEN = {
    "chrome": "Chrome",
    "edge": "Edg",
    "firefox": "Firefox",
    "safari": "Version/",
}
_CHROMIUM_FAMILY = {"chrome", "edge"}


class ProfileInconsistencyError(ValueError): ...


class ConsistencyValidator:
    @staticmethod
    def errors(profile: BrowserProfile) -> list[str]:
        errors: list[str] = []

        if profile.platform not in _PLATFORM_UA_TOKENS:
            errors.append(f"unknown platform {profile.platform!r}")
        else:
            tokens = _PLATFORM_UA_TOKENS[profile.platform]
            if not any(token in profile.user_agent for token in tokens):
                errors.append(
                    f"UA does not match platform {profile.platform!r} (expected one of {tokens})"
                )

        ua_token = _BROWSER_UA_TOKEN.get(profile.browser)
        if ua_token is None:
            errors.append(f"unknown browser {profile.browser!r}")
        elif ua_token not in profile.user_agent:
            errors.append(f"UA does not match browser {profile.browser!r} (expected {ua_token!r})")

        if not profile.impersonate.startswith(profile.browser):
            errors.append(
                f"impersonate {profile.impersonate!r} "
                f"does not match browser family {profile.browser!r}"
            )

        if not profile.accept_language.strip():
            errors.append("empty Accept-Language")

        is_chromium = profile.browser in _CHROMIUM_FAMILY
        if is_chromium:
            if not profile.sec_ch_ua:
                errors.append("Chromium profile must set Sec-CH-UA")
            expected_ch = _PLATFORM_CH.get(profile.platform, "")
            if profile.sec_ch_ua_platform != expected_ch:
                errors.append(
                    f"Sec-CH-UA-Platform {profile.sec_ch_ua_platform!r} "
                    f"!= expected {expected_ch!r} for {profile.platform!r}"
                )
        elif profile.sec_ch_ua or profile.sec_ch_ua_platform:
            errors.append(f"{profile.browser!r} must not send Sec-CH-UA headers")

        return errors

    @classmethod
    def check(cls, profile: BrowserProfile) -> None:
        errors = cls.errors(profile)
        if errors:
            raise ProfileInconsistencyError(f"profile {profile.name!r}: " + "; ".join(errors))
