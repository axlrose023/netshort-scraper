from __future__ import annotations

import csv
import os
import tempfile

import pytest

from scraper.domain.series import SeriesItem
from scraper.pipelines import (
    CSVExportStage,
    DeduplicateStage,
    DropItem,
    Pipeline,
    ValidateStage,
)


def _item(**kwargs) -> SeriesItem:
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


class TestValidateStage:
    def test_passes_valid_item(self):
        stage = ValidateStage()
        item = _item()
        assert stage.process(item) is item

    def test_drops_missing_id(self):
        stage = ValidateStage()
        with pytest.raises(DropItem, match="id"):
            stage.process(_item(id=""))

    def test_drops_missing_title(self):
        stage = ValidateStage()
        with pytest.raises(DropItem, match="title"):
            stage.process(_item(title=""))

    def test_drops_missing_series_url(self):
        stage = ValidateStage()
        with pytest.raises(DropItem, match="series_url"):
            stage.process(_item(series_url=""))

    def test_whitespace_only_title_is_dropped(self):
        stage = ValidateStage()
        with pytest.raises(DropItem):
            stage.process(_item(title="   "))


class TestDeduplicateStage:
    def test_first_item_passes(self):
        stage = DeduplicateStage()
        item = _item()
        assert stage.process(item) is item

    def test_duplicate_id_is_dropped(self):
        stage = DeduplicateStage()
        item = _item()
        stage.process(item)
        with pytest.raises(DropItem, match="Duplicate"):
            stage.process(_item(id=item.id, title="Different Title"))

    def test_different_ids_both_pass(self):
        stage = DeduplicateStage()
        stage.process(_item(id="111"))
        stage.process(_item(id="222"))
        assert stage.seen_count == 2


class TestCSVExportStage:
    def test_writes_correct_columns(self):
        with tempfile.NamedTemporaryFile(mode="r", suffix=".csv", delete=False) as f:
            path = f.name
        try:
            stage = CSVExportStage(path)
            stage.open()
            item = _item()
            stage.process(item)
            stage.close()

            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 1
            assert rows[0]["title"] == "Test Series"
            assert rows[0]["episode_count"] == "20"
            assert "id" not in rows[0]
        finally:
            os.unlink(path)

    def test_raises_if_not_opened(self):
        stage = CSVExportStage("/tmp/never_opened.csv")
        with pytest.raises(RuntimeError, match="open"):
            stage.process(_item())


class TestPipeline:
    def test_full_pipeline_exports_valid_item(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            with Pipeline(path) as pipeline:
                result = pipeline.process(_item())
            assert result is True
            assert pipeline.stats.exported == 1
            assert pipeline.stats.dropped == 0
        finally:
            os.unlink(path)

    def test_pipeline_drops_invalid_item(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            with Pipeline(path) as pipeline:
                result = pipeline.process(_item(title=""))
            assert result is False
            assert pipeline.stats.dropped == 1
        finally:
            os.unlink(path)

    def test_pipeline_deduplicates(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            item = _item()
            with Pipeline(path) as pipeline:
                pipeline.process(item)
                pipeline.process(_item(id=item.id, title="Same ID, different title"))
            assert pipeline.stats.exported == 1
            assert pipeline.stats.dropped == 1
        finally:
            os.unlink(path)
