from __future__ import annotations


class ValueReader:
    def integer(
        self,
        config: dict[str, object],
        key: str,
        default: int,
        override: int | None = None,
    ) -> int:
        value = override if override is not None else config.get(key, default)
        if isinstance(value, bool):
            raise ValueError(f"Config field {key!r} must be an integer")
        if isinstance(value, int):
            return value
        if not isinstance(value, str):
            raise ValueError(f"Config field {key!r} must be an integer")
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"Config field {key!r} must be an integer") from exc

    def number(self, config: dict[str, object], key: str, default: float) -> float:
        value = config.get(key, default)
        if isinstance(value, bool):
            raise ValueError(f"Config field {key!r} must be a number")
        if isinstance(value, int | float):
            return float(value)
        if not isinstance(value, str):
            raise ValueError(f"Config field {key!r} must be a number")
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"Config field {key!r} must be a number") from exc
