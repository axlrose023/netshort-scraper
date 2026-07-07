from __future__ import annotations

import csv
from typing import IO

from scraper.domain.series import CSV_COLUMNS, SeriesItem
from scraper.pipelines.exceptions import DropItem


class ValidateStage:
    REQUIRED: tuple[str, ...] = ("id", "title", "series_url")

    def process(self, item: SeriesItem) -> SeriesItem:
        for field in self.REQUIRED:
            if not getattr(item, field, "").strip():
                raise DropItem(f"Missing required field '{field}' - {item.series_url!r}")
        return item


class DeduplicateStage:
    def __init__(self) -> None:
        self._seen: set[str] = set()

    def process(self, item: SeriesItem) -> SeriesItem:
        if item.id in self._seen:
            raise DropItem(f"Duplicate id={item.id!r} ({item.title!r})")
        self._seen.add(item.id)
        return item

    @property
    def seen_count(self) -> int:
        return len(self._seen)


class CSVExportStage:
    def __init__(self, path: str) -> None:
        self._path = path
        self._file: IO[str] | None = None
        self._writer: csv.DictWriter[str] | None = None

    def open(self) -> None:
        self._file = open(self._path, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=list(CSV_COLUMNS))
        self._writer.writeheader()

    def process(self, item: SeriesItem) -> SeriesItem:
        if self._writer is None:
            raise RuntimeError("CSVExportStage.open() was not called")
        self._writer.writerow(item.to_csv_row())
        return item

    def close(self) -> None:
        if self._file:
            self._file.flush()
            self._file.close()
            self._file = None
            self._writer = None
