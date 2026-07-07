from __future__ import annotations

import pytest

from scraper.core.antibot.profile import (
    PROFILES,
    BrowserProfile,
    ConsistencyValidator,
    ProfileInconsistencyError,
    ProfilePool,
)


def _chrome_mac(**overrides) -> BrowserProfile:
    base = {
        "name": "t",
        "browser": "chrome",
        "platform": "macos",
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
        ),
        "accept": "text/html",
        "accept_language": "en-US,en;q=0.9",
        "impersonate": "chrome142",
        "sec_ch_ua": '"Google Chrome";v="142"',
        "sec_ch_ua_platform": '"macOS"',
    }
    base.update(overrides)
    return BrowserProfile(**base)


# ---------------------------------------------------------------------------
# Built-in profiles must all be internally consistent
# ---------------------------------------------------------------------------


class TestBuiltinProfiles:
    def test_all_builtin_profiles_pass(self):
        for p in PROFILES:
            assert ConsistencyValidator.errors(p) == [], f"{p.name} inconsistent"

    def test_pool_validates_on_construction(self):
        ProfilePool()


class TestConsistencyValidator:
    def test_valid_profile_has_no_errors(self):
        assert ConsistencyValidator.errors(_chrome_mac()) == []

    def test_ua_platform_mismatch(self):
        # macOS profile but a Windows UA
        p = _chrome_mac(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/142")
        assert any("does not match platform" in e for e in ConsistencyValidator.errors(p))

    def test_ua_browser_mismatch(self):
        # browser=chrome but a Firefox UA (still macOS, so the platform is fine)
        p = _chrome_mac(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7; rv:144.0) Firefox/144.0"
        )
        assert any("does not match browser" in e for e in ConsistencyValidator.errors(p))

    def test_sec_ch_ua_platform_mismatch(self):
        p = _chrome_mac(sec_ch_ua_platform='"Windows"')
        assert any("Sec-CH-UA-Platform" in e for e in ConsistencyValidator.errors(p))

    def test_chromium_without_client_hints(self):
        p = _chrome_mac(sec_ch_ua="", sec_ch_ua_platform="")
        errs = ConsistencyValidator.errors(p)
        assert any("must set Sec-CH-UA" in e for e in errs)

    def test_firefox_must_not_send_client_hints(self):
        p = BrowserProfile(
            name="bad-ff",
            browser="firefox",
            platform="windows",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Firefox/144.0",
            accept="text/html",
            accept_language="en-US,en;q=0.5",
            impersonate="firefox144",
            sec_ch_ua='"Firefox";v="144"',  # contradiction: Firefox never sends this
        )
        assert any("must not send Sec-CH-UA" in e for e in ConsistencyValidator.errors(p))

    def test_impersonate_family_mismatch(self):
        p = _chrome_mac(impersonate="firefox144")
        assert any("does not match browser family" in e for e in ConsistencyValidator.errors(p))

    def test_check_raises(self):
        with pytest.raises(ProfileInconsistencyError):
            ConsistencyValidator.check(_chrome_mac(sec_ch_ua=""))


class TestHeaders:
    def test_chrome_sends_client_hints(self):
        h = _chrome_mac().headers()
        assert h["Sec-CH-UA-Platform"] == '"macOS"'
        assert "Sec-CH-UA" in h
        assert h["User-Agent"].startswith("Mozilla/5.0 (Macintosh")

    def test_firefox_profile_omits_client_hints(self):
        ff = next(p for p in PROFILES if p.browser == "firefox")
        assert "Sec-CH-UA" not in ff.headers()


class TestProfilePool:
    def test_same_identity_is_sticky(self):
        pool = ProfilePool(seed=1)
        first = pool.get("proxyA")
        for _ in range(20):
            assert pool.get("proxyA") is first

    def test_different_identities_independent(self):
        pool = ProfilePool(seed=1)
        a = pool.get("proxyA")
        b = pool.get("proxyB")
        assert a in PROFILES and b in PROFILES

    def test_empty_profiles_rejected(self):
        with pytest.raises(ValueError):
            ProfilePool(profiles=[])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
