from __future__ import annotations

import yaml


class ConfigLoader:
    def load(self, source: str, path: str | None = None) -> dict[str, object]:
        config_path = path or f"scraper/config/{source}.yaml"
        with open(config_path, encoding="utf-8") as file:
            raw = yaml.safe_load(file)

        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise ValueError(f"Config {config_path!r} must contain a YAML mapping")
        return {str(key): value for key, value in raw.items()}

    def rate_limit(self, config: dict[str, object]) -> dict[str, object]:
        raw = config.get("rate_limit", {})
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise ValueError("Config field 'rate_limit' must be a mapping")
        return {str(key): value for key, value in raw.items()}
