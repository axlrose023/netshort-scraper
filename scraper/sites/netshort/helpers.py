from __future__ import annotations

import json
import re

JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
ID_RE = re.compile(r"-(\d{15,})(?:-ep-\d+)?(?:#.*)?$")
EP_SUFFIX_RE = re.compile(r"-ep-\d+$")
EP_TITLE_PREFIX_RE = re.compile(r"^EP\s+\d+\s*[-:]\s*", re.IGNORECASE)


def _series_id(url: str) -> str:
    match = ID_RE.search(url.split("?")[0].rstrip("/"))
    return match.group(1) if match else ""


def _is_episode_one(url: str) -> bool:
    path = url.split("?")[0].rstrip("/")
    return not EP_SUFFIX_RE.search(path)


def _extract_jsonld_nodes(html: str) -> list[dict[str, object]]:
    nodes: list[dict[str, object]] = []

    def append_node(value: object) -> None:
        if isinstance(value, dict):
            nodes.append(value)

    for match in JSONLD_RE.finditer(html):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            for node in data:
                append_node(node)
        elif isinstance(data, dict):
            graph = data.get("@graph")
            if isinstance(graph, list):
                for node in graph:
                    append_node(node)
            elif isinstance(graph, dict):
                append_node(graph)
            else:
                nodes.append(data)
    return nodes
