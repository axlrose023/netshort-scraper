from __future__ import annotations

import asyncio
import json
import logging
import re
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator

from scraper.core.antibot.middleware import DefaultBanPolicy, RequestMiddleware
from scraper.core.concurrency import map_bounded
from scraper.core.enricher import DetailParser, Enricher
from scraper.core.fetcher import FetchResponse
from scraper.sites.base import BaseScraper

logger = logging.getLogger(__name__)

# XML namespaces used in NetShort's video sitemaps
_NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "video": "http://www.google.com/schemas/sitemap-video/1.1",
}

# ---------------------------------------------------------------------------
# Site-specific ban policy
# ---------------------------------------------------------------------------


class NetshortBanPolicy(DefaultBanPolicy):
    """Extends the generic policy with Cloudflare JS-challenge detection.

    During testing, plain requests with browser-like headers passed through
    without an active challenge.  This subclass provides the hook to add
    body-pattern matching should the site tighten its bot protection.
    """

    _CF_MARKERS = ("Just a moment", "cf-browser-verification")

    def is_banned(self, response: FetchResponse) -> bool:
        if super().is_banned(response):
            return True
        if response.status_code == 200:
            for marker in self._CF_MARKERS:
                if marker in response.text:
                    logger.warning("Cloudflare JS challenge detected at %s", response.url)
                    return True
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
_ID_RE = re.compile(r"-(\d{15,})(?:-ep-\d+)?(?:#.*)?$")
_EP_SUFFIX_RE = re.compile(r"-ep-\d+$")
_EP_TITLE_PREFIX_RE = re.compile(r"^EP\s+\d+\s*[-:]\s*", re.IGNORECASE)


def _series_id(url: str) -> str:
    """Extract the numeric series ID from any episode or full-episodes URL."""
    m = _ID_RE.search(url.split("?")[0].rstrip("/"))
    return m.group(1) if m else ""


def _is_episode_one(url: str) -> bool:
    """True if the URL is the first episode (no -ep-N suffix)."""
    path = url.split("?")[0].rstrip("/")
    return not _EP_SUFFIX_RE.search(path)


def _extract_jsonld_nodes(html: str) -> list[dict[str, object]]:
    nodes: list[dict[str, object]] = []
    for m in _JSONLD_RE.finditer(html):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            nodes.extend(data)
        elif isinstance(data, dict) and "@graph" in data:
            nodes.extend(data["@graph"])
        elif isinstance(data, dict):
            nodes.append(data)
    return nodes


# ---------------------------------------------------------------------------
# Detail-page parser (Strategy) — canonical series description from JSON-LD
# ---------------------------------------------------------------------------


class NetshortDetailParser(DetailParser):
    """Pull the canonical series synopsis from the /full-episodes/ page's
    ``TVSeries`` JSON-LD node (richer than the episode-1 sitemap description)."""

    def parse(self, html: str) -> dict[str, str]:
        for node in _extract_jsonld_nodes(html):
            if node.get("@type") == "TVSeries":
                return {"description": str(node.get("description", ""))}
        return {}


# ---------------------------------------------------------------------------
# NetShort scraper
# ---------------------------------------------------------------------------


