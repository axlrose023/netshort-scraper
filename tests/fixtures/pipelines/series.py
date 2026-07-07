from __future__ import annotations

from collections.abc import Callable

import pytest

from scraper.schemas.series import SeriesItem


@pytest.fixture
def make_series_item() -> Callable[..., SeriesItem]:
    def build(**kwargs: str) -> SeriesItem:
        defaults = {
            "id": "1234567890123456789",
            "title": "Test Series",
            "series_url": "https://netshort.com/full-episodes/test-1234567890123456789",
            "cover_image_url": "https://example.com/cover.jpg",
            "description": "A test description.",
            "genre": "Action, Drama",
            "episode_count": "20",
            "status": "",
            "tags": "Action, Drama",
        }
        defaults.update(kwargs)
        return SeriesItem(**defaults)

    return build
