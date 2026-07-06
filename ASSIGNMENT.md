# Assignment: Netshort Series Scraping

> Verbatim task brief (source: `Netshort_Scraping_Assignment (1).docx`). Kept in-repo so
> requirements are never lost. Do not edit the requirements text below.

Scrape all publicly available series from NetShort.com and deliver the data in a clean CSV file.

## Required CSV fields
- Series title
- Series URL
- Cover image URL
- Description
- Genre / category, if available
- Number of episodes, if available
- Status, if available
- Tags / ranking, if available

## Requirements
- Collect all discoverable public series.
- Avoid duplicate records.
- Do not scrape behind login, payment, CAPTCHA, or restricted areas.
- Use reasonable scraping limits.

## Technical approach
- Before building the scraper, evaluate a few scraping technologies/approaches, choose one,
  and explain why it's the right fit for this job.
- Design the architecture so it can be extended to additional scrapers in the future, rather
  than being a one-off script tied to this single site. It should be built to handle proxies
  and anti-bot measures as first-class concerns, not an afterthought.
- We want to see that you're thinking about this as a reusable scraping system, not just
  solving for one specific target site.

## Anti-bot & proxy handling (expected in the solution)
- The solution should be built with dedicated anti-bot detection technology/tooling as part
  of the core architecture.
- It should make use of proxy servers to avoid detection and blocking while scraping.
- Bonus (nice-to-have, not required): if feasible, the solution can also handle bypassing
  Cloudflare protection and CAPTCHAs.

## Deliverables
- One CSV file with the fields above, deduplicated.
- A GitHub repo with your code.
- A short write-up (a few sentences) explaining which scraping technology/approach you chose
  and why.
- A brief note on how the architecture supports adding new scrapers, and how it handles
  proxies and anti-bot protection.

## Acceptance criteria
- The CSV should include all publicly available Netshort series with clean, structured, and
  deduplicated data.
- The codebase should demonstrate a scraping architecture that is reasonably extensible to
  other sites, with a clear approach to proxy rotation and anti-bot handling — not just a
  narrow, single-purpose script.
