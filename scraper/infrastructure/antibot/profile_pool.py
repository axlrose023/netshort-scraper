from __future__ import annotations

import random

from scraper.infrastructure.antibot.builtin_profiles import PROFILES
from scraper.infrastructure.antibot.profile import BrowserProfile
from scraper.infrastructure.antibot.profile_validator import ConsistencyValidator


class ProfilePool:
    def __init__(
        self,
        profiles: list[BrowserProfile] | None = None,
        seed: int | None = None,
    ) -> None:
        self._profiles = profiles if profiles is not None else PROFILES
        if not self._profiles:
            raise ValueError("ProfilePool needs at least one profile")
        for profile in self._profiles:
            ConsistencyValidator.check(profile)
        self._assigned: dict[str, BrowserProfile] = {}
        self._rng = random.Random(seed)

    def get(self, identity: str = "direct") -> BrowserProfile:
        if identity not in self._assigned:
            self._assigned[identity] = self._rng.choice(self._profiles)
        return self._assigned[identity]
