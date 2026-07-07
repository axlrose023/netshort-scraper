from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from typing import IO

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

CSV_COLUMNS: tuple[str, ...] = (
    "title",
    "series_url",
    "cover_image_url",
    "description",
    "genre",
    "episode_count",
    "status",
    "tags",
)


@dataclass
class SeriesItem:
    id: str            # numeric suffix from URL — dedup key only, not exported
    title: str
    series_url: str
    cover_image_url: str = ""
    description: str = ""
    genre: str = ""
    episode_count: str = ""
    status: str = ""
    tags: str = ""

    def to_csv_row(self) -> dict[str, str]:
        return {col: getattr(self, col, "") for col in CSV_COLUMNS}

    @classmethod
    def from_partial(
        cls,
        partial: dict[str, str],
        detail: dict[str, str] | None = None,
    ) -> SeriesItem:
        """The single construction point (Factory Method): merge listing *partial*
        with enrichment *detail*, where a non-empty *detail* value wins."""
        detail = detail or {}

        def pick(key: str) -> str:
            return str(detail.get(key) or partial.get(key) or "")

        return cls(
            id=pick("id"),
            title=pick("title"),
            series_url=pick("series_url"),
            cover_image_url=pick("cover_image_url"),
            description=pick("description"),
            genre=pick("genre"),
            episode_count=pick("episode_count"),
            status=pick("status"),
            tags=pick("tags"),
        )


# ---------------------------------------------------------------------------
# Pipeline control flow
# ---------------------------------------------------------------------------

class DropItem(Exception):
    """Raise from any pipeline stage to silently discard the item."""


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------

class ValidateStage:
    REQUIRED: tuple[str, ...] = ("title", "series_url")

    def process(self, item: SeriesItem) -> SeriesItem:
        for f in self.REQUIRED:
            if not getattr(item, f, "").strip():
                raise DropItem(f"Missing required field '{f}' — {item.series_url!r}")
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


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

@dataclass
class PipelineStats:
    processed: int = 0
    exported: int = 0
    dropped: int = 0


class Pipeline:
    """Chains stages: validate → deduplicate → csv export.

    Each stage either returns the (possibly mutated) item or raises DropItem.
    Stages are independent objects — add, remove, or reorder without touching others.
    """

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
        """Pass *item* through every stage. Returns True if exported, False if dropped."""
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
