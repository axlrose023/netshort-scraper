from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import cast

from scraper.services import FetcherName, ScraperApplication, ScraperRunConfig

APP = ScraperApplication()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reusable web scraper — fetches series data and writes a CSV.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--source",
        required=True,
        choices=APP.sources,
        help="Which site scraper to use.",
    )
    parser.add_argument(
        "--output",
        default="output.csv",
        help="Path for the output CSV file.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        metavar="N",
        help="Stop after N listing pages (omit to scrape all).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Max concurrent requests to the target domain "
        "(default: the site config's rate_limit.concurrency, else 5).",
    )
    parser.add_argument(
        "--fetcher",
        choices=["curl", "httpx"],
        default="curl",
        help=(
            "HTTP backend. 'curl' = curl_cffi with browser TLS/JA3 impersonation "
            "(stealth, recommended). 'httpx' = faster but a Python TLS fingerprint."
        ),
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to site YAML config (defaults to scraper/config/<source>.yaml).",
    )
    parser.add_argument(
        "--skip-enrich",
        action="store_true",
        help=(
            "Skip detail-page fetches. Uses episode-1 description from the sitemap "
            "instead of the canonical series description. Much faster (~90 requests "
            "vs ~40k), but description quality is lower."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args(argv)


async def run(args: argparse.Namespace) -> None:
    logger = logging.getLogger("main")
    result = await APP.run(
        ScraperRunConfig(
            source=args.source,
            output=args.output,
            config_path=args.config,
            max_pages=args.max_pages,
            concurrency=args.concurrency,
            fetcher=cast(FetcherName, args.fetcher),
            skip_enrich=args.skip_enrich,
        )
    )
    logger.info(
        "Done in %.1fs - exported=%d  dropped=%d  retries=%d  proxy_bans=%d",
        result.elapsed_seconds,
        result.pipeline_stats.exported,
        result.pipeline_stats.dropped,
        result.request_stats.retries,
        result.request_stats.proxy_bans,
    )
    logger.info("Output: %s", result.output_path)


def cli() -> None:
    args = _parse_args()
    _setup_logging(args.verbose)
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli()
