from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence


async def map_chunked[T, R](
    items: Sequence[T],
    coro_fn: Callable[[T], Awaitable[R]],
    *,
    chunk_size: int,
) -> AsyncIterator[R]:
    """Apply *coro_fn* to *items* in bounded concurrent chunks, yielding results.

    Fans out ``chunk_size`` coroutines at a time via ``asyncio.gather`` and
    yields each result as the chunk completes. The single shared home for the
    "batch → gather → drain" pattern used by both listing discovery and
    detail-page enrichment. Overall in-flight concurrency is still capped by the
    per-domain semaphore inside RequestMiddleware; this only bounds fan-out width.

    ``coro_fn`` is expected to handle its own errors (return a sentinel/empty
    result) — an exception raised here aborts the whole run, by design.
    """
    for offset in range(0, len(items), chunk_size):
        chunk = items[offset : offset + chunk_size]
        results = await asyncio.gather(*[coro_fn(item) for item in chunk])
        for result in results:
            yield result
