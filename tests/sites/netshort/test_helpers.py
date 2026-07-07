from __future__ import annotations

from scraper.sites.netshort import _extract_jsonld_nodes, _is_episode_one, _series_id


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


class TestExtractNodes:
    def test_detail_page_has_tv_series(self, detail_page_html):
        nodes = _extract_jsonld_nodes(detail_page_html)
        types = [node.get("@type") for node in nodes]
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
