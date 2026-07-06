"""Playwright probe — intercept network responses to find status field."""
import asyncio
import json
import re

from playwright.async_api import Response, async_playwright

URL = "https://netshort.com/full-episodes/right-beside-me-1808055875428081665"
STATUS_KEYS = {"seriesStatus", "status", "isCompleted", "playStatus", "completeStatus", "finished"}


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        api_hits: list[dict] = []

        async def on_response(response: Response) -> None:
            url = response.url
            ct = response.headers.get("content-type", "")
            if "json" not in ct and "javascript" not in ct:
                return
            try:
                body = await response.body()
                text = body.decode("utf-8", errors="ignore")
            except Exception:
                return

            # Quick check before JSON parse
            if not any(k.lower() in text.lower() for k in STATUS_KEYS):
                return
            # Try to parse JSON
            try:
                data = json.loads(text)
            except Exception:
                # Maybe it's in a JS variable — regex scan
                for k in STATUS_KEYS:
                    for m in re.finditer(rf'"{k}"\s*:\s*"([^"]+)"', text, re.IGNORECASE):
                        api_hits.append({"url": url, "key": k, "value": m.group(1)})
                return

            def walk(obj: object, path: str = "") -> None:
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k.lower() in {s.lower() for s in STATUS_KEYS}:
                            api_hits.append({"url": url, "key": k, "value": v, "path": path})
                        walk(v, f"{path}.{k}")
                elif isinstance(obj, list):
                    for i, v in enumerate(obj):
                        walk(v, f"{path}[{i}]")

            walk(data)

        page.on("response", on_response)

        print(f"Loading {URL} ...")
        await page.goto(URL, wait_until="networkidle", timeout=30_000)
        await page.wait_for_timeout(2000)

        if api_hits:
            print(f"\nFound {len(api_hits)} status-related fields in network responses:\n")
            for h in api_hits[:20]:
                print(f"  key={h['key']!r}  value={h['value']!r}")
                print(f"    url: {h['url'][:100]}")
                if "path" in h:
                    print(f"    path: {h['path'][:100]}")
                print()
        else:
            print("\nNo status field found in any network response.")
            print("Visible text scan:")
            texts = await page.evaluate("""() => {
                const all = [];
                document.querySelectorAll('*').forEach(el => {
                    const t = el.innerText?.trim();
                    if (t && t.length < 30 && t.length > 2) all.push(t);
                });
                return [...new Set(all)].slice(0, 60);
            }""")
            for t in texts:
                print(" ", repr(t))

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
