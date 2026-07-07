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
    yielding each result in completion order (not input order).

    A sliding window: the instant any task finishes the next item is scheduled,
    so at most ``limit`` tasks exist at once — memory is O(limit), the input may
    be a lazy iterator of millions, and results stream out with no per-batch
    head-of-line stall. This bounds fan-out; per-domain request throttling is the
    separate concern of the RequestMiddleware semaphore.
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

    try:
        _refill()
        while pending:
            done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                pending.discard(task)
                yield task.result()
            _refill()
    finally:
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
