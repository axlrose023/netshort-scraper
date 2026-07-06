from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine, Iterable
from typing import Any


async def map_bounded[T, R](
    items: Iterable[T],
    coro_fn: Callable[[T], Coroutine[Any, Any, R]],
    *,
    limit: int,
) -> AsyncIterator[R]:
    """Run *coro_fn* over *items* with at most *limit* coroutines in flight,
    yielding each result as soon as it completes (completion order — *not*
    input order).

    A sliding window: the instant any task finishes, the next item is scheduled,
    so at most ``limit`` tasks ever exist at once. Memory is O(limit) no matter
    how many items there are — the input may be a lazy iterator of millions —
    and results stream out immediately, with no per-batch head-of-line stalls.

    This bounds *fan-out* (how many units of work are materialised at once).
    Per-domain request throttling is a separate concern handled by the semaphore
    inside RequestMiddleware.

    ``coro_fn`` is expected to handle its own errors (return a sentinel/empty
    result); an exception it raises propagates here and aborts the whole run.
    """
    if limit < 1:
        raise ValueError("limit must be >= 1")

    it = iter(items)
    pending: set[asyncio.Task[R]] = set()

    def _refill() -> None:
        while len(pending) < limit:
            try:
                item = next(it)
            except StopIteration:
                return
            pending.add(asyncio.create_task(coro_fn(item)))

    _refill()
    while pending:
        done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            pending.discard(task)
            yield task.result()
        _refill()