class NetshortScraper(BaseScraper):
    """Scrapes every public series from netshort.com via the XML sitemaps.

    Listing pages (drama/all-plots?page=N) paginate client-side — every request
    returns the same 24 series — so discovery instead walks the ~90 sub-sitemaps,
    groups episode URLs by series ID, and counts episodes per series. The
    canonical description is the injected ``Enricher``'s job (see main.py).
    """

    def __init__(
        self,
        middleware: RequestMiddleware,
        enricher: Enricher | None = None,
        config: dict[str, object] | None = None,
        max_pages: int | None = None,
    ) -> None:
        super().__init__(middleware, enricher, max_pages)
        self._cfg: dict[str, object] = config or {}
        # Count of sub-sitemap files that could not be fetched, so a run that
        # lost whole files (e.g. a network outage) does not look complete.
        self._sitemap_failures = 0

    # ------------------------------------------------------------------
    # BaseScraper interface — discovery only
    # ------------------------------------------------------------------

    async def discover(self) -> AsyncIterator[dict[str, str]]:
        """Yield one partial-item dict per unique series via sitemap discovery."""
        sitemap_urls = await self._get_sub_sitemap_urls()
        if self.max_pages:
            sitemap_urls = sitemap_urls[: self.max_pages]
            logger.info("--max-pages set: limiting to %d sitemap files", len(sitemap_urls))

        logger.info("Fetching %d sub-sitemap files", len(sitemap_urls))
        self._sitemap_failures = 0

        # series_id → episode-1 entry (canonical metadata)
        series_meta: dict[str, dict[str, object]] = {}
        # series_id → total episode count across all sitemaps
        series_ep_count: dict[str, int] = {}

        processed = 0
        async for entries in map_bounded(
            sitemap_urls, self._fetch_and_parse_sitemap, limit=10
        ):
            for entry in entries:
                sid = str(entry["id"])
                series_ep_count[sid] = series_ep_count.get(sid, 0) + 1
                if sid not in series_meta and entry.get("_is_ep1") and "title" in entry:
                    series_meta[sid] = entry
            processed += 1
            if processed % 10 == 0 or processed == len(sitemap_urls):
                logger.info("Sitemap progress: %d / %d files", processed, len(sitemap_urls))

        logger.info("Discovered %d unique series from sitemaps", len(series_meta))
        if self._sitemap_failures:
            logger.warning(
                "%d/%d sitemap files failed to download — result may be INCOMPLETE "
                "(episode counts undercounted, some series missing). Re-run, or "
                "configure PROXY_LIST if the site is throttling.",
                self._sitemap_failures,
                len(sitemap_urls),
            )

        for sid, meta in series_meta.items():
            yield {
                "id": sid,
                "title": str(meta.get("title", "")),
                "series_url": str(meta.get("series_url", "")),
                "cover_image_url": str(meta.get("cover_image_url", "")),
                "genre": str(meta.get("genre", "")),
                "episode_count": str(series_ep_count.get(sid, 1)),
                "tags": str(meta.get("tags", "")),
                # Episode-1 description from the sitemap — a best-effort value the
                # enricher may replace with the canonical series synopsis.
                "description": str(meta.get("description", "")),
            }

    # ------------------------------------------------------------------
    # Sitemap helpers
    # ------------------------------------------------------------------

    async def _get_sub_sitemap_urls(self) -> list[str]:
        """Fetch the sitemap index and return sub-sitemap URLs."""
        index_url = str(self._cfg["sitemap_index_url"])
        response = await self.middleware.fetch(index_url)
        root = ET.fromstring(response.text)
        urls = [el.text.strip() for el in root.findall(".//sm:loc", _NS) if el.text]
        logger.debug("Sitemap index has %d sub-sitemaps", len(urls))
        return urls

    async def _fetch_and_parse_sitemap(self, url: str) -> list[dict[str, object]]:
        """Fetch one sub-sitemap → episode entry dicts. Failures are counted and
        swallowed (a bad file never aborts the run); the CPU-bound XML parse is
        offloaded to the executor so concurrent fetches keep running."""
        try:
            response = await self.middleware.fetch(url)
        except Exception as exc:
            logger.warning("Sitemap fetch error for %s: %s", url, exc)
            self._sitemap_failures += 1
            return []
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._parse_sitemap_xml, response.text)

    @staticmethod
    def _parse_sitemap_xml(xml_text: str) -> list[dict[str, object]]:
        """Parse a video sitemap XML and return one dict per episode URL."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("Sitemap XML parse error: %s", exc)
            return []

        entries: list[dict[str, object]] = []
        for url_el in root.findall("sm:url", _NS):
            loc = (url_el.findtext("sm:loc", "", _NS) or "").strip()
            if not loc:
                continue

            # Each series appears in the sitemap under three path types with the
            # same numeric ID: /episode/… (the actual episodes), /full-episodes/…
            # (the series landing page) and /hotseries/… (a promo page). Only the
            # /episode/ URLs are real episodes — counting the other two inflates
            # episode_count and makes _is_episode_one() flag three "ep-1"s.
            if "/episode/" not in loc:
                continue

            series_id = _series_id(loc)
            if not series_id:
                continue

            is_ep1 = _is_episode_one(loc)
            video = url_el.find("video:video", _NS)

            if video is None:
                entries.append({"id": series_id, "_is_ep1": is_ep1})
                continue

            raw_title = video.findtext("video:title", "", _NS) or ""
            title = _EP_TITLE_PREFIX_RE.sub("", raw_title).strip()
            description = video.findtext("video:description", "", _NS) or ""
            thumbnail = video.findtext("video:thumbnail_loc", "", _NS) or ""
            tag_els = video.findall("video:tag", _NS)
            tags_list = [t.text for t in tag_els if t.text]

            # Build the /full-episodes/ URL from the /episode/ one (the /episode/
            # segment is guaranteed present by the filter above).
            slug = _EP_SUFFIX_RE.sub("", loc.split("/episode/", 1)[1])
            series_url = f"https://netshort.com/full-episodes/{slug}"

            entries.append({
                "id": series_id,
                "_is_ep1": is_ep1,
                "title": title,
                "series_url": series_url,
                "cover_image_url": thumbnail,
                "description": description,
                "genre": ", ".join(tags_list[:3]),
                "tags": ", ".join(tags_list),
            })

        return entries
