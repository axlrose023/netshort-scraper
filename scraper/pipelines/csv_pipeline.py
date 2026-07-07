from __future__ import annotations

import logging

from scraper.domain.series import SeriesItem
from scraper.pipelines.exceptions import DropItem
from scraper.pipelines.stages import CSVExportStage, DeduplicateStage, ValidateStage
from scraper.pipelines.stats import PipelineStats

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, output_path: str) -> None:
        self.validate = ValidateStage()
        self.deduplicate = DeduplicateStage()
        self.export = CSVExportStage(output_path)
        self._stages: list[ValidateStage | DeduplicateStage | CSVExportStage] = [
            self.validate,
            self.deduplicate,
            self.export,
        ]
        self.stats = PipelineStats()

    def open(self) -> None:
        self.export.open()

    def process(self, item: SeriesItem) -> bool:
        self.stats.processed += 1
        try:
            result: SeriesItem = item
            for stage in self._stages:
                result = stage.process(result)
            self.stats.exported += 1
            return True
        except DropItem as exc:
            logger.debug("Dropped item: %s", exc)
            self.stats.dropped += 1
            return False

    def close(self) -> None:
        self.export.close()

    def __enter__(self) -> Pipeline:
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
