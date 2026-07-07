from __future__ import annotations

from pathlib import Path

from scraper.sites.netshort import (
    NetshortDetailParser,
    NetshortScraper,
    _extract_jsonld_nodes,
    _is_episode_one,
    _series_id,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestSeriesId:
    def test_extracts_id_from_full_url(self):
        url = "https://netshort.com/full-episodes/sky-citys-fallen-heiress-2072959628431728642"
        assert _series_id(url) == "2072959628431728642"

    def test_extracts_id_with_fragment(self):
        url = "https://netshort.com/full-episodes/test-1983832036239818755#series"
        assert _series_id(url) == "1983832036239818755"

    def test_extracts_id_with_query_string(self):
        url = "https://netshort.com/episode/test-1983832036239818755?utm=x"
        assert _series_id(url) == "1983832036239818755"

    def test_returns_empty_for_no_id(self):
        assert _series_id("https://netshort.com/drama/all-plots") == ""

    def test_requires_minimum_15_digits(self):
        assert _series_id("https://netshort.com/something-12345") == ""


# ---------------------------------------------------------------------------
# JSON-LD extraction
# ---------------------------------------------------------------------------


class TestExtractNodes:
    def test_detail_page_has_tv_series(self):
        nodes = _extract_jsonld_nodes(_html("detail_page.html"))
        types = [n.get("@type") for n in nodes]
        assert "TVSeries" in types

    def test_graph_dict_is_returned_as_node(self):
        html = (
            '<script type="application/ld+json">'
            '{"@graph": {"@type": "TVSeries", "description": "x"}}'
            "</script>"
        )
        assert _extract_jsonld_nodes(html) == [{"@type": "TVSeries", "description": "x"}]

    def test_non_object_list_entries_are_skipped(self):
        html = '<script type="application/ld+json">[{"@type": "TVSeries"}, "bad", 1]</script>'
        assert _extract_jsonld_nodes(html) == [{"@type": "TVSeries"}]

    def test_malformed_json_is_skipped(self):
        html = '<script type="application/ld+json">{bad json}</script>'
        assert _extract_jsonld_nodes(html) == []


# ---------------------------------------------------------------------------
# NetshortDetailParser (DetailParser Strategy)
# ---------------------------------------------------------------------------


class TestNetshortDetailParser:
    def setup_method(self):
        self.parser = NetshortDetailParser()

    def test_extracts_description(self):
        result = self.parser.parse(_html("detail_page.html"))
        assert "bullied butcher" in result["description"]

    def test_returns_empty_dict_on_missing_tv_series(self):
        result = self.parser.parse("<html><body>No JSON-LD here</body></html>")
        assert result == {}


# ---------------------------------------------------------------------------
# _is_episode_one
# ---------------------------------------------------------------------------


class TestIsEpisodeOne:
    def test_episode_one_no_suffix(self):
        assert _is_episode_one("https://netshort.com/episode/some-title-1808055875428081665")

    def test_episode_two_has_suffix(self):
        assert not _is_episode_one(
            "https://netshort.com/episode/some-title-1808055875428081665-ep-2"
        )

    def test_episode_100(self):
        assert not _is_episode_one(
            "https://netshort.com/episode/some-title-1808055875428081665-ep-100"
        )


# ---------------------------------------------------------------------------
# _parse_sitemap_xml
# ---------------------------------------------------------------------------


class TestParseSitemapXml:
    def _entries(self):
        xml = (FIXTURES / "sitemap_sub.xml").read_text()
        return NetshortScraper._parse_sitemap_xml(xml)

    def _ep1(self, entries, needle):
        return next(
            e for e in entries if e.get("_is_ep1") and needle in str(e.get("series_url", ""))
        )

    def test_returns_five_entries(self):
        # The fixture also holds /full-episodes/ and /hotseries/ URLs for the same
        # series IDs; those are not episodes and must be excluded from the count.
        assert len(self._entries()) == 5

    def test_non_episode_urls_excluded(self):
        # Right Beside Me has 3 /episode/ URLs plus a /full-episodes/ and a
        # /hotseries/ URL — only the 3 real episodes should be counted.
        rbm = [e for e in self._entries() if e.get("id") == "1808055875428081665"]
        assert len(rbm) == 3

    def test_episode_one_flagged(self):
        # Exactly one ep-1 per series — the /full-episodes/ and /hotseries/ URLs
        # (which also lack an -ep-N suffix) must NOT be mistaken for episode one.
        ep1_entries = [e for e in self._entries() if e.get("_is_ep1")]
        assert len(ep1_entries) == 2  # two series, each with exactly one ep-1

    def test_episode_one_has_correct_title(self):
        ep1 = self._ep1(self._entries(), "right-beside")
        assert ep1["title"] == "Right Beside Me"

    def test_ep_prefix_stripped_from_title(self):
        # "EP 2 - Sky City's Fallen Heiress" should become "Sky City's Fallen Heiress"
        heiress_ep2 = next(
            e
            for e in self._entries()
            if e.get("id") == "2072959628431728642" and not e.get("_is_ep1")
        )
        assert heiress_ep2["title"] == "Sky City's Fallen Heiress"

    def test_series_url_constructed_correctly(self):
        ep1 = self._ep1(self._entries(), "right-beside")
        assert ep1["series_url"] == (
            "https://netshort.com/full-episodes/right-beside-me-1808055875428081665"
        )

    def test_tags_joined_as_string(self):
        ep1 = self._ep1(self._entries(), "right-beside")
        assert "Unforgettable Love" in ep1["tags"]
        assert "Contract Lovers" in ep1["tags"]

    def test_malformed_xml_returns_empty(self):
        assert NetshortScraper._parse_sitemap_xml("<not valid xml>") == []
