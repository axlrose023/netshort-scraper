from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FetchResponse:
    status_code: int
    text: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
