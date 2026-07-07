from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PipelineStats:
    processed: int = 0
    exported: int = 0
    dropped: int = 0
