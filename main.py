from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time

import yaml

from scraper.core.antibot.middleware import RequestMiddleware
from scraper.core.antibot.profile import ProfilePool
from scraper.core.antibot.proxy_pool import ProxyPool
from scraper.core.enricher import DetailPageEnricher, NullEnricher
from scraper.core.fetcher import CurlCffiFetcher, Fetcher, HttpxFetcher
from scraper.core.pipeline import Pipeline
from scraper.sites.netshort import NetshortBanPolicy, NetshortDetailParser, NetshortScraper

# ---------------------------------------------------------------------------
# Scraper registry — add new sites here
# ---------------------------------------------------------------------------

SCRAPERS = {
    "netshort": NetshortScraper,
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quieten noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reusable web scraper — fetches series data and writes a CSV.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--source",
        required=True,
        choices=list(SCRAPERS),
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
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Main async entrypoint
# ---------------------------------------------------------------------------

async def run(args: argparse.Namespace) -> None:
    config_path = args.config or f"scraper/config/{args.source}.yaml"
    with open(config_path) as fh:
        cfg = yaml.safe_load(fh)

    rl = cfg.get("rate_limit", {})

    # CLI --concurrency wins if given, else the site config, else a safe default.
    concurrency = args.concurrency if args.concurrency is not None else rl.get("concurrency", 5)

    proxy_pool = ProxyPool()  # reads PROXY_LIST env var; empty = direct requests
    fetcher: Fetcher = (
        CurlCffiFetcher(timeout=30.0) if args.fetcher == "curl" else HttpxFetcher(timeout=30.0)
    )
    middleware = RequestMiddleware(
        fetcher=fetcher,
        proxy_pool=proxy_pool,
        ban_policy=NetshortBanPolicy() if args.source == "netshort" else None,
        profile_pool=ProfilePool(),  # coherent, per-IP-sticky browser identities
        concurrency=concurrency,
        delay_min=rl.get("delay_min", 0.5),
        delay_max=rl.get("delay_max", 1.5),
        max_retries=rl.get("max_retries", 3),
        backoff_base=rl.get("backoff_base", 2.0),
    )

    # Enrichment is an injected Strategy: skip it (NullEnricher) or fetch the
    # detail page and parse the canonical description (DetailPageEnricher).
    enricher = (
        NullEnricher()
        if args.skip_enrich
        else DetailPageEnricher(middleware, NetshortDetailParser())
    )

    scraper_cls = SCRAPERS[args.source]
    scraper = scraper_cls(
        middleware=middleware,
        enricher=enricher,
        config=cfg,
        max_pages=args.max_pages,
    )

    logger = logging.getLogger("main")
    logger.info("Starting %s → %s", args.source, args.output)
    logger.info(
        "Fetcher: %s%s",
        args.fetcher,
        " (browser TLS impersonation)" if args.fetcher == "curl" else " (Python TLS fingerprint)",
    )
    if proxy_pool.has_proxies():
        logger.info("Proxy pool: %d proxies configured", proxy_pool.available_count())
    else:
        logger.info("No proxies configured — using direct requests")

    t0 = time.monotonic()

    try:
        with Pipeline(args.output) as pipeline:
            async for item in scraper.scrape():
                pipeline.process(item)

                if pipeline.stats.exported % 100 == 0 and pipeline.stats.exported:
                    elapsed = time.monotonic() - t0
                    logger.info(
                        "Progress: %d exported, %d dropped, %.0fs elapsed",
                        pipeline.stats.exported,
                        pipeline.stats.dropped,
                        elapsed,
                    )
    finally:
        await middleware.close()  # close the fetcher's HTTP client / session

    elapsed = time.monotonic() - t0
    logger.info(
        "Done in %.1fs — exported=%d  dropped=%d  retries=%d  proxy_bans=%d",
        elapsed,
        pipeline.stats.exported,
        pipeline.stats.dropped,
        middleware.stats.retries,
        middleware.stats.proxy_bans,
    )
    logger.info("Output: %s", args.output)


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
