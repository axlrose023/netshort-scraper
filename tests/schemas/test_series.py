from __future__ import annotations

from scraper.schemas.series import SeriesItem


class TestFromPartial:
    def test_builds_from_partial_only(self):
        partial = {
            "id": "111",
            "title": "T",
            "series_url": "https://x/full-episodes/t-111",
            "description": "sitemap desc",
        }
        item = SeriesItem.from_partial(partial)
        assert item.title == "T"
        assert item.description == "sitemap desc"
        assert item.genre == ""

    def test_detail_overrides_partial(self):
        partial = {"id": "1", "title": "T", "series_url": "u", "description": "old"}
        item = SeriesItem.from_partial(partial, {"description": "canonical"})
        assert item.description == "canonical"

    def test_empty_detail_value_does_not_clobber_partial(self):
        partial = {"id": "1", "title": "T", "series_url": "u", "description": "keep"}
        item = SeriesItem.from_partial(partial, {"description": ""})
        assert item.description == "keep"
