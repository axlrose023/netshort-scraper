from __future__ import annotations

from scraper.sites.netshort import NetshortDetailParser


class TestNetshortDetailParser:
    def setup_method(self):
        self.parser = NetshortDetailParser()

    def test_extracts_description(self, detail_page_html):
        result = self.parser.parse(detail_page_html)
        assert "bullied butcher" in result["description"]

    def test_returns_empty_dict_on_missing_tv_series(self):
        result = self.parser.parse("<html><body>No JSON-LD here</body></html>")
        assert result == {}
