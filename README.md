# NetShort Series Scraper

Reusable async web scraping framework — first target: [NetShort.com](https://netshort.com).

## Write-up (deliverable summary)

**Technology chosen — `curl_cffi` (async) + JSON-LD/XML-sitemap parsing, over Scrapy or Playwright.**
NetShort is fully server-side rendered (Next.js): a plain HTTP GET returns every series'
metadata inside `<script type="application/ld+json">` and the public XML sitemaps enumerate
all ~40 k episode URLs — so a headless browser is unnecessary and Scrapy's framework is more
machinery than this crawl shape needs. `curl_cffi` (a drop-in for `httpx`) is the default
client because it forges a real browser's TLS/JA3 fingerprint — the one anti-bot signal that
perfect headers cannot fix. Parsing structured data instead of CSS selectors also survives
layout redesigns. Result: **40,675 unique series, deduplicated by numeric ID**, all required
fields populated (`status` is genuinely absent from the site — verified via a Playwright
network probe).

**Extensibility** — three decoupled layers (`core/` infrastructure, `sites/` parsing,
`config/` per-site YAML) tied together by design patterns: a new site implements one method,
`discover()`, and optionally a `DetailParser`; item construction, dedup, CSV export, proxies,
retries and rate limiting are all inherited. See *Architecture* below.

**Proxies & anti-bot (first-class)** — a dedicated `antibot/` package: `ProxyPool` (rotating /
sticky, ban-tracking, `PROXY_LIST`), `BanPolicy` (403/429 + Cloudflare-marker detection), and a
coherent-identity layer — `curl_cffi` TLS impersonation + a `BrowserProfile` single-source-of-
truth whose headers can't self-contradict (`ConsistencyValidator`), pinned per IP by
`ProfilePool`. See *Anti-bot and proxy handling* below.

## Quick start

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Scrape all series (writes netshort_series.csv)
uv run python main.py --source netshort --output netshort_series.csv

# Limit to first 5 pages (for testing)
uv run python main.py --source netshort --output sample.csv --max-pages 5

# With proxy rotation
PROXY_LIST="http://user:pass@host1:8080,http://user:pass@host2:8080" \
  uv run python main.py --source netshort --output netshort_series.csv
```

## CSV output

One row per unique series, deduplicated by numeric series ID:

| Column | Description |
|---|---|
| `title` | Series title |
| `series_url` | Canonical URL (`/full-episodes/...`) |
| `cover_image_url` | CDN cover image |
| `description` | Full plot summary |
| `genre` | Comma-separated genre tags |
| `episode_count` | Total public episode count |
| `status` | Not available from source (see note below) |
| `tags` | Full tag list (`genre` is the first 3 of these — see note below) |

## Technology choice

**Async HTTP client + JSON-LD/XML-sitemap structured data — not Scrapy, not Playwright.**

NetShort.com is fully server-side rendered (Next.js SSR): a plain HTTP GET returns
complete HTML including all series metadata in `<script type="application/ld+json">`
blocks, and the public XML sitemaps enumerate every episode URL. This makes a headless
browser unnecessary and a full framework like Scrapy more machinery than the crawl
pattern warrants.

Two async clients are provided behind one `Fetcher` interface:
- **`curl_cffi` (default)** — forges a real browser's TLS/JA3 + HTTP2 fingerprint. This is
  the decisive anti-bot property: `httpx`/`aiohttp`/`requests` all present a "Python" TLS
  handshake that no amount of header spoofing can hide.
- **`httpx`** (`--fetcher httpx`) — HTTP/2, faster, but a Python TLS fingerprint; fine when
  the target does no TLS fingerprinting.

Parsing structured data (JSON-LD / sitemap XML) instead of CSS selectors is more robust:
it is semantically versioned and far less likely to break on a layout redesign.

## Architecture — adding new scrapers

The codebase is split into three layers that never cross-contaminate:

```
scraper/core/          Generic infrastructure — no site knowledge
  fetcher.py           Fetcher ABC (swap httpx ↔ Playwright without touching scrapers)
  enricher.py          Enricher Strategy: NullEnricher / DetailPageEnricher + DetailParser ABC
  concurrency.py       map_bounded() — bounded sliding-window concurrent map
  pipeline.py          SeriesItem + validate → deduplicate → CSV (DropItem chain-of-responsibility)
  antibot/
    proxy_pool.py      Proxy rotation / ban tracking / env config
    middleware.py      UA injection, rate limiting, retry/backoff, ban detection (BanPolicy)

scraper/sites/         Site-specific parsing — no infrastructure knowledge
  base.py              BaseScraper ABC: template method scrape(), one abstract method discover()
  netshort.py          NetshortScraper (discover) + NetshortDetailParser (JSON-LD) + NetshortBanPolicy

scraper/config/        Site-specific runtime config
  netshort.yaml        URLs, rate limits (selectors go here if CSS is ever needed)
```

**Design patterns** keep the layers decoupled: **Template Method** (`BaseScraper.scrape`
= discover → enrich → build), **Strategy** (`Fetcher`, `BanPolicy`, `Enricher`,
`DetailParser` are all swappable), **Factory Method** (`SeriesItem.from_partial` is the
single item-construction point), and **Chain of Responsibility** (the pipeline stages).

**To add a new site:**

1. Create `scraper/sites/mysite.py` — extend `BaseScraper` and implement the single
   abstract method:
   - `discover()` — an async generator yielding one partial-item dict per unique series
     (at minimum `id`, `title`, `series_url`; any other field is a best-effort value).
2. If the site needs detail-page enrichment, add a `DetailParser` subclass with a
   `parse(html) -> dict` method. Wire it up in `main.py` by injecting a
   `DetailPageEnricher(middleware, MyDetailParser())` — or inject `NullEnricher()` to skip.
3. Create `scraper/config/mysite.yaml` with base URL and rate limit settings.
4. Register the scraper in `main.py`: `SCRAPERS = {"netshort": ..., "mysite": MySiteScraper}`.

Item construction, deduplication, CSV export, proxy rotation, retry/backoff, rate
limiting and concurrency fan-out are all inherited — none of that code is touched.

If the new site requires JavaScript execution, implement `PlaywrightFetcher(Fetcher)`
and pass it to `RequestMiddleware` instead of `HttpxFetcher`. Site scrapers never
reference the fetcher directly.

## Anti-bot and proxy handling

- **TLS/JA3 impersonation** (`CurlCffiFetcher`, default): the biggest tell for an HTTP
  scraper is its TLS handshake — `httpx`/`requests` present an unmistakably "Python"
  ClientHello no matter how perfect the headers are. The default fetcher uses
  [`curl_cffi`](https://github.com/lexiforest/curl_cffi) to forge the exact
  ClientHello/HTTP2 fingerprint of a real browser (e.g. `chrome142`), so the JA3 matches
  the User-Agent. `HttpxFetcher` remains available via `--fetcher httpx` (faster, but a
  Python fingerprint). Both are just `Fetcher` strategies — the scraper never knows which.

- **Coherent browser identity** (`BrowserProfile` + `ConsistencyValidator`): a `BrowserProfile`
  is the single source of truth for one identity — UA, `Accept`/`Accept-Language`,
  Client Hints (`Sec-CH-UA*`), and the matching `curl_cffi` impersonation target. The
  header set *agrees with itself*: a macOS Chrome profile sends `Sec-CH-UA-Platform: "macOS"`,
  while a Firefox profile sends **no** `Sec-CH-UA` at all (Firefox never does). Every
  profile is checked by `ConsistencyValidator` before use, so contradictions (Windows UA +
  macOS platform hint, Firefox UA + Chromium Client Hints, UA family ≠ TLS family) are
  impossible rather than merely unlikely.

- **Session policy** (`ProfilePool`): one profile is pinned per network identity (proxy/IP)
  for the whole run. A given IP therefore always presents the same UA, Client Hints and
  TLS fingerprint — they never drift under a stable IP, and rotate *together* only when the
  IP does. No "same IP, suddenly a different browser" tell.

- **Proxy pool** (`ProxyPool`): reads `PROXY_LIST` env var (comma-separated proxy URLs).
  Supports two rotation modes: `ROTATING` (random proxy per request) and `STICKY`
  (same proxy per domain until banned). Falls back to direct requests when no proxies
  are configured, so the scraper is fully runnable without proxy credentials.

- **Ban detection** is separated from retry logic via `BanPolicy` ABC. The generic
  `DefaultBanPolicy` treats HTTP 403/429 as bans; `NetshortBanPolicy` additionally
  checks response bodies for Cloudflare JS-challenge markers. When a ban is detected,
  the proxy is marked dead and a new one is selected — and its `BrowserProfile` is
  re-fetched too, so the fingerprint rotates *with* the IP, not one attempt behind it.

- **Rate limiting**: `asyncio.Semaphore` caps concurrent requests to the same domain
  (default: 5). A randomised delay (0.5–1.5 s by default) is added after each
  successful response.

- **Retry/backoff**: up to 3 retries with exponential backoff (`2^attempt + jitter`)
  on bans and transient 5xx errors.

**Cloudflare observation**: during reconnaissance, plain HTTPS requests with
browser-like headers passed through Cloudflare without a JS challenge. The
`NetshortBanPolicy` adds body-pattern detection as a defensive measure should the
site enable active challenges in the future.

## Known limitations

- **`status` field**: no structured "Ongoing/Completed" signal was found on any
  inspected page. The column is present in the CSV but always empty.

- **`tags` vs `genre`**: the site exposes a single taxonomy (the video `<tag>` list) — there
  is no separate ranking system. To fill both requested columns from it without inventing
  data, `tags` carries the **full** tag list and `genre` carries the **first three** as a
  concise category label. They therefore overlap but are not identical (they differ for
  ~99.97% of rows); this split is a presentation choice, noted rather than hidden.

- **Series count**: discovery via the XML sitemaps yields **40,675 unique series**
  (the site's 90 sub-sitemaps enumerate every episode URL; series are grouped by numeric
  ID and deduplicated). This matches the assignment brief's ~40,600 estimate. The listing
  pages (`drama/all-plots?page=N`) are *not* used — they paginate client-side and return
  the same 24 series for every page, so they only ever expose a small slice of the catalogue.
  The scraper reads the live sitemap set on each run, so it adapts if the catalogue grows.

- **Incomplete-run safety**: if one or more sub-sitemap files fail to download (e.g. a
  network outage), discovery logs a prominent `WARNING: N/90 sitemap files failed —
  result may be INCOMPLETE`. A dropped file silently loses whole series and undercounts
  episodes, so the warning tells you to re-run (or configure proxies) rather than trust
  a truncated CSV.

- **Run time**: discovery-only (`--skip-enrich`) over the 90 sitemaps takes ~4 minutes.
  A full run that also fetches all ~40 k detail pages for canonical descriptions takes
  substantially longer; use proxies and tune `--concurrency` accordingly.

## Running tests

```bash
uv run pytest -v
```

## Development

```bash
# Install dev dependencies and pre-commit hooks
uv sync
uv run pre-commit install

# Lint + format
uv run ruff check . --fix
uv run ruff format .

# Type check
uv run mypy scraper/ main.py
```
