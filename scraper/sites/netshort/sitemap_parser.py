from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from scraper.sites.netshort.helpers import (
    EP_SUFFIX_RE,
    EP_TITLE_PREFIX_RE,
    _is_episode_one,
    _series_id,
)

logger = logging.getLogger(__name__)

_NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "video": "http://www.google.com/schemas/sitemap-video/1.1",
}


class NetshortSitemapParser:
    def parse_index(self, xml_text: str) -> list[str]:
        root = ET.fromstring(xml_text)
        return [el.text.strip() for el in root.findall(".//sm:loc", _NS) if el.text]

    def parse_entries(self, xml_text: str) -> list[dict[str, object]]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("Sitemap XML parse error: %s", exc)
            return []

        entries: list[dict[str, object]] = []
        for url_el in root.findall("sm:url", _NS):
            loc = (url_el.findtext("sm:loc", "", _NS) or "").strip()
            if not loc or "/episode/" not in loc:
                continue

            series_id = _series_id(loc)
            if not series_id:
                continue

            video = url_el.find("video:video", _NS)
            is_ep1 = _is_episode_one(loc)
            if video is None:
                entries.append({"id": series_id, "_is_ep1": is_ep1})
                continue

            raw_title = video.findtext("video:title", "", _NS) or ""
            tag_els = video.findall("video:tag", _NS)
            tags_list = [tag.text for tag in tag_els if tag.text]
            slug = EP_SUFFIX_RE.sub("", loc.split("/episode/", 1)[1])

            entries.append(
                {
                    "id": series_id,
                    "_is_ep1": is_ep1,
                    "title": EP_TITLE_PREFIX_RE.sub("", raw_title).strip(),
                    "series_url": f"https://netshort.com/full-episodes/{slug}",
                    "cover_image_url": video.findtext("video:thumbnail_loc", "", _NS) or "",
                    "description": video.findtext("video:description", "", _NS) or "",
                    "genre": ", ".join(tags_list[:3]),
                    "tags": ", ".join(tags_list),
                }
            )

        return entries
