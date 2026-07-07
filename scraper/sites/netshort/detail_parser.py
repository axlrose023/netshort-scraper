from __future__ import annotations

from scraper.services.enrichment import DetailParser
from scraper.sites.netshort.helpers import _extract_jsonld_nodes


class NetshortDetailParser(DetailParser):
    def parse(self, html: str) -> dict[str, str]:
        for node in _extract_jsonld_nodes(html):
            if node.get("@type") == "TVSeries":
                return {"description": str(node.get("description", ""))}
        return {}
