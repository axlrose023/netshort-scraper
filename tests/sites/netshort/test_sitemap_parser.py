from __future__ import annotations

from scraper.sites.netshort import NetshortScraper


class TestParseSitemapXml:
    def _entries(self, sitemap_xml):
        return NetshortScraper._parse_sitemap_xml(sitemap_xml)

    def _ep1(self, entries, needle):
        return next(
            entry
            for entry in entries
            if entry.get("_is_ep1") and needle in str(entry.get("series_url", ""))
        )

    def test_returns_five_entries(self, sitemap_xml):
        assert len(self._entries(sitemap_xml)) == 5

    def test_non_episode_urls_excluded(self, sitemap_xml):
        rbm = [
            entry
            for entry in self._entries(sitemap_xml)
            if entry.get("id") == "1808055875428081665"
        ]
        assert len(rbm) == 3

    def test_episode_one_flagged(self, sitemap_xml):
        ep1_entries = [entry for entry in self._entries(sitemap_xml) if entry.get("_is_ep1")]
        assert len(ep1_entries) == 2

    def test_episode_one_has_correct_title(self, sitemap_xml):
        ep1 = self._ep1(self._entries(sitemap_xml), "right-beside")
        assert ep1["title"] == "Right Beside Me"

    def test_ep_prefix_stripped_from_title(self, sitemap_xml):
        heiress_ep2 = next(
            entry
            for entry in self._entries(sitemap_xml)
            if entry.get("id") == "2072959628431728642" and not entry.get("_is_ep1")
        )
        assert heiress_ep2["title"] == "Sky City's Fallen Heiress"

    def test_series_url_constructed_correctly(self, sitemap_xml):
        ep1 = self._ep1(self._entries(sitemap_xml), "right-beside")
        assert ep1["series_url"] == (
            "https://netshort.com/full-episodes/right-beside-me-1808055875428081665"
        )

    def test_tags_joined_as_string(self, sitemap_xml):
        ep1 = self._ep1(self._entries(sitemap_xml), "right-beside")
        assert "Unforgettable Love" in ep1["tags"]
        assert "Contract Lovers" in ep1["tags"]

    def test_malformed_xml_returns_empty(self):
        assert NetshortScraper._parse_sitemap_xml("<not valid xml>") == []
