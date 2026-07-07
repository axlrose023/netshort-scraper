from __future__ import annotations

from dataclasses import dataclass

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
    id: str
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
