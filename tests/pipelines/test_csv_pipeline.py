from __future__ import annotations

import csv
import os
import tempfile

import pytest

from scraper.pipelines import (
    CSVExportStage,
    DeduplicateStage,
    DropItem,
    Pipeline,
    ValidateStage,
)


class TestValidateStage:
    def test_passes_valid_item(self, make_series_item):
        stage = ValidateStage()
        item = make_series_item()
        assert stage.process(item) is item

    def test_drops_missing_id(self, make_series_item):
        stage = ValidateStage()
        with pytest.raises(DropItem, match="id"):
            stage.process(make_series_item(id=""))

    def test_drops_missing_title(self, make_series_item):
        stage = ValidateStage()
        with pytest.raises(DropItem, match="title"):
            stage.process(make_series_item(title=""))

    def test_drops_missing_series_url(self, make_series_item):
        stage = ValidateStage()
        with pytest.raises(DropItem, match="series_url"):
            stage.process(make_series_item(series_url=""))

    def test_whitespace_only_title_is_dropped(self, make_series_item):
        stage = ValidateStage()
        with pytest.raises(DropItem):
            stage.process(make_series_item(title="   "))


class TestDeduplicateStage:
    def test_first_item_passes(self, make_series_item):
        stage = DeduplicateStage()
        item = make_series_item()
        assert stage.process(item) is item

    def test_duplicate_id_is_dropped(self, make_series_item):
        stage = DeduplicateStage()
        item = make_series_item()
        stage.process(item)
        with pytest.raises(DropItem, match="Duplicate"):
            stage.process(make_series_item(id=item.id, title="Different Title"))

    def test_different_ids_both_pass(self, make_series_item):
        stage = DeduplicateStage()
        stage.process(make_series_item(id="111"))
        stage.process(make_series_item(id="222"))
        assert stage.seen_count == 2


class TestCSVExportStage:
    def test_writes_correct_columns(self, make_series_item):
        with tempfile.NamedTemporaryFile(mode="r", suffix=".csv", delete=False) as f:
            path = f.name
        try:
            stage = CSVExportStage(path)
            stage.open()
            item = make_series_item()
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

    def test_raises_if_not_opened(self, make_series_item):
        stage = CSVExportStage("/tmp/never_opened.csv")
        with pytest.raises(RuntimeError, match="open"):
            stage.process(make_series_item())


class TestPipeline:
    def test_full_pipeline_exports_valid_item(self, make_series_item):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            with Pipeline(path) as pipeline:
                result = pipeline.process(make_series_item())
            assert result is True
            assert pipeline.stats.exported == 1
            assert pipeline.stats.dropped == 0
        finally:
            os.unlink(path)

    def test_pipeline_drops_invalid_item(self, make_series_item):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            with Pipeline(path) as pipeline:
                result = pipeline.process(make_series_item(title=""))
            assert result is False
            assert pipeline.stats.dropped == 1
        finally:
            os.unlink(path)

    def test_pipeline_deduplicates(self, make_series_item):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            item = make_series_item()
            with Pipeline(path) as pipeline:
                pipeline.process(item)
                pipeline.process(make_series_item(id=item.id, title="Same ID, different title"))
            assert pipeline.stats.exported == 1
            assert pipeline.stats.dropped == 1
        finally:
            os.unlink(path)
