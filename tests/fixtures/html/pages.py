from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent


@pytest.fixture
def detail_page_html() -> str:
    return (FIXTURES_DIR / "detail_page.html").read_text(encoding="utf-8")


@pytest.fixture
def sitemap_xml() -> str:
    return (FIXTURES_DIR / "sitemap_sub.xml").read_text(encoding="utf-8")
